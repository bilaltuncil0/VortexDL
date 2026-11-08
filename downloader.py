"""
VideoDownloader - Modern Cross-Platform Video Downloader
Version: 2.0.0
Powered by yt-dlp + CustomTkinter + ffmpeg + aria2c
"""

import customtkinter as ctk
import threading
import os
import sys
import re
import shutil
import locale
import gettext
from pathlib import Path
from tkinter import filedialog, messagebox
import yt_dlp

# --- i18n / Localization Setup ---
APP_DIR = Path(__file__).resolve().parent
LOCALES_DIR = APP_DIR / "locales"

def get_system_language():
    """Detect system language code with fallback to en_US."""
    try:
        sys_loc = locale.getdefaultlocale()[0]
        if sys_loc and sys_loc.lower().startswith("tr"):
            return "tr_TR"
    except Exception:
        pass
    return "en_US"

CURRENT_LANG = get_system_language()

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
        def _(text):
            return text
    return _

setup_translation(CURRENT_LANG)


# --- Theme & Color Palette ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

THEME_CONFIGS = {
    "dark": {
        "bg_primary":    "#12121e",
        "bg_secondary":  "#1a1a2e",
        "bg_card":       "#1f2440",
        "accent":        "#e94560",
        "accent_hover":  "#c73652",
        "text_primary":  "#ffffff",
        "text_muted":    "#9ea3b5",
        "success":       "#00e676",
        "warning":       "#ffab00",
        "progress_fg":   "#00d4aa",
        "border":        "#2c3258",
    },
    "light": {
        "bg_primary":    "#f4f6fa",
        "bg_secondary":  "#ffffff",
        "bg_card":       "#e8ecf4",
        "accent":        "#d63031",
        "accent_hover":  "#b71540",
        "text_primary":  "#2d3436",
        "text_muted":    "#636e72",
        "success":       "#00b894",
        "warning":       "#e17055",
        "progress_fg":   "#0984e3",
        "border":        "#dfe6e9",
    }
}

COLORS = THEME_CONFIGS["dark"]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class VideoDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.current_lang = CURRENT_LANG
        self.title("🎬 VideoDownloader v2.0.0")
        self.geometry("820x680")
        self.minsize(740, 600)
        self.configure(fg_color=COLORS["bg_primary"])

        # Check for icon
        icon_path = APP_DIR / "icon.png"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Check aria2c availability
        self.aria2_path = shutil.which("aria2c")
        self.has_aria2 = self.aria2_path is not None

        # Download directory
        self.download_dir = str(Path.home() / "Downloads")

        # Runtime flags
        self._is_downloading = False
        self._cancel_flag = False

        self._build_ui()

    def _build_ui(self):
        # Header
        self.header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0, height=75)
        self.header.pack(fill="x", padx=0, pady=0)
        self.header.pack_propagate(False)

        title_box = ctk.CTkFrame(self.header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        self.title_lbl = ctk.CTkLabel(
            title_box,
            text="🎬  VideoDownloader",
            font=ctk.CTkFont(family="Helvetica", size=22, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self.title_lbl.pack(anchor="w")

        sub_text = "yt-dlp · ffmpeg"
        if self.has_aria2:
            sub_text += " · ⚡ aria2c"
        self.sub_lbl = ctk.CTkLabel(
            title_box,
            text=sub_text,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["progress_fg"] if self.has_aria2 else COLORS["text_muted"],
        )
        self.sub_lbl.pack(anchor="w")

        # Top Right Controls (Theme & Lang)
        controls_box = ctk.CTkFrame(self.header, fg_color="transparent")
        controls_box.pack(side="right", padx=20, pady=12)

        # Language Selector
        self.lang_var = ctk.StringVar(value="Türkçe" if self.current_lang == "tr_TR" else "English")
        self.lang_menu = ctk.CTkOptionMenu(
            controls_box,
            values=["Türkçe", "English"],
            variable=self.lang_var,
            width=100,
            height=30,
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11),
            command=self._change_language
        )
        self.lang_menu.pack(side="right", padx=(8, 0))

        # Theme Selector (Dark / Light / System)
        self.theme_var = ctk.StringVar(value=_("Dark"))
        self.theme_menu = ctk.CTkOptionMenu(
            controls_box,
            values=[_("Dark"), _("Light"), _("System")],
            variable=self.theme_var,
            width=105,
            height=30,
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11),
            command=self._change_theme
        )
        self.theme_menu.pack(side="right", padx=(0, 4))

        # Main Scrollable / Frame Content
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=12)

        self._build_url_card(self.content)
        self._build_settings_card(self.content)
        self._build_progress_card(self.content)
        self._build_log_card(self.content)

    def _build_url_card(self, parent):
        self.url_card = self._make_card(parent, f"🔗  {_('Video URL')}")

        self.url_entry = ctk.CTkEntry(
            self.url_card,
            placeholder_text=_("Paste URL here (YouTube, Instagram, TikTok, Twitter...)"),
            font=ctk.CTkFont(size=13),
            height=44,
            border_color=COLORS["border"],
            fg_color=COLORS["bg_primary"],
            text_color=COLORS["text_primary"],
        )
        self.url_entry.pack(fill="x", padx=16, pady=(4, 10))

        btn_row = ctk.CTkFrame(self.url_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 10))

        self.btn_paste = ctk.CTkButton(
            btn_row,
            text=f"📋  {_('Paste')}",
            width=110,
            height=32,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=12),
            command=self._paste_url,
        )
        self.btn_paste.pack(side="left", padx=(0, 8))

        self.btn_clear = ctk.CTkButton(
            btn_row,
            text=f"✖  {_('Clear')}",
            width=110,
            height=32,
            fg_color=COLORS["bg_card"],
            hover_color="#555555",
            font=ctk.CTkFont(size=12),
            command=lambda: self.url_entry.delete(0, "end"),
        )
        self.btn_clear.pack(side="left")

    def _build_settings_card(self, parent):
        self.settings_card = self._make_card(parent, f"⚙️  {_('Settings')}")
        row = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 12))

        # Format Option
        fmt_frame = ctk.CTkFrame(row, fg_color="transparent")
        fmt_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.fmt_lbl = ctk.CTkLabel(fmt_frame, text=_("Format"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12))
        self.fmt_lbl.pack(anchor="w")

        self.format_var = ctk.StringVar(value=_("Video (MP4)"))
        self.format_menu = ctk.CTkOptionMenu(
            fmt_frame,
            values=[_("Video (MP4)"), _("Audio Only (MP3)")],
            variable=self.format_var,
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=12),
            command=self._on_format_change,
        )
        self.format_menu.pack(fill="x", pady=(4, 0))

        # Quality Option
        qual_frame = ctk.CTkFrame(row, fg_color="transparent")
        qual_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.qual_lbl = ctk.CTkLabel(qual_frame, text=_("Quality"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12))
        self.qual_lbl.pack(anchor="w")

        self.quality_var = ctk.StringVar(value=_("Best Quality"))
        self.quality_menu = ctk.CTkOptionMenu(
            qual_frame,
            values=[_("Best Quality"), "1080p", "720p", "480p", "360p"],
            variable=self.quality_var,
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=12),
        )
        self.quality_menu.pack(fill="x", pady=(4, 0))

        # Destination Folder
        dir_frame = ctk.CTkFrame(row, fg_color="transparent")
        dir_frame.pack(side="left", fill="x", expand=True)
        self.dir_title_lbl = ctk.CTkLabel(dir_frame, text=_("Save Folder"), text_color=COLORS["text_muted"], font=ctk.CTkFont(size=12))
        self.dir_title_lbl.pack(anchor="w")

        dir_btn_row = ctk.CTkFrame(dir_frame, fg_color="transparent")
        dir_btn_row.pack(fill="x", pady=(4, 0))
        self.dir_label = ctk.CTkLabel(
            dir_btn_row,
            text=self._short_path(self.download_dir),
            text_color=COLORS["progress_fg"],
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.dir_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            dir_btn_row,
            text="📁",
            width=36,
            height=32,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["accent"],
            command=self._choose_dir,
        ).pack(side="right")

    def _build_progress_card(self, parent):
        self.progress_card = self._make_card(parent, f"📥  {_('Download')}")
        inner = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(4, 12))

        # Main Download Button
        self.download_btn = ctk.CTkButton(
            inner,
            text=f"⬇  {_('Download')}",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._start_download,
        )
        self.download_btn.pack(fill="x", pady=(0, 10))

        # Progress bar + Percent & Speed Box
        prog_row = ctk.CTkFrame(inner, fg_color="transparent")
        prog_row.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(
            prog_row,
            mode="determinate",
            height=18,
            progress_color=COLORS["progress_fg"],
            fg_color=COLORS["bg_primary"],
            corner_radius=9,
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.progress_bar.set(0)

        self.percent_label = ctk.CTkLabel(
            prog_row,
            text="0%",
            width=50,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["progress_fg"],
        )
        self.percent_label.pack(side="right")

        # Live Status (Speed, ETA, etc.)
        self.status_label = ctk.CTkLabel(
            inner,
            text=_("Ready"),
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(6, 0))

    def _build_log_card(self, parent):
        self.log_card = self._make_card(parent, f"📋  {_('Log')}", expand=True)

        self.log_box = ctk.CTkTextbox(
            self.log_card,
            font=ctk.CTkFont(family="Monospace", size=11),
            fg_color=COLORS["bg_primary"],
            text_color=COLORS["text_muted"],
            wrap="word",
            state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(4, 12))

    def _make_card(self, parent, title: str, expand: bool = False) -> ctk.CTkFrame:
        wrapper = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        wrapper.pack(fill="both", expand=expand, pady=(0, 10))

        lbl = ctk.CTkLabel(
            wrapper,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        lbl.pack(fill="x", padx=16, pady=(10, 0))

        sep = ctk.CTkFrame(wrapper, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=16, pady=(6, 0))

        return wrapper

    # --- UI Theme & Language Handlers ---
    def _change_theme(self, choice):
        global COLORS
        if choice in [_("Dark"), "Dark", "Karanlık"]:
            ctk.set_appearance_mode("dark")
            COLORS = THEME_CONFIGS["dark"]
        elif choice in [_("Light"), "Light", "Açık"]:
            ctk.set_appearance_mode("light")
            COLORS = THEME_CONFIGS["light"]
        else:
            ctk.set_appearance_mode("system")
            COLORS = THEME_CONFIGS["dark"]
        self._refresh_colors()

    def _refresh_colors(self):
        self.configure(fg_color=COLORS["bg_primary"])
        self.header.configure(fg_color=COLORS["bg_secondary"])
        self.title_lbl.configure(text_color=COLORS["text_primary"])
        self.progress_bar.configure(progress_color=COLORS["progress_fg"], fg_color=COLORS["bg_primary"])
        self.percent_label.configure(text_color=COLORS["progress_fg"])
        self.download_btn.configure(fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"])

    def _change_language(self, choice):
        new_lang = "tr_TR" if choice == "Türkçe" else "en_US"
        if new_lang != self.current_lang:
            self.current_lang = new_lang
            setup_translation(new_lang)
            # Rebuild whole UI to cleanly re-translate all labels
            for widget in self.winfo_children():
                widget.destroy()
            self._build_ui()

    def _paste_url(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text.strip())
        except Exception:
            pass

    def _choose_dir(self):
        path = filedialog.askdirectory(initialdir=self.download_dir)
        if path:
            self.download_dir = path
            self.dir_label.configure(text=self._short_path(path))

    def _on_format_change(self, value):
        is_audio = value in [_("Audio Only (MP3)"), "MP3 (Ses)", "Audio Only (MP3)"]
        self.quality_menu.configure(state="disabled" if is_audio else "normal")

    @staticmethod
    def _short_path(path: str, max_len: int = 28) -> str:
        return path if len(path) <= max_len else "…" + path[-(max_len - 1):]

    # --- Thread-Safe Logging & Progress ---
    def _log(self, msg: str):
        clean = strip_ansi(msg)
        self.after(0, self._append_log, clean)

    def _append_log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_progress(self, value: float, percent_text: str, status: str):
        self.after(0, self._update_progress_widgets, value, percent_text, status)

    def _update_progress_widgets(self, value: float, percent_text: str, status: str):
        self.progress_bar.set(value)
        self.percent_label.configure(text=percent_text)
        self.status_label.configure(text=status)

    def _set_downloading_state(self, downloading: bool):
        self._is_downloading = downloading
        self.after(0, self._toggle_btn, downloading)

    def _toggle_btn(self, downloading: bool):
        if downloading:
            self.download_btn.configure(
                text=f"⏹  {_('Cancel')}",
                fg_color="#555555",
                hover_color="#333333",
                command=self._cancel_download,
            )
        else:
            self.download_btn.configure(
                text=f"⬇  {_('Download')}",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                command=self._start_download,
            )

    def _cancel_download(self):
        self._cancel_flag = True
        self._log(f"⚠  {_('Cancellation requested...')}")
        self.status_label.configure(text=_("Cancellation requested..."), text_color=COLORS["warning"])

    def _build_format_string(self) -> str:
        fmt = self.format_var.get()
        qual = self.quality_var.get()

        if fmt in [_("Audio Only (MP3)"), "MP3 (Ses)", "Audio Only (MP3)"]:
            return "bestaudio/best"

        quality_map = {
            _("Best Quality"): "bestvideo+bestaudio/best",
            "Best Quality": "bestvideo+bestaudio/best",
            "En Yüksek": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        }
        return quality_map.get(qual, "bestvideo+bestaudio/best")

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(_("Warning"), _("Please enter a valid URL!"))
            return
        if self._is_downloading:
            return

        self._cancel_flag = False
        self._clear_log()
        self._set_downloading_state(True)
        self._set_progress(0, "0%", _("Connecting..."))
        self.status_label.configure(text_color=COLORS["text_muted"])

        thread = threading.Thread(target=self._download_worker, args=(url,), daemon=True)
        thread.start()

    def _download_worker(self, url: str):
        fmt = self.format_var.get()
        is_audio = fmt in [_("Audio Only (MP3)"), "MP3 (Ses)", "Audio Only (MP3)"]
        format_str = self._build_format_string()

        ydl_opts: dict = {
            "format": format_str,
            "outtmpl": os.path.join(self.download_dir, "%(title)s.%(ext)s"),
            "merge_output_format": "mp4" if not is_audio else None,
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "logger": _YTLogger(self._log),
            "quiet": True,
            "no_warnings": False,
            "noplaylist": False,
        }

        # aria2c acceleration if installed
        if self.has_aria2:
            ydl_opts["external_downloader"] = "aria2c"
            ydl_opts["external_downloader_args"] = [
                "-x", "16",
                "-s", "16",
                "-k", "1M",
                "--split=16",
                "--min-split-size=1M"
            ]
            self._log(f"⚡ {_('aria2 accelerated')}: {self.aria2_path}")

        if is_audio:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
            ydl_opts.pop("merge_output_format", None)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._log(f"🔍 {_('Analyzing URL: ')}{url}")
                if self._cancel_flag:
                    raise Exception(_("Cancelled"))
                ydl.download([url])

            if not self._cancel_flag:
                self._set_progress(1.0, "100%", f"✅ {_('Completed')} → {self._short_path(self.download_dir)}")
                self.after(0, lambda: self.status_label.configure(text_color=COLORS["success"]))
                self._log(f"✅ {_('Download completed! Location: ')}{self.download_dir}")

        except Exception as exc:
            err = str(exc)
            if self._cancel_flag:
                self._set_progress(0, "0%", f"⚠ {_('Cancelled')}")
                self.after(0, lambda: self.status_label.configure(text_color=COLORS["warning"]))
                self._log(f"⚠ {_('Cancelled')}")
            else:
                self._set_progress(0, "0%", f"❌ {_('Error occurred')}")
                self.after(0, lambda: self.status_label.configure(text_color=COLORS["accent"]))
                self._log(f"❌ {_('Error: ')}{err}")
        finally:
            self._set_downloading_state(False)

    def _progress_hook(self, d: dict):
        if self._cancel_flag:
            raise Exception("Cancelled by user")

        status = d.get("status", "")

        if status == "downloading":
            pct_str = strip_ansi(d.get("_percent_str", "0%")).strip()
            try:
                pct_val = float(pct_str.replace("%", "")) / 100.0
            except ValueError:
                pct_val = 0.0

            speed  = strip_ansi(d.get("_speed_str", "")).strip()
            eta    = strip_ansi(d.get("_eta_str", "")).strip()
            status_txt = f"{_('Downloading...')} {pct_str}"
            if speed:
                status_txt += f"  |  {speed}"
            if eta:
                status_txt += f"  |  ETA {eta}"

            self._set_progress(pct_val, pct_str, status_txt)

        elif status == "finished":
            self._set_progress(0.95, "95%", f"🔀 {_('Merging streams (ffmpeg)...')}")
            self._log(f"⬇ {_('Downloaded: ')}{d.get('filename', '')}")

        elif status == "error":
            self._log(f"❌ {_('Error occurred')}: {d.get('filename', '')}")

    def _postprocessor_hook(self, d: dict):
        if d.get("status") == "finished":
            self._set_progress(1.0, "100%", f"✅ {_('Merging completed')}")


class _YTLogger:
    def __init__(self, log_fn):
        self._log = log_fn

    def debug(self, msg):
        if msg.startswith("[debug]"):
            return
        self._log(msg)

    def info(self, msg):
        self._log(msg)

    def warning(self, msg):
        self._log(f"⚠  {msg}")

    def error(self, msg):
        self._log(f"❌  {msg}")


if __name__ == "__main__":
    app = VideoDownloaderApp()
    app.mainloop()
