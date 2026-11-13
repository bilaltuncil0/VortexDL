"""Cupertino-inspired glass palette and lightweight Tk animation helpers.

CustomTkinter surfaces remain opaque for cross-platform rendering consistency;
layered colors and specular borders provide the glass treatment without
platform-specific blur APIs.
"""
from __future__ import annotations

import time


RADIUS = {
    "panel": 16,
    "card": 16,
    "control": 12,
    "button": 12,
    "pill": 999,
    "badge": 999,
}

THEME_CONFIGS = {
    "dark": {
        "bg_primary": "#141417",
        "bg_secondary": "#1F1F24",
        "bg_card": "#1F1F24",
        "bg_hover": "#2A2A32",
        "accent": "#0A84FF",
        "accent_hover": "#0070E0",
        "accent_purple": "#0A84FF",
        "text_primary": "#F5F5F7",
        "text_muted": "#A1A1AA",
        "success": "#30D158",
        "warning": "#FF9F0A",
        "danger": "#FF453A",
        "progress_fg": "#0A84FF",
        "border": "#383842",
        "border_hover": "#50505E",
        "tab_active": "#2A2A32",
        # Apple Cupertino Glass specification aliases
        "deep_glass": "#141417",
        "card_surface": "#1F1F24",
        "hover_surface": "#2A2A32",
        "specular_border": "#383842",
        "primary": "#0A84FF",
    },
    "light": {
        "bg_primary": "#F2F2F7",
        "bg_secondary": "#FFFFFF",
        "bg_card": "#FFFFFF",
        "bg_hover": "#E5E5EA",
        "accent": "#0A84FF",
        "accent_hover": "#0070E0",
        "accent_purple": "#0A84FF",
        "text_primary": "#1C1C1E",
        "text_muted": "#6E6E73",
        "success": "#30D158",
        "warning": "#FF9F0A",
        "danger": "#FF453A",
        "progress_fg": "#0A84FF",
        "border": "#D1D1D6",
        "border_hover": "#B0B0B8",
        "tab_active": "#E5E5EA",
        # Apple Cupertino Glass specification aliases
        "deep_glass": "#F2F2F7",
        "card_surface": "#FFFFFF",
        "hover_surface": "#E5E5EA",
        "specular_border": "#D1D1D6",
        "primary": "#0A84FF",
    },
}


class GlassAnimator:
    """Small Tk after-driven animator paced at roughly 60 frames per second."""

    def __init__(self, widget, frame_interval_ms: int = 16):
        self.widget = widget
        self.frame_interval_ms = max(1, int(frame_interval_ms))
        self._jobs = {}
        self._values = {}

    def animate(self, key, start, end, update, *, duration: float = 0.2, easing=None):
        """Animate a numeric value without blocking Tk's event loop."""
        self.cancel(key)
        start_time = time.perf_counter()
        duration = max(0.001, float(duration))
        easing = easing or (lambda t: 1 - (1 - t) ** 3)

        def frame():
            elapsed = max(0.0, time.perf_counter() - start_time)
            ratio = min(1.0, elapsed / duration)
            eased = easing(ratio)
            value = start + (end - start) * eased
            self._values[key] = value
            try:
                update(value)
            except Exception:
                self._jobs.pop(key, None)
                return
            if ratio >= 1.0:
                self._values[key] = end
                self._jobs.pop(key, None)
                return
            try:
                self._jobs[key] = self.widget.after(self.frame_interval_ms, frame)
            except Exception:
                self._jobs.pop(key, None)

        try:
            self._jobs[key] = self.widget.after(0, frame)
        except Exception:
            self._jobs.pop(key, None)

    def value(self, key, default=0.0):
        return self._values.get(key, default)

    def cancel(self, key):
        job = self._jobs.pop(key, None)
        if job is not None:
            try:
                self.widget.after_cancel(job)
            except Exception:
                pass

    def cancel_all(self):
        for key in tuple(self._jobs):
            self.cancel(key)
