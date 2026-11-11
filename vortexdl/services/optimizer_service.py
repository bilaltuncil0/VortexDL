"""Conservative cache and stale-download cleanup for VortexDL."""
import gc
import os
import shutil
import tempfile
import threading
import time


class SystemOptimizer:
    """Remove only application caches and old partial downloads."""

    PARTIAL_SUFFIXES = (".part", ".ytdl")
    MAX_PARTIAL_AGE_SECONDS = 24 * 60 * 60

    def __init__(self, project_root, download_dirs=()):
        self.project_root = os.path.realpath(os.fspath(project_root))
        self.download_dirs = tuple(
            os.path.realpath(os.path.expanduser(os.fspath(path)))
            for path in download_dirs if path
        )
        self._lock = threading.Lock()

    def cleanup(self):
        """Delete app bytecode caches and stale partial files; return counts."""
        if not self._lock.acquire(blocking=False):
            return {"cache_dirs": 0, "partial_files": 0}
        removed = {"cache_dirs": 0, "partial_files": 0}
        try:
            removed["cache_dirs"] = self._remove_project_caches()
            roots = {self.project_root, *self.download_dirs}
            roots.add(os.path.realpath(tempfile.gettempdir()))
            removed["partial_files"] = self._remove_old_partials(roots)
            removed["partial_files"] += self._remove_app_temp_files()
        finally:
            self._lock.release()
        return removed

    def cleanup_async(self, callback=None):
        def worker():
            try:
                result = self.cleanup()
            except Exception:
                result = {"cache_dirs": 0, "partial_files": 0}
            if callback:
                try:
                    callback(result)
                except Exception:
                    pass
        threading.Thread(target=worker, name="vortexdl-cleanup", daemon=True).start()

    def optimize_memory(self):
        try:
            return gc.collect()
        except Exception:
            return 0

    def _remove_project_caches(self):
        count = 0
        for current, dirs, _files in os.walk(self.project_root, topdown=True):
            dirs[:] = [name for name in dirs if name not in {".git", ".venv", "venv"}]
            if "__pycache__" in dirs:
                path = os.path.join(current, "__pycache__")
                try:
                    shutil.rmtree(path)
                    count += 1
                    dirs.remove("__pycache__")
                except OSError:
                    pass
        return count

    def _remove_old_partials(self, roots):
        cutoff = time.time() - self.MAX_PARTIAL_AGE_SECONDS
        deleted = 0
        for root in roots:
            if not os.path.isdir(root):
                continue
            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                dirs[:] = [name for name in dirs if name not in {".git", ".venv", "venv"}]
                for name in files:
                    if not name.lower().endswith(self.PARTIAL_SUFFIXES):
                        continue
                    path = os.path.join(current, name)
                    try:
                        if not os.path.islink(path) and os.path.getmtime(path) < cutoff:
                            os.remove(path)
                            deleted += 1
                    except OSError:
                        continue
        return deleted

    @staticmethod
    def _remove_app_temp_files():
        temp_root = tempfile.gettempdir()
        deleted = 0
        try:
            names = os.listdir(temp_root)
        except OSError:
            return 0
        for name in names:
            if not name.lower().startswith(("vortexdl-", "vortexdl_")):
                continue
            path = os.path.join(temp_root, name)
            try:
                if os.path.isfile(path) and not os.path.islink(path):
                    os.remove(path)
                    deleted += 1
                elif os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                    deleted += 1
            except OSError:
                continue
        return deleted
