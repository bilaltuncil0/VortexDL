"""Tk-safe polling service for detecting supported media links in the clipboard.

Clipboard access is scheduled through Tk's event loop because Tk clipboard APIs
must only be called from the thread that owns the Tk interpreter.
"""
import re
import tkinter as tk
from urllib.parse import urlsplit

_URL_RE = re.compile(r"""https?://[^\s<>"']+""", re.IGNORECASE)
_SUPPORTED_DOMAINS = (
    "youtube.com", "youtu.be", "twitter.com", "x.com", "vimeo.com",
    "tiktok.com", "instagram.com", "dailymotion.com", "twitch.tv",
    "facebook.com", "reddit.com", "soundcloud.com", "streamable.com",
)


def find_supported_media_url(text):
    """Return the first supported HTTP(S) URL in text, or an empty string."""
    for match in _URL_RE.finditer(text or ""):
        candidate = match.group(0).rstrip(".,!?;:)]}")
        try:
            parsed = urlsplit(candidate)
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError:
            continue
        if parsed.scheme.lower() not in ("http", "https") or not host:
            continue
        if any(host == domain or host.endswith("." + domain)
               for domain in _SUPPORTED_DOMAINS):
            return candidate
    return ""


class ClipboardMonitorService:
    """Poll a Tk root at a low frequency and report each new supported URL once."""

    def __init__(self, root, on_url_detected, poll_interval_ms=1000):
        self.root = root
        self.on_url_detected = on_url_detected
        self.poll_interval_ms = max(250, int(poll_interval_ms))
        self.running = False
        self._after_id = None
        self._last_detected_url = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._after_id = self.root.after(0, self._poll)

    def stop(self):
        self.running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except (tk.TclError, RuntimeError):
                pass
            self._after_id = None

    def _poll(self):
        self._after_id = None
        if not self.running:
            return
        try:
            clipboard_text = self.root.clipboard_get()
        except (tk.TclError, AttributeError):
            clipboard_text = ""

        url = find_supported_media_url(clipboard_text)
        if url:
            if url != self._last_detected_url:
                self._last_detected_url = url
                self.on_url_detected(url)
        else:
            self._last_detected_url = None

        if self.running:
            self._after_id = self.root.after(self.poll_interval_ms, self._poll)
