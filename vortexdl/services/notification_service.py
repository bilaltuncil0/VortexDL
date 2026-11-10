"""Cross-platform desktop notifications with graceful fallback."""
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class NotificationService:
    """Send native OS notifications through Plyer when a backend is available."""

    def __init__(self, app_name="VortexDL", icon_path=None, timeout=8):
        self.app_name = app_name
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        self.icon_path = Path(icon_path).expanduser() if icon_path else root / "assets" / "icon.png"
        self.timeout = max(1, int(timeout))

    def send_notification(self, title, message, icon=None):
        """Send a notification and return whether the platform backend accepted it."""
        try:
            from plyer import notification

            selected_icon = Path(icon).expanduser() if icon else self.icon_path
            app_icon = str(selected_icon) if selected_icon.is_file() else None
            notification.notify(
                title=str(title),
                message=str(message),
                app_name=self.app_name,
                app_icon=app_icon,
                timeout=self.timeout,
            )
            return True
        except Exception as exc:
            # Notification backends can be unavailable in headless sessions or
            # desktop environments without a notification daemon. Never fail a
            # download because its optional OS notification could not be shown.
            logger.debug("Unable to send desktop notification: %s", exc)
            return False
