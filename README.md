<div align="center">

<img src="icon.png" alt="VideoDownloader Logo" width="96"/>

# 🎬 VideoDownloader

**Modern, koyu temalı masaüstü video indirme uygulaması**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![yt-dlp](https://img.shields.io/badge/powered%20by-yt--dlp-red.svg)](https://github.com/yt-dlp/yt-dlp)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](https://zorin.com/os/)

</div>

---

## 📌 Proje Hakkında

**VideoDownloader**, [yt-dlp](https://github.com/yt-dlp/yt-dlp) motorunu kullanan, **Zorin OS** ve tüm **Ubuntu/Debian tabanlı** Linux dağıtımları için geliştirilmiş modern bir masaüstü video indirme uygulamasıdır. [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) ile inşa edilmiş koyu temalı arayüzü sayesinde YouTube, Instagram, TikTok ve 1000'den fazla platformdan video veya ses indirebilirsiniz.

### ✨ Özellikler

| Özellik | Detay |
|---|---|
| 🎥 **Çoklu platform** | YouTube, Instagram, TikTok, Twitter/X, Vimeo, Reddit ve [1000+ site](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) |
| 🎞️ **MP4 & MP3** | Video (ffmpeg ile birleştirme) veya ses (MP3, 320 kbps) |
| 📊 **Kalite seçimi** | En Yüksek · 1080p · 720p · 480p · 360p |
| ⚡ **Non-blocking UI** | Threading ile donmayan arayüz |
| 📈 **Canlı ilerleme** | % + hız (MB/s) + ETA göstergesi |
| ⏹️ **İptal desteği** | İndirme ortasında güvenli durdurma |
| 📁 **Dizin seçici** | Kayıt konumunu serbestçe belirle |
| 🌙 **Koyu tema** | Dark mode varsayılan, CustomTkinter ile |

---

## 🖥️ Desteklenen Sistemler

| İşletim Sistemi | Durum |
|---|---|
| Zorin OS 16 / 17 | ✅ Birincil hedef |
| Ubuntu 22.04 / 24.04 LTS | ✅ Tam destek |
| Linux Mint 21+ | ✅ Test edildi |
| Debian 12 (Bookworm) | ✅ Destekleniyor |
| Diğer Debian/Ubuntu tabanlı | ⚠️ Büyük ihtimalle çalışır |
| Windows / macOS | ❌ Resmi destek yok |

---

## ⚙️ Sistem Gereksinimleri

- **Python** ≥ 3.10
- **ffmpeg** (video+ses birleştirme için **zorunlu**)
- **python3-tk** (Tkinter GUI desteği)
- İnternet bağlantısı

---

## 🚀 Kurulum ve Çalıştırma

### Yöntem 1 — Otomatik Kurulum (Önerilen)

```bash
# 1. Repoyu klonla
git clone https://github.com/kullaniciadiniz/VideoDownloader.git
cd VideoDownloader

# 2. Kurulum scriptini çalıştır (her şeyi otomatik halleder)
chmod +x setup_and_run.sh
./setup_and_run.sh
```

Script şunları yapar:
- `ffmpeg`, `python3-tk`, `python3-venv` yoksa `sudo apt install` ile kurar
- Proje dizininde `.venv` sanal ortamı oluşturur
- Tüm Python bağımlılıklarını kurar
- Zorin OS uygulama menüsüne kısayol ekler
- Uygulamayı başlatır

---

### Yöntem 2 — Manuel Kurulum

```bash
# 1. Sistem bağımlılıkları
sudo apt update
sudo apt install -y ffmpeg python3-tk python3-pip python3-venv

# 2. Repoyu klonla
git clone https://github.com/kullaniciadiniz/VideoDownloader.git
cd VideoDownloader

# 3. Sanal ortam oluştur ve aktifleştir
python3 -m venv .venv
source .venv/bin/activate

# 4. Python paketlerini kur
pip install -r requirements.txt

# 5. Uygulamayı başlat
python3 downloader.py
```

---

### Yöntem 3 — AppImage (Derleme gerekmez)

> GitHub Releases sayfasından en güncel `.AppImage` dosyasını indir.

```bash
# İndir ve çalıştır
chmod +x VideoDownloader-x86_64.AppImage
./VideoDownloader-x86_64.AppImage
```

AppImage'i kendin derlemek için bkz. [Derleme Kılavuzu](#-derleme-ve-paketleme).

---

## 📦 Derleme ve Paketleme

### PyInstaller ile Binary Üretme

```bash
# Geliştirme bağımlılıklarını kur
source .venv/bin/activate
pip install -r requirements-dev.txt

# Derleme betiğini çalıştır
chmod +x build_linux.sh
./build_linux.sh
```

Çıktı dosyaları `dist/` dizininde üretilir:
- `dist/VideoDownloader` — tek dosya çalıştırılabilir
- `dist/VideoDownloader-x86_64.AppImage` — taşınabilir AppImage (appimagetool gerekir)

---

## 📂 Proje Yapısı

```
VideoDownloader/
├── downloader.py              ← Ana uygulama (CustomTkinter + yt-dlp)
├── requirements.txt           ← Runtime Python bağımlılıkları
├── requirements-dev.txt       ← Geliştirme/derleme bağımlılıkları
├── setup_and_run.sh           ← Kurulum + başlatma scripti
├── build_linux.sh             ← PyInstaller + AppImage derleme scripti
├── VideoDownloader.desktop    ← Zorin OS / GNOME uygulama menüsü kısayolu
├── VideoDownloader_Kurulum.md ← Türkçe kurulum kılavuzu
├── icon.png                   ← Uygulama ikonu
├── LICENSE                    ← GNU GPL v3.0
├── .gitignore                 ← Git hariç tutma kuralları
└── README.md                  ← Bu dosya
```

---

## 🔧 Sorun Giderme

### `ffmpeg bulunamadı` / birleştirme hatası
```bash
sudo apt install ffmpeg
which ffmpeg   # /usr/bin/ffmpeg çıktısı vermeli
```

### `ModuleNotFoundError: No module named 'customtkinter'`
```bash
source .venv/bin/activate
pip install customtkinter
```

### `No module named '_tkinter'`
```bash
sudo apt install python3-tk
```

### yt-dlp siteyi desteklemiyor / güncel değil
```bash
source .venv/bin/activate
pip install -U yt-dlp
```

### Instagram / TikTok indirme hatası (giriş gerekiyor)
```bash
# Tarayıcı çerezleri ile kimlik doğrulama (uygulama dışı)
yt-dlp --cookies-from-browser firefox "URL"
```

---

## 🤝 Katkıda Bulunma

1. Bu repoyu **fork**'layın
2. Özellik dalı açın: `git checkout -b feature/yeni-ozellik`
3. Değişikliklerinizi commit edin: `git commit -m 'feat: yeni özellik eklendi'`
4. Dalı push edin: `git push origin feature/yeni-ozellik`
5. **Pull Request** açın

---

## ⚖️ Yasal Sorumluluk Reddi

> **UYARI / DISCLAIMER**
>
> Bu yazılım yalnızca **kişisel kullanım** ve **Creative Commons / telif hakkı bulunmayan** içerikler için tasarlanmıştır. Telif hakkıyla korunan içerikleri sahiplerinin izni olmadan indirmek, ilgili ülkelerin telif hakkı yasalarını ihlal edebilir.
>
> Yazılımın kullanımından doğabilecek hukuki sonuçların sorumluluğu tamamen kullanıcıya aittir. Geliştiriciler herhangi bir yasal sorumluluk kabul etmez.
>
> YouTube, Instagram ve diğer platformların **Hizmet Şartları**'nı (Terms of Service) incelemeniz ve bu kurallara uymanız tavsiye edilir.

---

## 📄 Lisans

Bu proje **GNU General Public License v3.0** altında lisanslanmıştır.
Ayrıntılar için [LICENSE](LICENSE) dosyasına bakın.

---

<div align="center">
<sub>Built with ❤️ using <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a>, <a href="https://github.com/TomSchimansky/CustomTkinter">CustomTkinter</a> and <a href="https://ffmpeg.org/">ffmpeg</a></sub>
</div>
