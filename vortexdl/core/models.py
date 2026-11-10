"""Domain models for queued downloads and UI events."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """One queued media download and its observable state."""
    url: str
    quality: str = "best"
    output_dir: str = ""
    media_format: str = "video"
    task_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    speed: str = ""
    speed_mib: float = 0.0
    eta: str = ""
    progress: float = 0.0
    status: DownloadStatus = DownloadStatus.QUEUED
    output_path: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class DownloadEvent:
    """Immutable worker-to-UI event; every update is keyed by task_id."""
    task_id: str
    kind: str
    status: DownloadStatus
    progress: float = 0.0
    speed: str = ""
    speed_mib: float = 0.0
    eta: str = ""
    title: str = ""
    message: str = ""
    output_path: str = ""



@dataclass
class CategoryRule:
    """Route a downloaded file to a folder based on extension or content type."""
    name: str
    extensions: list[str] = field(default_factory=list)
    folder: str = ""
    content_types: list[str] = field(default_factory=list)
