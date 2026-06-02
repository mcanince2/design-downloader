# Design Downloader Chrome Extension

Behance, Dribbble ve Pinterest'ten tasarim indirmek icin Chrome extension ve backend server.

---

## Icindekiler

- [Kurulum](#kurulum)
- [Kullanim](#kullanim)
- [Test Etme (Development)](#test-etme-development)
- [Production'a Alma](#productiona-alma)
- [Sorun Giderme](#sorun-giderme)

---

## Kurulum

### 1. Backend Server Kurulumu

```bash
cd path/to/design-downloader

# Gerekli paketleri yukle
pip install flask flask-cors requests beautifulsoup4 selenium webdriver-manager pillow

# Server'i baslat
python server.py
```

Server `http://localhost:5200` adresinde calisacak.

### 2. Chrome Extension Yukleme (Development Mode)

1. Chrome'da `chrome://extensions/` adresine git
2. Sag ustteki **"Developer mode"** (Gelistirici modu) toggle'ini ac
3. **"Load unpacked"** (Paketlenmemis uzanti yukle) butonuna tikla
4. `extension` klasorunu sec:
   ```
   path/to/design-downloader/extension
   ```
5. Extension yuklendi! Toolbar'da mor ikonu goreceksin

---

## Kullanim

### Extension Popup
1. Extension ikonuna tikla
2. URL kutusuna Behance/Dribbble/Pinterest linki yapistir
3. **DOWNLOAD** butonuna tikla
4. Kuyrukta indirme durumunu takip et

### Sag Tik Menusu
1. Behance/Dribbble/Pinterest sayfasinda sag tikla
2. **"Download with Design Downloader"** sec
3. Otomatik olarak kuyruga eklenir

### Current Page
1. Bir tasarim sayfasindayken extension'i ac
2. **CURRENT PAGE** butonuna tikla
3. Mevcut sayfa otomatik algilaniyor

---

## Test Etme (Development)

### 1. Local Test

```bash
# Terminal 1: Server'i baslat
cd path/to/design-downloader
python server.py

# Server calistigini kontrol et
curl http://localhost:5200/api/status
# Beklenen cevap: {"status": "running", ...}
```

### 2. Extension Test

1. Chrome'da extension'i yukle (yukardaki adimlari takip et)
2. Extension popup'ini ac
3. **Status indicator** "ONLINE" (yesil) olmali
4. Test URL'leri dene:
   - Behance: `https://www.behance.net/gallery/123456/example`
   - Dribbble: `https://dribbble.com/shots/12345678-example`
   - Pinterest: `https://www.pinterest.com/pin/123456/`

### 3. Console Hatalari Kontrolu

1. Extension popup'ta sag tikla > **"Inspect"**
2. Console sekmesinde hatalari kontrol et
3. Network sekmesinde API isteklerini izle

### 4. Server Loglarini Izle

Server terminalde tum API isteklerini loglar:
```
127.0.0.1 - - [23/Jan/2026 14:30:22] "POST /api/download HTTP/1.1" 200 -
```

---

## Production'a Alma

### Chrome Web Store'a Yukleme

#### 1. Developer Hesabi Olustur

1. [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole) adresine git
2. Google hesabinla giris yap
3. **$5 tek seferlik kayit ucreti** ode
4. Developer agreement'i kabul et

#### 2. Extension'i Paketle

```bash
cd path/to/design-downloader

# Extension klasorunu zipli
cd extension
zip -r ../design-downloader-extension.zip . -x "*.DS_Store" -x "__MACOSX/*"
cd ..

# Dosya olusturuldu:
# design-downloader-extension.zip
```

#### 3. Store'a Yukle

1. Developer Dashboard'da **"New Item"** (Yeni oge) tikla
2. ZIP dosyasini yukle
3. Gerekli bilgileri doldur:

**Store Listing:**
| Alan | Deger |
|------|-------|
| Name | Design Downloader |
| Summary | Download designs from Behance, Dribbble & Pinterest |
| Category | Productivity |
| Language | English |

**Screenshots (gerekli):**
- 1280x800 veya 640x400 boyutlarinda minimum 1 screenshot
- Store listing icin 440x280 promotional tile (opsiyonel)

**Privacy:**
- Privacy policy URL'si (gerekli)
- Single purpose description yazin

4. **"Submit for Review"** tikla
5. Google incelemesi 1-3 gun surebilir

#### 4. Server Hosting (Production)

Local server yerine production icin:

**Secenek A: VPS (Digital Ocean, Linode, AWS)**
```bash
# Server'da
pip install gunicorn

# Production'da calistir
gunicorn -w 4 -b 0.0.0.0:5200 server:app
```

**Secenek B: Heroku**
```bash
# Procfile olustur
echo "web: gunicorn server:app" > Procfile

# Heroku'ya deploy et
heroku create design-downloader-api
git push heroku main
```

**Secenek C: Railway.app**
1. GitHub repo'suna push et
2. Railway.app'e bagla
3. Otomatik deploy

> **Not:** Production'da `extension/popup.js` ve `extension/background.js` dosyalarindaki `DEFAULT_SERVER_URL`'i guncelle.

---

## Dosya Yapisi

```
Behancedownloader/
├── server.py                 # Backend API server
├── extension/                # Chrome extension
│   ├── manifest.json         # Extension manifest (v3)
│   ├── popup.html            # Popup UI
│   ├── popup.css             # Cyberpunk styles
│   ├── popup.js              # Popup logic
│   ├── background.js         # Service worker
│   └── icons/                # Extension icons
│       ├── icon.svg
│       ├── icon16.png
│       ├── icon32.png
│       ├── icon48.png
│       └── icon128.png
├── main_app.py               # Original desktop app
├── requirements.txt          # Python dependencies
└── EXTENSION_GUIDE.md        # Bu dosya
```

---

## API Endpoints

| Method | Endpoint | Aciklama |
|--------|----------|----------|
| GET | `/api/status` | Server durumu |
| POST | `/api/detect` | URL platform tespiti |
| POST | `/api/download` | Indirme kuyruguna ekle |
| GET | `/api/downloads` | Tum indirmeleri listele |
| GET | `/api/download/:id` | Tek indirme durumu |
| POST | `/api/search` | Platform arama |
| POST | `/api/clear` | Tamamlananlari temizle |
| GET | `/api/settings` | Ayarlari getir |
| POST | `/api/settings` | Ayarlari guncelle |

---

## Sorun Giderme

### "OFFLINE" Gozukuyor

1. Server calistigindan emin ol:
   ```bash
   curl http://localhost:5000/api/status
   ```
2. Port 5000 baska bir uygulama tarafindan kullaniliyor olabilir:
   ```bash
   lsof -i :5200
   ```

### Indirme Baslamiyor

1. Chrome driver guncel mi kontrol et
2. Selenium WebDriver log'larini kontrol et
3. Hedef site'nin yapisi degismis olabilir

### Extension Yuklenmiyor

1. `manifest.json` syntax hatasiz olmali
2. Tum icon dosyalarinin mevcut oldugundan emin ol
3. Chrome'u yeniden baslat

### CORS Hatasi

Server'da CORS aktif olmali:
```python
from flask_cors import CORS
CORS(app)
```

---

## Requirements

### Python (requirements.txt)
```
flask>=2.0.0
flask-cors>=3.0.0
requests>=2.28.0
beautifulsoup4>=4.11.0
selenium>=4.8.0
webdriver-manager>=3.8.0
pillow>=9.4.0
```

### Chrome
- Chrome 88+ (Manifest V3 destegi icin)

---

## Lisans

MIT License - Istediginiz gibi kullanin!
