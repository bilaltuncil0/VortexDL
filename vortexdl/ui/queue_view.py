"""Scrollable, task-oriented download queue widgets."""
import customtkinter as ctk

from vortexdl.core.models import DownloadStatus, DownloadTask


class TaskRow(ctk.CTkFrame):
    """One independently-updatable row in the download queue."""
    def __init__(self, master, task: DownloadTask, *, colors, translate,
                 on_cancel, on_pause, on_resume, on_show_folder):
        super().__init__(master, fg_color=colors["bg_card"], corner_radius=12,
                         border_width=1, border_color=colors["border"])
        self.colors = colors
        self._ = translate
        self.on_cancel = on_cancel
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_show_folder = on_show_folder
        self.task_id = task.task_id

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(9, 3))
        self.title_label = ctk.CTkLabel(
            top, text="", anchor="w", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=colors["text_primary"],
        )
        self.title_label.pack(side="left", fill="x", expand=True)
        self.status_badge = ctk.CTkLabel(
            top, text="", width=100, height=24, corner_radius=8,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.status_badge.pack(side="right", padx=(8, 0))

        self.details_label = ctk.CTkLabel(
            self, text="", anchor="w", font=ctk.CTkFont(size=10),
            text_color=colors["text_muted"],
        )
        self.details_label.pack(fill="x", padx=12, pady=(0, 5))

        progress_row = ctk.CTkFrame(self, fg_color="transparent")
        progress_row.pack(fill="x", padx=12, pady=(0, 2))
        self.progress_bar = ctk.CTkProgressBar(
            progress_row, height=10, corner_radius=6,
            progress_color=colors["accent"], fg_color=colors["bg_primary"],
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.percent_label = ctk.CTkLabel(
            progress_row, text="0%", width=48,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=colors["accent"],
        )
        self.percent_label.pack(side="right")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(2, 9))
        self.rate_label = ctk.CTkLabel(
            bottom, text="", anchor="w", font=ctk.CTkFont(size=10),
            text_color=colors["text_muted"],
        )
        self.rate_label.pack(side="left", fill="x", expand=True)
        self.folder_button = ctk.CTkButton(
            bottom, text=self._("Open Folder"), width=100, height=26,
            fg_color=colors["bg_secondary"], hover_color=colors["accent_hover"],
            command=lambda: self.on_show_folder(self._current.output_path),
        )
        self.folder_button.pack(side="right", padx=(5, 0))
        self.cancel_button = ctk.CTkButton(
            bottom, text=self._("Cancel"), width=72, height=26,
            fg_color=colors["danger"], hover_color="#b30000",
            command=lambda: self.on_cancel(self.task_id),
        )
        self.cancel_button.pack(side="right", padx=(5, 0))
        self.pause_button = ctk.CTkButton(
            bottom, text=self._("Pause"), width=72, height=26,
            fg_color=colors["warning"], hover_color=colors["accent_hover"],
            command=lambda: self.on_pause(self.task_id),
        )
        self.pause_button.pack(side="right", padx=(5, 0))
        self.update_task(task)

    def update_task(self, task: DownloadTask) -> None:
        self._current = task
        self.title_label.configure(text=task.title or task.url)
        fmt = self._("Audio Only (MP3)") if task.media_format == "audio" else self._("Video (MP4)")
        quality = self._("Best Quality") if task.quality in ("best", "Best Quality") else task.quality
        self.details_label.configure(text=f"{fmt} · {quality}")
        self.progress_bar.set(max(0.0, min(1.0, task.progress / 100.0)))
        self.percent_label.configure(text=f"{task.progress:.1f}%")
        eta = task.eta or "—"
        rate = task.speed if task.speed else "0.00 MiB/s"
        self.rate_label.configure(text=f"{rate}   ·   ETA {eta}")

        labels = {
            DownloadStatus.QUEUED: (self._("Waiting"), self.colors["warning"]),
            DownloadStatus.DOWNLOADING: (self._("Downloading..."), self.colors["accent"]),
            DownloadStatus.PAUSED: (self._("Paused"), self.colors["warning"]),
            DownloadStatus.COMPLETED: (self._("Completed"), self.colors["success"]),
            DownloadStatus.FAILED: (self._("Error occurred"), self.colors["danger"]),
            DownloadStatus.CANCELLED: (self._("Cancelled"), self.colors["text_muted"]),
        }
        label, color = labels.get(task.status, (task.status.value, self.colors["text_muted"]))
        self.status_badge.configure(text=label, fg_color=color, text_color="#ffffff")

        active = task.status in (DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED)
        queued = task.status == DownloadStatus.QUEUED
        if task.status == DownloadStatus.PAUSED:
            self.pause_button.configure(text=self._("Resume"), command=lambda: self.on_resume(self.task_id))
            self.pause_button.pack(side="right", padx=(5, 0))
        elif task.status == DownloadStatus.DOWNLOADING:
            self.pause_button.configure(text=self._("Pause"), command=lambda: self.on_pause(self.task_id))
            self.pause_button.pack(side="right", padx=(5, 0))
        else:
            self.pause_button.pack_forget()
        if active or queued:
            self.cancel_button.pack(side="right", padx=(5, 0))
        else:
            self.cancel_button.pack_forget()
        self.folder_button.configure(state="normal" if task.output_path else "disabled")


class QueueView(ctk.CTkScrollableFrame):
    """Scrollable queue that updates only the row matching each task id."""
    def __init__(self, master, *, colors, translate, on_cancel, on_pause, on_resume, on_show_folder, **kwargs):
        super().__init__(master, label_text=translate("Download Queue"),
                         fg_color=colors["bg_secondary"], corner_radius=14,
                         border_width=1, border_color=colors["border"], **kwargs)
        self.colors = colors
        self._ = translate
        self.on_cancel = on_cancel
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_show_folder = on_show_folder
        self.rows: dict[str, TaskRow] = {}
        self.empty_label = ctk.CTkLabel(
            self, text=translate("No downloads yet."),
            text_color=colors["text_muted"],
        )
        self.empty_label.pack(pady=24)

    def upsert(self, task: DownloadTask) -> None:
        row = self.rows.get(task.task_id)
        if row is None:
            if self.empty_label.winfo_exists():
                self.empty_label.pack_forget()
            row = TaskRow(
                self, task, colors=self.colors, translate=self._,
                on_cancel=self.on_cancel, on_pause=self.on_pause,
                on_resume=self.on_resume, on_show_folder=self.on_show_folder,
            )
            self.rows[task.task_id] = row
            row.pack(fill="x", padx=5, pady=5)
        else:
            row.update_task(task)
