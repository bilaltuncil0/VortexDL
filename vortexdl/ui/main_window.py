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


# --- Premium Color Palettes ---
THEME_CONFIGS = {
    "dark": {
        "bg_primary":    "#0b0d19",
        "bg_secondary":  "#131629",
        "bg_card":       "#1b203a",
        "accent":        "#00f0ff",
        "accent_hover":  "#00b8c4",
        "accent_purple": "#7928ca",
        "text_primary":  "#ffffff",
        "text_muted":    "#8e97b8",
        "success":       "#00f5a0",
        "warning":       "#ff9f43",
        "danger":        "#ff3838",
        "progress_fg":   "#00f0ff",
        "border":        "#222847",
        "tab_active":    "#1f2648"
    },
    "light": {
        "bg_primary":    "#f7f9fc",
        "bg_secondary":  "#ffffff",
        "bg_card":       "#edf2f7",
        "accent":        "#0984e3",
        "accent_hover":  "#076bb8",
        "accent_purple": "#6c5ce7",
        "text_primary":  "#1e293b",
        "text_muted":    "#64748b",
        "success":       "#10b981",
        "warning":       "#f59e0b",
        "danger":        "#ef4444",
        "progress_fg":   "#0984e3",
        "border":        "#e2e8f0",
        "tab_active":    "#e2e8f0"
    }
}

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
        self.download_service = DownloadQueueService()
        self._active_task_id = None
        self._closing = False

        self.current_lang = CURRENT_LANG
        self.settings = USER_SETTINGS
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
        self.after(100, self._drain_download_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Run Auto-Updater asynchronously
        self.updater = AutoUpdater(callback_on_update=self._notify_new_update)
        if not self.settings.get("disable_telemetry", False):
            self.updater.check_for_updates_async()

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
            nav_box, text=f"📥  {_('Download')}", width=115, height=36, corner_radius=18,
            fg_color=COLORS["tab_active"], text_color=COLORS["accent"], font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._switch_tab("downloader")
        )
        self.nav_down_btn.pack(side="left", padx=4)

        self.nav_hist_btn = ctk.CTkButton(
            nav_box, text=f"📜  {_('History')}", width=110, height=36, corner_radius=18,
            fg_color="transparent", text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._switch_tab("history")
        )
        self.nav_hist_btn.pack(side="left", padx=4)

        self.nav_set_btn = ctk.CTkButton(
            nav_box, text=f"⚙️  {_('Settings')}", width=110, height=36, corner_radius=18,
            fg_color="transparent", text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._switch_tab("settings")
        )
        self.nav_set_btn.pack(side="left", padx=4)

        # Update Alert Notification Button (hidden by default)
        self.update_btn = ctk.CTkButton(
            self.header, text=f"🚀 {_('Update Available')}", height=32, corner_radius=16,
            fg_color=COLORS["accent_purple"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"), command=self._on_update_clicked
        )

        # Quick Language Selector on Top Right
        self.lang_var = ctk.StringVar(value=self._get_lang_display(self.current_lang))
        self.lang_menu = ctk.CTkOptionMenu(
            self.header,
            values=["Türkçe", "English", "Deutsch", "Français", "Italiano", "العربية", "中文"],
            variable=self.lang_var, width=105, height=32, corner_radius=16,
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
            font=ctk.CTkFont(size=13), height=46, corner_radius=14,
            border_color=COLORS["border"], fg_color=COLORS["bg_primary"], text_color=COLORS["text_primary"]
        )
        self.url_entry.pack(fill="x", padx=18, pady=(4, 12))

        btn_row = ctk.CTkFrame(url_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkButton(
            btn_row, text=f"📋  {_('Paste')}", width=115, height=34, corner_radius=17,
            fg_color=COLORS["bg_card"], hover_color=COLORS["accent_purple"],
            font=ctk.CTkFont(size=12, weight="bold"), command=self._paste_url
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text=f"✖  {_('Clear')}", width=100, height=34, corner_radius=17,
            fg_color=COLORS["bg_card"], hover_color="#444",
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
            fg_color=COLORS["bg_card"], button_color=COLORS["bg_card"], button_hover_color=COLORS["accent_purple"],
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
            fg_color=COLORS["bg_card"], button_color=COLORS["bg_card"], button_hover_color=COLORS["accent_purple"],
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
            dir_sub, text="📁", width=36, height=32, corner_radius=10,
            fg_color=COLORS["bg_card"], hover_color=COLORS["accent_purple"], command=self._choose_dir
        ).pack(side="right")

        # 3. Action / Progress Card
        prog_card = self._create_card(self.main_container, f"⚡  {_('Download')}")
        prog_inner = ctk.CTkFrame(prog_card, fg_color="transparent")
        prog_inner.pack(fill="x", padx=18, pady=(4, 12))

        self.download_btn = ctk.CTkButton(
            prog_inner, text=f"⬇  {_('Download')}", height=46, corner_radius=23,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["accent_purple"], hover_color=COLORS["accent"],
            text_color="#ffffff", command=self._start_download
        )
        self.download_btn.pack(fill="x", pady=(0, 10))

        bar_row = ctk.CTkFrame(prog_inner, fg_color="transparent")
        bar_row.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(
            bar_row, mode="determinate", height=16, corner_radius=8,
            progress_color=COLORS["accent"], fg_color=COLORS["bg_primary"]
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.progress_bar.set(0)

        self.percent_label = ctk.CTkLabel(
            bar_row, text="0%", width=50,
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["accent"]
        )
        self.percent_label.pack(side="right")

        self.status_label = ctk.CTkLabel(
            prog_inner, text=_("Ready"), font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"], anchor="w"
        )
        self.status_label.pack(fill="x", pady=(6, 0))

        # 4. Logs Box (Collapsible / Clean)
        log_card = self._create_card(self.main_container, f"📋  {_('Log')}", expand=True)
        self.log_box = ctk.CTkTextbox(
            log_card, font=ctk.CTkFont(family="Monospace", size=11),
            fg_color=COLORS["bg_primary"], text_color=COLORS["text_muted"],
            wrap="word", state="disabled", corner_radius=12
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
            hist_header, text=f"🗑️ {_('Clear History')}", height=32, corner_radius=16,
            fg_color=COLORS["danger"], hover_color="#b30000", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._clear_history_action
        ).pack(side="right")

        # Scrollable list for downloads
        scroll = ctk.CTkScrollableFrame(
            self.main_container, fg_color=COLORS["bg_secondary"],
            corner_radius=16, border_width=1, border_color=COLORS["border"]
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
            item = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"], corner_radius=14)
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
                act_box, text="📁", width=36, height=32, corner_radius=10,
                fg_color=COLORS["bg_secondary"], hover_color=COLORS["accent_purple"],
                command=lambda p=fpath: self._open_file_folder(p)
            ).pack(side="left", padx=4)

            ctk.CTkButton(
                act_box, text="❌", width=36, height=32, corner_radius=10,
                fg_color=COLORS["bg_secondary"], hover_color=COLORS["danger"],
                command=lambda i=eid: self._delete_history_item(i)
            ).pack(side="left", padx=4)

    # =========================================================================
    # VIEW 3: SETTINGS & PRIVACY (Obfuscated JSON)
    # =========================================================================
    def _render_settings_view(self):
        card = self._create_card(self.main_container, f"⚙️  {_('Settings')} & {_('Theme')}")

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

        # Cloud Sync API Keys (User-Configurable)
        cloud_card = self._create_card(self.main_container, f"☁️  {_('Cloud Sync / Storage')}")
        
        g_row = ctk.CTkFrame(cloud_card, fg_color="transparent")
        g_row.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(g_row, text=_("Google Drive API Key"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.gdrive_entry = ctk.CTkEntry(
            g_row, placeholder_text="Enter custom API key/token...", show="•",
            corner_radius=10, fg_color=COLORS["bg_primary"], text_color=COLORS["text_primary"]
        )
        self.gdrive_entry.pack(fill="x", pady=(2, 0))
        if self.settings.get("gdrive_api_key"):
            self.gdrive_entry.insert(0, self.settings["gdrive_api_key"])

        o_row = ctk.CTkFrame(cloud_card, fg_color="transparent")
        o_row.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(o_row, text=_("OneDrive API Key"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.onedrive_entry = ctk.CTkEntry(
            o_row, placeholder_text="Enter custom OneDrive token...", show="•",
            corner_radius=10, fg_color=COLORS["bg_primary"], text_color=COLORS["text_primary"]
        )
        self.onedrive_entry.pack(fill="x", pady=(2, 0))
        if self.settings.get("onedrive_api_key"):
            self.onedrive_entry.insert(0, self.settings["onedrive_api_key"])

        # Save Button
        ctk.CTkButton(
            self.main_container, text=f"💾  {_('Save Settings')}", height=44, corner_radius=22,
            fg_color=COLORS["accent_purple"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=14, weight="bold"), command=self._save_settings_action
        ).pack(fill="x", pady=10)

    # --- UI Helpers ---
    def _create_card(self, parent, title: str, expand: bool = False):
        card = ctk.CTkFrame(
            parent, fg_color=COLORS["bg_secondary"], corner_radius=18,
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

    def _save_settings_action(self):
        theme_ch = self.set_theme_menu.get()
        new_theme = "Light" if theme_ch in [_("Light"), "Light"] else "Dark"
        self.settings["default_quality"] = self.set_qual_menu.get()
        self.settings["theme"] = new_theme
        self.settings["disable_telemetry"] = self.telem_var.get()
        self.settings["gdrive_api_key"] = self.gdrive_entry.get().strip()
        self.settings["onedrive_api_key"] = self.onedrive_entry.get().strip()
        save_settings(self.settings)

        global COLORS
        COLORS = THEME_CONFIGS[new_theme.lower()]
        ctk.set_appearance_mode(new_theme.lower())

        messagebox.showinfo(_("Settings"), _("Settings saved successfully!"))
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()

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

    def _set_progress(self, val: float, pct_text: str, status: str):
        self.after(0, self._update_prog, val, pct_text, status)

    def _update_prog(self, val: float, pct_text: str, status: str):
        if hasattr(self, "progress_bar") and self.progress_bar.winfo_exists():
            self.progress_bar.set(val)
            self.percent_label.configure(text=pct_text)
            self.status_label.configure(text=status)

    def _set_downloading_state(self, is_down: bool):
        self._is_downloading = is_down
        self.after(0, self._toggle_dl_btn, is_down)

    def _toggle_dl_btn(self, is_down: bool):
        if hasattr(self, "download_btn") and self.download_btn.winfo_exists():
            if is_down:
                self.download_btn.configure(
                    text=f"⏹  {_('Cancel')}", fg_color=COLORS["danger"],
                    hover_color="#990000", command=self._cancel_download
                )
            else:
                self.download_btn.configure(
                    text=f"⬇  {_('Download')}", fg_color=COLORS["accent_purple"],
                    hover_color=COLORS["accent"], command=self._start_download
                )

    def _cancel_download(self):
        if self._active_task_id:
            self.download_service.cancel(self._active_task_id)
            self._log(f"⚠  {_('Cancellation requested...')}")

    def _build_format_string(self) -> str:
        fmt = self.format_var.get()
        qual = self.quality_var.get()
        if fmt in [_("Audio Only (MP3)"), "Audio Only (MP3)", "Sadece Ses (MP3)"]:
            return "bestaudio/best"
        q_map = {
            _("Best Quality"): "bestvideo+bestaudio/best",
            "Best Quality": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        }
        return q_map.get(qual, "bestvideo+bestaudio/best")

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(_("Warning"), _("Please enter a valid URL!"))
            return
        fmt = self.format_var.get()
        quality = self.quality_var.get()
        is_audio = fmt in [_("Audio Only (MP3)"), "Audio Only (MP3)", "Sadece Ses (MP3)"]
        if quality in [_("Best Quality"), "Best Quality", "En Yüksek"]:
            quality = "best"
        else:
            quality = quality.replace("p", "")
        try:
            task = self.download_service.add(
                url=url,
                quality=quality,
                output_dir=self.download_dir,
                media_format="audio" if is_audio else "video",
            )
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror(_("Error occurred"), str(exc))
            return
        self._active_task_id = task.task_id
        self._clear_log()
        self._set_downloading_state(True)
        self._set_progress(0, "0%", _("Connecting..."))
        self.status_label.configure(text_color=COLORS["text_muted"])
        self._log(f"🔍 {_('Analyzing URL: ')}{url}")

    def _drain_download_events(self):
        if self._closing:
            return
        changed = False
        try:
            while True:
                event = self.download_service.events.get_nowait()
                changed = True
                if event.message:
                    self._log(event.message)
                if event.kind == "progress":
                    pct = max(0.0, min(100.0, event.progress))
                    self._set_progress(
                        pct / 100.0,
                        f"{pct:.1f}%",
                        f"{_('Downloading...')} {pct:.1f}%  |  {event.speed}".strip(),
                    )
                elif event.status == DownloadStatus.QUEUED:
                    self._set_progress(0, "0%", _("Connecting..."))
                elif event.status == DownloadStatus.COMPLETED:
                    self._set_progress(1, "100%", f"✅ {_('Completed')}")
                    self._set_downloading_state(False)
                    self._set_status_color(COLORS["success"])
                elif event.status == DownloadStatus.CANCELLED:
                    self._set_progress(0, "0%", f"⚠ {_('Cancelled')}")
                    self._set_downloading_state(False)
                    self._set_status_color(COLORS["warning"])
                elif event.status == DownloadStatus.FAILED:
                    self._set_progress(0, "0%", f"❌ {_('Error occurred')}")
                    self._set_downloading_state(False)
                    self._set_status_color(COLORS["danger"])
        except queue.Empty:
            pass
        self.after(100, self._drain_download_events)

    def _set_status_color(self, color):
        label = getattr(self, "status_label", None)
        if label is not None and label.winfo_exists():
            label.configure(text_color=color)

    def _on_close(self):
        self._closing = True
        self.download_service.shutdown(wait=False)
        self.destroy()


def create_app():
    """Build the application window without starting the Tk event loop."""
    return VortexDLApp()


if __name__ == "__main__":
    app = create_app()
    app.mainloop()
