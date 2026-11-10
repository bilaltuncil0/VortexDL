"""Small domain models shared by the UI and background services."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """One video or audio download and its observable state."""
    url: str
    quality: str = "best"
    output_dir: str = ""
    media_format: str = "video"
    task_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    speed: str = ""
    progress: float = 0.0
    status: DownloadStatus = DownloadStatus.QUEUED
    output_path: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class DownloadEvent:
    """Thread-safe message sent from a worker to the Tk main loop."""
    task_id: str
    kind: str
    status: DownloadStatus
    progress: float = 0.0
    speed: str = ""
    message: str = ""
    output_path: str = ""
