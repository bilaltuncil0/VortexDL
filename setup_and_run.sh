#!/usr/bin/env bash
# VideoDownloader — Kurulum ve Başlatma Scripti (Zorin OS / Ubuntu)
# Kullanım: chmod +x setup_and_run.sh && ./setup_and_run.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "============================================"
echo "  🎬  VideoDownloader Kurulum Scripti"
echo "============================================"

# 1. Sistem bağımlılıkları
echo ""
echo "▶ Sistem paketleri kontrol ediliyor..."
MISSING_PKGS=()

command -v ffmpeg >/dev/null 2>&1 || MISSING_PKGS+=(ffmpeg)
python3 -c "import tkinter" >/dev/null 2>&1 || MISSING_PKGS+=(python3-tk)

if ! python3 -m venv --help >/dev/null 2>&1; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    MISSING_PKGS+=("python${PY_VER}-venv")
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo "   Eksik paketler: ${MISSING_PKGS[*]}"
    echo "   Yükleniyor (sudo gerekiyor)..."
    sudo apt update -qq
    sudo apt install -y "${MISSING_PKGS[@]}"
else
    echo "   ✅ Sistem bağımlılıkları mevcut."
fi

# 2. Python sanal ortamı
echo ""
echo "▶ Python sanal ortamı hazırlanıyor..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "   ✅ Sanal ortam oluşturuldu: $VENV_DIR"
else
    echo "   ✅ Sanal ortam zaten mevcut."
fi

# 3. Python bağımlılıkları
echo ""
echo "▶ Python paketleri yükleniyor..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
echo "   ✅ customtkinter ve yt-dlp yüklendi."

# 4. Masaüstü kısayolu (opsiyonel)
DESKTOP_SRC="$SCRIPT_DIR/VideoDownloader.desktop"
DESKTOP_DST="$HOME/.local/share/applications/VideoDownloader.desktop"
if [ ! -f "$DESKTOP_DST" ]; then
    mkdir -p "$HOME/.local/share/applications"
    sed "s|Exec=python3|Exec=$VENV_DIR/bin/python3|" "$DESKTOP_SRC" > "$DESKTOP_DST"
    chmod +x "$DESKTOP_DST"
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
    echo ""
    echo "   ✅ Masaüstü kısayolu oluşturuldu."
fi

# 5. Uygulamayı başlat
echo ""
echo "============================================"
echo "  🚀  Uygulama başlatılıyor…"
echo "============================================"
echo ""
"$VENV_DIR/bin/python3" "$SCRIPT_DIR/downloader.py"
