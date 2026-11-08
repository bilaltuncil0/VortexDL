"""
VideoDownloader - Modern masaüstü video indirme uygulaması
Powered by yt-dlp + CustomTkinter + ffmpeg
"""

import customtkinter as ctk
import threading
import os
import re
import yt_dlp
from pathlib import Path
from tkinter import filedialog, messagebox


# --- Tema & Renk Ayarları ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg_primary":    "#1a1a2e",
    "bg_secondary":  "#16213e",
    "bg_card":       "#0f3460",
    "accent":        "#e94560",
    "accent_hover":  "#c73652",
    "text_primary":  "#eaeaea",
    "text_muted":    "#a0a0b0",
    "success":       "#4caf50",
    "warning":       "#ff9800",
    "progress_fg":   "#00d4aa",
}


# ---------------------------------------------------------------------------
# Yardımcı: ANSI renk kodlarını temizle
# ---------------------------------------------------------------------------
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Ana Uygulama Sınıfı
# ---------------------------------------------------------------------------
class VideoDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🎬 VideoDownloader")
        self.geometry("780x620")
        self.minsize(680, 560)
        self.configure(fg_color=COLORS["bg_primary"])

        # İkon (opsiyonel – yoksa sessizce geç)
        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        # İndirme dizini (varsayılan: ~/Downloads)
        self.download_dir = str(Path.home() / "Downloads")

        # Durum bayrakları
        self._is_downloading = False
        self._cancel_flag = False

        self._build_ui()

    # -----------------------------------------------------------------------
    # Arayüz inşası
    # -----------------------------------------------------------------------
    def _build_ui(self):
        # --- Başlık ---
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0, height=70)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="🎬  VideoDownloader",
            font=ctk.CTkFont(family="Helvetica", size=22, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left", padx=24, pady=0)

        ctk.CTkLabel(
            header,
            text="yt-dlp · ffmpeg · CustomTkinter",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
        ).pack(side="right", padx=24)

        # --- Ana içerik çerçevesi ---
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)

        # Kart: URL girişi
        self._build_url_card(content)

        # Kart: Ayarlar (format + kalite + dizin)
        self._build_settings_card(content)

        # Kart: İndirme butonu + ilerleme
        self._build_progress_card(content)

        # Kart: Log
        self._build_log_card(content)

    # -----------------------------------------------------------------------
    def _build_url_card(self, parent):
        card = self._make_card(parent, "🔗  Video URL")

        self.url_entry = ctk.CTkEntry(
            card,
            placeholder_text="YouTube, Instagram, TikTok, Vimeo… URL'yi buraya yapıştırın",
            font=ctk.CTkFont(size=14),
            height=46,
            border_color=COLORS["bg_card"],
            fg_color=COLORS["bg_secondary"],
            text_color=COLORS["text_primary"],
        )
        self.url_entry.pack(fill="x", padx=16, pady=(4, 12))

        # Yapıştır & Temizle butonları
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkButton(
            btn_row,
            text="📋  Yapıştır",
            width=110,
            height=32,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=12),
            command=self._paste_url,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="✖  Temizle",
            width=110,
            height=32,
            fg_color=COLORS["bg_card"],
            hover_color="#555",
            font=ctk.CTkFont(size=12),
            command=lambda: self.url_entry.delete(0, "end"),
        ).pack(side="left")

    # -----------------------------------------------------------------------
    def _build_settings_card(self, parent):
        card = self._make_card(parent, "⚙️  Ayarlar")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 12))

        # Format
        fmt_frame = ctk.CTkFrame(row, fg_color="transparent")
        fmt_frame.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkLabel(fmt_frame, text="Format", text_color=COLORS["text_muted"],
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.format_var = ctk.StringVar(value="MP4 (Video)")
        self.format_menu = ctk.CTkOptionMenu(
            fmt_frame,
            values=["MP4 (Video)", "MP3 (Ses)"],
            variable=self.format_var,
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=13),
            command=self._on_format_change,
        )
        self.format_menu.pack(fill="x", pady=(4, 0))

        # Kalite
        qual_frame = ctk.CTkFrame(row, fg_color="transparent")
        qual_frame.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkLabel(qual_frame, text="Kalite", text_color=COLORS["text_muted"],
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.quality_var = ctk.StringVar(value="En Yüksek")
        self.quality_menu = ctk.CTkOptionMenu(
            qual_frame,
            values=["En Yüksek", "1080p", "720p", "480p", "360p"],
            variable=self.quality_var,
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_card"],
            button_hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=13),
        )
        self.quality_menu.pack(fill="x", pady=(4, 0))

        # Dizin
        dir_frame = ctk.CTkFrame(row, fg_color="transparent")
        dir_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(dir_frame, text="Kayıt Klasörü", text_color=COLORS["text_muted"],
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
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

    # -----------------------------------------------------------------------
    def _build_progress_card(self, parent):
        card = self._make_card(parent, "📥  İndirme")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(4, 12))

        # İndir / İptal butonu
        self.download_btn = ctk.CTkButton(
            inner,
            text="⬇  İndir",
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._start_download,
        )
        self.download_btn.pack(fill="x", pady=(0, 10))

        # İlerleme çubuğu + yüzde
        prog_row = ctk.CTkFrame(inner, fg_color="transparent")
        prog_row.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(
            prog_row,
            mode="determinate",
            height=16,
            progress_color=COLORS["progress_fg"],
            fg_color=COLORS["bg_secondary"],
            corner_radius=8,
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.progress_bar.set(0)

        self.percent_label = ctk.CTkLabel(
            prog_row,
            text="0%",
            width=48,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["progress_fg"],
        )
        self.percent_label.pack(side="right")

        # Durum etiketi
        self.status_label = ctk.CTkLabel(
            inner,
            text="Hazır",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(6, 0))

    # -----------------------------------------------------------------------
    def _build_log_card(self, parent):
        card = self._make_card(parent, "📋  Log", expand=True)

        self.log_box = ctk.CTkTextbox(
            card,
            font=ctk.CTkFont(family="Monospace", size=11),
            fg_color=COLORS["bg_secondary"],
            text_color=COLORS["text_muted"],
            wrap="word",
            state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(4, 12))

    # -----------------------------------------------------------------------
    # Kart fabrikası
    # -----------------------------------------------------------------------
    def _make_card(self, parent, title: str, expand: bool = False) -> ctk.CTkFrame:
        wrapper = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["bg_card"],
        )
        wrapper.pack(fill="both", expand=expand, pady=(0, 10))

        ctk.CTkLabel(
            wrapper,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(10, 0))

        sep = ctk.CTkFrame(wrapper, height=1, fg_color=COLORS["bg_card"])
        sep.pack(fill="x", padx=16, pady=(6, 0))

        return wrapper

    # -----------------------------------------------------------------------
    # Yardımcı UI metotları
    # -----------------------------------------------------------------------
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
        is_audio = value == "MP3 (Ses)"
        self.quality_menu.configure(state="disabled" if is_audio else "normal")

    @staticmethod
    def _short_path(path: str, max_len: int = 28) -> str:
        return path if len(path) <= max_len else "…" + path[-(max_len - 1):]

    # -----------------------------------------------------------------------
    # Log metotları (thread-safe)
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # UI güncelleme (thread-safe)
    # -----------------------------------------------------------------------
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
                text="⏹  İptal Et",
                fg_color="#555",
                hover_color="#444",
                command=self._cancel_download,
            )
        else:
            self.download_btn.configure(
                text="⬇  İndir",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                command=self._start_download,
            )

    # -----------------------------------------------------------------------
    # İptal
    # -----------------------------------------------------------------------
    def _cancel_download(self):
        self._cancel_flag = True
        self._log("⚠  İptal isteği gönderildi…")
        self.status_label.configure(text="İptal ediliyor…", text_color=COLORS["warning"])

    # -----------------------------------------------------------------------
    # yt-dlp format dizesi
    # -----------------------------------------------------------------------
    def _build_format_string(self) -> str:
        fmt = self.format_var.get()
        qual = self.quality_var.get()

        if fmt == "MP3 (Ses)":
            return "bestaudio/best"

        quality_map = {
            "En Yüksek": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        }
        return quality_map.get(qual, "bestvideo+bestaudio/best")

    # -----------------------------------------------------------------------
    # İndirme başlat
    # -----------------------------------------------------------------------
    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Uyarı", "Lütfen bir URL girin!")
            return
        if self._is_downloading:
            return

        self._cancel_flag = False
        self._clear_log()
        self._set_downloading_state(True)
        self._set_progress(0, "0%", "Bağlanıyor…")
        self.status_label.configure(text_color=COLORS["text_muted"])

        thread = threading.Thread(target=self._download_worker, args=(url,), daemon=True)
        thread.start()

    # -----------------------------------------------------------------------
    # İndirme iş parçacığı
    # -----------------------------------------------------------------------
    def _download_worker(self, url: str):
        fmt = self.format_var.get()
        is_audio = fmt == "MP3 (Ses)"
        format_str = self._build_format_string()

        # yt-dlp seçenekleri
        ydl_opts: dict = {
            "format": format_str,
            "outtmpl": os.path.join(self.download_dir, "%(title)s.%(ext)s"),
            "merge_output_format": "mp4" if not is_audio else None,
            "ffmpeg_location": "/usr/bin",   # genellikle burada; PATH'te de aranır
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "logger": _YTLogger(self._log),
            "quiet": True,
            "no_warnings": False,
            "noplaylist": False,
        }

        if is_audio:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
            ydl_opts.pop("merge_output_format", None)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._log(f"🔍  URL analiz ediliyor: {url}")
                if self._cancel_flag:
                    raise Exception("İptal edildi")
                ydl.download([url])

            if not self._cancel_flag:
                self._set_progress(1.0, "100%", f"✅  Tamamlandı → {self._short_path(self.download_dir)}")
                self.after(0, lambda: self.status_label.configure(text_color=COLORS["success"]))
                self._log(f"✅  İndirme tamamlandı! Konum: {self.download_dir}")

        except Exception as exc:
            err = str(exc)
            if self._cancel_flag:
                self._set_progress(0, "0%", "⚠  İptal edildi")
                self.after(0, lambda: self.status_label.configure(text_color=COLORS["warning"]))
                self._log("⚠  İndirme iptal edildi.")
            else:
                self._set_progress(0, "0%", "❌  Hata oluştu")
                self.after(0, lambda: self.status_label.configure(text_color=COLORS["accent"]))
                self._log(f"❌  Hata: {err}")
        finally:
            self._set_downloading_state(False)

    # -----------------------------------------------------------------------
    # yt-dlp ilerleme kancası
    # -----------------------------------------------------------------------
    def _progress_hook(self, d: dict):
        if self._cancel_flag:
            raise Exception("Kullanıcı iptal etti")

        status = d.get("status", "")

        if status == "downloading":
            # Yüzde
            pct_str = strip_ansi(d.get("_percent_str", "0%")).strip()
            try:
                pct_val = float(pct_str.replace("%", "")) / 100.0
            except ValueError:
                pct_val = 0.0

            # Hız & ETA
            speed  = strip_ansi(d.get("_speed_str", "")).strip()
            eta    = strip_ansi(d.get("_eta_str", "")).strip()
            status_txt = f"İndiriliyor… {pct_str}"
            if speed:
                status_txt += f"  |  {speed}"
            if eta:
                status_txt += f"  |  ETA {eta}"

            self._set_progress(pct_val, pct_str, status_txt)

        elif status == "finished":
            self._set_progress(0.95, "95%", "🔀  Birleştiriliyor (ffmpeg)…")
            self._log(f"⬇  İndirildi: {d.get('filename', '')}")

        elif status == "error":
            self._log(f"❌  İndirme hatası: {d.get('filename', '')}")

    # -----------------------------------------------------------------------
    # yt-dlp işlem sonrası kanca (birleştirme tamamlandı)
    # -----------------------------------------------------------------------
    def _postprocessor_hook(self, d: dict):
        if d.get("status") == "finished":
            self._set_progress(1.0, "100%", "✅  İşlem tamamlandı")


# ---------------------------------------------------------------------------
# yt-dlp özel logger
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = VideoDownloaderApp()
    app.mainloop()
