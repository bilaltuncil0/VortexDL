"""Thread-safe Tk animation engine for glass opacity, progress and colors."""
from __future__ import annotations

import queue
import threading
import time
from tkinter import TclError


class UIAnimator:
    """Run all UI mutations on Tk's thread at a 16 ms cadence."""

    def __init__(self, window, *, enabled=True, frame_ms=16, opacity=0.93):
        self.window = window
        self.enabled = bool(enabled)
        self.frame_ms = max(1, int(frame_ms))
        self.opacity = max(0.0, min(1.0, float(opacity)))
        self._commands = queue.Queue()
        self._active = {}
        self._alive = True
        self._main_thread = threading.get_ident()
        self._job = None
        try:
            self._job = self.window.after(self.frame_ms, self._tick)
        except TclError:
            self._alive = False

    def apply_window_glass(self, window=None, opacity=0.93):
        target = window or self.window
        opacity = max(0.0, min(1.0, float(opacity)))
        self.opacity = opacity
        try:
            target.attributes("-alpha", opacity)
            return True
        except TclError:
            return False

    def fade_in(self, window=None, duration_ms=220, target_opacity=None):
        target = window or self.window
        opacity = self.opacity if target_opacity is None else max(
            0.0, min(1.0, float(target_opacity))
        )
        try:
            target.attributes("-alpha", 0.0)
        except TclError:
            return False
        self.animate(
            ("window-alpha", str(target)), 0.0, opacity,
            lambda value: self._set_alpha(target, value),
            duration_ms=duration_ms, easing="cubic",
        )
        return True

    def smooth_progress(self, widget, target, *, start=None, duration_ms=180, key=None):
        target = max(0.0, min(1.0, float(target)))
        if start is None:
            try:
                start = float(widget.get())
            except Exception:
                start = 0.0
        self.animate(
            key or ("progress", id(widget)), float(start), target,
            lambda value: widget.set(value), duration_ms=duration_ms,
        )

    def interpolate_color(self, widget, option, start, end, *, duration_ms=160, key=None):
        self.animate(
            key or ("color", id(widget), option), 0.0, 1.0,
            lambda ratio: widget.configure(**{
                option: self._mix_color(start, end, ratio)
            }),
            duration_ms=duration_ms,
        )

    def bind_hover(self, widget, *, option, normal, hover, duration_ms=150):
        widget.bind(
            "<Enter>",
            lambda _event: self.interpolate_color(
                widget, option, normal, hover, duration_ms=duration_ms
            ),
            add="+",
        )
        widget.bind(
            "<Leave>",
            lambda _event: self.interpolate_color(
                widget, option, hover, normal, duration_ms=duration_ms
            ),
            add="+",
        )

    def animate(self, key, start, end, update, *, duration_ms=200, easing="ease_out"):
        """Queue an animation request; safe to call from worker threads."""
        if not self._alive:
            return
        self._commands.put((key, float(start), float(end), update,
                            max(1, int(duration_ms)), easing))

    def set_enabled(self, enabled):
        """Enable motion, or complete active animations at their target values."""
        self._commands.put(("__enabled__", bool(enabled)))

    def stop(self):
        self._alive = False
        try:
            if self._job is not None:
                self.window.after_cancel(self._job)
        except TclError:
            pass
        self._job = None
        self._active.clear()

    @staticmethod
    def _set_alpha(window, value):
        try:
            window.attributes("-alpha", max(0.0, min(1.0, value)))
        except TclError:
            pass

    @staticmethod
    def _mix_color(start, end, ratio):
        try:
            a = tuple(int(start[i:i + 2], 16) for i in (1, 3, 5))
            b = tuple(int(end[i:i + 2], 16) for i in (1, 3, 5))
            values = tuple(round(x + (y - x) * ratio) for x, y in zip(a, b))
            return "#" + "".join(f"{value:02x}" for value in values)
        except (TypeError, ValueError, IndexError):
            return end if ratio >= 0.5 else start

    def _tick(self):
        if not self._alive:
            return
        try:
            while True:
                command = self._commands.get_nowait()
                if command[0] == "__enabled__":
                    self.enabled = command[1]
                    if not self.enabled:
                        for _key, item in tuple(self._active.items()):
                            try:
                                item["update"](item["end"])
                            except (TclError, Exception):
                                pass
                        self._active.clear()
                    continue
                key, start, end, update, duration_ms, easing = command
                if not self.enabled:
                    try:
                        update(end)
                    except (TclError, Exception):
                        pass
                    continue
                self._active[key] = {
                    "start": start, "end": end, "update": update,
                    "started": time.perf_counter(),
                    "duration": duration_ms / 1000.0, "easing": easing,
                }
        except queue.Empty:
            pass

        now = time.perf_counter()
        for key, item in tuple(self._active.items()):
            ratio = min(1.0, (now - item["started"]) / item["duration"])
            if item["easing"] == "cubic":
                ratio = 1 - (1 - ratio) ** 3
            elif item["easing"] == "linear":
                pass
            else:
                ratio = 1 - (1 - ratio) ** 3
            value = item["start"] + (item["end"] - item["start"]) * ratio
            try:
                item["update"](value)
            except (TclError, Exception):
                self._active.pop(key, None)
                continue
            if (now - item["started"]) >= item["duration"]:
                self._active.pop(key, None)
        try:
            self._job = self.window.after(self.frame_ms, self._tick)
        except TclError:
            self.stop()
