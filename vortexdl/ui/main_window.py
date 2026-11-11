"""
VortexDL - Ultimate Modern Cross-Platform Video Downloader
Version: 3.0.0
Powered by yt-dlp + CustomTkinter + ffmpeg + aria2c + SQLite
"""

import customtkinter as ctk
import threading
import os
import sys
import re
import shutil
import locale
import gettext
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox
import queue

from vortexdl.core.models import DownloadStatus
from vortexdl.services.download_service import DownloadQueueService
from vortexdl.services.metadata_service import MetadataService, VideoMetadata
from vortexdl.services.category_service import CategoryRoutingService
from vortexdl.ui.settings_view import SmartCategoriesSettingsView
from vortexdl.services.clipboard_service import ClipboardMonitorService
from vortexdl.ui.queue_view import QueueView
from vortexdl.ui.preview_dialog import PreviewDialog
from vortexdl.ui.tray_manager import TrayManager
from vortexdl.ui.glass_theme import THEME_CONFIGS, RADIUS
from vortexdl.services.sound_service import SoundService
from vortexdl.ui.slide_toast import SlideToast
from vortexdl.services.optimizer_service import SystemOptimizer
from vortexdl.services.auto_updater import AutoUpdater as GitAutoUpdater

from storage import load_settings, save_settings
from vortexdl.storage.database import (
    get_history_entries, clear_all_history, delete_history_entry
)
from updater import AutoUpdater, CURRENT_VERSION

# --- App Directories & Locales ---
APP_DIR = Path(__file__).resolve().parents[2]
LOCALES_DIR = APP_DIR / "locales"
ASSETS_DIR = APP_DIR / "assets"

def get_system_language():
    try:
        sys_loc = locale.getdefaultlocale()[0]
        if sys_loc:
            prefix = sys_loc.lower()[:2]
            mapping = {
                "tr": "tr_TR", "en": "en_US", "de": "de_DE",
                "fr": "fr_FR", "it": "it_IT", "ar": "ar_SA", "zh": "zh_CN"
            }
            if prefix in mapping:
                return mapping[prefix]
    except Exception:
        pass
    return "en_US"

USER_SETTINGS = load_settings()
CURRENT_LANG = USER_SETTINGS.get("language") or get_system_language()

def setup_translation(lang_code):
    global _
    try:
        t = gettext.translation(
            domain="videodownloader",
            localedir=str(LOCALES_DIR),
            languages=[lang_code],
            fallback=True
        )
        t.install()
        _ = t.gettext
    except Exception:
        def _(text): return text
    return _

setup_translation(CURRENT_LANG)


# --- Cupertino glass palette ---
active_mode = USER_SETTINGS.get("theme", "Dark").lower()
if active_mode not in ["dark", "light"]:
    active_mode = "dark"
ctk.set_appearance_mode(active_mode)
COLORS = THEME_CONFIGS[active_mode]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class VortexDLApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = USER_SETTINGS
        self.download_service = DownloadQueueService(
            max_workers=3,
            global_speed_limit=self.settings.get("global_speed_limit", 0),
        )
        self.metadata_service = MetadataService()
        self.category_service = CategoryRoutingService()
        self._download_dir_manually_selected = False
        self._metadata_request_id = None
        self._pending_metadata_defaults = ("best", "video")
        self._active_task_id = None
        self._closing = False
        self.sound_service = SoundService(self.settings.get('enable_sound_effects', True))
        self.optimizer = SystemOptimizer(
            APP_DIR,
            download_dirs=(
                self.settings.get("default_folder") or str(Path.home() / "Downloads"),
            ),
        )
        self.tray_manager = TrayManager(ASSETS_DIR, translate=_)
        self._clipboard_toast = None
        self.clipboard_service = ClipboardMonitorService(
            self, self._show_clipboard_toast, poll_interval_ms=1000
        )

        self.current_lang = CURRENT_LANG
        self.title("⚡ VortexDL v3.0.0 — Ultimate Video Downloader")
        self.geometry("880x730")
        self.minsize(780, 640)
        self.configure(fg_color=COLORS["bg_primary"])

        # Set Icon
        for ext in ["png", "ico"]:
            icon_p = ASSETS_DIR / f"icon.{ext}"
            if icon_p.exists():
                try:
                    self.iconbitmap(str(icon_p))
                    break
                except Exception:
                    pass

        # aria2c detection
        self.aria2_path = shutil.which("aria2c")
        self.has_aria2 = self.aria2_path is not None

        # Download directory
        self.download_dir = self.settings.get("default_folder") or str(Path.home() / "Downloads")

        # State flags
        self._is_downloading = False
        self._cancel_flag = False
        self._active_tab = "downloader"

        self._build_ui()
        # Initialize detached tray integration before Tk enters mainloop.
        self.tray_manager.start()
        if self.settings.get("clipboard_monitoring", False):
            self.clipboard_service.start()
        self.after(100, self._drain_download_events)
        self.after(100, self._drain_metadata_results)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Run the release notice and guarded source updater asynchronously.
        self.updater = AutoUpdater(callback_on_update=self._notify_new_update)
        if not self.settings.get("disable_telemetry", False):
            self.updater.check_for_updates_async()
        self.optimizer.cleanup_async()
        self.auto_updater = GitAutoUpdater(
            APP_DIR,
            status_callback=lambda message: self.after(
                0, self._handle_updater_status, message
            ),
            safe_to_update=lambda: (
                not self._closing and all(
                    task.status in (
                        DownloadStatus.COMPLETED, DownloadStatus.FAILED,
                        DownloadStatus.CANCELLED,
                    )
                    for task in self.download_service.list_tasks()
                )
            ),
        )
        if self.settings.get("auto_update_enabled", True):
            self.auto_updater.check_and_apply_async()

    def _build_ui(self):
        # --- Top Navigation Bar ---
        self.header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0, height=75)
        self.header.pack(fill="x", padx=0, pady=0)
        self.header.pack_propagate(False)

        # Brand / Logo
        brand_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        brand_frame.pack(side="left", padx=24, pady=12)

        self.logo_lbl = ctk.CTkLabel(
            brand_frame,
            text="⚡ VortexDL",
            font=ctk.CTkFont(family="Helvetica", size=24, weight="bold"),
            text_color=COLORS["accent"],
        )
        self.logo_lbl.pack(anchor="w")

        sub_info = f"v{CURRENT_VERSION} · yt-dlp"
        if self.has_aria2:
            sub_info += " · ⚡ aria2c"
        self.sub_lbl = ctk.CTkLabel(
            brand_frame,
            text=sub_info,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["success"] if self.has_aria2 else COLORS["text_muted"],
        )
        self.sub_lbl.pack(anchor="w")

        # Navigation Tabs (Downloader, History, Settings)
        nav_box = ctk.CTkFrame(self.header, fg_color="transparent")
        nav_box.pack(side="left", padx=30, pady=16)

        self.nav_down_btn = ctk.CTkButton(
            nav_box, text=f"📥  {_('Download')}", width=115, height=36, corner_radius=RADIUS["pill"],
            fg_color=COLORS["tab_active"], text_color=COLORS["accent"], font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._switch_tab("downloader")
        )
        self.nav_down_btn.pack(side="left", padx=4)

        self.nav_hist_btn = ctk.CTkButton(
            nav_box, text=f"📜  {_('History')}", width=110, height=36, corner_radius=RADIUS["pill"],
            fg_color="transparent", text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._switch_tab("history")
        )
        self.nav_hist_btn.pack(side="left", padx=4)

        self.nav_set_btn = ctk.CTkButton(
            nav_box, text=f"⚙️  {_('Settings')}", width=110, height=36, corner_radius=RADIUS["pill"],
            fg_color="transparent", text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._switch_tab("settings")
        )
        self.nav_set_btn.pack(side="left", padx=4)

        # Update Alert Notification Button (hidden by default)
        self.update_btn = ctk.CTkButton(
            self.header, text=f"🚀 {_('Update Available')}", height=32, corner_radius=RADIUS["control"],
            fg_color=COLORS["accent_purple"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"), command=self._on_update_clicked
        )

        # Quick Language Selector on Top Right
        self.lang_var = ctk.StringVar(value=self._get_lang_display(self.current_lang))
        self.lang_menu = ctk.CTkOptionMenu(
            self.header,
            values=["Türkçe", "English", "Deutsch", "Français", "Italiano", "العربية", "中文"],
            variable=self.lang_var, width=105, height=32, corner_radius=RADIUS["control"],
            fg_color=COLORS["bg_card"], button_color=COLORS["bg_card"], button_hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11), command=self._on_language_select
        )
        self.lang_menu.pack(side="right", padx=20, pady=18)

        # --- Main Dynamic Body Frame ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=24, pady=16)

        # Initial Tab
        self._render_downloader_view()

    def _switch_tab(self, tab_name):
        if self._active_tab == tab_name:
            return
        self._active_tab = tab_name

        # Update button visual states
        tabs = {
            "downloader": self.nav_down_btn,
            "history": self.nav_hist_btn,
            "settings": self.nav_set_btn
        }
        for name, btn in tabs.items():
            if name == tab_name:
                btn.configure(fg_color=COLORS["tab_active"], text_color=COLORS["accent"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_muted"])

        # Animated Fade Transition (destroy and rebuild)
        for widget in self.main_container.winfo_children():
            widget.destroy()

        if tab_name == "downloader":
            self._render_downloader_view()
        elif tab_name == "history":
            self._render_history_view()
        elif tab_name == "settings":
            self._render_settings_view()

    # =========================================================================
    # VIEW 1: DOWNLOADER
    # =========================================================================
    def _render_downloader_view(self):
        # 1. URL Entry Card
        url_card = self._create_card(self.main_container, f"🔗  {_('Video URL')}")
        self.url_entry = ctk.CTkEntry(
            url_card,
            placeholder_text=_("Paste URL here (YouTube, Instagram, TikTok, Twitter...)"),
            font=ctk.CTkFont(size=13), height=46, corner_radius=RADIUS["control"],
            border_color=COLORS["border"], fg_color=COLORS["bg_primary"], text_color=COLORS["text_primary"]
        )
        self.url_entry.pack(fill="x", padx=18, pady=(4, 12))

        btn_row = ctk.CTkFrame(url_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkButton(
            btn_row, text=f"📋  {_('Paste')}", width=115, height=34, corner_radius=RADIUS["control"],
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=12, weight="bold"), command=self._paste_url
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text=f"✖  {_('Clear')}", width=100, height=34, corner_radius=RADIUS["control"],
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=12), command=lambda: self.url_entry.delete(0, "end")
        ).pack(side="left")

        # 2. Config Row (Format, Quality, Directory)
        cfg_card = self._create_card(self.main_container, f"⚙️  {_('Format')} & {_('Quality')}")
        cfg_row = ctk.CTkFrame(cfg_card, fg_color="transparent")
        cfg_row.pack(fill="x", padx=18, pady=(4, 12))

        # Format
        fmt_frame = ctk.CTkFrame(cfg_row, fg_color="transparent")
        fmt_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(fmt_frame, text=_("Format"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12)).pack(anchor="w")

        self.format_var = ctk.StringVar(value=_("Video (MP4)"))
        self.format_menu = ctk.CTkOptionMenu(
            fmt_frame, values=[_("Video (MP4)"), _("Audio Only (MP3)")],
            variable=self.format_var, corner_radius=12,
            fg_color=COLORS["bg_card"], button_color=COLORS["bg_card"], button_hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=12), command=self._on_format_change
        )
        self.format_menu.pack(fill="x", pady=(4, 0))

        # Quality
        qual_frame = ctk.CTkFrame(cfg_row, fg_color="transparent")
        qual_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkLabel(qual_frame, text=_("Quality"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12)).pack(anchor="w")

        def_qual = self.settings.get("default_quality", "Best Quality")
        self.quality_var = ctk.StringVar(value=def_qual)
        self.quality_menu = ctk.CTkOptionMenu(
            qual_frame, values=[_("Best Quality"), "1080p", "720p", "480p", "360p"],
            variable=self.quality_var, corner_radius=12,
            fg_color=COLORS["bg_card"], button_color=COLORS["bg_card"], button_hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=12)
        )
        self.quality_menu.pack(fill="x", pady=(4, 0))

        # Directory
        dir_frame = ctk.CTkFrame(cfg_row, fg_color="transparent")
        dir_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(dir_frame, text=_("Save Folder"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12)).pack(anchor="w")

        dir_sub = ctk.CTkFrame(dir_frame, fg_color="transparent")
        dir_sub.pack(fill="x", pady=(4, 0))
        self.dir_label = ctk.CTkLabel(
            dir_sub, text=self._short_path(self.download_dir),
            text_color=COLORS["accent"], font=ctk.CTkFont(size=11), anchor="w"
        )
        self.dir_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            dir_sub, text="📁", width=36, height=32, corner_radius=RADIUS["control"],
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"], command=self._choose_dir
        ).pack(side="right")

        # 3. Concurrent download queue
        queue_card = self._create_card(
            self.main_container, f"📥  {_('Download Queue')}", expand=True
        )
        queue_inner = ctk.CTkFrame(queue_card, fg_color="transparent")
        queue_inner.pack(fill="both", expand=True, padx=18, pady=(4, 10))

        self.download_btn = ctk.CTkButton(
            queue_inner, text=f"⬇  {_('Download')}", height=42, corner_radius=RADIUS["control"],
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent_purple"], hover_color=COLORS["accent_hover"],
            text_color="#ffffff", command=self._start_download
        )
        self.download_btn.pack(fill="x", pady=(0, 8))
        if self._metadata_request_id:
            self.download_btn.configure(
                state="disabled", text=f"🔎  {_('Loading...')}"
            )

        self.status_label = ctk.CTkLabel(
            queue_inner, text=_("Ready"), font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"], anchor="w"
        )
        self.status_label.pack(fill="x", pady=(0, 6))

        self.queue_view = QueueView(
            queue_inner, colors=COLORS, translate=_,
            on_cancel=self._cancel_task,
            on_pause=self._pause_task,
            on_resume=self._resume_task,
            on_show_folder=self._open_file_folder,
            height=250,
        )
        self.queue_view.pack(fill="both", expand=True, pady=(0, 8))
        for task in self.download_service.list_tasks():
            self.queue_view.upsert(task)

        summary = ctk.CTkFrame(
            queue_inner, fg_color=COLORS["bg_card"], corner_radius=RADIUS["control"]
        )
        summary.pack(fill="x")
        self.active_count_label = ctk.CTkLabel(
            summary, text="", anchor="w", font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        )
        self.active_count_label.pack(side="left", padx=12, pady=7)
        speed_limit_frame = ctk.CTkFrame(summary, fg_color="transparent")
        speed_limit_frame.pack(side="left", padx=10, pady=4)
        ctk.CTkLabel(
            speed_limit_frame, text=_("Speed Limit"),
            text_color=COLORS["text_muted"], font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(0, 6))
        self._speed_limit_choices = {
            _("Unlimited"): 0,
            "512 KB/s": 512 * 1024,
            "1 MB/s": 1024 * 1024,
            "2 MB/s": 2 * 1024 * 1024,
            "5 MB/s": 5 * 1024 * 1024,
        }
        saved_limit = self.download_service.global_speed_limit
        initial_choice = next(
            (label for label, value in self._speed_limit_choices.items()
             if value == saved_limit),
            _("Unlimited"),
        )
        self.speed_limit_var = ctk.StringVar(value=initial_choice)
        self.speed_limit_menu = ctk.CTkOptionMenu(
            speed_limit_frame,
            values=list(self._speed_limit_choices),
            variable=self.speed_limit_var,
            width=125, height=28, corner_radius=RADIUS["control"],
            fg_color=COLORS["bg_secondary"], button_color=COLORS["bg_secondary"],
            button_hover_color=COLORS["bg_hover"],
            font=ctk.CTkFont(size=11),
            command=self._on_speed_limit_change,
        )
        self.speed_limit_menu.pack(side="left")
        self.bandwidth_label = ctk.CTkLabel(
            summary, text="", anchor="e", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["accent"],
        )
        self.bandwidth_label.pack(side="right", padx=12, pady=7)
        self._update_queue_summary()

        # 4. Logs Box (Collapsible / Clean)
        log_card = self._create_card(self.main_container, f"📋  {_('Log')}", expand=False)
        self.log_box = ctk.CTkTextbox(
            log_card, font=ctk.CTkFont(family="Monospace", size=11),
            fg_color=COLORS["bg_primary"], text_color=COLORS["text_muted"],
            wrap="word", state="disabled", corner_radius=12, height=90
        )
        self.log_box.pack(fill="both", expand=True, padx=18, pady=(4, 12))

    # =========================================================================
    # VIEW 2: DOWNLOAD HISTORY (SQLite)
    # =========================================================================
    def _render_history_view(self):
        hist_header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        hist_header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            hist_header, text=f"📜 {_('History')}",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["text_primary"]
        ).pack(side="left")

        ctk.CTkButton(
            hist_header, text=f"🗑️ {_('Clear History')}", height=32, corner_radius=RADIUS["control"],
            fg_color=COLORS["danger"], hover_color=COLORS["danger"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self._clear_history_action
        ).pack(side="right")

        # Scrollable list for downloads
        scroll = ctk.CTkScrollableFrame(
            self.main_container, fg_color=COLORS["bg_secondary"],
            corner_radius=RADIUS["panel"], border_width=1, border_color=COLORS["border"]
        )
        scroll.pack(fill="both", expand=True)

        entries = get_history_entries(limit=100)
        if not entries:
            ctk.CTkLabel(
                scroll, text=f"✨ {_('No downloads yet.')}",
                font=ctk.CTkFont(size=14), text_color=COLORS["text_muted"]
            ).pack(pady=60)
            return

        for row in entries:
            eid, title, url, fmt, qual, fpath, fsize, ts = row
            item = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"], corner_radius=RADIUS["panel"] )
            item.pack(fill="x", padx=12, pady=6)

            info_box = ctk.CTkFrame(item, fg_color="transparent")
            info_box.pack(side="left", fill="both", expand=True, padx=14, pady=10)

            t_lbl = ctk.CTkLabel(
                info_box, text=title or "Unknown Title",
                font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"], anchor="w"
            )
            t_lbl.pack(fill="x")

            sub_txt = f"{ts} · {fmt} · {qual}"
            if fsize:
                sub_txt += f" · {fsize}"
            ctk.CTkLabel(
                info_box, text=sub_txt,
                font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"], anchor="w"
            ).pack(fill="x")

            act_box = ctk.CTkFrame(item, fg_color="transparent")
            act_box.pack(side="right", padx=12, pady=10)

            ctk.CTkButton(
                act_box, text="📁", width=36, height=32, corner_radius=RADIUS["control"],
                fg_color=COLORS["bg_secondary"], hover_color=COLORS["bg_hover"],
                command=lambda p=fpath: self._open_file_folder(p)
            ).pack(side="left", padx=4)

            ctk.CTkButton(
                act_box, text="❌", width=36, height=32, corner_radius=RADIUS["control"],
                fg_color=COLORS["bg_secondary"], hover_color=COLORS["danger"],
                command=lambda i=eid: self._delete_history_item(i)
            ).pack(side="left", padx=4)

    # =========================================================================
    # VIEW 3: SETTINGS & PRIVACY (Obfuscated JSON)
    # =========================================================================
    def _render_settings_view(self):
        settings_content = ctk.CTkScrollableFrame(
            self.main_container, fg_color="transparent"
        )
        settings_content.pack(fill="both", expand=True)
        card = self._create_card(settings_content, f"⚙️  {_('Settings')} & {_('Theme')}")

        # Default Quality
        q_frame = ctk.CTkFrame(card, fg_color="transparent")
        q_frame.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(q_frame, text=_("Default Quality"), text_color=COLORS["text_primary"], font=ctk.CTkFont(size=13)).pack(side="left")
        self.set_qual_menu = ctk.CTkOptionMenu(
            q_frame, values=["Best Quality", "1080p", "720p", "480p", "360p"],
            corner_radius=12, fg_color=COLORS["bg_card"], button_color=COLORS["bg_card"]
        )
        self.set_qual_menu.set(self.settings.get("default_quality", "Best Quality"))
        self.set_qual_menu.pack(side="right")

        # Theme Switch
        t_frame = ctk.CTkFrame(card, fg_color="transparent")
        t_frame.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(t_frame, text=_("Theme"), text_color=COLORS["text_primary"], font=ctk.CTkFont(size=13)).pack(side="left")
        self.set_theme_menu = ctk.CTkOptionMenu(
            t_frame, values=[_("Dark"), _("Light")],
            corner_radius=12, fg_color=COLORS["bg_card"], button_color=COLORS["bg_card"]
        )
        self.set_theme_menu.set(_("Dark") if self.settings.get("theme", "Dark").lower() == "dark" else _("Light"))
        self.set_theme_menu.pack(side="right")

        # Telemetry / Privacy Mode
        p_frame = ctk.CTkFrame(card, fg_color="transparent")
        p_frame.pack(fill="x", padx=20, pady=12)
        self.telem_var = ctk.BooleanVar(value=self.settings.get("disable_telemetry", True))
        ctk.CTkSwitch(
            p_frame, text=f"🛡️  {_('Disable Telemetry (Privacy Mode)')}",
            variable=self.telem_var, font=ctk.CTkFont(size=13),
            progress_color=COLORS["accent"]
        ).pack(side="left")

        # Close-to-tray preference
        tray_frame = ctk.CTkFrame(card, fg_color="transparent")
        tray_frame.pack(fill="x", padx=20, pady=(4, 12))
        self.minimize_to_tray_var = ctk.BooleanVar(
            value=bool(self.settings.get("minimize_to_tray", True))
        )
        ctk.CTkSwitch(
            tray_frame, text=f"🧺  {_('Minimize to tray on close')}",
            variable=self.minimize_to_tray_var, font=ctk.CTkFont(size=13),
            progress_color=COLORS["accent"]
        ).pack(side="left")

        # Automatic updates and conservative cleanup
        updater_frame = ctk.CTkFrame(card, fg_color="transparent")
        updater_frame.pack(fill="x", padx=20, pady=8)
        self.auto_update_var = ctk.BooleanVar(
            value=bool(self.settings.get("auto_update_enabled", True))
        )
        ctk.CTkSwitch(
            updater_frame, text=f"🔄  {_('Auto-Update & Clean')}",
            variable=self.auto_update_var, font=ctk.CTkFont(size=13),
            progress_color=COLORS["accent"],
        ).pack(side="left")
        self.optimize_now_button = ctk.CTkButton(
            card, text=_("Optimize and Update Now"), height=34,
            corner_radius=RADIUS["control"], fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_hover"], command=self._optimize_and_update_now,
        )
        self.optimize_now_button.pack(fill="x", padx=20, pady=(0, 10))

        # Optional UI sound effects
        sound_frame = ctk.CTkFrame(card, fg_color="transparent")
        sound_frame.pack(fill="x", padx=20, pady=8)
        self.sound_effects_var = ctk.BooleanVar(
            value=bool(self.settings.get("enable_sound_effects", True))
        )
        ctk.CTkSwitch(
            sound_frame, text=f"🔊  {_('Enable Sound Effects')}",
            variable=self.sound_effects_var, font=ctk.CTkFont(size=13),
            progress_color=COLORS["accent"],
        ).pack(side="left")

        # Clipboard monitoring (opt-in; clipboard contents are never persisted)
        cb_frame = ctk.CTkFrame(card, fg_color="transparent")
        cb_frame.pack(fill="x", padx=20, pady=8)
        self.clipboard_monitor_var = ctk.BooleanVar(
            value=bool(self.settings.get("clipboard_monitoring", False))
        )
        ctk.CTkSwitch(
            cb_frame, text=f"📋  {_('Enable Clipboard Monitoring')}",
            variable=self.clipboard_monitor_var,
            command=self._apply_clipboard_monitor_setting,
            font=ctk.CTkFont(size=13), progress_color=COLORS["accent"]
        ).pack(side="left")

        self.smart_categories_view = SmartCategoriesSettingsView(
            settings_content, settings=self.settings, colors=COLORS, translate=_
        )
        self.smart_categories_view.pack(fill="x", pady=(0, 12))

        # Cloud Sync API Keys (User-Configurable)
        cloud_card = self._create_card(settings_content, f"☁️  {_('Cloud Sync / Storage')}")
        
        g_row = ctk.CTkFrame(cloud_card, fg_color="transparent")
        g_row.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(g_row, text=_("Google Drive API Key"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.gdrive_entry = ctk.CTkEntry(
            g_row, placeholder_text="Enter custom API key/token...", show="•",
            corner_radius=RADIUS["control"], fg_color=COLORS["bg_primary"], text_color=COLORS["text_primary"]
        )
        self.gdrive_entry.pack(fill="x", pady=(2, 0))
        if self.settings.get("gdrive_api_key"):
            self.gdrive_entry.insert(0, self.settings["gdrive_api_key"])

        o_row = ctk.CTkFrame(cloud_card, fg_color="transparent")
        o_row.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(o_row, text=_("OneDrive API Key"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.onedrive_entry = ctk.CTkEntry(
            o_row, placeholder_text="Enter custom OneDrive token...", show="•",
            corner_radius=RADIUS["control"], fg_color=COLORS["bg_primary"], text_color=COLORS["text_primary"]
        )
        self.onedrive_entry.pack(fill="x", pady=(2, 0))
        if self.settings.get("onedrive_api_key"):
            self.onedrive_entry.insert(0, self.settings["onedrive_api_key"])

        # Save Button
        ctk.CTkButton(
            settings_content, text=f"💾  {_('Save Settings')}", height=44, corner_radius=RADIUS["control"],
            fg_color=COLORS["accent_purple"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=14, weight="bold"), command=self._save_settings_action
        ).pack(fill="x", pady=10)

    # --- UI Helpers ---
    def _create_card(self, parent, title: str, expand: bool = False):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["bg_secondary"], corner_radius=RADIUS["panel"],
            border_width=1, border_color=COLORS["border"]
        )
        card.pack(fill="both", expand=expand, pady=(0, 12))
        lbl = ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        lbl.pack(fill="x", padx=18, pady=(12, 0))
        sep = ctk.CTkFrame(card, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=18, pady=(6, 0))
        return card

    def _get_lang_display(self, code):
        mapping = {
            "tr_TR": "Türkçe", "en_US": "English", "de_DE": "Deutsch",
            "fr_FR": "Français", "it_IT": "Italiano", "ar_SA": "العربية", "zh_CN": "中文"
        }
        return mapping.get(code, "English")

    def _on_language_select(self, choice):
        rev_map = {
            "Türkçe": "tr_TR", "English": "en_US", "Deutsch": "de_DE",
            "Français": "fr_FR", "Italiano": "it_IT", "العربية": "ar_SA", "中文": "zh_CN"
        }
        new_lang = rev_map.get(choice, "en_US")
        if new_lang != self.current_lang:
            self.current_lang = new_lang
            self.settings["language"] = new_lang
            save_settings(self.settings)
            setup_translation(new_lang)
            for widget in self.winfo_children():
                widget.destroy()
            self._build_ui()

    def _apply_clipboard_monitor_setting(self):
        """Persist the user's opt-in choice and start/stop Tk-safe polling."""
        enabled = bool(self.clipboard_monitor_var.get())
        self.settings["clipboard_monitoring"] = enabled
        save_settings(self.settings)
        if enabled:
            self.clipboard_service.start()
        else:
            self.clipboard_service.stop()
            self._close_clipboard_toast()

    def _close_clipboard_toast(self):
        toast = getattr(self, "_clipboard_toast", None)
        if toast is not None:
            self._clipboard_toast = None
            try:
                toast.close()
            except Exception:
                pass

    def _show_status_toast(self, icon, title, message):
        if self._closing:
            return
        self._close_clipboard_toast()
        try:
            toast = SlideToast(
                self, title=title, message=message, icon=icon, colors=COLORS,
                duration_ms=3500,
                on_close=lambda closed: setattr(self, "_clipboard_toast", None)
                if getattr(self, "_clipboard_toast", None) is closed else None,
            )
            self._clipboard_toast = toast
        except Exception:
            pass

    def _show_clipboard_toast(self, url):
        if self._closing or not self.settings.get("clipboard_monitoring", False):
            return
        self._close_clipboard_toast()
        self.sound_service.play_queued()

        def accept_url():
            if self._metadata_request_id:
                messagebox.showinfo(_("Please wait"), _("A preview is already loading."))
                return
            self._switch_tab("downloader")
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self._start_download()

        actions = [
            (_("Ignore"), self._close_clipboard_toast, False),
            (_("Download"), accept_url, True),
        ]
        try:
            self._clipboard_toast = SlideToast(
                self, title=_("Clipboard link detected"), message=url, icon="↗",
                colors=COLORS, actions=actions, duration_ms=0,
                on_close=lambda closed: setattr(self, "_clipboard_toast", None)
                if getattr(self, "_clipboard_toast", None) is closed else None,
            )
        except Exception:
            self._clipboard_toast = None

    def _save_settings_action(self):
        theme_ch = self.set_theme_menu.get()
        new_theme = "Light" if theme_ch in [_("Light"), "Light"] else "Dark"
        self.settings["default_quality"] = self.set_qual_menu.get()
        self.settings["theme"] = new_theme
        self.settings["disable_telemetry"] = self.telem_var.get()
        self.settings["clipboard_monitoring"] = self.clipboard_monitor_var.get()
        self.settings["gdrive_api_key"] = self.gdrive_entry.get().strip()
        self.settings["onedrive_api_key"] = self.onedrive_entry.get().strip()
        self.settings["minimize_to_tray"] = self.minimize_to_tray_var.get()
        self.settings["enable_sound_effects"] = self.sound_effects_var.get()
        self.settings["auto_update_enabled"] = self.auto_update_var.get()
        self.sound_service.set_enabled(self.settings["enable_sound_effects"])
        self.settings.update(self.smart_categories_view.get_values())
        save_settings(self.settings)

        global COLORS
        COLORS = THEME_CONFIGS[new_theme.lower()]
        ctk.set_appearance_mode(new_theme.lower())

        messagebox.showinfo(_("Settings"), _("Settings saved successfully!"))
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()

    def _handle_updater_status(self, message):
        if self._closing:
            return
        self._log(message)
        self._show_status_toast("↻", _("Auto-Update & Clean"), message)

    def _optimize_and_update_now(self):
        button = getattr(self, "optimize_now_button", None)
        if button is not None and button.winfo_exists():
            button.configure(state="disabled", text=_("Optimizing…"))
        self.optimizer.cleanup_async(
            callback=lambda result: self.after(0, self._finish_optimization, result)
        )

    def _finish_optimization(self, result):
        button = getattr(self, "optimize_now_button", None)
        if button is not None and button.winfo_exists():
            button.configure(state="normal", text=_("Optimize and Update Now"))
        self._handle_updater_status(
            _("Cleanup finished: %(caches)s caches and %(partials)s partial files removed.")
            % {
                "caches": result.get("cache_dirs", 0),
                "partials": result.get("partial_files", 0),
            }
        )
        self.auto_updater.check_and_apply_async(force=True)

    def _notify_new_update(self, version_tag, url):
        def show_btn():
            self.update_btn.configure(text=f"🚀 {_('New Version Available')}: {version_tag}")
            self.update_btn.pack(side="right", padx=12, pady=18)
        self.after(0, show_btn)

    def _on_update_clicked(self):
        self.updater.open_download_page()

    def _open_file_folder(self, filepath):
        if not filepath:
            return
        folder = os.path.dirname(filepath) if os.path.exists(filepath) else self.download_dir
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.run(["open", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)

    def _clear_history_action(self):
        clear_all_history()
        self._switch_tab("history")

    def _delete_history_item(self, entry_id):
        delete_history_entry(entry_id)
        self._switch_tab("history")

    def _paste_url(self):
        try:
            txt = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, txt.strip())
        except Exception:
            pass

    def _choose_dir(self):
        p = filedialog.askdirectory(initialdir=self.download_dir)
        if p:
            self.download_dir = p
            self._download_dir_manually_selected = True
            self.dir_label.configure(text=self._short_path(p))

    def _on_format_change(self, val):
        is_audio = val in [_("Audio Only (MP3)"), "Audio Only (MP3)", "Sadece Ses (MP3)"]
        self.quality_menu.configure(state="disabled" if is_audio else "normal")

    @staticmethod
    def _short_path(path: str, max_len: int = 24) -> str:
        return path if len(path) <= max_len else "…" + path[-(max_len - 1):]

    # --- Thread Safe Logging & State ---
    def _log(self, msg: str):
        self.after(0, self._append_log, strip_ansi(msg))

    def _append_log(self, msg: str):
        if hasattr(self, "log_box") and self.log_box.winfo_exists():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

    def _clear_log(self):
        if hasattr(self, "log_box") and self.log_box.winfo_exists():
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")

    def _on_speed_limit_change(self, selection):
        limit = self._speed_limit_choices.get(selection)
        if limit is None:
            return
        self.settings["global_speed_limit"] = limit
        save_settings(self.settings)
        self.download_service.set_global_speed_limit(limit)
        self._log(f"⚡ {_('Speed limit updated to: ')}{selection}")

    def _update_queue_summary(self):
        active = self.download_service.active_count
        speed = self.download_service.total_bandwidth_mib
        count_label = getattr(self, "active_count_label", None)
        speed_label = getattr(self, "bandwidth_label", None)
        if count_label is not None and count_label.winfo_exists():
            count_label.configure(text=f"{_('Active downloads')}: {active}")
        if speed_label is not None and speed_label.winfo_exists():
            speed_label.configure(text=f"{_('Total speed')}: {speed:.2f} MiB/s")

    def _set_queue_status(self, text, color=None):
        label = getattr(self, "status_label", None)
        if label is not None and label.winfo_exists():
            label.configure(text=text)
            if color:
                label.configure(text_color=color)

    def _cancel_task(self, task_id):
        if self.download_service.cancel(task_id):
            self._log(f"⚠  {_('Cancellation requested...')}")

    def _pause_task(self, task_id):
        self.download_service.pause(task_id)

    def _resume_task(self, task_id):
        self.download_service.resume(task_id)

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(_("Warning"), _("Please enter a valid URL!"))
            return
        if self._metadata_request_id:
            return

        selected_format = self.format_var.get()
        is_audio = selected_format in [
            _("Audio Only (MP3)"), "Audio Only (MP3)", "Sadece Ses (MP3)"
        ]
        selected_quality = self.quality_var.get()
        if selected_quality in [_("Best Quality"), "Best Quality", "En Yüksek"]:
            quality = "best"
        else:
            quality = selected_quality.replace("p", "")
        self._pending_metadata_defaults = (
            quality, "audio" if is_audio else "video"
        )

        try:
            self._metadata_request_id = self.metadata_service.fetch(url)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror(_("Error occurred"), str(exc))
            return

        if hasattr(self, "download_btn") and self.download_btn.winfo_exists():
            self.download_btn.configure(
                state="disabled", text=f"🔎  {_('Loading...')}"
            )
        self._set_queue_status(_("Inspecting connection..."), COLORS["accent"])
        self._log(f"🔎 {_('Inspecting link: ')}{url}")

    def _drain_metadata_results(self):
        if self._closing:
            return
        try:
            while True:
                result = self.metadata_service.results.get_nowait()
                if result.request_id != self._metadata_request_id:
                    continue
                self._metadata_request_id = None
                self._restore_download_button()
                if result.error:
                    self._set_queue_status(_("Error occurred"), COLORS["danger"])
                    messagebox.showerror(_("Preview failed"), result.error)
                    continue
                if result.metadata is not None:
                    self._set_queue_status(_("Preview ready"), COLORS["success"])
                    self._open_preview(result.metadata)
        except queue.Empty:
            pass
        self.after(100, self._drain_metadata_results)

    def _restore_download_button(self):
        button = getattr(self, "download_btn", None)
        if button is not None and button.winfo_exists():
            button.configure(state="normal", text=f"⬇  {_('Download')}")

    def _open_preview(self, metadata: VideoMetadata):
        quality, media_format = self._pending_metadata_defaults
        PreviewDialog(
            self,
            metadata,
            colors=COLORS,
            translate=_,
            default_quality=quality,
            default_media_format=media_format,
            on_add=lambda selected_quality, selected_format: self._queue_preview_download(
                metadata, selected_quality, selected_format
            ),
        )

    def _queue_preview_download(
        self, metadata: VideoMetadata, quality: str, media_format: str
    ) -> bool:
        try:
            output_dir = self.category_service.resolve_output_dir(
                url=metadata.url,
                title=metadata.title,
                media_format=media_format,
                available_formats=metadata.available_formats,
                default_folder=self.download_dir,
                manual_folder=(
                    self.download_dir if self._download_dir_manually_selected else ""
                ),
                settings=self.settings,
            )
            task = self.download_service.add(
                url=metadata.url,
                quality=quality,
                output_dir=output_dir,
                media_format=media_format,
                title=metadata.title,
            )
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror(_("Error occurred"), str(exc))
            return False

        entry = getattr(self, "url_entry", None)
        if entry is not None and entry.winfo_exists() and entry.get().strip() == metadata.url:
            entry.delete(0, "end")
        queue_view = getattr(self, "queue_view", None)
        if queue_view is not None and queue_view.winfo_exists():
            queue_view.upsert(task)
        self._set_queue_status(_("Waiting"), COLORS["warning"])
        self._update_queue_summary()
        self._log(f"📥 {_('Added to queue: ')}{metadata.title}")
        return True

    def _drain_download_events(self):
        if self._closing:
            return
        try:
            while True:
                event = self.download_service.events.get_nowait()
                if event.kind == "queued":
                    self.sound_service.play_queued()
                    self._show_status_toast("↓", _("Queued"), event.title or event.message)
                if event.status in (DownloadStatus.COMPLETED, DownloadStatus.CANCELLED):
                    self.optimizer.optimize_memory()
                if event.status == DownloadStatus.COMPLETED:
                    self.sound_service.play_completed()
                    self._show_status_toast("✓", _("Download Complete"), event.title or event.message)
                elif event.status == DownloadStatus.FAILED:
                    self.sound_service.play_error()
                    self._show_status_toast("!", _("Download Failed"), event.title or event.message)
                if event.kind == "retrying":
                    self._log(
                        _("Error. Retrying in %(seconds)s seconds... "
                          "(%(retry_count)s/%(max_retries)s)") % {
                            "seconds": int(event.retry_delay_seconds),
                            "retry_count": event.retry_count,
                            "max_retries": event.max_retries,
                        }
                    )
                elif event.message and event.kind != "progress":
                    self._log(event.message)
                task = self.download_service.get_task(event.task_id)
                queue_view = getattr(self, "queue_view", None)
                if task is not None and queue_view is not None and queue_view.winfo_exists():
                    queue_view.upsert(task)
                if event.status == DownloadStatus.QUEUED:
                    self._set_queue_status(_("Waiting"), COLORS["warning"])
                elif event.status == DownloadStatus.DOWNLOADING:
                    self._set_queue_status(_("Downloading..."), COLORS["accent"])
                elif event.status == DownloadStatus.PAUSED:
                    self._set_queue_status(_("Paused"), COLORS["warning"])
                elif event.status == DownloadStatus.RETRYING:
                    self._set_queue_status(
                        _("Retrying (%(retry_count)s/%(max_retries)s)") % {
                            "retry_count": event.retry_count,
                            "max_retries": event.max_retries,
                        },
                        COLORS["warning"],
                    )
                elif event.status == DownloadStatus.COMPLETED:
                    self._set_queue_status(_("Completed"), COLORS["success"])
                elif event.status == DownloadStatus.CANCELLED:
                    self._set_queue_status(_("Cancelled"), COLORS["warning"])
                elif event.status == DownloadStatus.FAILED:
                    self._set_queue_status(_("Error occurred"), COLORS["danger"])
                self._update_queue_summary()
        except queue.Empty:
            pass
        self.after(100, self._drain_download_events)

    def _on_close(self):
        if self._closing:
            return
        if self.settings.get("minimize_to_tray", True):
            if self.tray_manager.show():
                self.withdraw()
                self.after(100, self._drain_tray_events)
                return
            self._log(_("System tray could not be started; the window remains open."))
            return
        self._quit_app()

    def _drain_tray_events(self):
        if self._closing:
            return
        try:
            while True:
                event = self.tray_manager.events.get_nowait()
                action = event[0] if isinstance(event, tuple) else event
                if action == "show":
                    self.tray_manager.hide()
                    self.deiconify()
                    self.state("normal")
                    self.lift()
                    self.focus_force()
                elif action == "pause_all":
                    for task in self.download_service.list_tasks():
                        if task.status == DownloadStatus.DOWNLOADING:
                            self.download_service.pause(task.task_id)
                elif action == "quit":
                    self._quit_app()
                    return
                elif action == "error":
                    self.tray_manager.stop()
                    self.deiconify()
                    self.state("normal")
                    self.lift()
                    self._log(_("System tray could not be started; the window remains open."))
        except queue.Empty:
            pass
        if self.state() == "withdrawn" and self.tray_manager.is_running:
            self.after(200, self._drain_tray_events)

    def _quit_app(self):
        if self._closing:
            return
        self._closing = True
        self.tray_manager.stop()
        self.clipboard_service.stop()
        self._close_clipboard_toast()
        self.metadata_service.shutdown(wait=False)
        self.download_service.shutdown(wait=False)
        self.destroy()


def create_app():
    """Build the application window without starting the Tk event loop."""
    return VortexDLApp()


if __name__ == "__main__":
    app = create_app()
    app.mainloop()
