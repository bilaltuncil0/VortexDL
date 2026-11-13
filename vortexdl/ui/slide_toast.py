"""Top-right, slide-in glass toast for status messages and clipboard actions."""
import time
import customtkinter as ctk


class SlideToast(ctk.CTkToplevel):
    WIDTH = 360
    HEIGHT = 148
    DURATION_MS = 280
    FRAME_MS = 16

    def __init__(self, master, *, title, message, icon="•", colors,
                 actions=None, duration_ms=3500, on_close=None):
        super().__init__(master)
        self.colors = colors
        self._on_close_callback = on_close
        self._closed = False
        self._after_job = None
        self._actions = actions or []
        self.overrideredirect(True)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{self._screen_width()+20}+48")
        try:
            self.attributes("-topmost", True)
            self.attributes("-alpha", 0.93)
        except Exception:
            pass
        self.configure(fg_color=colors["bg_secondary"])

        shell = ctk.CTkFrame(
            self, fg_color=colors["bg_secondary"], corner_radius=16,
            border_width=1, border_color=colors.get("border", "#383842"),
        )
        shell.pack(fill="both", expand=True)
        heading = ctk.CTkFrame(shell, fg_color="transparent")
        heading.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            heading, text=icon, width=30, font=ctk.CTkFont(size=19, weight="bold"),
            text_color=colors["accent"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            heading, text=title, anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=colors["text_primary"],
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            heading, text="×", width=26, height=26, corner_radius=12,
            fg_color="transparent", hover_color=colors["bg_hover"],
            text_color=colors["text_muted"], command=self.close,
        ).pack(side="right")
        ctk.CTkLabel(
            shell, text=message, anchor="w", justify="left", wraplength=310,
            font=ctk.CTkFont(size=11), text_color=colors["text_muted"],
        ).pack(fill="x", padx=18, pady=(0, 8))

        if self._actions:
            actions_frame = ctk.CTkFrame(shell, fg_color="transparent")
            actions_frame.pack(fill="x", padx=16, pady=(0, 12))
            for label, callback, primary in self._actions:
                ctk.CTkButton(
                    actions_frame, text=label, width=92, height=30,
                    corner_radius=12,
                    fg_color=colors["accent"] if primary else colors["bg_hover"],
                    hover_color=colors["accent_hover"] if primary else colors["border"],
                    command=lambda cb=callback: self._run_action(cb),
                ).pack(side="right", padx=(6, 0))

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        self._x_target = max(0, self._screen_width() - self.WIDTH - 24)
        self._x_start = self._screen_width() + 20
        self._y = 48
        self._animate(self._x_start, self._x_target, entering=True)
        if not self._actions and duration_ms:
            self.after(max(500, int(duration_ms)), self.close)

    def _screen_width(self):
        try:
            return self.winfo_screenwidth()
        except Exception:
            return 1024

    def _run_action(self, callback):
        if self._closed:
            return
        self.close()
        try:
            callback()
        except Exception:
            pass

    def _animate(self, start, end, *, entering):
        started = time.perf_counter()
        duration = self.DURATION_MS / 1000.0

        def frame():
            if self._closed:
                return
            ratio = min(1.0, (time.perf_counter() - started) / duration)
            eased = 1 - (1 - ratio) ** 3
            x = round(start + (end - start) * eased)
            try:
                self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{self._y}")
            except Exception:
                return
            if ratio >= 1.0:
                if not entering:
                    self._destroy()
                return
            self._after_job = self.after(self.FRAME_MS, frame)

        self._after_job = self.after(0, frame)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._after_job is not None:
                self.after_cancel(self._after_job)
        except Exception:
            pass
        self._closed = False
        self._animate(self.winfo_x(), self._screen_width() + 20, entering=False)

    def _destroy(self):
        if self._closed:
            return
        self._closed = True
        try:
            super().destroy()
        except Exception:
            pass
        callback = self._on_close_callback
        if callback:
            try:
                callback(self)
            except Exception:
                pass
