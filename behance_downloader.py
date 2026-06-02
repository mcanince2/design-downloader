#!/usr/bin/env python3
"""
Behance Gallery Downloader v2.0
Modern Cyberpunk GUI - Downloads only project images at highest resolution
"""

import os
import re
import sys
import hashlib
import time
import queue
import threading
import requests
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from io import BytesIO

try:
    import customtkinter as ctk
    from CTkMessagebox import CTkMessagebox
    from PIL import Image
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install customtkinter CTkMessagebox pillow")
    import customtkinter as ctk
    from CTkMessagebox import CTkMessagebox
    from PIL import Image

from tkinter import filedialog
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ═══════════════════════════════════════════════════════════════
# CYBERPUNK COLOR SCHEME
# ═══════════════════════════════════════════════════════════════
COLORS = {
    'bg_dark': '#0a0a0f',
    'bg_medium': '#12121a',
    'bg_light': '#1a1a2e',
    'accent_cyan': '#00fff5',
    'accent_magenta': '#ff00ff',
    'accent_purple': '#bd00ff',
    'accent_blue': '#0080ff',
    'accent_green': '#00ff88',
    'accent_orange': '#ff8800',
    'text_primary': '#ffffff',
    'text_secondary': '#888899',
    'text_dim': '#444455',
    'success': '#00ff88',
    'error': '#ff3366',
    'warning': '#ffaa00',
    'border': '#2a2a3e',
}


class BehanceDownloader:
    """Handles scraping and downloading of Behance gallery images"""

    def __init__(self):
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
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
                raise Exception(f"Chrome driver error: {e}")

    def close_driver(self):
        """Close the Chrome driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def extract_gallery_id(self, url):
        """Extract gallery ID and name from Behance URL"""
        match = re.search(r'/gallery/(\d+)/([^/?]+)', url)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def _get_image_hash(self, url):
        """Extract unique identifier from image URL"""
        # Behance images have patterns like /project_modules/1400/abc123.jpg
        # We want to extract the unique part (abc123)
        match = re.search(r'/([a-f0-9]+)(?:_[a-f0-9]+)?\.(?:jpg|jpeg|png|gif|webp)', url, re.I)
        if match:
            return match.group(1)

        # Fallback: use the filename without size indicators
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        # Remove size prefixes/suffixes
        clean_name = re.sub(r'^(fs|disp|max_\d+|source|original|hd|[\d]+)_?', '', filename)
        clean_name = re.sub(r'_?(fs|disp|max_\d+|source|original|hd|[\d]+)\.', '.', clean_name)
        return clean_name

    def _get_image_size_score(self, url):
        """Get a score representing image size (higher = larger)"""
        url_lower = url.lower()

        # Size indicators and their scores
        size_scores = {
            '/source/': 1000,
            '/original/': 900,
            '/max_3840/': 850,
            '/max_2800/': 800,
            '/max_1920/': 750,
            '/fs/': 700,
            '/1400/': 600,
            '/1400_opt/': 590,
            '/max_1400/': 580,
            '/1200/': 500,
            '/max_1200/': 490,
            '/808/': 400,
            '/max_808/': 390,
            '/600/': 300,
            '/404/': 200,
            '/300/': 100,
            '/230/': 50,
            '/202/': 40,
            '/115/': 20,
            '/50/': 10,
        }

        for pattern, score in size_scores.items():
            if pattern in url_lower:
                return score

        # Check for dimension in filename
        dim_match = re.search(r'[_-](\d+)(?:x\d+)?\.', url_lower)
        if dim_match:
            return int(dim_match.group(1))

        return 500  # Default medium score

    def get_gallery_images(self, url, progress_callback=None):
        """Scrape project images from a Behance gallery - excluding suggested/related"""
        images = []

        try:
            self.init_driver()

            if progress_callback:
                progress_callback("[ CONNECTING ] Loading page...")

            self.driver.get(url)
            time.sleep(3)

            # Scroll to load lazy images, but not too far (to avoid suggested section)
            if progress_callback:
                progress_callback("[ SCANNING ] Loading project images...")

            # Get initial page height
            initial_height = self.driver.execute_script("return document.body.scrollHeight")

            # Scroll incrementally
            scroll_position = 0
            scroll_step = 800
            max_scroll = initial_height * 0.7  # Only scroll 70% to avoid suggested

            while scroll_position < max_scroll:
                scroll_position += scroll_step
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                time.sleep(0.5)

                # Check if we've reached suggested section
                try:
                    suggested = self.driver.find_elements("css selector", "[class*='Recommend'], [class*='Related'], [class*='Suggested'], [class*='MoreFrom']")
                    if suggested:
                        break
                except:
                    pass

            # Scroll back up to ensure we're in project area
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)

            # Get page source and parse
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            if progress_callback:
                progress_callback("[ ANALYZING ] Extracting project images...")

            # Find and remove suggested/related sections from parsing
            for section in soup.find_all(['section', 'div'], class_=re.compile(
                r'Recommend|Related|Suggested|MoreFrom|Appreciations|Comments|ProjectInfo|Owner|Stats',
                re.I
            )):
                section.decompose()

            # Also remove footer and navigation
            for elem in soup.find_all(['footer', 'nav', 'header']):
                elem.decompose()

            # Remove elements that typically contain suggested projects
            for elem in soup.find_all(['div', 'section'], attrs={'data-related': True}):
                elem.decompose()

            for elem in soup.find_all(['div', 'section'], id=re.compile(r'related|suggested|recommend', re.I)):
                elem.decompose()

            # Collect all potential images with their metadata
            image_candidates = {}  # hash -> {url, score}

            # Method 1: Project modules (main content)
            project_modules = soup.find_all('div', class_=re.compile(r'Project-?[Mm]odule|project-module'))
            for module in project_modules:
                for img in module.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if src and self._is_valid_project_image(src):
                        img_hash = self._get_image_hash(src)
                        score = self._get_image_size_score(src)

                        if img_hash not in image_candidates or score > image_candidates[img_hash]['score']:
                            image_candidates[img_hash] = {'url': src, 'score': score}

            # Method 2: Image elements in main content
            main_content = soup.find('main') or soup.find('div', class_=re.compile(r'project-content|Project-content'))
            if main_content:
                for img in main_content.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if src and self._is_valid_project_image(src):
                        img_hash = self._get_image_hash(src)
                        score = self._get_image_size_score(src)

                        if img_hash not in image_candidates or score > image_candidates[img_hash]['score']:
                            image_candidates[img_hash] = {'url': src, 'score': score}

            # Method 3: All Behance CDN images (filtered)
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and 'mir-s3-cdn-cf.behance.net' in src:
                    # Skip if parent has related/suggested class
                    parent = img.find_parent(['div', 'section', 'article'])
                    if parent:
                        parent_classes = ' '.join(parent.get('class', []))
                        if re.search(r'related|suggest|recommend|thumbnail|avatar|owner', parent_classes, re.I):
                            continue

                    if self._is_valid_project_image(src):
                        img_hash = self._get_image_hash(src)
                        score = self._get_image_size_score(src)

                        if img_hash not in image_candidates or score > image_candidates[img_hash]['score']:
                            image_candidates[img_hash] = {'url': src, 'score': score}

            # Convert to high-res URLs
            for img_hash, data in image_candidates.items():
                high_res = self._upgrade_to_high_res(data['url'])
                images.append(high_res)

            if progress_callback:
                progress_callback(f"[ FOUND ] {len(images)} unique images")

        except Exception as e:
            if progress_callback:
                progress_callback(f"[ ERROR ] {str(e)}")
            raise

        return images

    def _is_valid_project_image(self, url):
        """Check if URL is a valid project image"""
        if not url:
            return False

        url_lower = url.lower()

        # Must be from Behance CDN
        if 'behance.net' not in url_lower:
            return False

        # Must be in project_modules path (main project images)
        if '/project_modules/' not in url_lower:
            return False

        # Exclude small thumbnails and avatars
        exclude_patterns = [
            '/50/', '/100/', '/115/', '/130/', '/138/', '/202/', '/230/',
            '/avatar', '/profile', '/icon', '/logo', '/user',
            'favicon', 'sprite', 'placeholder', 'loading'
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        return True

    def _upgrade_to_high_res(self, url):
        """Convert URL to highest available resolution"""
        high_res = url

        # Replace size indicators with source/original
        replacements = [
            (r'/disp/', '/source/'),
            (r'/404/', '/source/'),
            (r'/808/', '/source/'),
            (r'/1200/', '/source/'),
            (r'/1400/', '/source/'),
            (r'/1400_opt/', '/source/'),
            (r'/max_404/', '/source/'),
            (r'/max_808/', '/source/'),
            (r'/max_1200/', '/source/'),
            (r'/max_1400/', '/source/'),
            (r'/max_1920/', '/source/'),
            (r'/fs/', '/source/'),
        ]

        for pattern, replacement in replacements:
            high_res = re.sub(pattern, replacement, high_res)

        return high_res

    def download_image(self, url, save_path, min_size=5000):
        """Download image and validate it"""
        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()

            # Check content length
            content_length = int(response.headers.get('content-length', 0))
            if content_length > 0 and content_length < min_size:
                return False, "Too small"

            # Download to memory first
            data = BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    data.write(chunk)

            # Validate image
            data.seek(0)
            if data.getbuffer().nbytes < min_size:
                return False, "Too small"

            # Try to open and validate
            try:
                img = Image.open(data)
                img.verify()

                # Check dimensions
                data.seek(0)
                img = Image.open(data)
                width, height = img.size

                if width < 200 or height < 200:
                    return False, "Dimensions too small"

            except Exception as e:
                return False, f"Invalid image: {e}"

            # Save the file
            data.seek(0)
            with open(save_path, 'wb') as f:
                f.write(data.read())

            return True, "OK"

        except Exception as e:
            return False, str(e)


class DownloadQueue:
    """Manages the download queue"""

    def __init__(self):
        self.queue = queue.Queue()
        self.items = []
        self.lock = threading.Lock()

    def add(self, url, folder_name=None):
        with self.lock:
            item = {
                'url': url,
                'folder_name': folder_name,
                'status': 'QUEUED',
                'progress': 0,
                'images_found': 0,
                'images_downloaded': 0,
            }
            self.items.append(item)
            self.queue.put(len(self.items) - 1)
            return len(self.items) - 1

    def update_status(self, index, status, progress=None, **kwargs):
        with self.lock:
            if 0 <= index < len(self.items):
                self.items[index]['status'] = status
                if progress is not None:
                    self.items[index]['progress'] = progress
                for key, value in kwargs.items():
                    self.items[index][key] = value

    def clear(self):
        with self.lock:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
            self.items.clear()

    def get_items(self):
        with self.lock:
            return self.items.copy()


class CyberpunkFrame(ctk.CTkFrame):
    """Custom frame with cyberpunk styling"""

    def __init__(self, master, title=None, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS['bg_medium'],
            border_color=COLORS['border'],
            border_width=1,
            corner_radius=8,
            **kwargs
        )

        if title:
            title_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
            title_frame.pack(fill="x", padx=15, pady=(12, 5))

            # Accent bar
            accent = ctk.CTkFrame(title_frame, fg_color=COLORS['accent_cyan'], width=3, height=16, corner_radius=2)
            accent.pack(side="left", padx=(0, 10))

            ctk.CTkLabel(
                title_frame,
                text=title.upper(),
                font=ctk.CTkFont(family="Courier", size=12, weight="bold"),
                text_color=COLORS['accent_cyan']
            ).pack(side="left")


class GlowButton(ctk.CTkButton):
    """Button with glow effect"""

    def __init__(self, master, glow_color=COLORS['accent_cyan'], **kwargs):
        self.glow_color = glow_color
        super().__init__(
            master,
            font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
            corner_radius=6,
            border_width=2,
            border_color=glow_color,
            **kwargs
        )


class BehanceDownloaderApp(ctk.CTk):
    """Main application with Cyberpunk theme"""

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("BEHANCE DOWNLOADER v2.0")
        self.geometry("1000x800")
        self.minsize(900, 700)
        self.configure(fg_color=COLORS['bg_dark'])

        # Set theme
        ctk.set_appearance_mode("dark")

        # Initialize components
        self.downloader = BehanceDownloader()
        self.download_queue = DownloadQueue()
        self.download_folder = str(Path.home() / "Downloads" / "Behance")
        self.is_downloading = False
        self.stop_requested = False
        self.download_thread = None

        # Create UI
        self._create_ui()
        os.makedirs(self.download_folder, exist_ok=True)

    def _create_ui(self):
        """Create the cyberpunk interface"""
        # Main container
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=25, pady=20)

        # Header
        self._create_header()

        # URL Input Section
        self._create_url_section()

        # Folder Section
        self._create_folder_section()

        # Queue Section
        self._create_queue_section()

        # Progress Section
        self._create_progress_section()

        # Control Section
        self._create_control_section()

    def _create_header(self):
        """Create header with title"""
        header = ctk.CTkFrame(self.main_container, fg_color="transparent", height=70)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)

        # ASCII-style title
        title_text = """
██████╗ ███████╗██╗  ██╗ █████╗ ███╗   ██╗ ██████╗███████╗
██╔══██╗██╔════╝██║  ██║██╔══██╗████╗  ██║██╔════╝██╔════╝
██████╔╝█████╗  ███████║███████║██╔██╗ ██║██║     █████╗
██╔══██╗██╔══╝  ██╔══██║██╔══██║██║╚██╗██║██║     ██╔══╝
██████╔╝███████╗██║  ██║██║  ██║██║ ╚████║╚██████╗███████╗
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝"""

        title_label = ctk.CTkLabel(
            header,
            text="◢ BEHANCE GALLERY DOWNLOADER ◣",
            font=ctk.CTkFont(family="Courier", size=22, weight="bold"),
            text_color=COLORS['accent_cyan']
        )
        title_label.pack(side="left")

        # Version badge
        version = ctk.CTkLabel(
            header,
            text="[ v2.0 ]",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=COLORS['accent_magenta']
        )
        version.pack(side="left", padx=15)

        # Status indicator
        self.connection_status = ctk.CTkLabel(
            header,
            text="● READY",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=COLORS['accent_green']
        )
        self.connection_status.pack(side="right")

    def _create_url_section(self):
        """Create URL input section"""
        frame = CyberpunkFrame(self.main_container, title="TARGET URL")
        frame.pack(fill="x", pady=(0, 12))

        # URL input row
        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(5, 12))

        self.url_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="https://www.behance.net/gallery/...",
            height=42,
            font=ctk.CTkFont(family="Courier", size=13),
            fg_color=COLORS['bg_dark'],
            border_color=COLORS['border'],
            text_color=COLORS['text_primary']
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.url_entry.bind("<Return>", lambda e: self._add_to_queue())

        self.add_btn = GlowButton(
            input_frame,
            text="◈ ADD TO QUEUE",
            width=150,
            height=42,
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['accent_cyan'],
            text_color=COLORS['accent_cyan'],
            glow_color=COLORS['accent_cyan'],
            command=self._add_to_queue
        )
        self.add_btn.pack(side="right")

        # Custom folder name row
        folder_row = ctk.CTkFrame(frame, fg_color="transparent")
        folder_row.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(
            folder_row,
            text="CUSTOM FOLDER:",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=COLORS['text_secondary']
        ).pack(side="left", padx=(0, 10))

        self.custom_folder_entry = ctk.CTkEntry(
            folder_row,
            placeholder_text="(optional) Custom folder name for this download",
            height=32,
            font=ctk.CTkFont(family="Courier", size=11),
            fg_color=COLORS['bg_dark'],
            border_color=COLORS['border'],
            text_color=COLORS['text_primary']
        )
        self.custom_folder_entry.pack(side="left", fill="x", expand=True)

    def _create_folder_section(self):
        """Create download folder section"""
        frame = CyberpunkFrame(self.main_container, title="OUTPUT DIRECTORY")
        frame.pack(fill="x", pady=(0, 12))

        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(5, 12))

        self.folder_entry = ctk.CTkEntry(
            input_frame,
            height=38,
            font=ctk.CTkFont(family="Courier", size=12),
            fg_color=COLORS['bg_dark'],
            border_color=COLORS['border'],
            text_color=COLORS['accent_orange']
        )
        self.folder_entry.insert(0, self.download_folder)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.browse_btn = GlowButton(
            input_frame,
            text="◉ BROWSE",
            width=100,
            height=38,
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['accent_orange'],
            text_color=COLORS['accent_orange'],
            glow_color=COLORS['accent_orange'],
            command=self._browse_folder
        )
        self.browse_btn.pack(side="right")

    def _create_queue_section(self):
        """Create queue display section"""
        frame = CyberpunkFrame(self.main_container, title="DOWNLOAD QUEUE")
        frame.pack(fill="both", expand=True, pady=(0, 12))

        # Queue header with clear button
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(0, 5))

        self.queue_count = ctk.CTkLabel(
            header,
            text="[ 0 ITEMS ]",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=COLORS['text_secondary']
        )
        self.queue_count.pack(side="left")

        self.clear_btn = ctk.CTkButton(
            header,
            text="✕ CLEAR",
            width=80,
            height=26,
            font=ctk.CTkFont(family="Courier", size=10),
            fg_color="transparent",
            hover_color=COLORS['error'],
            text_color=COLORS['error'],
            border_width=1,
            border_color=COLORS['error'],
            command=self._clear_queue
        )
        self.clear_btn.pack(side="right")

        # Queue display
        self.queue_textbox = ctk.CTkTextbox(
            frame,
            font=ctk.CTkFont(family="Courier", size=12),
            fg_color=COLORS['bg_dark'],
            text_color=COLORS['text_primary'],
            border_width=1,
            border_color=COLORS['border'],
            corner_radius=6
        )
        self.queue_textbox.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        self._update_queue_display()

    def _create_progress_section(self):
        """Create progress display section"""
        frame = CyberpunkFrame(self.main_container, title="SYSTEM STATUS")
        frame.pack(fill="x", pady=(0, 12))

        # Status row
        status_row = ctk.CTkFrame(frame, fg_color="transparent")
        status_row.pack(fill="x", padx=15, pady=(5, 8))

        self.status_label = ctk.CTkLabel(
            status_row,
            text="◉ STANDBY",
            font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
            text_color=COLORS['accent_green']
        )
        self.status_label.pack(side="left")

        self.stats_label = ctk.CTkLabel(
            status_row,
            text="",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=COLORS['text_secondary']
        )
        self.stats_label.pack(side="right")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            frame,
            height=8,
            fg_color=COLORS['bg_dark'],
            progress_color=COLORS['accent_cyan'],
            corner_radius=4
        )
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 8))
        self.progress_bar.set(0)

        # Detail label
        self.detail_label = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=COLORS['text_dim']
        )
        self.detail_label.pack(anchor="w", padx=15, pady=(0, 12))

    def _create_control_section(self):
        """Create control buttons section"""
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        frame.pack(fill="x")

        # Start button
        self.start_btn = GlowButton(
            frame,
            text="▶ EXECUTE",
            width=180,
            height=50,
            fg_color=COLORS['accent_green'],
            hover_color="#00cc6a",
            text_color=COLORS['bg_dark'],
            glow_color=COLORS['accent_green'],
            command=self._start_download
        )
        self.start_btn.pack(side="left", padx=(0, 15))

        # Stop button
        self.stop_btn = GlowButton(
            frame,
            text="◼ TERMINATE",
            width=180,
            height=50,
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['error'],
            text_color=COLORS['error'],
            glow_color=COLORS['error'],
            state="disabled",
            command=self._stop_download
        )
        self.stop_btn.pack(side="left")

        # Terminal-style log
        self.log_label = ctk.CTkLabel(
            frame,
            text="SYS > Awaiting commands...",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=COLORS['text_dim']
        )
        self.log_label.pack(side="right")

    def _add_to_queue(self):
        """Add URL to download queue"""
        url = self.url_entry.get().strip()
        custom_folder = self.custom_folder_entry.get().strip()

        if not url:
            CTkMessagebox(
                title="ERROR",
                message="Please enter a URL",
                icon="cancel",
                fg_color=COLORS['bg_medium'],
                bg_color=COLORS['bg_dark']
            )
            return

        if 'behance.net/gallery/' not in url:
            CTkMessagebox(
                title="INVALID URL",
                message="Please enter a valid Behance gallery URL\nExample: https://www.behance.net/gallery/123456/...",
                icon="cancel"
            )
            return

        self.download_queue.add(url, custom_folder if custom_folder else None)
        self.url_entry.delete(0, "end")
        self.custom_folder_entry.delete(0, "end")
        self._update_queue_display()
        self._log(f"Added to queue: {url[:50]}...")

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
            CTkMessagebox(title="WARNING", message="Cannot clear queue while downloading!", icon="warning")
            return
        self.download_queue.clear()
        self._update_queue_display()
        self._log("Queue cleared")

    def _update_queue_display(self):
        """Update the queue display"""
        self.queue_textbox.delete("1.0", "end")
        items = self.download_queue.get_items()

        self.queue_count.configure(text=f"[ {len(items)} ITEMS ]")

        if not items:
            self.queue_textbox.insert("end", "  ◇ Queue empty - Add URLs to begin\n")
            self.queue_textbox.configure(text_color=COLORS['text_dim'])
            return

        self.queue_textbox.configure(text_color=COLORS['text_primary'])

        for i, item in enumerate(items, 1):
            _, gallery_name = self.downloader.extract_gallery_id(item['url'])
            display_name = item.get('folder_name') or gallery_name or "Unknown"
            status = item['status']
            progress = item.get('progress', 0)

            # Status colors/icons
            if status == 'QUEUED':
                icon = "◇"
                color_tag = "dim"
            elif status == 'SCANNING':
                icon = "◈"
                color_tag = "cyan"
            elif 'DOWNLOADING' in status:
                icon = "▣"
                color_tag = "blue"
            elif status == 'COMPLETE':
                icon = "◆"
                color_tag = "green"
            elif 'ERROR' in status:
                icon = "✕"
                color_tag = "red"
            else:
                icon = "○"
                color_tag = "dim"

            line = f"  {icon} [{i:02d}] {display_name[:40]:<40} | {status}"
            if progress > 0 and progress < 100:
                line += f" ({progress:.0f}%)"
            line += "\n"

            self.queue_textbox.insert("end", line)

    def _start_download(self):
        """Start the download process"""
        if self.is_downloading:
            return

        self.download_folder = self.folder_entry.get().strip()
        os.makedirs(self.download_folder, exist_ok=True)

        items = self.download_queue.get_items()
        pending = [i for i in items if i['status'] == 'QUEUED']

        if not pending:
            CTkMessagebox(title="WARNING", message="No items in queue!", icon="warning")
            return

        self.is_downloading = True
        self.stop_requested = False

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.add_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")
        self.connection_status.configure(text="● ACTIVE", text_color=COLORS['accent_cyan'])

        self.download_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.download_thread.start()

    def _stop_download(self):
        """Stop the download process"""
        self.stop_requested = True
        self._update_status("◉ TERMINATING...", COLORS['warning'])
        self._log("Stop requested")

    def _download_worker(self):
        """Background download worker"""
        items = self.download_queue.get_items()
        total_downloaded = 0
        total_skipped = 0

        for idx, item in enumerate(items):
            if self.stop_requested:
                break

            if item['status'] != 'QUEUED':
                continue

            url = item['url']
            gallery_id, gallery_name = self.downloader.extract_gallery_id(url)
            folder_name = item.get('folder_name') or gallery_name

            if not gallery_id:
                self.download_queue.update_status(idx, 'ERROR: Invalid URL')
                self.after(0, self._update_queue_display)
                continue

            # Scanning phase
            self.download_queue.update_status(idx, 'SCANNING')
            self.after(0, self._update_queue_display)
            self.after(0, lambda fn=folder_name: self._update_status(f"◈ SCANNING: {fn}", COLORS['accent_cyan']))

            try:
                images = self.downloader.get_gallery_images(
                    url,
                    progress_callback=lambda msg: self.after(0, lambda m=msg: self._update_detail(m))
                )

                if not images:
                    self.download_queue.update_status(idx, 'ERROR: No images found')
                    self.after(0, self._update_queue_display)
                    continue

                # Create folder
                safe_name = re.sub(r'[^\w\s-]', '', folder_name)[:50]
                gallery_folder = os.path.join(self.download_folder, f"{gallery_id}_{safe_name}")
                os.makedirs(gallery_folder, exist_ok=True)

                self.download_queue.update_status(idx, f'DOWNLOADING 0/{len(images)}', images_found=len(images))
                self.after(0, self._update_queue_display)

                downloaded = 0
                for img_idx, img_url in enumerate(images):
                    if self.stop_requested:
                        break

                    ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                    filename = f"image_{img_idx + 1:03d}{ext}"
                    filepath = os.path.join(gallery_folder, filename)

                    if os.path.exists(filepath):
                        continue

                    success, msg = self.downloader.download_image(img_url, filepath)

                    if success:
                        downloaded += 1
                        total_downloaded += 1
                    else:
                        total_skipped += 1
                        self.after(0, lambda m=msg: self._log(f"Skipped: {m}"))

                    progress = ((img_idx + 1) / len(images)) * 100
                    self.download_queue.update_status(
                        idx,
                        f'DOWNLOADING {img_idx + 1}/{len(images)}',
                        progress,
                        images_downloaded=downloaded
                    )
                    self.after(0, self._update_queue_display)
                    self.after(0, lambda p=progress/100: self.progress_bar.set(p))
                    self.after(0, lambda d=total_downloaded, s=total_skipped: self._update_stats(d, s))

                if not self.stop_requested:
                    self.download_queue.update_status(idx, f'COMPLETE ({downloaded} images)')
                else:
                    self.download_queue.update_status(idx, 'TERMINATED')

                self.after(0, self._update_queue_display)

            except Exception as e:
                self.download_queue.update_status(idx, f'ERROR: {str(e)[:30]}')
                self.after(0, self._update_queue_display)

        self.downloader.close_driver()
        self.after(0, self._download_complete)

    def _update_status(self, text, color=COLORS['accent_green']):
        """Update status label"""
        self.status_label.configure(text=text, text_color=color)

    def _update_detail(self, text):
        """Update detail label"""
        self.detail_label.configure(text=f"  └─ {text}")

    def _update_stats(self, downloaded, skipped):
        """Update stats label"""
        self.stats_label.configure(text=f"Downloaded: {downloaded} | Skipped: {skipped}")

    def _log(self, msg):
        """Update log label"""
        self.log_label.configure(text=f"SYS > {msg[:50]}")

    def _download_complete(self):
        """Called when download is complete"""
        self.is_downloading = False

        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.add_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")
        self.progress_bar.set(0)

        if self.stop_requested:
            self._update_status("◉ TERMINATED", COLORS['warning'])
            self.connection_status.configure(text="● STOPPED", text_color=COLORS['warning'])
        else:
            self._update_status("◉ COMPLETE", COLORS['accent_green'])
            self.connection_status.configure(text="● READY", text_color=COLORS['accent_green'])

        self.stop_requested = False
        self._log("Operation finished")

    def on_closing(self):
        """Handle window close"""
        if self.is_downloading:
            self.stop_requested = True
            time.sleep(0.5)
        self.downloader.close_driver()
        self.destroy()


def main():
    app = BehanceDownloaderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
