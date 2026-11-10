"""Modal metadata preview shown before a task enters the download queue."""
import webbrowser

import customtkinter as ctk
from tkinter import messagebox

from vortexdl.services.metadata_service import VideoMetadata


class PreviewDialog(ctk.CTkToplevel):
    """Let the user inspect a media URL and choose a quality before queuing."""
    def __init__(
        self,
        master,
        metadata: VideoMetadata,
        *,
        colors,
        translate,
        on_add,
        default_quality: str = "best",
        default_media_format: str = "video",
    ):
        super().__init__(master)
        self.metadata = metadata
        self.colors = colors
        self._ = translate
        self.on_add = on_add
        self.title(self._("Download Preview"))
        self.geometry("520x360")
        self.minsize(440, 320)
        self.configure(fg_color=colors["bg_primary"])
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        body = ctk.CTkFrame(self, fg_color=colors["bg_secondary"], corner_radius=16)
        body.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            body,
            text=metadata.title,
            wraplength=450,
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=colors["text_primary"],
        ).pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            body,
            text=f'{self._("Duration")}: {self._format_duration(metadata.duration)}',
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=colors["text_muted"],
        ).pack(fill="x", padx=18, pady=(0, 4))

        formats = ", ".join(metadata.available_formats) or self._("Unknown")
        ctk.CTkLabel(
            body,
            text=f'{self._("Available formats")}: {formats}',
            anchor="w",
            wraplength=450,
            font=ctk.CTkFont(size=11),
            text_color=colors["text_muted"],
        ).pack(fill="x", padx=18, pady=(0, 12))

        if metadata.thumbnail_url:
            ctk.CTkButton(
                body,
                text=self._("Open Cover Image"),
                height=30,
                fg_color=colors["bg_card"],
                hover_color=colors["accent_purple"],
                command=lambda: webbrowser.open(metadata.thumbnail_url),
            ).pack(anchor="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(
            body,
            text=self._("Choose quality or format"),
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=colors["text_muted"],
        ).pack(fill="x", padx=18)

        self._options_by_label = {}
        for option in metadata.quality_options:
            label = self._(option.label)
            self._options_by_label[label] = option
        labels = list(self._options_by_label) or [self._("Best Quality")]
        self.selected_var = ctk.StringVar(value=self._default_label(
            metadata.quality_options, default_quality, default_media_format,
            labels[0], self._
        ))
        self.quality_menu = ctk.CTkOptionMenu(
            body,
            values=labels,
            variable=self.selected_var,
            fg_color=colors["bg_card"],
            button_color=colors["bg_card"],
            button_hover_color=colors["accent_purple"],
            text_color=colors["text_primary"],
        )
        self.quality_menu.pack(fill="x", padx=18, pady=(6, 18))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 18))
        ctk.CTkButton(
            actions,
            text=self._("Cancel"),
            fg_color=colors["bg_card"],
            hover_color=colors["danger"],
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions,
            text=self._("Add to Queue"),
            fg_color=colors["accent_purple"],
            hover_color=colors["accent"],
            command=self._add_to_queue,
        ).pack(side="right")

        self.grab_set()
        self.focus_force()

    def _add_to_queue(self) -> None:
        option = self._options_by_label.get(self.selected_var.get())
        if option is None:
            messagebox.showerror(self._("Error occurred"), self._("Choose a quality or format."))
            return
        try:
            added = self.on_add(option.quality, option.media_format)
        except Exception as exc:
            messagebox.showerror(self._("Error occurred"), str(exc), parent=self)
            return
        if added is not False:
            self.destroy()

    @staticmethod
    def _default_label(options, quality: str, media_format: str, fallback: str, translate) -> str:
        for option in options:
            if option.media_format == media_format and option.quality == quality:
                return translate(option.label)
        return fallback

    @staticmethod
    def _format_duration(seconds) -> str:
        if seconds is None:
            return "—"
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:d}:{secs:02d}"
