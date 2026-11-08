# 🎬 VideoDownloader — Kurulum & Kullanım Kılavuzu

> Zorin OS (Ubuntu tabanlı) için hazırlanmıştır.

## Proje Yapısı

```
VideoDownloader/
├── downloader.py          ← Ana uygulama
├── requirements.txt       ← Python bağımlılıkları
└── VideoDownloader.desktop ← Masaüstü kısayolu (opsiyonel)
```

---

## 1. Sistem Bağımlılıklarını Kur

```bash
# Paket listesini güncelle
sudo apt update

# ffmpeg (video/ses birleştirme için zorunlu)
sudo apt install -y ffmpeg

# Python 3 ve pip (büyük ihtimalle zaten kurulu)
sudo apt install -y python3 python3-pip python3-tk

# Tkinter GTK desteği (CustomTkinter için önerilir)
sudo apt install -y python3-pil python3-pil.imagetk
```

---

## 2. Python Bağımlılıklarını Kur

```bash
cd /home/bilal/.gemini/antigravity/scratch/VideoDownloader

# Sanal ortam oluştur (önerilir ama zorunlu değil)
python3 -m venv .venv
source .venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

> [!TIP]
> Sanal ortam kullanıyorsan her seferinde `source .venv/bin/activate` komutunu çalıştırman gerekir.
> Bunu atlamak istersen sanal ortamsız `pip install --user -r requirements.txt` de kullanabilirsin.

---

## 3. Uygulamayı Çalıştır

```bash
cd /home/bilal/.gemini/antigravity/scratch/VideoDownloader

# Sanal ortam aktifse:
python3 downloader.py

# Sanal ortamsız kurduysanız:
python3 downloader.py
```

---

## 4. Masaüstü Kısayolu Oluştur (Opsiyonel)

Uygulamayı menüden veya masaüstünden başlatmak istersen:

```bash
# .desktop dosyasını uygulamalar dizinine kopyala
cp VideoDownloader.desktop ~/.local/share/applications/

# Yürütme iznini ver
chmod +x ~/.local/share/applications/VideoDownloader.desktop

# Önbelleği güncelle
update-desktop-database ~/.local/share/applications/
```

Artık Zorin OS uygulama menüsünde "VideoDownloader" görünür.

---

## 5. Hızlı Başlatma Alias'ı (Opsiyonel)

```bash
# ~/.bashrc veya ~/.zshrc dosyasına ekle:
alias videodownloader='cd /home/bilal/.gemini/antigravity/scratch/VideoDownloader && source .venv/bin/activate && python3 downloader.py'

# Değişikliği uygula:
source ~/.bashrc
```

Artık terminalde `videodownloader` yazarak uygulamayı açabilirsin.

---

## 6. Desteklenen Platformlar

| Platform | Durum |
|---|---|
| YouTube | ✅ Tam destek |
| Instagram (Reels, Post) | ✅ Destekleniyor |
| TikTok | ✅ Destekleniyor |
| Twitter / X | ✅ Destekleniyor |
| Vimeo | ✅ Destekleniyor |
| Facebook | ✅ Destekleniyor |
| Dailymotion | ✅ Destekleniyor |
| Reddit | ✅ Destekleniyor |
| Twitch (klipler) | ✅ Destekleniyor |
| 1000+ platform | ✅ yt-dlp desteği |

---

## 7. Özellik Özeti

| Özellik | Detay |
|---|---|
| **İndirme motoru** | yt-dlp (en güncel) |
| **Video formatı** | MP4 (video+ses ffmpeg ile birleştirilir) |
| **Ses formatı** | MP3 (320kbps, FFmpegExtractAudio) |
| **Kalite seçenekleri** | En Yüksek / 1080p / 720p / 480p / 360p |
| **Canlı ilerleme** | % + hız + ETA göstergesi |
| **UI donması** | Yok — threading ile önlenmiş |
| **İptal** | Destekleniyor |
| **Kayıt yeri** | Seçilebilir (varsayılan ~/Downloads) |
| **Tema** | Koyu (dark mode) |

---

## 8. Sorun Giderme

### `ModuleNotFoundError: No module named 'customtkinter'`
```bash
pip install customtkinter
```

### `ffmpeg bulunamadı` / birleştirme hatası
```bash
which ffmpeg          # /usr/bin/ffmpeg çıktısı vermeli
sudo apt install ffmpeg
```

### `ModuleNotFoundError: No module named 'yt_dlp'`
```bash
pip install yt-dlp
# veya sanal ortam aktif değilse:
pip install --user yt-dlp
```

### yt-dlp güncellemesi (site değişikliklerinde)
```bash
pip install -U yt-dlp
```

> [!IMPORTANT]
> Instagram ve TikTok indirmeleri zaman zaman oturum açmayı gerektirebilir.
> Çerezlerle oturum desteği için `yt-dlp --cookies-from-browser firefox` yöntemini kullanabilirsiniz (uygulama dışı, terminal üzerinden).

> [!WARNING]
> Telif hakkıyla korunan içerikleri yalnızca kişisel kullanım için ve yasal çerçevede indirin.

