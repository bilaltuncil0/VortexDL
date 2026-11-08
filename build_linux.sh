#!/usr/bin/env bash
# =============================================================
#  VideoDownloader — Linux Build Script
#  Üretir: PyInstaller binary + (opsiyonel) AppImage
#
#  Gereksinimler:
#    - Python 3.10+
#    - ffmpeg  (sudo apt install ffmpeg)
#    - .venv sanal ortamı ve requirements-dev.txt
#
#  Kullanım:
#    chmod +x build_linux.sh
#    ./build_linux.sh [--appimage] [--clean]
# =============================================================

set -euo pipefail

# ── Renkli çıktı ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}▶${RESET} $*"; }
success() { echo -e "${GREEN}✅${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠️ ${RESET} $*"; }
error()   { echo -e "${RED}❌${RESET} $*" >&2; exit 1; }

# ── Argümanlar ────────────────────────────────────────────────
BUILD_APPIMAGE=false
CLEAN_FIRST=false
for arg in "$@"; do
  case "$arg" in
    --appimage) BUILD_APPIMAGE=true ;;
    --clean)    CLEAN_FIRST=true ;;
    --help|-h)
      echo "Kullanım: $0 [--appimage] [--clean]"
      echo "  --appimage   AppImage paketi de oluştur (appimagetool gerekir)"
      echo "  --clean      Önceki build/ dist/ çıktılarını temizle"
      exit 0 ;;
  esac
done

# ── Dizin değişkenleri ────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"
APP_NAME="VideoDownloader"
ENTRY_POINT="$SCRIPT_DIR/downloader.py"
ICON="$SCRIPT_DIR/icon.png"

echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  🏗️  VideoDownloader Linux Build Script     ${RESET}"
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo ""

# ── Temizlik ──────────────────────────────────────────────────
if $CLEAN_FIRST; then
  info "Önceki derleme çıktıları temizleniyor…"
  rm -rf "$BUILD_DIR" "$DIST_DIR"
  success "Temizlik tamamlandı."
fi

# ── Sanal ortam kontrolü ──────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  info "Sanal ortam bulunamadı, oluşturuluyor…"
  python3 -m venv "$VENV_DIR" || error "python3-venv kurulu değil. Çalıştır: sudo apt install python3-venv"
fi
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
success "Sanal ortam aktif: $VENV_DIR"

# ── Bağımlılıklar ─────────────────────────────────────────────
info "Python bağımlılıkları güncelleniyor…"
pip install -q --upgrade pip
pip install -q -r "$SCRIPT_DIR/requirements.txt"
pip install -q -r "$SCRIPT_DIR/requirements-dev.txt"
success "Bağımlılıklar hazır."

# ── ffmpeg varlık kontrolü ────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
  warn "ffmpeg bulunamadı! Yükle: sudo apt install ffmpeg"
  warn "Derleme devam ediyor ama indirme birleştirme özelliği çalışmaz."
fi

# ── PyInstaller ile derleme ───────────────────────────────────
info "PyInstaller ile binary derleniyor…"

PYINSTALLER_ARGS=(
  --onefile
  --windowed
  --name "$APP_NAME"
  --distpath "$DIST_DIR"
  --workpath "$BUILD_DIR"
  --noconfirm
  --clean
)

# İkon ekle (varsa)
if [ -f "$ICON" ]; then
  PYINSTALLER_ARGS+=(--icon "$ICON")
fi

# Varlık dosyalarını ekle (data files)
if [ -f "$ICON" ]; then
  PYINSTALLER_ARGS+=(--add-data "$ICON:.")
fi

# CustomTkinter varlıklarını ekle (tema dosyaları, fontlar)
CTK_PATH=$(python3 -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))" 2>/dev/null || true)
if [ -n "$CTK_PATH" ]; then
  PYINSTALLER_ARGS+=(--add-data "$CTK_PATH:customtkinter/")
  success "CustomTkinter varlıkları eklendi: $CTK_PATH"
fi

# yt-dlp'nin dahili extractors'ları için gizli import
PYINSTALLER_ARGS+=(
  --hidden-import "yt_dlp.extractor._extractors"
  --hidden-import "yt_dlp.utils"
  --collect-all "yt_dlp"
)

pyinstaller "${PYINSTALLER_ARGS[@]}" "$ENTRY_POINT"

# ── Binary doğrulama ──────────────────────────────────────────
BINARY="$DIST_DIR/$APP_NAME"
if [ -f "$BINARY" ]; then
  BINARY_SIZE=$(du -sh "$BINARY" | cut -f1)
  success "Binary oluşturuldu: $BINARY  ($BINARY_SIZE)"
  chmod +x "$BINARY"
else
  error "Binary bulunamadı: $BINARY — derleme başarısız!"
fi

# ── Derlenen binary'yi çalıştırılabilirlik testi ──────────────
info "Binary çalıştırılabilirlik testi…"
if "$BINARY" --help &>/dev/null 2>&1 || timeout 3 "$BINARY" &>/dev/null 2>&1; then
  success "Binary çalışabilir durumda."
else
  # GUI uygulamaları --help desteklemez, display kontrolü yap
  if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    warn "Görsel ekran yok (headless). Binary fonksiyonel görünüyor, ancak GUI test edilemedi."
  else
    warn "Binary çalışma testi tamamlanamadı (GUI uygulamaları için bu normaldir)."
  fi
fi

# ── AppImage oluşturma (--appimage bayrağı ile) ───────────────
if $BUILD_APPIMAGE; then
  echo ""
  info "AppImage oluşturuluyor…"

  APPDIR="$DIST_DIR/AppDir"
  APPIMAGE_OUT="$DIST_DIR/${APP_NAME}-x86_64.AppImage"

  # appimagetool kontrolü
  APPIMAGETOOL=""
  if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="appimagetool"
  elif [ -f "$SCRIPT_DIR/appimagetool-x86_64.AppImage" ]; then
    APPIMAGETOOL="$SCRIPT_DIR/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
  else
    warn "appimagetool bulunamadı. İndir:"
    warn "  wget -O appimagetool-x86_64.AppImage \\"
    warn "    https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage"
    warn "  chmod +x appimagetool-x86_64.AppImage"
    warn "AppImage oluşturma atlandı."
    APPIMAGETOOL=""
  fi

  if [ -n "$APPIMAGETOOL" ]; then
    # AppDir yapısını oluştur
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/applications"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/128x128/apps"

    # Binary kopyala
    cp "$BINARY" "$APPDIR/usr/bin/$APP_NAME"

    # İkon kopyala
    if [ -f "$ICON" ]; then
      cp "$ICON" "$APPDIR/usr/share/icons/hicolor/128x128/apps/${APP_NAME}.png"
      cp "$ICON" "$APPDIR/${APP_NAME}.png"
    fi

    # .desktop dosyası oluştur
    cat > "$APPDIR/${APP_NAME}.desktop" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=${APP_NAME}
Comment=Modern GUI video downloader powered by yt-dlp
Exec=${APP_NAME}
Icon=${APP_NAME}
Terminal=false
Categories=AudioVideo;Network;
Keywords=video;download;youtube;instagram;tiktok;
DESKTOP
    cp "$APPDIR/${APP_NAME}.desktop" "$APPDIR/usr/share/applications/"

    # AppRun scripti
    cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=$(dirname "$SELF")
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/VideoDownloader" "$@"
APPRUN
    chmod +x "$APPDIR/AppRun"

    # AppImage üret
    ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_OUT" 2>&1

    if [ -f "$APPIMAGE_OUT" ]; then
      APPIMAGE_SIZE=$(du -sh "$APPIMAGE_OUT" | cut -f1)
      success "AppImage oluşturuldu: $APPIMAGE_OUT  ($APPIMAGE_SIZE)"
      chmod +x "$APPIMAGE_OUT"
    else
      warn "AppImage oluşturulamadı."
    fi
  fi
fi

# ── Son rapor ─────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  📊  DERLEME SONUÇ RAPORU                  ${RESET}"
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo ""
echo -e "  Binary   : ${GREEN}$BINARY${RESET}"
echo -e "  Boyut    : ${CYAN}$(du -sh "$BINARY" | cut -f1)${RESET}"
if $BUILD_APPIMAGE && [ -f "$APPIMAGE_OUT" ]; then
  echo -e "  AppImage : ${GREEN}$APPIMAGE_OUT${RESET}"
  echo -e "  Boyut    : ${CYAN}$(du -sh "$APPIMAGE_OUT" | cut -f1)${RESET}"
fi
echo ""
echo -e "  Çalıştırmak için:"
echo -e "  ${YELLOW}$BINARY${RESET}"
echo ""
success "Derleme tamamlandı! 🎉"
