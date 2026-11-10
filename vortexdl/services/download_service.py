"""Concurrent yt-dlp queue service; workers communicate only through events."""
import errno
import logging
import queue
import re
import shutil
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Optional

import yt_dlp

from vortexdl.core.errors import (
    DependencyMissingError,
    DiskFullError,
    DownloadCancelled,
    DownloadError,
    NetworkDownloadError,
    OutputDirectoryError,
)
from vortexdl.core.models import DownloadEvent, DownloadStatus, DownloadTask
from vortexdl.storage.database import add_history_entry
from vortexdl.services.notification_service import NotificationService


_SPEED_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*([KMGT]?i?B)/s", re.IGNORECASE)
_SPEED_FACTORS = {
    "B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3,
    "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3,
}


class DownloadQueueService:
    """Tracks tasks and runs up to max_workers downloads concurrently."""
    def __init__(self, events: Optional[queue.Queue] = None, max_workers: int = 3, notification_service: Optional[NotificationService] = None):
        self.events = events if events is not None else queue.Queue()
        self.max_workers = max(1, int(max_workers))
        self._tasks = {}
        self._cancel_events = {}
        self._pause_events = {}
        self._futures: dict[str, Future] = {}
        self._lock = threading.RLock()
        self._closed = False
        self.notification_service = notification_service or NotificationService()
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="vortexdl-download"
        )

    def add(self, url: str, quality: str = "best", output_dir: str = "", media_format: str = "video", title: str = "") -> DownloadTask:
        url = (url or "").strip()
        if not url:
            raise ValueError("URL boş olamaz.")
        with self._lock:
            if self._closed:
                raise RuntimeError("İndirme servisi kapatılmış.")
            task = DownloadTask(
                url=url, quality=quality, output_dir=output_dir, media_format=media_format,
                title=title,
            )
            cancel_event = threading.Event()
            pause_event = threading.Event()
            self._tasks[task.task_id] = task
            self._cancel_events[task.task_id] = cancel_event
            self._pause_events[task.task_id] = pause_event
            self._emit(task, "queued", "İndirme kuyruğa eklendi.")
            # Submit while holding the lock so the worker cannot emit "started"
            # before the queued event or before its Future is registered.
            self._futures[task.task_id] = self._executor.submit(self._run_task, task.task_id)
            return replace(task)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            cancel_event = self._cancel_events.get(task_id)
            future = self._futures.get(task_id)
            if task is None or cancel_event is None or task.status in (
                DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED
            ):
                return False
            cancel_event.set()
            self._pause_events[task_id].clear()
            cancelled_before_start = bool(future and future.cancel())
        if cancelled_before_start:
            self._change(
                task_id, "cancelled", "İndirme iptal edildi.",
                status=DownloadStatus.CANCELLED, speed="", speed_mib=0.0, eta="",
            )
        return True

    def pause(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != DownloadStatus.DOWNLOADING:
                return False
            self._pause_events[task_id].set()
        self._change(task_id, "paused", "İndirme duraklatıldı.", status=DownloadStatus.PAUSED)
        return True

    def resume(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != DownloadStatus.PAUSED:
                return False
            self._pause_events[task_id].clear()
        self._change(task_id, "resumed", "İndirme sürdürüldü.", status=DownloadStatus.DOWNLOADING)
        return True

    def list_tasks(self):
        with self._lock:
            return [replace(task) for task in self._tasks.values()]

    def get_task(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
            return replace(task) if task else None

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(task.status == DownloadStatus.DOWNLOADING for task in self._tasks.values())

    @property
    def total_bandwidth_mib(self) -> float:
        with self._lock:
            return sum(
                task.speed_mib for task in self._tasks.values()
                if task.status == DownloadStatus.DOWNLOADING
            )

    def shutdown(self, wait: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            pending = []
            for task_id, cancel_event in self._cancel_events.items():
                cancel_event.set()
                self._pause_events[task_id].clear()
                future = self._futures.get(task_id)
                if future and future.cancel():
                    pending.append(task_id)
        for task_id in pending:
            self._change(
                task_id, "cancelled", "İndirme uygulama kapatılırken iptal edildi.",
                status=DownloadStatus.CANCELLED, speed="", speed_mib=0.0, eta="",
            )
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _emit(self, task: DownloadTask, kind: str, message: str = "") -> None:
        self.events.put(DownloadEvent(
            task_id=task.task_id,
            kind=kind,
            status=task.status,
            progress=task.progress,
            speed=task.speed,
            speed_mib=task.speed_mib,
            eta=task.eta,
            title=task.title,
            message=message,
            output_path=task.output_path,
        ))

    def _change(self, task_id: str, kind: str, message: str = "", **changes) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            previous_status = task.status
            for key, value in changes.items():
                setattr(task, key, value)
            snapshot = replace(task)
            should_notify = (
                snapshot.status != previous_status
                and snapshot.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED)
            )
        self._emit(snapshot, kind, message)
        if should_notify:
            self._notify_terminal_status(snapshot)

    def _notify_terminal_status(self, task: DownloadTask) -> None:
        """Notify the user once when a task reaches a terminal result."""
        import builtins

        translate = getattr(builtins, "_", lambda text: text)
        name = task.title or task.url or "VortexDL"
        if task.status == DownloadStatus.COMPLETED:
            title = translate("Download Complete")
            message = translate("Download completed: %(title)s") % {"title": name}
        elif task.status == DownloadStatus.FAILED:
            title = translate("Download Failed")
            message = translate("Download failed: %(title)s") % {"title": name}
        else:
            return
        try:
            self.notification_service.send_notification(title, message)
        except Exception:
            # A notification backend must never interfere with queue state.
            logging.getLogger(__name__).exception("Desktop notification failed")

    def _wait_if_paused(self, task_id: str, cancel_event: threading.Event, pause_event: threading.Event) -> None:
        while pause_event.is_set():
            if cancel_event.is_set():
                raise DownloadCancelled("İndirme iptal edildi.")
            time.sleep(0.1)
        if cancel_event.is_set():
            raise DownloadCancelled("İndirme iptal edildi.")

    def _run_task(self, task_id: str) -> None:
        task = self.get_task(task_id)
        with self._lock:
            cancel_event = self._cancel_events.get(task_id)
            pause_event = self._pause_events.get(task_id)
        if task is None or cancel_event is None or pause_event is None:
            return
        try:
            self._wait_if_paused(task_id, cancel_event, pause_event)
            output_dir = self._validate_output_dir(task.output_dir)
            ffmpeg = shutil.which("ffmpeg")
            if task.media_format == "audio" and not ffmpeg:
                raise DependencyMissingError("MP3 dönüştürme için FFmpeg bulunamadı.")
            self._wait_if_paused(task_id, cancel_event, pause_event)
            self._change(task_id, "started", "İndirme başladı.", status=DownloadStatus.DOWNLOADING)

            def progress_hook(data):
                self._wait_if_paused(task_id, cancel_event, pause_event)
                if data.get("status") != "downloading":
                    return
                raw_percent = str(data.get("_percent_str", "0%")).replace("%", "").strip()
                try:
                    progress = max(0.0, min(100.0, float(raw_percent)))
                except ValueError:
                    progress = 0.0
                raw_speed = str(data.get("_speed_str", "")).strip()
                speed_mib = self._speed_to_mib(raw_speed)
                eta = str(data.get("_eta_str", "")).strip()
                info = data.get("info_dict") or {}
                title = info.get("title") or ""
                self._change(
                    task_id, "progress", progress=progress,
                    speed=f"{speed_mib:.2f} MiB/s" if raw_speed else "",
                    speed_mib=speed_mib, eta=eta, title=title,
                )

            options = {
                # Avoid a merge step when FFmpeg is unavailable.
                "format": self._format_selector(task, ffmpeg_available=bool(ffmpeg)),
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
            self._wait_if_paused(task_id, cancel_event, pause_event)
            self._change(
                task_id, "completed", "İndirme tamamlandı.",
                status=DownloadStatus.COMPLETED, progress=100.0,
                title=info.get("title") or "Video", output_path=output_path,
                speed="", speed_mib=0.0, eta="",
            )
            completed = self.get_task(task_id)
            try:
                add_history_entry(completed)
            except Exception as exc:
                self._emit(completed, "warning", f"Geçmiş kaydedilemedi: {exc}")
        except DownloadCancelled as exc:
            self._change(
                task_id, "cancelled", str(exc), status=DownloadStatus.CANCELLED,
                speed="", speed_mib=0.0, eta="",
            )
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                error = DiskFullError("Hedef diskte yeterli boş alan yok.")
            elif exc.errno in (errno.EACCES, errno.EPERM):
                error = OutputDirectoryError("Hedef klasöre yazma izni yok.")
            else:
                error = OutputDirectoryError(str(exc))
            self._mark_failed(task_id, error)
        except (DependencyMissingError, DownloadError) as exc:
            self._mark_failed(task_id, exc)
        except yt_dlp.utils.DownloadError as exc:
            message = str(exc)
            network_markers = ("network", "connection", "timed out", "temporary failure", "unable to download")
            error = NetworkDownloadError(message) if any(word in message.lower() for word in network_markers) else DownloadError(message)
            self._mark_failed(task_id, error)
        except Exception as exc:
            self._mark_failed(task_id, DownloadError(f"Beklenmeyen indirme hatası: {exc}"), repr(exc))

    def _mark_failed(self, task_id: str, error: Exception, detail: str = "") -> None:
        self._change(
            task_id, "failed", str(error), status=DownloadStatus.FAILED,
            error=detail or str(error), speed="", speed_mib=0.0, eta="",
        )

    @staticmethod
    def _speed_to_mib(raw_speed: str) -> float:
        match = _SPEED_RE.search(raw_speed.replace(" ", ""))
        if not match:
            return 0.0
        amount = float(match.group(1))
        unit = match.group(2).upper()
        factor = _SPEED_FACTORS.get(unit, 0)
        return amount * factor / (1024**2) if factor else 0.0

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
    def _format_selector(task: DownloadTask, ffmpeg_available: bool = True) -> str:
        if task.media_format == "audio":
            return "bestaudio/best"
        if task.quality in ("best", "Best Quality"):
            return "bestvideo+bestaudio/best" if ffmpeg_available else "best"
        try:
            height = int(task.quality.rstrip("p"))
        except (ValueError, AttributeError):
            return "bestvideo+bestaudio/best" if ffmpeg_available else "best"
        if ffmpeg_available:
            return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
        return f"best[height<={height}]/best"
