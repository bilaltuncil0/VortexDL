"""CustomTkinter UI. All download work is delegated to DownloadQueueService."""
import gettext
import locale
import queue
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from vortexdl.core.models import DownloadStatus
from vortexdl.services.download_service import DownloadQueueService
from vortexdl.storage.database import get_history_entries


APP_ROOT = Path(__file__).resolve().parents[2]
try:
    language = (locale.getlocale()[0] or "en_US").split(".")[0]
except (ValueError, TypeError):
    language = "en_US"
_TRANSLATION = gettext.translation(
    "videodownloader", localedir=str(APP_ROOT / "locales"),
    languages=[language], fallback=True,
)
_ = _TRANSLATION.gettext


class VortexDLApp(ctk.CTk):
    def __init__(self, service=None):
        super().__init__()
        self.title("VortexDL")
        self.geometry("900x680")
        self.minsize(760, 560)
        self.service = service or DownloadQueueService()
        self.events = self.service.events
        self._closing = False
        self.download_dir = str(Path.home() / "Downloads")
        self._rows = {}
        ctk.set_appearance_mode("System")
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_events)
        self._render_tasks()

    def _build_ui(self):
        header = ctk.CTkFrame(self, corner_radius=0, height=68)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="⚡ VortexDL", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left", padx=20, pady=16)
        ctk.CTkButton(header, text=_("History"), width=90, command=self._show_history).pack(side="right", padx=16)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=18)
        add_card = ctk.CTkFrame(body, corner_radius=16)
        add_card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(add_card, text=_("Video URL"), font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(14, 6))
        self.url_entry = ctk.CTkEntry(add_card, placeholder_text=_("Paste URL here (YouTube, Instagram, TikTok, Twitter...)"))
        self.url_entry.pack(fill="x", padx=16, pady=6)
        controls = ctk.CTkFrame(add_card, fg_color="transparent")
        controls.pack(fill="x", padx=16, pady=(4, 14))
        self.format_menu = ctk.CTkOptionMenu(controls, values=[_("Video (MP4)"), _("Audio Only (MP3)")])
        self.format_menu.pack(side="left", padx=(0, 8))
        self.quality_menu = ctk.CTkOptionMenu(controls, values=[_("Best Quality"), "1080p", "720p", "480p", "360p"])
        self.quality_menu.pack(side="left", padx=8)
        self.folder_label = ctk.CTkLabel(controls, text=self.download_dir, anchor="w")
        self.folder_label.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(controls, text=_("Open Folder"), width=90, command=self._choose_folder).pack(side="left", padx=5)
        ctk.CTkButton(controls, text=_("Download"), command=self._add_download).pack(side="right", padx=(8, 0))

        self.status_label = ctk.CTkLabel(body, text=_("Ready"), anchor="w")
        self.status_label.pack(fill="x", pady=(0, 8))
        self.task_list = ctk.CTkScrollableFrame(body, label_text=_("Download"))
        self.task_list.pack(fill="both", expand=True)

    def _add_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(_("Warning"), _("Please enter a valid URL!"), parent=self)
            return
        quality = self.quality_menu.get()
        if quality == "Best Quality":
            quality = "best"
        media_format = "audio" if self.format_menu.get() == _("Audio Only (MP3)") else "video"
        try:
            self.service.add(url, quality, self.download_dir, media_format)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror(_("Error occurred"), str(exc), parent=self)
            return
        self.url_entry.delete(0, "end")
        self._render_tasks()

    def _choose_folder(self):
        selected = filedialog.askdirectory(initialdir=self.download_dir, parent=self)
        if selected:
            self.download_dir = selected
            self.folder_label.configure(text=selected)

    def _drain_events(self):
        if self._closing:
            return
        handled = False
        try:
            while True:
                event = self.events.get_nowait()
                handled = True
                self.status_label.configure(text=event.message or _(event.status.value.title()))
                if event.kind == "failed":
                    self.status_label.configure(text=f"Hata: {event.message}")
                elif event.kind == "completed":
                    self.status_label.configure(text=f"Tamamlandı: {event.output_path}")
        except queue.Empty:
            pass
        if handled:
            self._render_tasks()
        self.after(100, self._drain_events)

    def _render_tasks(self):
        for child in self.task_list.winfo_children():
            child.destroy()
        tasks = self.service.list_tasks()
        if not tasks:
            ctk.CTkLabel(self.task_list, text="Henüz indirme yok.").pack(pady=30)
            return
        for task in reversed(tasks):
            row = ctk.CTkFrame(self.task_list, corner_radius=12)
            row.pack(fill="x", padx=6, pady=5)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(9, 3))
            title = task.title or task.url
            ctk.CTkLabel(top, text=title[:100], anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(top, text=task.status.value).pack(side="right", padx=8)
            progress = ctk.CTkProgressBar(row, height=10)
            progress.pack(fill="x", padx=12, pady=4)
            progress.set(max(0.0, min(1.0, task.progress / 100.0)))
            bottom = ctk.CTkFrame(row, fg_color="transparent")
            bottom.pack(fill="x", padx=12, pady=(2, 8))
            detail = f"{task.progress:.1f}%  {task.speed}".strip()
            if task.error:
                detail = task.error
            ctk.CTkLabel(bottom, text=detail, anchor="w").pack(side="left", fill="x", expand=True)
            if task.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING):
                ctk.CTkButton(bottom, text=_("Cancel"), width=64, height=26,
                              command=lambda task_id=task.task_id: self._cancel(task_id)).pack(side="right")

    def _cancel(self, task_id):
        self.service.cancel(task_id)

    def _show_history(self):
        try:
            rows = get_history_entries(100)
        except Exception as exc:
            messagebox.showerror(_("History"), str(exc), parent=self)
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("İndirme geçmişi")
        dialog.geometry("720x480")
        view = ctk.CTkScrollableFrame(dialog, label_text=_("History"))
        view.pack(fill="both", expand=True, padx=12, pady=12)
        if not rows:
            ctk.CTkLabel(view, text=_("No downloads yet.")).pack(pady=24)
            return
        for row in rows:
            _, title, url, media_format, quality, filepath, size, timestamp = row
            text = f"{title or url}\n{timestamp} · {media_format} · {quality} · {filepath or ''}"
            ctk.CTkLabel(view, text=text, anchor="w", justify="left").pack(fill="x", padx=8, pady=6)

    def _on_close(self):
        self._closing = True
        self.service.shutdown(wait=False)
        self.destroy()


def create_app():
    return VortexDLApp()
