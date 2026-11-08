#!/usr/bin/env bash
# =============================================================
#  VideoDownloader — GitHub Yayınlama Kurulum Betiği
#  setup_git_auth.sh
#
#  Bu betik tek seferlik çalıştırılır:
#    chmod +x setup_git_auth.sh
#    ./setup_git_auth.sh
#
#  Yapacakları:
#    1. GitHub kullanıcı adını sorar (tek sefer)
#    2. SSH açık anahtarını GitHub'a nasıl ekleneceğini gösterir
#    3. GitHub reposunu oluşturur (API üzerinden)
#    4. Tüm commit ve tag'leri push eder
#    5. gh CLI kurulursa Release oluşturur
# =============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}▶${RESET} $*"; }
success() { echo -e "${GREEN}✅${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠️ ${RESET} $*"; }
error()   { echo -e "${RED}❌${RESET} $*" >&2; exit 1; }
box()     { echo -e "${BOLD}════════════════════════════════════════${RESET}"; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_KEY="$HOME/.ssh/id_ed25519_github"
SSH_PUB="$SSH_KEY.pub"
REPO_NAME="VideoDownloader"
BINARY="$PROJECT_DIR/dist/VideoDownloader"

box
echo -e "  🔑  VideoDownloader GitHub Kurulum Betiği"
box
echo ""

# ── 1. GitHub kullanıcı adı ──────────────────────────────────
if [ -z "${GITHUB_USER:-}" ]; then
  read -rp "  GitHub kullanıcı adın: " GITHUB_USER
fi
[ -z "$GITHUB_USER" ] && error "GitHub kullanıcı adı boş olamaz!"
success "Kullanıcı: $GITHUB_USER"

# ── 2. SSH anahtarı kontrolü ─────────────────────────────────
if [ ! -f "$SSH_PUB" ]; then
  info "SSH anahtarı oluşturuluyor…"
  ssh-keygen -t ed25519 -C "videodownloader-github" -f "$SSH_KEY" -N ""
fi
success "SSH açık anahtarı hazır."

# ── 3. GitHub'a SSH anahtarı ekleme yönlendirmesi ────────────
echo ""
box
echo -e "  📋  ADIM: GitHub'a SSH Anahtarı Ekle"
box
echo ""
echo -e "  Tarayıcıda aç: ${CYAN}https://github.com/settings/ssh/new${RESET}"
echo ""
echo -e "  'Key' alanına şunu yapıştır:"
echo ""
echo -e "  ${YELLOW}$(cat "$SSH_PUB")${RESET}"
echo ""
echo -e "  'Title' olarak 'VideoDownloader-ZorinOS' yaz."
echo ""

# GitHub'a SSH erişimi test et (zaten eklendiyse geç)
SSH_OK=false
info "Mevcut SSH erişimi test ediliyor…"
if ssh -o BatchMode=yes -o ConnectTimeout=8 -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  SSH_OK=true
  success "SSH erişimi zaten aktif! Anahtar eklemeye gerek yok."
else
  warn "SSH henüz doğrulanamadı."
  read -rp "  Anahtarı GitHub'a ekledikten sonra Enter'a bas…" _WAIT
  # Tekrar test et
  if ssh -o BatchMode=yes -o ConnectTimeout=8 -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    SSH_OK=true
    success "SSH erişimi doğrulandı!"
  else
    warn "SSH doğrulanamadı. PAT (token) yöntemi deneniyor…"
  fi
fi

# ── 4. PAT (Personal Access Token) alternatifi ───────────────
USE_PAT=false
if ! $SSH_OK; then
  echo ""
  box
  echo -e "  🔐  GitHub Personal Access Token (PAT) Yöntemi"
  box
  echo ""
  echo -e "  Token oluştur: ${CYAN}https://github.com/settings/tokens/new${RESET}"
  echo -e "  Scope: ${YELLOW}repo${RESET} (tam repo erişimi)"
  echo ""
  read -rsp "  Token'ı buraya yapıştır (gizli): " GH_PAT
  echo ""
  [ -z "$GH_PAT" ] && error "Token boş olamaz!"

  # Token'ı git credential store'a kaydet (şifreli değil ama pratik)
  git config --global credential.helper store
  printf "https://%s:%s@github.com\n" "$GITHUB_USER" "$GH_PAT" \
    > "$HOME/.git-credentials"
  chmod 600 "$HOME/.git-credentials"
  USE_PAT=true
  success "PAT credential store'a kaydedildi."
fi

# ── 5. GitHub repo oluştur (API) ──────────────────────────────
echo ""
info "GitHub reposu kontrol ediliyor / oluşturuluyor…"

CREATE_PAYLOAD="{
  \"name\": \"${REPO_NAME}\",
  \"description\": \"Modern GUI video downloader powered by yt-dlp — Zorin OS / Linux\",
  \"private\": false,
  \"has_issues\": true,
  \"has_wiki\": false
}"

if $USE_PAT; then
  AUTH_HEADER="Authorization: token $GH_PAT"
elif [ -n "${GITHUB_TOKEN:-}" ]; then
  AUTH_HEADER="Authorization: token $GITHUB_TOKEN"
else
  AUTH_HEADER=""
fi

if [ -n "$AUTH_HEADER" ]; then
  HTTP_STATUS=$(curl -s -o /tmp/gh_create.json -w "%{http_code}" \
    -X POST https://api.github.com/user/repos \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$CREATE_PAYLOAD")

  if [ "$HTTP_STATUS" = "201" ]; then
    success "GitHub reposu oluşturuldu: https://github.com/$GITHUB_USER/$REPO_NAME"
  elif [ "$HTTP_STATUS" = "422" ]; then
    warn "Repo zaten mevcut: https://github.com/$GITHUB_USER/$REPO_NAME"
  else
    warn "Repo oluşturma yanıtı: $HTTP_STATUS"
    cat /tmp/gh_create.json 2>/dev/null | python3 -m json.tool 2>/dev/null | head -10 || true
  fi
else
  warn "Token yok — repo manuel oluşturulmalı:"
  warn "  https://github.com/new → isim: $REPO_NAME"
  read -rp "  Repoyu oluşturduktan sonra Enter'a bas…" _WAIT2
fi

# ── 6. Remote URL ayarla ve push et ──────────────────────────
echo ""
info "Git remote yapılandırılıyor…"
cd "$PROJECT_DIR"

git remote remove origin 2>/dev/null || true

if $SSH_OK; then
  REMOTE_URL="git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
elif $USE_PAT; then
  REMOTE_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
else
  REMOTE_URL="git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
fi

git remote add origin "$REMOTE_URL"
success "Remote URL: $REMOTE_URL"

echo ""
info "main dalı push ediliyor…"
git push -u origin main
success "main push tamamlandı."

echo ""
info "v1.0.0 tag'ı push ediliyor…"
git push origin v1.0.0
success "Tag push tamamlandı."

# ── 7. GitHub Release (token varsa) ──────────────────────────
if [ -n "${AUTH_HEADER:-}" ] && [ -f "$BINARY" ]; then
  echo ""
  info "GitHub Release v1.0.0 oluşturuluyor…"

  RELEASE_PAYLOAD="{
    \"tag_name\": \"v1.0.0\",
    \"name\": \"v1.0.0 — Kararlı Sürüm\",
    \"body\": \"## VideoDownloader v1.0.0\\n\\nModern GUI video indirme uygulaması.\\n\\n### Özellikler\\n- yt-dlp motoru (1000+ platform)\\n- ffmpeg ile video+ses birleştirme\\n- MP4 / MP3 format seçimi\\n- Kalite seçici (En Yüksek, 1080p, 720p...)\\n- Canlı ilerleme çubuğu\\n\\n### Kurulum\\n\\`\\`\\`bash\\nchmod +x VideoDownloader\\n./VideoDownloader\\n\\`\\`\\`\",
    \"draft\": false,
    \"prerelease\": false
  }"

  RELEASE_STATUS=$(curl -s -o /tmp/gh_release.json -w "%{http_code}" \
    -X POST "https://api.github.com/repos/${GITHUB_USER}/${REPO_NAME}/releases" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$RELEASE_PAYLOAD")

  if [ "$RELEASE_STATUS" = "201" ]; then
    UPLOAD_URL=$(python3 -c "import json,sys; d=json.load(open('/tmp/gh_release.json')); print(d['upload_url'].split('{')[0])" 2>/dev/null)
    success "Release oluşturuldu!"

    if [ -n "$UPLOAD_URL" ] && [ -f "$BINARY" ]; then
      info "Binary yükleniyor…"
      curl -s -o /dev/null -w "HTTP %{http_code}\n" \
        -X POST "${UPLOAD_URL}?name=VideoDownloader-linux-x86_64" \
        -H "Content-Type: application/octet-stream" \
        -H "$AUTH_HEADER" \
        --data-binary "@$BINARY"
      success "Binary GitHub Release'e yüklendi."
    fi
  else
    warn "Release oluşturma yanıtı: $RELEASE_STATUS"
  fi
fi

# ── 8. Masaüstü entegrasyonu ─────────────────────────────────
echo ""
info "Zorin OS uygulama menüsü entegrasyonu…"
DESKTOP_DST="$HOME/.local/share/applications/videodownloader.desktop"
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_DST" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=VideoDownloader
GenericName=Video Downloader
Comment=Modern GUI video downloader powered by yt-dlp
Exec=$BINARY
Icon=$PROJECT_DIR/icon.png
Terminal=false
StartupNotify=true
Categories=AudioVideo;Network;
Keywords=video;download;youtube;instagram;tiktok;yt-dlp;
MimeType=x-scheme-handler/videodownloader;
DESKTOP

chmod +x "$DESKTOP_DST"
update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
success "Uygulama menüsü kısayolu oluşturuldu: $DESKTOP_DST"

# ── Son rapor ─────────────────────────────────────────────────
echo ""
box
echo -e "  🎉  TÜM İŞLEMLER TAMAMLANDI!"
box
echo ""
echo -e "  Repo      : ${CYAN}https://github.com/$GITHUB_USER/$REPO_NAME${RESET}"
echo -e "  SSH Key   : ${CYAN}$SSH_PUB${RESET}"
echo -e "  Binary    : ${CYAN}$BINARY${RESET}"
echo -e "  .desktop  : ${CYAN}$DESKTOP_DST${RESET}"
echo ""
success "VideoDownloader başarıyla GitHub'da yayınlandı!"
