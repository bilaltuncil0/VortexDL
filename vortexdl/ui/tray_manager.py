"""Cross-platform system tray icon and menu for VortexDL."""
import logging
import queue
import threading
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class TrayManager:
    """Manage a detached pystray icon and queue its menu actions for Tk."""

    def __init__(self, assets_dir, translate=lambda text: text):
        self.assets_dir = Path(assets_dir)
        self.translate = translate
        self.events = queue.Queue()
        self._icon = None
        self._lock = threading.RLock()

    @property
    def is_running(self):
        return self._icon is not None

    def _load_image(self):
        for filename in ("icon.png", "icon.ico"):
            path = self.assets_dir / filename
            if path.is_file():
                with Image.open(path) as source:
                    return source.convert("RGBA").resize((64, 64))
        raise FileNotFoundError(f"VortexDL tray icon not found in {self.assets_dir}")

    def start(self):
        """Initialize pystray detached from Tk; call before Tk's mainloop."""
        with self._lock:
            if self._icon is not None:
                return True
            try:
                import pystray

                menu = pystray.Menu(
                    pystray.MenuItem(
                        self.translate("Show"),
                        lambda icon, item: self.events.put("show"),
                    ),
                    pystray.MenuItem(
                        self.translate("Pause All"),
                        lambda icon, item: self.events.put("pause_all"),
                    ),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(
                        self.translate("Quit"),
                        lambda icon, item: self.events.put("quit"),
                    ),
                )
                icon = pystray.Icon(
                    "VortexDL", self._load_image(), "VortexDL", menu
                )
                self._icon = icon
                icon.run_detached(setup=self._setup_hidden)
                return True
            except Exception as exc:
                self._icon = None
                logger.warning("Unable to initialize system tray: %s", exc)
                return False

    def _setup_hidden(self, icon):
        try:
            icon.visible = False
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def show(self):
        with self._lock:
            icon = self._icon
        if icon is None:
            return False
        try:
            icon.visible = True
            return True
        except Exception as exc:
            self.events.put(("error", str(exc)))
            return False

    def hide(self):
        with self._lock:
            icon = self._icon
        if icon is None:
            return
        try:
            icon.visible = False
        except Exception:
            logger.debug("Unable to hide tray icon", exc_info=True)

    def stop(self):
        """Stop the icon loop if it is active."""
        with self._lock:
            icon = self._icon
            self._icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                logger.debug("Unable to stop system tray cleanly", exc_info=True)
