"""Asynchronous metadata inspection for downloadable media URLs."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import queue
import threading
from typing import Optional
from uuid import uuid4

import yt_dlp


@dataclass(frozen=True)
class QualityOption:
    """A user-facing format choice mapped to DownloadTask fields."""
    label: str
    quality: str
    media_format: str = "video"


@dataclass(frozen=True)
class VideoMetadata:
    """Metadata needed to preview a video before queuing it."""
    url: str
    title: str
    duration: Optional[float]
    thumbnail_url: str
    available_formats: tuple[str, ...]
    quality_options: tuple[QualityOption, ...]


@dataclass(frozen=True)
class MetadataResult:
    """Result delivered to the UI queue by a metadata worker."""
    request_id: str
    url: str
    metadata: Optional[VideoMetadata] = None
    error: str = ""


class MetadataService:
    """Fetch yt-dlp metadata in worker threads without touching Tk widgets."""
    def __init__(self, results: Optional[queue.Queue] = None, max_workers: int = 2):
        self.results = results if results is not None else queue.Queue()
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="vortexdl-metadata",
        )
        self._lock = threading.Lock()
        self._closed = False

    def fetch(self, url: str) -> str:
        """Schedule metadata inspection and return a request identifier."""
        url = (url or "").strip()
        if not url:
            raise ValueError("URL boş olamaz.")
        with self._lock:
            if self._closed:
                raise RuntimeError("Metadata servisi kapatılmış.")
            request_id = str(uuid4())
            self._executor.submit(self._inspect, request_id, url)
            return request_id

    def _inspect(self, request_id: str, url: str) -> None:
        try:
            options = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "extract_flat": False,
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
            if not isinstance(info, dict):
                raise ValueError("URL için video bilgisi alınamadı.")
            metadata = self._to_metadata(url, info)
            result = MetadataResult(request_id=request_id, url=url, metadata=metadata)
        except (yt_dlp.utils.DownloadError, ValueError, OSError) as exc:
            result = MetadataResult(request_id=request_id, url=url, error=str(exc))
        except Exception as exc:
            # Treat extractor/plugin failures as a failed preview, not a GUI crash.
            result = MetadataResult(
                request_id=request_id,
                url=url,
                error=f"Meta veriler alınamadı: {exc}",
            )
        self.results.put(result)

    @staticmethod
    def _to_metadata(url: str, info: dict) -> VideoMetadata:
        formats = info.get("formats") or []
        resolutions = set()
        available_formats = set()
        has_video = False
        for item in formats:
            if not isinstance(item, dict):
                continue
            video_codec = item.get("vcodec")
            height = item.get("height")
            if video_codec != "none" and (video_codec or height):
                has_video = True
                if height:
                    try:
                        resolutions.add(int(height))
                    except (TypeError, ValueError):
                        pass
                ext = item.get("ext")
                if ext:
                    available_formats.add(str(ext).upper())

        if info.get("height"):
            has_video = True
            try:
                resolutions.add(int(info["height"]))
            except (TypeError, ValueError):
                pass
        if info.get("vcodec") and info.get("vcodec") != "none":
            has_video = True

        video_options = []
        if has_video:
            video_options = [
                QualityOption("Best Video", "best", "video"),
                *[
                    QualityOption(f"{height}p", str(height), "video")
                    for height in sorted(resolutions, reverse=True)
                ],
            ]
        quality_options = [
            *video_options,
            QualityOption("Audio Only (MP3)", "best", "audio"),
        ]
        duration = info.get("duration")
        try:
            duration = float(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration = None

        return VideoMetadata(
            url=url,
            title=str(info.get("title") or "Untitled media"),
            duration=duration,
            thumbnail_url=str(info.get("thumbnail") or ""),
            available_formats=tuple(sorted(available_formats)),
            quality_options=tuple(quality_options),
        )

    def shutdown(self, wait: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=True)
