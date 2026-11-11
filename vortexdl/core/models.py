"""Domain models for queued downloads and UI events."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    RETRYING = "retrying"
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
    retry_count: int = 0
    max_retries: int = 3
    retry_delay_seconds: float = 0.0
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
    retry_count: int = 0
    max_retries: int = 3
    retry_delay_seconds: float = 0.0
