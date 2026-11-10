"""SQLite history storage with platform-appropriate data directories."""
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def app_data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "VortexDL"


DB_PATH = app_data_dir() / "history.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT, title TEXT, url TEXT NOT NULL, format TEXT, quality TEXT,
        filepath TEXT, filesize INTEGER, timestamp TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def add_history_entry(task) -> None:
    size = None
    try:
        size = Path(task.output_path).stat().st_size if task.output_path else None
    except OSError:
        pass
    with _connect() as conn:
        conn.execute(
            """INSERT INTO history
               (task_id, title, url, format, quality, filepath, filesize, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (task.task_id, task.title, task.url, task.media_format, task.quality,
             task.output_path, size, datetime.now(timezone.utc).isoformat()),
        )


def get_history_entries(limit: int = 100):
    with _connect() as conn:
        return conn.execute(
            """SELECT id, title, url, format, quality, filepath, filesize, timestamp
               FROM history ORDER BY id DESC LIMIT ?""", (max(1, min(int(limit), 1000)),)
        ).fetchall()
