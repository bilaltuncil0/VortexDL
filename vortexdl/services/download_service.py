"""Queued yt-dlp worker service. This module never imports or calls Tkinter."""
import errno
import os
import queue
import shutil
import threading
from dataclasses import replace
from pathlib import Path
from typing import Optional

import yt_dlp

from vortexdl.core.errors import (
    DependencyMissingError, DiskFullError, DownloadCancelled, DownloadError,
    NetworkDownloadError, OutputDirectoryError,
)
from vortexdl.core.models import DownloadEvent, DownloadStatus, DownloadTask
from vortexdl.storage.database import add_history_entry


class DownloadQueueService:
    """Owns download tasks and workers; consumers read events on their own thread."""
    def __init__(self, events: Optional[queue.Queue] = None, workers: int = 1):
        self.events = events if events is not None else queue.Queue()
        self._pending = queue.Queue()
        self._tasks = {}
        self._cancel = {}
        self._lock = threading.RLock()
        self._closed = False
        self._threads = []
        for index in range(max(1, workers)):
            thread = threading.Thread(target=self._worker, name=f"vortexdl-download-{index + 1}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def add(self, url: str, quality: str = "best", output_dir: str = "", media_format: str = "video") -> DownloadTask:
        url = (url or "").strip()
        if not url:
            raise ValueError("URL boş olamaz.")
        with self._lock:
            if self._closed:
                raise RuntimeError("İndirme servisi kapatılmış.")
            task = DownloadTask(url=url, quality=quality, output_dir=output_dir, media_format=media_format)
            self._tasks[task.task_id] = task
            self._cancel[task.task_id] = threading.Event()
        self._emit(task, "queued", "İndirme kuyruğa eklendi.")
        self._pending.put(task.task_id)
        return replace(task)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            event = self._cancel.get(task_id)
            task = self._tasks.get(task_id)
            if event is None or task is None or task.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED):
                return False
            event.set()
        return True

    def list_tasks(self):
        with self._lock:
            return [replace(task) for task in self._tasks.values()]

    def get_task(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
            return replace(task) if task else None

    def shutdown(self, wait: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for cancel_event in self._cancel.values():
                cancel_event.set()
        for _ in self._threads:
            self._pending.put(None)
        if wait:
            for thread in self._threads:
                thread.join(timeout=2)

    def _emit(self, task: DownloadTask, kind: str, message: str = "") -> None:
        self.events.put(DownloadEvent(
            task_id=task.task_id, kind=kind, status=task.status,
            progress=task.progress, speed=task.speed, message=message,
            output_path=task.output_path,
        ))

    def _change(self, task_id: str, kind: str, message: str = "", **changes) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            for key, value in changes.items():
                setattr(task, key, value)
            snapshot = replace(task)
        self._emit(snapshot, kind, message)

    def _worker(self) -> None:
        while True:
            task_id = self._pending.get()
            try:
                if task_id is None:
                    return
                with self._lock:
                    task = self._tasks.get(task_id)
                    cancel_event = self._cancel.get(task_id)
                    if task is None or cancel_event is None:
                        continue
                    task = replace(task)
                if cancel_event.is_set():
                    self._change(task_id, "cancelled", "İndirme iptal edildi.", status=DownloadStatus.CANCELLED)
                    continue
                self._run_task(task, cancel_event)
            finally:
                self._pending.task_done()

    def _run_task(self, task: DownloadTask, cancel_event: threading.Event) -> None:
        try:
            output_dir = self._validate_output_dir(task.output_dir)
            ffmpeg = shutil.which("ffmpeg")
            if task.media_format == "audio" and not ffmpeg:
                raise DependencyMissingError("MP3 dönüştürme için FFmpeg bulunamadı.")
            self._change(task.task_id, "started", "İndirme başladı.", status=DownloadStatus.DOWNLOADING)

            def progress_hook(data):
                if cancel_event.is_set():
                    raise DownloadCancelled("İndirme iptal edildi.")
                if data.get("status") == "downloading":
                    raw = str(data.get("_percent_str", "0%")).replace("%", "").strip()
                    try:
                        progress = max(0.0, min(100.0, float(raw)))
                    except ValueError:
                        progress = 0.0
                    self._change(task.task_id, "progress", progress=progress,
                                 speed=str(data.get("_speed_str", "")).strip())

            options = {
                "format": self._format_selector(task),
                "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
                "noplaylist": True,
                "continuedl": True,
                "retries": 3,
                "fragment_retries": 3,
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": False,
            }
            if task.media_format == "audio":
                options["postprocessors"] = [{
                    "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"
                }]
            aria2c = shutil.which("aria2c")
            if aria2c:
                options["external_downloader"] = aria2c
                options["external_downloader_args"] = {"default": ["-x", "8", "-s", "8", "-k", "1M"]}

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(task.url, download=True)
                output_path = ydl.prepare_filename(info)
            if task.media_format == "audio":
                output_path = str(Path(output_path).with_suffix(".mp3"))
            if cancel_event.is_set():
                raise DownloadCancelled("İndirme iptal edildi.")
            with self._lock:
                current = self._tasks[task.task_id]
                current.title = info.get("title") or "Video"
            self._change(task.task_id, "completed", "İndirme tamamlandı.",
                         status=DownloadStatus.COMPLETED, progress=100.0,
                         output_path=output_path, speed="")
            completed = self.get_task(task.task_id)
            try:
                add_history_entry(completed)
            except Exception as exc:
                self._emit(completed, "warning", f"Geçmiş kaydedilemedi: {exc}")
        except DownloadCancelled as exc:
            self._change(task.task_id, "cancelled", str(exc), status=DownloadStatus.CANCELLED, speed="")
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                error = DiskFullError("Hedef diskte yeterli boş alan yok.")
            elif exc.errno in (errno.EACCES, errno.EPERM):
                error = OutputDirectoryError("Hedef klasöre yazma izni yok.")
            else:
                error = OutputDirectoryError(str(exc))
            self._change(task.task_id, "failed", str(error), status=DownloadStatus.FAILED, error=str(error), speed="")
        except DependencyMissingError as exc:
            self._change(task.task_id, "failed", str(exc), status=DownloadStatus.FAILED, error=str(exc), speed="")
        except yt_dlp.utils.DownloadError as exc:
            message = str(exc)
            network_markers = ("network", "connection", "timed out", "temporary failure", "unable to download")
            error = NetworkDownloadError(message) if any(word in message.lower() for word in network_markers) else DownloadError(message)
            self._change(task.task_id, "failed", str(error), status=DownloadStatus.FAILED, error=str(error), speed="")
        except Exception as exc:
            # Unexpected worker failures are contained so the UI and other tasks keep running.
            self._change(task.task_id, "failed", f"Beklenmeyen indirme hatası: {exc}",
                         status=DownloadStatus.FAILED, error=repr(exc), speed="")

    @staticmethod
    def _validate_output_dir(path: str) -> Path:
        folder = Path(path).expanduser() if path else Path.home() / "Downloads"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".vortexdl-write-check"
            with probe.open("w", encoding="utf-8") as handle:
                handle.write("")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise OutputDirectoryError(f"Hedef klasör yazılabilir değil: {folder}") from exc
        if not folder.is_dir():
            raise OutputDirectoryError(f"Hedef bir klasör değil: {folder}")
        return folder

    @staticmethod
    def _format_selector(task: DownloadTask) -> str:
        if task.media_format == "audio":
            return "bestaudio/best"
        if task.quality in ("best", "Best Quality"):
            return "bestvideo+bestaudio/best"
        try:
            height = int(task.quality.rstrip("p"))
        except (ValueError, AttributeError):
            return "bestvideo+bestaudio/best"
        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
