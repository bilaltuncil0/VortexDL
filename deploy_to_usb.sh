#!/usr/bin/env bash
# ==============================================================================
# VortexDL — Yerel Derleme ve USB Dağıtım Betiği
# ==============================================================================
# Uygulamayı PyInstaller ile tek parça bağımsız ikili dosyaya (standalone executable)
# dönüştürür ve doğrudan modem/ağ USB sürücüsüne (/mnt/modem_usb/usb1_1) kopyalar.
# ==============================================================================

set -euo pipefail

# --- Renk ve Biçim Tanımları ---
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_CYAN="\033[36m"
CLR_GREEN="\033[32m"
CLR_YELLOW="\033[33m"
CLR_RED="\033[31m"
CLR_MAGENTA="\033[35m"

log_info()    { echo -e "${CLR_CYAN}${CLR_BOLD}[*]${CLR_RESET} $1"; }
log_success() { echo -e "${CLR_GREEN}${CLR_BOLD}[✓]${CLR_RESET} $1"; }
log_warn()    { echo -e "${CLR_YELLOW}${CLR_BOLD}[!]${CLR_RESET} $1"; }
log_error()   { echo -e "${CLR_RED}${CLR_BOLD}[✗]${CLR_RESET} $1"; }
log_step()    { echo -e "\n${CLR_MAGENTA}${CLR_BOLD}==>${CLR_RESET} ${CLR_BOLD}$1${CLR_RESET}"; }

# --- Dizin Tanımları ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="VortexDL"
USB_TARGET_DIR="${1:-/mnt/modem_usb/usb1_1}"
VENV_DIR="$SCRIPT_DIR/.venv"

echo -e "${CLR_CYAN}${CLR_BOLD}"
echo "============================================================"
echo "          ⚡ VortexDL — USB Dağıtım & Derleme Sihirbazı      "
echo "============================================================"
echo -e "${CLR_RESET}"

# 1. USB Bağlantı Kontrolü
log_step "USB hedef dizini kontrol ediliyor..."
if [ ! -d "$USB_TARGET_DIR" ]; then
    log_error "USB takılı değil veya ağ sürücüsü bağlı değil"
    log_warn "Hedef konum bulunamadı: ${USB_TARGET_DIR}"
    exit 1
fi
log_success "USB sürücüsü hazır ve bağlı: ${USB_TARGET_DIR}"

# 2. Python Sanal Ortam & Bağımlılık Kontrolü
log_step "Derleme ortamı hazırlanıyor..."
if [ -d "$VENV_DIR" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    log_info "Sanal ortam aktifleştirildi (.venv)"
else
    log_warn "Sanal ortam (.venv) bulunamadı, sistem ortamı kullanılıyor."
fi

if ! command -v pyinstaller &>/dev/null; then
    log_error "PyInstaller kurulu değil! 'pip install pyinstaller' çalıştırın."
    exit 1
fi

# Dil dosyalarını derle (varsa)
if command -v msgfmt &>/dev/null; then
    log_info "Dil katalogları derleniyor (.po -> .mo)..."
    python3 -c "
import subprocess, os
for lang in ['tr_TR', 'en_US', 'de_DE', 'fr_FR', 'it_IT', 'ar_SA', 'zh_CN']:
    po = os.path.join('locales', lang, 'LC_MESSAGES', 'videodownloader.po')
    mo = os.path.join('locales', lang, 'LC_MESSAGES', 'videodownloader.mo')
    if os.path.exists(po):
        subprocess.run(['msgfmt', po, '-o', mo], check=False)
" 2>/dev/null || true
fi

# 3. PyInstaller Derleme İşlemi (Paketleniyor...)
log_step "Paketleniyor..."
log_info "Parametreler: Tek dosya (--onefile), konsol penceresiz (--windowed)"

if [ -f "VortexDL.spec" ]; then
    log_info "VortexDL.spec yapılandırması kullanılarak derleniyor..."
    pyinstaller --noconfirm --clean VortexDL.spec
else
    log_info "Varsayılan parametrelerle PyInstaller çalıştırılıyor..."
    pyinstaller --noconfirm --clean \
        --onefile \
        --windowed \
        --name "$APP_NAME" \
        --add-data "assets:assets" \
        --add-data "icon.png:." \
        --add-data "locales:locales" \
        --collect-all "customtkinter" \
        --collect-all "yt_dlp" \
        --hidden-import "gettext" \
        --hidden-import "sqlite3" \
        --hidden-import "storage" \
        --hidden-import "updater" \
        downloader.py
fi

COMPILED_BIN="$SCRIPT_DIR/dist/$APP_NAME"
if [ ! -f "$COMPILED_BIN" ]; then
    log_error "Derleme başarısız oldu! '${COMPILED_BIN}' dosyası bulunamadı."
    exit 1
fi
log_success "Paketleme başarıyla tamamlandı: ${COMPILED_BIN} ($(du -sh "$COMPILED_BIN" | cut -f1))"

# 4. USB'ye Aktarım (USB'ye aktarılıyor...)
log_step "USB'ye aktarılıyor..."
log_info "Kaynak: ${COMPILED_BIN}"
log_info "Hedef : ${USB_TARGET_DIR}/${APP_NAME}"

cp -f "$COMPILED_BIN" "${USB_TARGET_DIR}/${APP_NAME}"
chmod +x "${USB_TARGET_DIR}/${APP_NAME}" 2>/dev/null || true
log_success "Dosya başarıyla aktarıldı: ${USB_TARGET_DIR}/${APP_NAME}"

# Kullanıcı yerel /home/bilal konumuna da kopyalamak isterse:
if [ -d "/home/bilal" ] && [ "$USB_TARGET_DIR" != "/home/bilal" ]; then
    cp -f "$COMPILED_BIN" "/home/bilal/${APP_NAME}" 2>/dev/null || true
    chmod +x "/home/bilal/${APP_NAME}" 2>/dev/null || true
    log_info "Yerel kullanıcı kopyası da güncellendi: /home/bilal/${APP_NAME}"
fi

# 5. Temizlik (Build kalıntıları)
log_step "Derleme kalıntıları temizleniyor..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist"
find "$SCRIPT_DIR" -maxdepth 1 -name "*.spec" ! -name "VortexDL.spec" -exec rm -f {} + 2>/dev/null || true
log_success "Geçici build kalıntıları temizlendi."

echo ""
echo -e "${CLR_GREEN}${CLR_BOLD}============================================================${CLR_RESET}"
echo -e "${CLR_GREEN}${CLR_BOLD}🎉 Dağıtım Başarıyla Tamamlandı!${CLR_RESET}"
echo -e "${CLR_CYAN}Uygulama Konumu:${CLR_RESET} ${USB_TARGET_DIR}/${APP_NAME}"
echo -e "${CLR_GREEN}${CLR_BOLD}============================================================${CLR_RESET}"
