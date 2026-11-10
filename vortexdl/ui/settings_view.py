"""Settings controls for smart download categories."""
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog


class SmartCategoriesSettingsView(ctk.CTkFrame):
    """Editable opt-in category folders embedded in the Settings page."""

    _FOLDERS = (
        ("music_folder", "Music", "🎵"),
        ("video_folder", "Video", "🎬"),
        ("documents_folder", "Documents", "📄"),
    )

    def __init__(self, master, *, settings, colors, translate):
        super().__init__(
            master, fg_color=colors["bg_secondary"], corner_radius=16,
            border_width=1, border_color=colors["border"],
        )
        self._settings = settings
        self._colors = colors
        self._ = translate
        self._paths = {}
        self._enabled = ctk.BooleanVar(
            value=bool(settings.get("smart_categories_enabled", False))
        )

        ctk.CTkLabel(
            self, text=f"🗂️  {translate('Smart Categories')}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=colors["text_primary"], anchor="w",
        ).pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkSwitch(
            self, text=translate("Enable Smart Categories"),
            variable=self._enabled, progress_color=colors["accent"],
        ).pack(anchor="w", padx=18, pady=(4, 10))

        for key, label, icon in self._FOLDERS:
            self._add_folder_row(key, label, icon)

    def _add_folder_row(self, key, label, icon):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(
            row, text=f"{icon}  {self._(label)}",
            width=105, anchor="w", text_color=self._colors["text_muted"],
        ).pack(side="left")
        default = str(Path.home() / label)
        value = self._settings.get(key) or default
        path_label = ctk.CTkLabel(
            row, text=value, anchor="w", text_color=self._colors["text_primary"],
        )
        path_label.pack(side="left", fill="x", expand=True, padx=8)
        self._paths[key] = (value, path_label)
        ctk.CTkButton(
            row, text=self._("Choose Folder"), width=115, height=30,
            fg_color=self._colors["bg_card"],
            command=lambda k=key: self._choose_folder(k),
        ).pack(side="right")

    def _choose_folder(self, key):
        current, label = self._paths[key]
        initial = current if Path(current).is_dir() else str(Path.home())
        selected = filedialog.askdirectory(initialdir=initial)
        if selected:
            self._paths[key] = (selected, label)
            label.configure(text=selected)

    def get_values(self):
        """Return settings values ready for persistence."""
        return {
            "smart_categories_enabled": bool(self._enabled.get()),
            **{key: value for key, (value, _label) in self._paths.items()},
        }
