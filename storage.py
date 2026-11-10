"""
VortexDL Database & Security Manager
- SQLite Download History
- Obfuscated Settings Manager
- Secure .part File Cleanup
"""

import sqlite3
import json
import base64
import os
import glob
from pathlib import Path
from datetime import datetime

APP_DIR = Path.home() / ".config" / "vortexdl"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "history.db"
SETTINGS_PATH = APP_DIR / "settings.dat"

_XOR_KEY = b"VortexDL_v3_SuperSecretKey2026"

def _obfuscate(data: str) -> str:
    raw = data.encode("utf-8")
    xor_bytes = bytes([b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(raw)])
    return base64.b64encode(xor_bytes).decode("utf-8")

def _deobfuscate(data: str) -> str:
    try:
        xor_bytes = base64.b64decode(data.encode("utf-8"))
        raw = bytes([b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(xor_bytes)])
        return raw.decode("utf-8")
    except Exception:
        return "{}"

# --- Settings Manager ---
DEFAULT_SETTINGS = {
    "default_quality": "Best Quality",
    "default_folder": str(Path.home() / "Downloads"),
    "disable_telemetry": True,
    "theme": "Dark",
    "language": "en_US",
    "gdrive_api_key": "",
    "onedrive_api_key": "",
    "global_speed_limit": 0
}

def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        content = SETTINGS_PATH.read_text(encoding="utf-8")
        decrypted = _deobfuscate(content)
        data = json.loads(decrypted)
        merged = DEFAULT_SETTINGS.copy()
        merged.update(data)
        return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict):
    try:
        dumped = json.dumps(settings, indent=2)
        encrypted = _obfuscate(dumped)
        SETTINGS_PATH.write_text(encrypted, encoding="utf-8")
    except Exception as e:
        print(f"Error saving settings: {e}")

# --- SQLite Download History ---
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            format TEXT,
            quality TEXT,
            filepath TEXT,
            filesize TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def add_history_entry(title: str, url: str, fmt: str, quality: str, filepath: str, filesize: str = ""):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("""
            INSERT INTO history (title, url, format, quality, filepath, filesize, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, url, fmt, quality, filepath, filesize, now))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving history: {e}")

def get_history_entries(limit: int = 100):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, url, format, quality, filepath, filesize, timestamp FROM history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def clear_all_history():
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error clearing history: {e}")

def delete_history_entry(entry_id: int):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error deleting history entry: {e}")

# --- Secure File Cleanup ---
def cleanup_temp_artifacts(download_dir: str):
    """Safely cleans up any orphaned .part or .ytdl or partial temp files."""
    try:
        patterns = ["*.part", "*.ytdl", "*.temp", "*.f*.mp4", "*.f*.m4a", "*.f*.webm"]
        for pat in patterns:
            for f in glob.glob(os.path.join(download_dir, pat)):
                try:
                    if os.path.isfile(f):
                        # Overwrite with zeros before deletion if privacy mode is on
                        with open(f, "ba+", buffering=0) as delf:
                            length = delf.tell()
                            delf.seek(0)
                            delf.write(b"\x00" * min(length, 1024 * 1024))
                        os.remove(f)
                except Exception:
                    pass
    except Exception:
        pass
