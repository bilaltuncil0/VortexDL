"""Safe source-checkout updater with a clean-tree guard and GUI-safe callbacks."""
import os
import subprocess
import sys
import threading
from pathlib import Path


class AutoUpdater:
    """Check origin/main and apply updates only to an untouched source checkout."""

    def __init__(self, repo_root, *, status_callback=None, safe_to_update=None):
        self.repo_root = Path(repo_root).resolve()
        self.status_callback = status_callback or (lambda message: None)
        self.safe_to_update = safe_to_update or (lambda: True)
        self._lock = threading.Lock()
        self._running = False

    def check_and_apply_async(self, *, force=False):
        """Run a single update check without blocking Tk."""
        with self._lock:
            if self._running:
                return False
            self._running = True

        def worker():
            try:
                self._check_and_apply(force=force)
            except Exception as exc:
                self._notify(f"Updater stopped safely: {exc}")
            finally:
                with self._lock:
                    self._running = False

        threading.Thread(target=worker, name="vortexdl-auto-updater", daemon=True).start()
        return True

    def _check_and_apply(self, *, force):
        if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
            return
        if getattr(sys, "frozen", False) or not (self.repo_root / ".git").exists():
            self._notify("Automatic Git updates are available only in a source checkout.")
            return
        if not force and not self._git_config_enabled():
            return
        if not self.safe_to_update():
            self._notify("An update is waiting until active downloads finish.")
            return

        dirty = self._run_git(["status", "--porcelain", "--untracked-files=all"]).stdout.strip()
        if dirty:
            self._notify("Update skipped to preserve local or untracked files.")
            return

        self._run_git(["fetch", "origin", "main"])
        counts = self._run_git(
            ["rev-list", "--left-right", "--count", "HEAD...origin/main"]
        ).stdout.split()
        if len(counts) != 2:
            self._notify("Unable to compare local and remote versions.")
            return
        ahead, behind = (int(counts[0]), int(counts[1]))
        if behind == 0:
            self._notify("VortexDL is already up to date.")
            return
        if ahead:
            self._notify("Update skipped because the local branch has commits absent from origin/main.")
            return
        if not self.safe_to_update():
            self._notify("Update skipped because a download started.")
            return
        dirty_again = self._run_git(
            ["status", "--porcelain", "--untracked-files=all"]
        ).stdout.strip()
        if dirty_again:
            self._notify("Update skipped because local files changed during the check.")
            return

        requirements_changed = self._run_git(
            ["diff", "--name-only", "HEAD", "origin/main", "--", "requirements.txt"]
        ).stdout.strip() == "requirements.txt"

        # The clean-tree check above ensures reset/clean cannot discard user work.
        self._run_git(["reset", "--hard", "origin/main"])
        self._run_git(["clean", "-fd"])
        if requirements_changed:
            self._notify("Installing updated dependencies…")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"],
                cwd=self.repo_root, check=True, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=600,
            )
        self._notify("Update installed. Restarting VortexDL…")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _git_config_enabled(self):
        try:
            from storage import load_settings
            return bool(load_settings().get("auto_update_enabled", True))
        except Exception:
            return True

    def _run_git(self, args):
        return subprocess.run(
            ["git", *args], cwd=self.repo_root, check=True,
            capture_output=True, text=True, timeout=120,
        )

    def _notify(self, message):
        try:
            self.status_callback(message)
        except Exception:
            pass
