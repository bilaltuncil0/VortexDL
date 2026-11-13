#!/usr/bin/env bash
# ==============================================================================
# VortexDL — Bulut Dağıtım Paketi Oluşturucu (Cloud Release Bundler)
# ==============================================================================
# Uygulamayı tek parça bağımsız ikili dosya (standalone executable) haline getirip
# .zip arşivine paketler ve Google Drive, iCloud, OneDrive veya yerel paylaşımlara
# elle yüklenmeye hazır şekilde Masaüstüne bırakır.
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

# --- Dizin ve Paket Tanımları ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="VortexDL"
PACKAGE_DIR="VortexDL_v1.0_Portable"
ZIP_NAME="VortexDL_v1.0_Linux.zip"
VENV_DIR="$SCRIPT_DIR/.venv"

echo -e "${CLR_CYAN}${CLR_BOLD}"
echo "============================================================"
echo "      ☁️  VortexDL — Bulut Dağıtım Paketi Oluşturucu         "
echo "============================================================"
echo -e "${CLR_RESET}"

# 1. Ortam ve Bağımlılık Kontrolü
log_step "Ortam ve araç bağımlılıkları denetleniyor..."
if [ -d "$VENV_DIR" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    log_info "Sanal ortam aktifleştirildi (.venv)"
fi

if ! command -v pyinstaller &>/dev/null; then
    log_error "PyInstaller bulunamadı! Lütfen 'pip install pyinstaller' çalıştırın."
    exit 1
fi

if ! command -v zip &>/dev/null; then
    log_error "'zip' komutu bulunamadı! Lütfen sistem paket yöneticisinden 'zip' paketini yükleyin."
    exit 1
fi

# Dil dosyalarını derle (varsa)
if command -v msgfmt &>/dev/null; then
    log_info "Yerelleştirme katalogları derleniyor (.po -> .mo)..."
    python3 -c "
import subprocess, os
for lang in ['tr_TR', 'en_US', 'de_DE', 'fr_FR', 'it_IT', 'ar_SA', 'zh_CN']:
    po = os.path.join('locales', lang, 'LC_MESSAGES', 'videodownloader.po')
    mo = os.path.join('locales', lang, 'LC_MESSAGES', 'videodownloader.mo')
    if os.path.exists(po):
        subprocess.run(['msgfmt', po, '-o', mo], check=False)
" 2>/dev/null || true
fi

# 2. PyInstaller ile Derleme
log_step "Uygulama derleniyor..."
log_info "Mod: Tek dosya (--onefile), pencere modu (--windowed, konsol penceresiz)"

if [ -f "VortexDL.spec" ]; then
    log_info "VortexDL.spec yapılandırması kullanılarak derleniyor..."
    pyinstaller --noconfirm --clean VortexDL.spec
else
    log_info "Varsayılan parametrelerle PyInstaller derlemesi başlatılıyor..."
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
    log_error "Derleme başarısız! '${COMPILED_BIN}' dosyası üretilemedi."
    exit 1
fi
log_success "Uygulama başarıyla derlendi: ${COMPILED_BIN} ($(du -sh "$COMPILED_BIN" | cut -f1))"

# 3. Geçici Paket Klasörünün Oluşturulması
log_step "Taşınabilir paket hazırlanıyor (${PACKAGE_DIR})..."
rm -rf "$SCRIPT_DIR/$PACKAGE_DIR"
mkdir -p "$SCRIPT_DIR/$PACKAGE_DIR"

cp -f "$COMPILED_BIN" "$SCRIPT_DIR/$PACKAGE_DIR/$APP_NAME"
chmod +x "$SCRIPT_DIR/$PACKAGE_DIR/$APP_NAME"

if [ -f "$SCRIPT_DIR/README.md" ]; then
    cp -f "$SCRIPT_DIR/README.md" "$SCRIPT_DIR/$PACKAGE_DIR/README.md"
    log_info "README.md pakete dahil edildi."
fi

# 4. Zip Arşivleme
log_step "Zip arşivi sıkıştırılıyor (${ZIP_NAME})..."
rm -f "$SCRIPT_DIR/$ZIP_NAME"
zip -r -q "$SCRIPT_DIR/$ZIP_NAME" "$PACKAGE_DIR"
log_success "Zip arşivi oluşturuldu: ${ZIP_NAME} ($(du -sh "$SCRIPT_DIR/$ZIP_NAME" | cut -f1))"

# 5. Arşivi Hedef Konuma (OneDrive veya Masaüstü) Taşıma
log_step "Arşiv hedef konuma aktarılıyor..."
ONEDRIVE_BASE="$HOME/OneDrive"

if [ -d "$ONEDRIVE_BASE" ]; then
    ONEDRIVE_BACKUP_DIR="$ONEDRIVE_BASE/VortexDL_Yedekler"
    mkdir -p "$ONEDRIVE_BACKUP_DIR"
    TARGET_ZIP_PATH="$ONEDRIVE_BACKUP_DIR/$ZIP_NAME"
    mv -f "$SCRIPT_DIR/$ZIP_NAME" "$TARGET_ZIP_PATH"
    log_success "Zip arşivi OneDrive/VortexDL_Yedekler klasörüne kopyalandı ve bulut eşitlemesi için hazır!"
    log_info "Konum: ${TARGET_ZIP_PATH}"
else
    # Fallback: Masaüstü Konumu (~/Masaüstü veya ~/Desktop)
    if [ -d "$HOME/Masaüstü" ]; then
        FALLBACK_DIR="$HOME/Masaüstü"
    elif [ -d "$HOME/Desktop" ]; then
        FALLBACK_DIR="$HOME/Desktop"
    else
        FALLBACK_DIR="$HOME/Masaüstü"
        mkdir -p "$FALLBACK_DIR"
    fi
    TARGET_ZIP_PATH="$FALLBACK_DIR/$ZIP_NAME"
    mv -f "$SCRIPT_DIR/$ZIP_NAME" "$TARGET_ZIP_PATH"
    log_warn "OneDrive klasörü bulunamadı, Zip arşivi Masaüstüne çıkarıldı."
    log_info "Konum: ${TARGET_ZIP_PATH}"
fi

# 6. Temizlik
log_step "Derleme kalıntıları ve geçici dosyalar temizleniyor..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist" "$SCRIPT_DIR/$PACKAGE_DIR"
find "$SCRIPT_DIR" -maxdepth 1 -name "*.spec" ! -name "VortexDL.spec" -exec rm -f {} + 2>/dev/null || true
log_success "Tüm geçici dosyalar temizlendi."

echo ""
echo -e "${CLR_GREEN}${CLR_BOLD}============================================================${CLR_RESET}"
echo -e "${CLR_GREEN}${CLR_BOLD}🎉 Bulut Dağıtım Paketi Hazır!${CLR_RESET}"
echo -e "${CLR_CYAN}Arşiv Dosyası:${CLR_RESET} ${TARGET_ZIP_PATH}"
echo -e "${CLR_GREEN}${CLR_BOLD}============================================================${CLR_RESET}"
