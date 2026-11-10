"""SQLite history storage with compatibility for the existing VortexDL database."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Keep the existing database location so previous history remains visible.
APP_DIR = Path.home() / ".config" / "vortexdl"
DB_PATH = APP_DIR / "history.db"


def _connect() -> sqlite3.Connection:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, url TEXT, format TEXT, quality TEXT,
        filepath TEXT, filesize TEXT, timestamp TEXT
    )""")
    conn.commit()
    return conn


def add_history_entry(task) -> None:
    size = ""
    try:
        size = f"{Path(task.output_path).stat().st_size / (1024 * 1024):.1f} MB" if task.output_path else ""
    except OSError:
        pass
    with _connect() as conn:
        conn.execute(
            """INSERT INTO history (title, url, format, quality, filepath, filesize, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task.title, task.url, task.media_format, task.quality, task.output_path,
             size, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
        )


def get_history_entries(limit: int = 100):
    with _connect() as conn:
        return conn.execute(
            """SELECT id, title, url, format, quality, filepath, filesize, timestamp
               FROM history ORDER BY id DESC LIMIT ?""",
            (max(1, min(int(limit), 1000)),),
        ).fetchall()


def clear_all_history() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM history")


def delete_history_entry(entry_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM history WHERE id = ?", (int(entry_id),))
