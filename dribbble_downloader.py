#!/usr/bin/env python3
"""
Dribbble Shot Downloader
Modern GUI application to download images from Dribbble shots
"""

import os
import re
import sys
import json
import time
import queue
import threading
import requests
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime

try:
    import customtkinter as ctk
    from CTkMessagebox import CTkMessagebox
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install customtkinter CTkMessagebox")
    import customtkinter as ctk
    from CTkMessagebox import CTkMessagebox

from tkinter import filedialog
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class DribbbleDownloader:
    """Handles the scraping and downloading of Dribbble shot images"""

    def __init__(self):
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://dribbble.com/',
        })

    def init_driver(self):
        """Initialize headless Chrome driver"""
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                print(f"Chrome driver error: {e}")
                raise

    def close_driver(self):
        """Close the Chrome driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def extract_shot_info(self, url):
        """Extract shot ID and name from Dribbble URL"""
        # Pattern: /shots/12345678-shot-name or /shots/12345678
        match = re.search(r'/shots/(\d+)(?:-([^/?]+))?', url)
        if match:
            shot_id = match.group(1)
            shot_name = match.group(2) if match.group(2) else f"shot_{shot_id}"
            return shot_id, shot_name
        return None, None

    def get_shot_images(self, url, progress_callback=None):
        """Scrape all images from a Dribbble shot"""
        images = []

        try:
            self.init_driver()

            if progress_callback:
                progress_callback("Sayfa yükleniyor...")

            self.driver.get(url)
            time.sleep(3)  # Wait for initial load

            # Scroll to load all content
            if progress_callback:
                progress_callback("İçerik yükleniyor...")

            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 10

            while scroll_attempts < max_scrolls:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                    if scroll_attempts >= 2:
                        break
                else:
                    scroll_attempts = 0
                last_height = new_height

            # Get page source and parse
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            if progress_callback:
                progress_callback("Resimler ayrıştırılıyor...")

            found_urls = set()

            # Method 1: Find main shot image (media-shot)
            shot_containers = soup.find_all('div', class_=re.compile(r'media-shot|shot-image|shot__media'))
            for container in shot_containers:
                imgs = container.find_all('img')
                for img in imgs:
                    src = img.get('src') or img.get('data-src') or img.get('data-srcset')
                    if src and self._is_valid_shot_image(src):
                        high_res = self._get_high_res_url(src)
                        if high_res not in found_urls:
                            found_urls.add(high_res)
                            images.append(high_res)

            # Method 2: Find images in picture elements
            pictures = soup.find_all('picture')
            for picture in pictures:
                # Get source with highest resolution
                sources = picture.find_all('source')
                for source in sources:
                    srcset = source.get('srcset', '')
                    # Parse srcset and get highest resolution
                    urls = re.findall(r'(https://[^\s,]+)', srcset)
                    for u in urls:
                        if self._is_valid_shot_image(u):
                            high_res = self._get_high_res_url(u)
                            if high_res not in found_urls:
                                found_urls.add(high_res)
                                images.append(high_res)

                # Also check img tag in picture
                img = picture.find('img')
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src and self._is_valid_shot_image(src):
                        high_res = self._get_high_res_url(src)
                        if high_res not in found_urls:
                            found_urls.add(high_res)
                            images.append(high_res)

            # Method 3: Find all Dribbble CDN images
            all_imgs = soup.find_all('img')
            for img in all_imgs:
                src = img.get('src') or img.get('data-src')
                if src and ('dribbble' in src or 'cdn.dribbble.com' in src):
                    if self._is_valid_shot_image(src):
                        high_res = self._get_high_res_url(src)
                        if high_res not in found_urls:
                            found_urls.add(high_res)
                            images.append(high_res)

            # Method 4: Look for attachment images (multiple images in a shot)
            attachment_containers = soup.find_all('div', class_=re.compile(r'attachment|media-content'))
            for container in attachment_containers:
                imgs = container.find_all('img')
                for img in imgs:
                    src = img.get('src') or img.get('data-src')
                    if src and self._is_valid_shot_image(src):
                        high_res = self._get_high_res_url(src)
                        if high_res not in found_urls:
                            found_urls.add(high_res)
                            images.append(high_res)

            # Method 5: Check for video poster images
            videos = soup.find_all('video')
            for video in videos:
                poster = video.get('poster')
                if poster and self._is_valid_shot_image(poster):
                    if poster not in found_urls:
                        found_urls.add(poster)
                        images.append(poster)

            if progress_callback:
                progress_callback(f"{len(images)} resim bulundu")

        except Exception as e:
            if progress_callback:
                progress_callback(f"Hata: {str(e)}")
            raise

        return images

    def _is_valid_shot_image(self, url):
        """Check if URL is a valid shot image (not avatar, icon, etc.)"""
        if not url:
            return False

        url_lower = url.lower()

        # Must be from Dribbble CDN
        valid_domains = ['dribbble.com', 'cdn.dribbble.com', 'shots.ltxxxxx.dribbble.net']
        if not any(domain in url_lower for domain in valid_domains):
            # Also accept common CDN patterns
            if 'dribbble' not in url_lower:
                return False

        # Exclude small images, avatars, icons
        exclude_patterns = [
            '/avatars/', '/mini/', '/small/', '/teaser/',
            '_teaser', '_mini', '_small', '_1x',
            '/users/', 'profile', 'icon', 'logo',
            'favicon', 'sprite', 'placeholder',
            '50x50', '100x100', '60x60', '80x80'
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # Should be a shot/attachment image
        valid_patterns = [
            '/shots/', '/attachments/', '/uploads/',
            '_4x', '_2x', 'original', 'large', 'normal',
            '/original/', '/large/', '/normal/', '/hd/'
        ]

        # If it's clearly a small thumbnail, reject
        size_match = re.search(r'_(\d+)x(\d+)', url_lower)
        if size_match:
            width = int(size_match.group(1))
            height = int(size_match.group(2))
            if width < 200 or height < 200:
                return False

        return True

    def _get_high_res_url(self, url):
        """Convert URL to highest resolution version"""
        high_res = url

        # Dribbble CDN patterns for higher resolution
        replacements = [
            (r'_teaser\.', '_4x.'),
            (r'_small\.', '_4x.'),
            (r'_mini\.', '_4x.'),
            (r'_1x\.', '_4x.'),
            (r'_2x\.', '_4x.'),
            (r'/teaser/', '/original/'),
            (r'/small/', '/original/'),
            (r'/mini/', '/original/'),
            (r'/normal/', '/original/'),
            (r'w=\d+', 'w=1600'),
            (r'h=\d+', 'h=1200'),
        ]

        for pattern, replacement in replacements:
            high_res = re.sub(pattern, replacement, high_res)

        # Remove resize parameters if present
        high_res = re.sub(r'\?.*$', '', high_res)

        return high_res

    def download_image(self, url, save_path, progress_callback=None):
        """Download a single image"""
        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress)

            return True
        except Exception as e:
            print(f"Download error: {e}")
            return False


class DownloadQueue:
    """Manages the download queue"""

    def __init__(self):
        self.queue = queue.Queue()
        self.items = []
        self.lock = threading.Lock()

    def add(self, url, folder_name=None):
        """Add URL to queue with optional custom folder name"""
        with self.lock:
            item = {
                'url': url,
                'folder_name': folder_name,
                'status': 'Bekliyor',
                'progress': 0,
                'added_time': datetime.now()
            }
            self.items.append(item)
            self.queue.put(item)
            return len(self.items) - 1

    def get(self):
        """Get next item from queue"""
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None

    def update_status(self, index, status, progress=None):
        """Update item status"""
        with self.lock:
            if 0 <= index < len(self.items):
                self.items[index]['status'] = status
                if progress is not None:
                    self.items[index]['progress'] = progress

    def clear(self):
        """Clear the queue"""
        with self.lock:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
            self.items.clear()

    def get_items(self):
        """Get all items for display"""
        with self.lock:
            return self.items.copy()


class DribbbleDownloaderApp(ctk.CTk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Dribbble Shot Downloader")
        self.geometry("950x750")
        self.minsize(850, 650)

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize components
        self.downloader = DribbbleDownloader()
        self.download_queue = DownloadQueue()
        self.download_folder = str(Path.home() / "Downloads" / "Dribbble")
        self.is_downloading = False
        self.stop_requested = False
        self.download_thread = None

        # Create UI
        self._create_ui()

        # Ensure download folder exists
        os.makedirs(self.download_folder, exist_ok=True)

    def _create_ui(self):
        """Create the user interface"""
        # Main container
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ctk.CTkLabel(
            self.main_container,
            text="🏀 Dribbble Shot Downloader",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(0, 20))

        # URL Input Section
        url_frame = ctk.CTkFrame(self.main_container)
        url_frame.pack(fill="x", pady=(0, 10))

        url_label = ctk.CTkLabel(url_frame, text="Shot URL:", font=ctk.CTkFont(size=14))
        url_label.pack(anchor="w", padx=10, pady=(10, 5))

        url_input_frame = ctk.CTkFrame(url_frame, fg_color="transparent")
        url_input_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.url_entry = ctk.CTkEntry(
            url_input_frame,
            placeholder_text="https://dribbble.com/shots/...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Custom folder name input
        folder_name_frame = ctk.CTkFrame(url_frame, fg_color="transparent")
        folder_name_frame.pack(fill="x", padx=10, pady=(0, 10))

        folder_name_label = ctk.CTkLabel(
            folder_name_frame,
            text="Klasör Adı (opsiyonel):",
            font=ctk.CTkFont(size=12)
        )
        folder_name_label.pack(side="left", padx=(0, 10))

        self.folder_name_entry = ctk.CTkEntry(
            folder_name_frame,
            placeholder_text="Boş bırakırsan shot adı kullanılır",
            height=35,
            width=300,
            font=ctk.CTkFont(size=12)
        )
        self.folder_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.add_btn = ctk.CTkButton(
            folder_name_frame,
            text="Kuyruğa Ekle",
            width=120,
            height=35,
            command=self._add_to_queue
        )
        self.add_btn.pack(side="right")

        # Download Folder Section
        folder_frame = ctk.CTkFrame(self.main_container)
        folder_frame.pack(fill="x", pady=(0, 10))

        folder_label = ctk.CTkLabel(folder_frame, text="Ana İndirme Klasörü:", font=ctk.CTkFont(size=14))
        folder_label.pack(anchor="w", padx=10, pady=(10, 5))

        folder_input_frame = ctk.CTkFrame(folder_frame, fg_color="transparent")
        folder_input_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.folder_entry = ctk.CTkEntry(
            folder_input_frame,
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.folder_entry.insert(0, self.download_folder)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browse_btn = ctk.CTkButton(
            folder_input_frame,
            text="Gözat",
            width=100,
            height=40,
            command=self._browse_folder
        )
        self.browse_btn.pack(side="right")

        # Batch Import Section
        batch_frame = ctk.CTkFrame(self.main_container)
        batch_frame.pack(fill="x", pady=(0, 10))

        batch_header = ctk.CTkFrame(batch_frame, fg_color="transparent")
        batch_header.pack(fill="x", padx=10, pady=10)

        batch_label = ctk.CTkLabel(
            batch_header,
            text="Toplu URL Ekleme (her satıra bir URL):",
            font=ctk.CTkFont(size=14)
        )
        batch_label.pack(side="left")

        self.batch_btn = ctk.CTkButton(
            batch_header,
            text="Toplu Ekle",
            width=100,
            height=30,
            command=self._batch_add
        )
        self.batch_btn.pack(side="right")

        self.batch_textbox = ctk.CTkTextbox(
            batch_frame,
            height=80,
            font=ctk.CTkFont(size=11)
        )
        self.batch_textbox.pack(fill="x", padx=10, pady=(0, 10))

        # Queue Section
        queue_frame = ctk.CTkFrame(self.main_container)
        queue_frame.pack(fill="both", expand=True, pady=(0, 10))

        queue_header = ctk.CTkFrame(queue_frame, fg_color="transparent")
        queue_header.pack(fill="x", padx=10, pady=10)

        queue_label = ctk.CTkLabel(queue_header, text="İndirme Kuyruğu:", font=ctk.CTkFont(size=14))
        queue_label.pack(side="left")

        self.clear_btn = ctk.CTkButton(
            queue_header,
            text="Temizle",
            width=80,
            height=30,
            fg_color="gray",
            command=self._clear_queue
        )
        self.clear_btn.pack(side="right")

        # Queue listbox
        self.queue_textbox = ctk.CTkTextbox(
            queue_frame,
            height=150,
            font=ctk.CTkFont(size=12)
        )
        self.queue_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Progress Section
        progress_frame = ctk.CTkFrame(self.main_container)
        progress_frame.pack(fill="x", pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Hazır",
            font=ctk.CTkFont(size=13)
        )
        self.status_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=20)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self.progress_bar.set(0)

        self.detail_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.detail_label.pack(anchor="w", padx=10, pady=(0, 10))

        # Control Buttons
        control_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        control_frame.pack(fill="x")

        self.start_btn = ctk.CTkButton(
            control_frame,
            text="▶ Başlat",
            width=150,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#E44D8A",
            hover_color="#C43D7A",
            command=self._start_download
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            control_frame,
            text="⏹ Durdur",
            width=150,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="red",
            hover_color="darkred",
            state="disabled",
            command=self._stop_download
        )
        self.stop_btn.pack(side="left")

        # Stats
        self.stats_label = ctk.CTkLabel(
            control_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.stats_label.pack(side="right")

    def _add_to_queue(self):
        """Add URL to download queue"""
        url = self.url_entry.get().strip()
        custom_folder = self.folder_name_entry.get().strip()

        if not url:
            CTkMessagebox(title="Hata", message="Lütfen bir URL girin!", icon="cancel")
            return

        if 'dribbble.com/shots/' not in url:
            CTkMessagebox(
                title="Hata",
                message="Geçerli bir Dribbble shot URL'si girin!\nÖrnek: https://dribbble.com/shots/12345678-...",
                icon="cancel"
            )
            return

        self.download_queue.add(url, custom_folder if custom_folder else None)
        self.url_entry.delete(0, "end")
        self.folder_name_entry.delete(0, "end")
        self._update_queue_display()

    def _batch_add(self):
        """Add multiple URLs from batch textbox"""
        text = self.batch_textbox.get("1.0", "end").strip()
        if not text:
            CTkMessagebox(title="Hata", message="Lütfen URL'leri girin!", icon="cancel")
            return

        urls = [line.strip() for line in text.split('\n') if line.strip()]
        added = 0

        for url in urls:
            if 'dribbble.com/shots/' in url:
                self.download_queue.add(url, None)
                added += 1

        self.batch_textbox.delete("1.0", "end")
        self._update_queue_display()

        CTkMessagebox(
            title="Eklendi",
            message=f"{added} URL kuyruğa eklendi.",
            icon="check"
        )

    def _browse_folder(self):
        """Browse for download folder"""
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def _clear_queue(self):
        """Clear the download queue"""
        if self.is_downloading:
            CTkMessagebox(
                title="Uyarı",
                message="İndirme devam ederken kuyruk temizlenemez!",
                icon="warning"
            )
            return

        self.download_queue.clear()
        self._update_queue_display()

    def _update_queue_display(self):
        """Update the queue display"""
        self.queue_textbox.delete("1.0", "end")
        items = self.download_queue.get_items()

        if not items:
            self.queue_textbox.insert("end", "Kuyruk boş - URL ekleyin")
            return

        for i, item in enumerate(items, 1):
            shot_id, shot_name = self.downloader.extract_shot_info(item['url'])

            # Use custom folder name if provided
            display_name = item.get('folder_name') or shot_name or "Bilinmeyen"
            status = item['status']
            progress = item.get('progress', 0)

            if progress > 0 and progress < 100:
                line = f"{i}. 📁 {display_name[:40]}... [{status}] ({progress:.0f}%)\n"
            else:
                line = f"{i}. 📁 {display_name[:40]}... [{status}]\n"

            self.queue_textbox.insert("end", line)

    def _start_download(self):
        """Start the download process"""
        if self.is_downloading:
            return

        # Update download folder from entry
        self.download_folder = self.folder_entry.get().strip()
        os.makedirs(self.download_folder, exist_ok=True)

        items = self.download_queue.get_items()
        pending_items = [item for item in items if item['status'] == 'Bekliyor']

        if not pending_items:
            CTkMessagebox(
                title="Uyarı",
                message="İndirilecek öğe yok! Kuyruğa URL ekleyin.",
                icon="warning"
            )
            return

        self.is_downloading = True
        self.stop_requested = False

        # Update UI
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.add_btn.configure(state="disabled")
        self.batch_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")

        # Start download thread
        self.download_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.download_thread.start()

    def _stop_download(self):
        """Stop the download process"""
        self.stop_requested = True
        self._update_status("Durduruluyor...")

    def _download_worker(self):
        """Background worker for downloading"""
        items = self.download_queue.get_items()
        total_downloaded = 0
        total_errors = 0

        for idx, item in enumerate(items):
            if self.stop_requested:
                break

            if item['status'] != 'Bekliyor':
                continue

            url = item['url']
            shot_id, shot_name = self.downloader.extract_shot_info(url)

            # Use custom folder name if provided
            folder_name = item.get('folder_name') or shot_name

            if not shot_id:
                self.download_queue.update_status(idx, 'Hata: Geçersiz URL')
                total_errors += 1
                self.after(0, self._update_queue_display)
                continue

            # Update status
            self.download_queue.update_status(idx, 'Resimler taranıyor...')
            self.after(0, self._update_queue_display)
            self.after(0, lambda fn=folder_name: self._update_status(f"Taraniyor: {fn}"))

            try:
                # Get images
                images = self.downloader.get_shot_images(
                    url,
                    progress_callback=lambda msg: self.after(0, lambda m=msg: self._update_detail(m))
                )

                if not images:
                    self.download_queue.update_status(idx, 'Resim bulunamadı')
                    self.after(0, self._update_queue_display)
                    continue

                # Create folder for this shot
                safe_name = re.sub(r'[^\w\s-]', '', folder_name)[:50]
                shot_folder = os.path.join(self.download_folder, f"{shot_id}_{safe_name}")
                os.makedirs(shot_folder, exist_ok=True)

                # Download images
                self.download_queue.update_status(idx, f'İndiriliyor (0/{len(images)})')
                self.after(0, self._update_queue_display)

                for img_idx, img_url in enumerate(images):
                    if self.stop_requested:
                        break

                    # Generate filename
                    ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                    if not ext.startswith('.'):
                        ext = '.jpg'
                    filename = f"image_{img_idx + 1:03d}{ext}"
                    filepath = os.path.join(shot_folder, filename)

                    # Skip if exists
                    if os.path.exists(filepath):
                        continue

                    # Download
                    success = self.downloader.download_image(img_url, filepath)

                    if success:
                        total_downloaded += 1
                    else:
                        total_errors += 1

                    # Update progress
                    progress = ((img_idx + 1) / len(images)) * 100
                    self.download_queue.update_status(
                        idx,
                        f'İndiriliyor ({img_idx + 1}/{len(images)})',
                        progress
                    )
                    self.after(0, self._update_queue_display)
                    self.after(0, lambda p=progress/100: self.progress_bar.set(p))
                    self.after(0, lambda: self._update_stats(total_downloaded, total_errors))

                if not self.stop_requested:
                    self.download_queue.update_status(idx, f'Tamamlandı ({len(images)} resim)')
                else:
                    self.download_queue.update_status(idx, 'Durduruldu')

                self.after(0, self._update_queue_display)

            except Exception as e:
                self.download_queue.update_status(idx, f'Hata: {str(e)[:30]}')
                total_errors += 1
                self.after(0, self._update_queue_display)

        # Cleanup
        self.downloader.close_driver()

        # Update UI
        self.after(0, self._download_complete)

    def _update_status(self, text):
        """Update status label"""
        self.status_label.configure(text=text)

    def _update_detail(self, text):
        """Update detail label"""
        self.detail_label.configure(text=text)

    def _update_stats(self, downloaded, errors):
        """Update stats label"""
        self.stats_label.configure(text=f"İndirilen: {downloaded} | Hata: {errors}")

    def _download_complete(self):
        """Called when download is complete"""
        self.is_downloading = False

        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.add_btn.configure(state="normal")
        self.batch_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")

        if self.stop_requested:
            self._update_status("Durduruldu")
        else:
            self._update_status("Tamamlandı!")

        self.stop_requested = False
        self.progress_bar.set(0)

    def on_closing(self):
        """Handle window close"""
        if self.is_downloading:
            self.stop_requested = True
            time.sleep(0.5)
        self.downloader.close_driver()
        self.destroy()


def main():
    """Main entry point"""
    app = DribbbleDownloaderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
