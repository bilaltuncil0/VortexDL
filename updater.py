"""
VortexDL Auto-Updater & Cloud Integration Modules
- Checks GitHub Releases for latest versions
- Non-blocking async check
- Flexible Cloud Sync Module (User-configurable API keys)
"""

import threading
import urllib.request
import json
import webbrowser

CURRENT_VERSION = "v3.0.0"
REPO_OWNER = "bilaltuncil0"
REPO_NAME = "VideoDownloader"

class AutoUpdater:
    def __init__(self, callback_on_update=None):
        self.callback = callback_on_update
        self.latest_version = None
        self.release_url = None

    def check_for_updates_async(self):
        thread = threading.Thread(target=self._check_worker, daemon=True)
        thread.start()

    def _check_worker(self):
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "VortexDL-App"})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    tag = data.get("tag_name", "")
                    html_url = data.get("html_url", "")
                    if tag and tag != CURRENT_VERSION:
                        # Version comparison (simple semver check)
                        if self._is_newer(tag, CURRENT_VERSION):
                            self.latest_version = tag
                            self.release_url = html_url
                            if self.callback:
                                self.callback(self.latest_version, self.release_url)
        except Exception:
            pass

    def _is_newer(self, latest, current):
        try:
            v_l = [int(x) for x in latest.lstrip("v").split(".")]
            v_c = [int(x) for x in current.lstrip("v").split(".")]
            return v_l > v_c
        except Exception:
            return latest != current

    def open_download_page(self):
        if self.release_url:
            webbrowser.open(self.release_url)
        else:
            webbrowser.open(f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases")


class CloudSyncManager:
    """
    Flexible Cloud Integration:
    Users can provide their own Google Drive or OneDrive API keys/tokens.
    """
    def __init__(self, gdrive_key="", onedrive_key=""):
        self.gdrive_key = gdrive_key
        self.onedrive_key = onedrive_key

    def sync_file_to_cloud(self, filepath: str, service: str = "Google Drive"):
        # Placeholder for user-provided REST API execution
        if service == "Google Drive":
            if not self.gdrive_key:
                return False, "Google Drive API key not configured."
            # In production, uses user credentials to upload via Google Drive REST API
            return True, f"Simulated upload of {filepath} to Google Drive."
        elif service == "OneDrive":
            if not self.onedrive_key:
                return False, "OneDrive API key not configured."
            return True, f"Simulated upload of {filepath} to OneDrive."
        return False, "Unknown service."
