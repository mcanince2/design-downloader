#!/usr/bin/env python3
"""
Design Downloader
Behance, Dribbble & Pinterest unified downloader with AI-powered folder organization
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
from urllib.parse import urlparse, quote
from datetime import datetime
from io import BytesIO

try:
    import customtkinter as ctk
    from CTkMessagebox import CTkMessagebox
    from PIL import Image, ImageTk, ImageDraw, ImageFilter
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install customtkinter CTkMessagebox pillow")
    import customtkinter as ctk
    from CTkMessagebox import CTkMessagebox
    from PIL import Image, ImageTk, ImageDraw, ImageFilter

from tkinter import filedialog
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ═══════════════════════════════════════════════════════════════
# COLOR SCHEME - Deep Purple & Neon with Glow
# ═══════════════════════════════════════════════════════════════
COLORS = {
    # Deep purple backgrounds
    'bg_darkest': '#0a0812',
    'bg_dark': '#120e1f',
    'bg_medium': '#1a1429',
    'bg_light': '#251d38',
    'bg_lighter': '#332850',

    # Main purple (neon glow)
    'purple_deep': '#331378',
    'purple': '#5a2d9c',
    'purple_bright': '#7c3aed',
    'purple_neon': '#a855f7',
    'purple_glow': '#c084fc',
    'purple_super_glow': '#e879f9',

    # Neon accents
    'neon_pink': '#ff2d95',
    'neon_cyan': '#00f5ff',
    'neon_green': '#39ff14',
    'neon_orange': '#ff6b35',
    'neon_yellow': '#f0ff00',

    # Platform colors (all purple themed)
    'behance': '#9333ea',
    'dribbble': '#a855f7',
    'pinterest': '#7c3aed',

    # Status colors
    'success': '#22c55e',
    'error': '#ef4444',
    'warning': '#f59e0b',

    # Text
    'text_primary': '#f8fafc',
    'text_secondary': '#a5b4c4',
    'text_dim': '#6b7a8a',

    # Borders with glow effect
    'border': '#3d2d5c',
    'border_glow': '#8b5cf6',
    'border_super_glow': '#a855f7',
}


# ═══════════════════════════════════════════════════════════════
# DOWNLOADER ENGINES
# ═══════════════════════════════════════════════════════════════

class BaseDownloader:
    """Base class for platform downloaders"""

    def __init__(self):
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        })

    def init_driver(self):
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def download_image(self, url, save_path, min_size=5000):
        """Download and validate image"""
        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()

            data = BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    data.write(chunk)

            data.seek(0)
            if data.getbuffer().nbytes < min_size:
                return False, "Too small"

            try:
                img = Image.open(data)
                img.verify()
                data.seek(0)
                img = Image.open(data)
                width, height = img.size
                if width < 200 or height < 200:
                    return False, "Dimensions too small"
            except Exception as e:
                return False, f"Invalid: {e}"

            data.seek(0)
            with open(save_path, 'wb') as f:
                f.write(data.read())

            return True, "OK"
        except Exception as e:
            return False, str(e)

    def get_thumbnail(self, url, size=(50, 50)):
        """Get thumbnail image for preview"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            data = BytesIO(response.content)
            img = Image.open(data)
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Make it square with padding
            square = Image.new('RGBA', size, (0, 0, 0, 0))
            offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
            square.paste(img, offset)

            return ctk.CTkImage(light_image=square, dark_image=square, size=size)
        except:
            return None


class BehanceEngine(BaseDownloader):
    """Behance download engine"""

    def extract_info(self, url):
        match = re.search(r'/gallery/(\d+)/([^/?]+)', url)
        if match:
            return match.group(1), match.group(2).replace('-', ' ')
        return None, None

    def _get_image_hash(self, url):
        match = re.search(r'/([a-f0-9]+)(?:_[a-f0-9]+)?\.(?:jpg|jpeg|png|gif|webp)', url, re.I)
        if match:
            return match.group(1)
        return os.path.basename(urlparse(url).path)

    def _get_size_score(self, url):
        scores = {
            '/source/': 1000, '/original/': 900, '/fs/': 700,
            '/1400/': 600, '/1200/': 500, '/808/': 400, '/404/': 200,
        }
        for pattern, score in scores.items():
            if pattern in url.lower():
                return score
        return 500

    def _upgrade_url(self, url):
        replacements = [
            (r'/disp/', '/source/'), (r'/404/', '/source/'),
            (r'/808/', '/source/'), (r'/1200/', '/source/'),
            (r'/1400/', '/source/'), (r'/fs/', '/source/'),
            (r'/max_\d+/', '/source/'),
        ]
        for pattern, repl in replacements:
            url = re.sub(pattern, repl, url)
        return url

    def _get_thumbnail_url(self, url):
        """Get smaller version for thumbnail"""
        return re.sub(r'/source/', '/404/', url)

    def get_images(self, url, callback=None):
        images = []
        try:
            self.init_driver()
            if callback: callback("Loading Behance page...")

            self.driver.get(url)
            time.sleep(3)

            initial_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_pos = 0
            max_scroll = initial_height * 0.7

            while scroll_pos < max_scroll:
                scroll_pos += 800
                self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                time.sleep(0.5)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            for section in soup.find_all(['section', 'div'], class_=re.compile(
                r'Recommend|Related|Suggested|MoreFrom|Comment|Owner|Stats', re.I
            )):
                section.decompose()

            for elem in soup.find_all(['footer', 'nav', 'header']):
                elem.decompose()

            if callback: callback("Extracting images...")

            candidates = {}
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and 'mir-s3-cdn-cf.behance.net' in src and '/project_modules/' in src:
                    if any(p in src.lower() for p in ['/50/', '/100/', '/115/', '/130/', '/202/', '/230/']):
                        continue

                    img_hash = self._get_image_hash(src)
                    score = self._get_size_score(src)

                    if img_hash not in candidates or score > candidates[img_hash]['score']:
                        candidates[img_hash] = {'url': src, 'score': score}

            for data in candidates.values():
                images.append(self._upgrade_url(data['url']))

            if callback: callback(f"Found {len(images)} images")

        except Exception as e:
            if callback: callback(f"Error: {e}")

        return images

    def get_first_image_url(self, url):
        """Get first image URL for preview without full scraping"""
        try:
            self.init_driver()
            self.driver.get(url)
            time.sleep(2)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and 'mir-s3-cdn-cf.behance.net' in src and '/project_modules/' in src:
                    if not any(p in src.lower() for p in ['/50/', '/100/', '/115/', '/130/']):
                        # Return thumbnail version
                        return re.sub(r'/(source|fs|1400|1200|808)/', '/404/', src)

        except:
            pass
        return None

    def search(self, query, limit=20, callback=None):
        """Search Behance and return gallery URLs"""
        results = []
        try:
            self.init_driver()
            if callback: callback(f"Searching Behance: {query}...")

            search_url = f"https://www.behance.net/search/projects?search={quote(query)}"
            self.driver.get(search_url)
            time.sleep(4)

            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            for link in soup.find_all('a', href=re.compile(r'/gallery/\d+')):
                href = link.get('href')
                if href and '/gallery/' in href:
                    full_url = f"https://www.behance.net{href}" if href.startswith('/') else href
                    if full_url not in results:
                        results.append(full_url)
                        if len(results) >= limit:
                            break

            if callback: callback(f"Found {len(results)} projects")

        except Exception as e:
            if callback: callback(f"Search error: {e}")

        return results[:limit]


class DribbbleEngine(BaseDownloader):
    """Dribbble download engine"""

    def extract_info(self, url):
        match = re.search(r'/shots/(\d+)(?:-([^/?]+))?', url)
        if match:
            shot_id = match.group(1)
            name = match.group(2).replace('-', ' ') if match.group(2) else f"Shot {shot_id}"
            return shot_id, name
        return None, None

    def _get_image_hash(self, url):
        match = re.search(r'/([a-f0-9-]+)(?:_\d+x)?\.(?:jpg|jpeg|png|gif|webp)', url, re.I)
        if match:
            return match.group(1)
        return os.path.basename(urlparse(url).path)

    def _upgrade_url(self, url):
        url = re.sub(r'_teaser\.', '_4x.', url)
        url = re.sub(r'_small\.', '_4x.', url)
        url = re.sub(r'_1x\.', '_4x.', url)
        url = re.sub(r'\?.*$', '', url)
        return url

    def get_images(self, url, callback=None):
        images = []
        try:
            self.init_driver()
            if callback: callback("Loading Dribbble page...")

            # Extract shot ID from URL to filter only main shot images
            shot_id, _ = self.extract_info(url)

            self.driver.get(url)
            time.sleep(3)

            # Only scroll a bit - we don't want to load recommended shots
            for _ in range(2):
                self.driver.execute_script("window.scrollTo(0, 800);")
                time.sleep(0.3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            if callback: callback("Extracting main shot images...")

            found = set()

            # Method 1: Find the main shot content container
            # Main shot images are in containers like: media-shot, shot-media-container, mediabox
            main_containers = soup.find_all(['div', 'figure', 'section'], class_=re.compile(
                r'media-shot|shot-media|mediabox|shot__media|media-content|shot-content|'
                r'attachment|carousel|gallery-container|shot-page-container',
                re.I
            ))

            for container in main_containers:
                # Skip if container looks like recommendations/related
                container_class = ' '.join(container.get('class', []))
                if any(skip in container_class.lower() for skip in ['related', 'suggest', 'recommend', 'more-from', 'sidebar']):
                    continue

                for img in container.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if not src:
                        continue

                    if 'dribbble' in src.lower() or 'cdn.dribbble.com' in src:
                        if any(p in src.lower() for p in ['/avatars/', '/mini/', '/small/', '/teaser/', '50x50', '80x80', '100x100']):
                            continue

                        high_res = self._upgrade_url(src)
                        img_hash = self._get_image_hash(high_res)

                        if img_hash not in found:
                            found.add(img_hash)
                            images.append(high_res)

            # Method 2: Look for picture elements in main content
            for container in main_containers:
                for picture in container.find_all('picture'):
                    for source in picture.find_all('source'):
                        srcset = source.get('srcset', '')
                        urls = re.findall(r'(https://[^\s,]+)', srcset)
                        for u in urls:
                            if 'dribbble' in u.lower():
                                high_res = self._upgrade_url(u)
                                img_hash = self._get_image_hash(high_res)
                                if img_hash not in found:
                                    found.add(img_hash)
                                    images.append(high_res)

            # Method 3: If no images found in containers, try finding shot-specific images by ID
            if not images and shot_id:
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if not src:
                        continue

                    # Only include images that contain the shot ID in the URL
                    if shot_id in src and ('dribbble' in src.lower() or 'cdn.dribbble.com' in src):
                        if any(p in src.lower() for p in ['/avatars/', '/mini/', '/small/', '/teaser/', '50x50', '80x80']):
                            continue

                        high_res = self._upgrade_url(src)
                        img_hash = self._get_image_hash(high_res)

                        if img_hash not in found:
                            found.add(img_hash)
                            images.append(high_res)

            # Fallback: If still nothing, get first few large images (likely the main shot)
            if not images:
                all_imgs = []
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if not src:
                        continue

                    if 'dribbble' in src.lower() or 'cdn.dribbble.com' in src:
                        # Skip small thumbnails and avatars
                        if any(p in src.lower() for p in ['/avatars/', '/mini/', '/small/', '/teaser/', '50x50', '80x80', '100x100']):
                            continue

                        # Skip if it's clearly from another shot (has different numeric ID pattern)
                        if shot_id and re.search(r'/shots/(\d+)', src):
                            img_shot_id = re.search(r'/shots/(\d+)', src).group(1)
                            if img_shot_id != shot_id:
                                continue

                        high_res = self._upgrade_url(src)
                        img_hash = self._get_image_hash(high_res)

                        if img_hash not in found:
                            found.add(img_hash)
                            all_imgs.append(high_res)

                # Take only first 10 images max (main shot usually has 1-10 images)
                images = all_imgs[:10]

            if callback: callback(f"Found {len(images)} main images")

        except Exception as e:
            if callback: callback(f"Error: {e}")

        return images

    def search(self, query, limit=20, callback=None):
        """Search Dribbble and return shot URLs"""
        results = []
        try:
            self.init_driver()
            if callback: callback(f"Searching Dribbble: {query}...")

            search_url = f"https://dribbble.com/search/shots/popular?q={quote(query)}"
            self.driver.get(search_url)
            time.sleep(4)

            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            for link in soup.find_all('a', href=re.compile(r'/shots/\d+')):
                href = link.get('href')
                if href and '/shots/' in href:
                    full_url = f"https://dribbble.com{href}" if href.startswith('/') else href
                    full_url = re.sub(r'\?.*$', '', full_url)
                    if full_url not in results and '/shots/' in full_url:
                        results.append(full_url)
                        if len(results) >= limit:
                            break

            if callback: callback(f"Found {len(results)} shots")

        except Exception as e:
            if callback: callback(f"Search error: {e}")

        return results[:limit]


class PinterestEngine(BaseDownloader):
    """Pinterest download engine"""

    def extract_info(self, url):
        # Handle pin URLs: pinterest.com/pin/123456/
        match = re.search(r'/pin/(\d+)', url)
        if match:
            return match.group(1), f"Pin {match.group(1)}"
        # Handle board URLs
        match = re.search(r'pinterest\.com/([^/]+)/([^/]+)', url)
        if match:
            return match.group(2), match.group(2).replace('-', ' ')
        # Handle search URLs
        match = re.search(r'[?&]q=([^&]+)', url)
        if match:
            return "search", match.group(1).replace('+', ' ')
        return None, None

    def _get_image_hash(self, url):
        match = re.search(r'/([a-f0-9]+)(?:_[a-f0-9]+)?\.(?:jpg|jpeg|png|gif|webp)', url, re.I)
        if match:
            return match.group(1)
        return os.path.basename(urlparse(url).path)

    def _upgrade_url(self, url):
        # Pinterest uses /originals/ for full resolution
        url = re.sub(r'/\d+x/', '/originals/', url)
        url = re.sub(r'/\d+x\d+/', '/originals/', url)
        url = re.sub(r'/236x/', '/originals/', url)
        url = re.sub(r'/474x/', '/originals/', url)
        url = re.sub(r'/736x/', '/originals/', url)
        return url

    def _is_pin_page(self, url):
        """Check if URL is a pin detail page"""
        return '/pin/' in url and 'search' not in url

    def get_images(self, url, callback=None):
        """Get images from Pinterest - handles both pin pages and search/board pages"""
        images = []
        try:
            self.init_driver()

            if self._is_pin_page(url):
                # Single pin page - get main image and related pins
                if callback: callback("Loading Pinterest pin...")
                images = self._get_pin_images(url, callback)
            else:
                # Board or search page - get all visible pins
                if callback: callback("Loading Pinterest page...")
                images = self._get_board_images(url, callback)

        except Exception as e:
            if callback: callback(f"Error: {e}")

        return images

    def _get_pin_images(self, url, callback=None):
        """Get main pin image and related images"""
        images = []
        found = set()

        self.driver.get(url)
        time.sleep(3)

        # Scroll to load related pins
        for _ in range(3):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        if callback: callback("Extracting main pin and related images...")

        # First, get the main pin image (usually the largest one or in specific container)
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src or 'pinimg.com' not in src:
                continue

            # Skip avatars and tiny thumbnails
            if any(p in src.lower() for p in ['/75x/', '/140x/', '/avatars/', 'profile', 'user']):
                continue

            high_res = self._upgrade_url(src)
            img_hash = self._get_image_hash(high_res)

            if img_hash not in found:
                found.add(img_hash)
                images.append(high_res)

        if callback: callback(f"Found {len(images)} images")
        return images

    def _get_board_images(self, url, callback=None):
        """Get images from board or search page"""
        images = []
        found = set()

        self.driver.get(url)
        time.sleep(4)

        # Scroll to load more images
        for _ in range(5):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        if callback: callback("Extracting images...")

        # Find all pin images
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src:
                continue

            if 'pinimg.com' in src:
                # Skip small thumbnails and avatars
                if any(p in src.lower() for p in ['/75x/', '/140x/', '/avatars/', 'profile', 'user']):
                    continue

                high_res = self._upgrade_url(src)
                img_hash = self._get_image_hash(high_res)

                if img_hash not in found:
                    found.add(img_hash)
                    images.append(high_res)

        # Also check srcset for higher quality
        for img in soup.find_all('img', srcset=True):
            srcset = img.get('srcset', '')
            urls = re.findall(r'(https://[^\s,]+pinimg\.com[^\s,]+)', srcset)
            for u in urls:
                high_res = self._upgrade_url(u)
                img_hash = self._get_image_hash(high_res)
                if img_hash not in found:
                    found.add(img_hash)
                    images.append(high_res)

        if callback: callback(f"Found {len(images)} images")
        return images

    def search(self, query, limit=20, callback=None):
        """Search Pinterest and return direct image URLs for download"""
        images = []
        try:
            self.init_driver()
            if callback: callback(f"Searching Pinterest: {query}...")

            search_url = f"https://www.pinterest.com/search/pins/?q={quote(query)}"
            self.driver.get(search_url)
            time.sleep(4)

            # Calculate scroll iterations based on limit
            scroll_count = min(limit // 10 + 2, 10)

            for i in range(scroll_count):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
                if callback: callback(f"Loading more results... ({i+1}/{scroll_count})")

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            if callback: callback("Extracting search results...")

            found = set()

            # Get images directly from search results
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if not src or 'pinimg.com' not in src:
                    continue

                # Skip avatars and tiny thumbnails
                if any(p in src.lower() for p in ['/75x/', '/140x/', '/avatars/', 'profile', 'user']):
                    continue

                high_res = self._upgrade_url(src)
                img_hash = self._get_image_hash(high_res)

                if img_hash not in found:
                    found.add(img_hash)
                    images.append(high_res)
                    if len(images) >= limit:
                        break

            if callback: callback(f"Found {len(images)} images")

        except Exception as e:
            if callback: callback(f"Search error: {e}")

        return images[:limit]

    def search_pins(self, query, limit=20, callback=None):
        """Search Pinterest and return pin URLs (for link-based download)"""
        results = []
        try:
            self.init_driver()
            if callback: callback(f"Searching Pinterest pins: {query}...")

            search_url = f"https://www.pinterest.com/search/pins/?q={quote(query)}"
            self.driver.get(search_url)
            time.sleep(4)

            scroll_count = min(limit // 10 + 2, 10)

            for _ in range(scroll_count):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            for link in soup.find_all('a', href=re.compile(r'/pin/\d+')):
                href = link.get('href')
                if href and '/pin/' in href:
                    full_url = f"https://www.pinterest.com{href}" if href.startswith('/') else href
                    full_url = re.sub(r'\?.*$', '', full_url)
                    if full_url not in results:
                        results.append(full_url)
                        if len(results) >= limit:
                            break

            if callback: callback(f"Found {len(results)} pins")

        except Exception as e:
            if callback: callback(f"Search error: {e}")

        return results[:limit]


# ═══════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════

class ProjectFolder:
    """Represents a project folder with links"""

    def __init__(self, name, keywords=None):
        self.name = name
        self.keywords = keywords or []
        self.links = []

    def add_link(self, url, platform, thumbnail_url=None):
        self.links.append({
            'url': url,
            'platform': platform,
            'status': 'pending',
            'progress': 0,
            'thumbnail_url': thumbnail_url,
            'thumbnail': None  # Will be loaded async
        })

    def remove_link(self, index):
        if 0 <= index < len(self.links):
            del self.links[index]

    def matches_keywords(self, text):
        """Check if text matches folder keywords"""
        text_lower = text.lower()
        folder_name_lower = self.name.lower()

        if folder_name_lower in text_lower:
            return True

        for kw in self.keywords:
            if kw.lower() in text_lower:
                return True

        return False


class ProjectManager:
    """Manages all project folders"""

    def __init__(self):
        self.folders = {}

    def create_folder(self, name, keywords=None):
        if name and name not in self.folders:
            self.folders[name] = ProjectFolder(name, keywords)
            return True
        return False

    def delete_folder(self, name):
        if name in self.folders:
            del self.folders[name]
            return True
        return False

    def get_folder(self, name):
        return self.folders.get(name)

    def get_all_folders(self):
        return list(self.folders.keys())

    def get_total_links(self):
        return sum(len(f.links) for f in self.folders.values())

    def find_matching_folder(self, text):
        """Find folder that matches given text (for auto-foldering)"""
        for name, folder in self.folders.items():
            if folder.matches_keywords(text):
                return name
        return None


# ═══════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════

class GlowFrame(ctk.CTkFrame):
    """Custom styled frame with purple glow effect"""

    def __init__(self, master, title=None, glow_intensity=1, **kwargs):
        # Glow border colors based on intensity
        if glow_intensity >= 2:
            border_color = COLORS['purple_super_glow']
            border_width = 2
        elif glow_intensity >= 1:
            border_color = COLORS['border_glow']
            border_width = 2
        else:
            border_color = COLORS['border']
            border_width = 1

        super().__init__(
            master,
            fg_color=COLORS['bg_medium'],
            border_color=border_color,
            border_width=border_width,
            corner_radius=12,
            **kwargs
        )

        if title:
            header = ctk.CTkFrame(self, fg_color="transparent", height=38)
            header.pack(fill="x", padx=18, pady=(14, 6))

            # Glowing accent bar
            accent = ctk.CTkFrame(
                header,
                fg_color=COLORS['purple_neon'],
                width=4,
                height=20,
                corner_radius=2
            )
            accent.pack(side="left", padx=(0, 14))

            ctk.CTkLabel(
                header,
                text=title.upper(),
                font=ctk.CTkFont(family="SF Pro Display", size=13, weight="bold"),
                text_color=COLORS['purple_glow']
            ).pack(side="left")


class FolderItem(ctk.CTkFrame):
    """Folder list item with glow effect on selection"""

    def __init__(self, master, name, link_count, selected=False, is_system=False, on_click=None, on_delete=None):
        if selected:
            bg = COLORS['purple_deep']
            border = COLORS['purple_neon']
            border_width = 2
        else:
            bg = COLORS['bg_dark']
            border = COLORS['border']
            border_width = 1

        super().__init__(
            master,
            fg_color=bg,
            border_color=border,
            border_width=border_width,
            corner_radius=10,
            height=54
        )
        self.pack_propagate(False)

        self.name = name
        self.on_click = on_click
        self.on_delete = on_delete
        self.is_system = is_system

        self.bind("<Button-1>", self._clicked)

        # Folder icon
        icon_text = "📂" if selected else ("💾" if is_system else "📁")
        icon = ctk.CTkLabel(
            self,
            text=icon_text,
            font=ctk.CTkFont(size=20)
        )
        icon.pack(side="left", padx=(14, 10))
        icon.bind("<Button-1>", self._clicked)

        # Name and count
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)
        info_frame.bind("<Button-1>", self._clicked)

        name_color = COLORS['text_primary'] if selected else COLORS['text_secondary']
        name_label = ctk.CTkLabel(
            info_frame,
            text=name[:20] + "..." if len(name) > 20 else name,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=name_color,
            anchor="w"
        )
        name_label.pack(anchor="w", pady=(10, 0))
        name_label.bind("<Button-1>", self._clicked)

        count_text = f"{link_count} links" if not is_system else "System folder"
        count_label = ctk.CTkLabel(
            info_frame,
            text=count_text,
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_dim'],
            anchor="w"
        )
        count_label.pack(anchor="w")
        count_label.bind("<Button-1>", self._clicked)

        # Delete button (only for non-system folders)
        if not is_system and on_delete:
            del_btn = ctk.CTkButton(
                self,
                text="×",
                width=32,
                height=32,
                font=ctk.CTkFont(size=18),
                fg_color="transparent",
                hover_color=COLORS['error'],
                text_color=COLORS['text_dim'],
                corner_radius=6,
                command=self._delete
            )
            del_btn.pack(side="right", padx=10)

    def _clicked(self, event=None):
        if self.on_click:
            self.on_click(self.name)

    def _delete(self):
        if self.on_delete:
            self.on_delete(self.name)


class LinkItem(ctk.CTkFrame):
    """Link list item with thumbnail preview"""

    def __init__(self, master, url, platform, status, index, thumbnail=None, on_delete=None):
        super().__init__(master, fg_color=COLORS['bg_dark'], corner_radius=8, height=56)
        self.pack_propagate(False)

        # Thumbnail preview
        thumb_frame = ctk.CTkFrame(self, fg_color=COLORS['bg_medium'], corner_radius=6, width=44, height=44)
        thumb_frame.pack(side="left", padx=(8, 10), pady=6)
        thumb_frame.pack_propagate(False)

        if thumbnail:
            thumb_label = ctk.CTkLabel(thumb_frame, image=thumbnail, text="")
            thumb_label.pack(expand=True)
        else:
            # Placeholder with platform indicator
            platform_labels = {'behance': 'BE', 'dribbble': 'DR', 'pinterest': 'PI'}
            placeholder_text = platform_labels.get(platform, 'XX')
            placeholder_color = COLORS.get(platform, COLORS['purple_neon'])
            ctk.CTkLabel(
                thumb_frame,
                text=placeholder_text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=placeholder_color
            ).pack(expand=True)

        # Platform badge (purple themed)
        platform_labels = {'behance': 'BE', 'dribbble': 'DR', 'pinterest': 'PI'}
        badge_color = COLORS.get(platform, COLORS['purple_neon'])
        badge_text = platform_labels.get(platform, 'XX')

        badge = ctk.CTkLabel(
            self,
            text=badge_text,
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=badge_color,
            text_color=COLORS['text_primary'],
            corner_radius=3,
            width=26,
            height=18
        )
        badge.pack(side="left", padx=(0, 8))

        # URL
        display_url = url[:45] + "..." if len(url) > 45 else url
        url_label = ctk.CTkLabel(
            self,
            text=display_url,
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_secondary'],
            anchor="w"
        )
        url_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Status indicator with glow
        status_config = {
            'pending': (COLORS['text_dim'], "○", "PENDING"),
            'downloading': (COLORS['neon_cyan'], "◉", "LOADING"),
            'complete': (COLORS['neon_green'], "✓", "DONE"),
            'error': (COLORS['error'], "✕", "ERROR")
        }
        color, symbol, text = status_config.get(status, (COLORS['text_dim'], "○", "PENDING"))

        status_label = ctk.CTkLabel(
            self,
            text=f"{symbol} {text}",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=color
        )
        status_label.pack(side="right", padx=10)

        # Delete button
        if on_delete:
            del_btn = ctk.CTkButton(
                self,
                text="×",
                width=24,
                height=24,
                font=ctk.CTkFont(size=14),
                fg_color="transparent",
                hover_color=COLORS['error'],
                text_color=COLORS['text_dim'],
                command=lambda: on_delete(index)
            )
            del_btn.pack(side="right", padx=(0, 4))


class SystemFolderItem(ctk.CTkFrame):
    """System folder from filesystem - clickable to select for adding links"""

    def __init__(self, master, name, path, file_count=0, selected=False, on_click=None):
        self.name = name
        self.path = path
        self.on_click = on_click

        if selected:
            bg = COLORS['purple_deep']
            border = COLORS['purple_neon']
            text_color = COLORS['text_primary']
        else:
            bg = COLORS['bg_dark']
            border = COLORS['border']
            text_color = COLORS['text_dim']

        super().__init__(
            master,
            fg_color=bg,
            border_color=border,
            border_width=1 if not selected else 2,
            corner_radius=8,
            height=44
        )
        self.pack_propagate(False)

        # Make frame clickable
        self.bind("<Button-1>", self._clicked)

        # Folder icon
        icon = ctk.CTkLabel(
            self,
            text="📂" if selected else "💾",
            font=ctk.CTkFont(size=16)
        )
        icon.pack(side="left", padx=(12, 8))
        icon.bind("<Button-1>", self._clicked)

        # Name
        name_label = ctk.CTkLabel(
            self,
            text=name[:25] + "..." if len(name) > 25 else name,
            font=ctk.CTkFont(size=11, weight="bold" if selected else "normal"),
            text_color=text_color,
            anchor="w"
        )
        name_label.pack(side="left", fill="x", expand=True)
        name_label.bind("<Button-1>", self._clicked)

        # File count
        count_label = ctk.CTkLabel(
            self,
            text=f"{file_count} files",
            font=ctk.CTkFont(size=10),
            text_color=text_color
        )
        count_label.pack(side="right", padx=12)
        count_label.bind("<Button-1>", self._clicked)

    def _clicked(self, event=None):
        if self.on_click:
            self.on_click(self.name, self.path)


# ═══════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════

class DesignDownloaderApp(ctk.CTk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Window config
        self.title("Design Downloader")
        self.geometry("1350x920")
        self.minsize(1150, 800)
        self.configure(fg_color=COLORS['bg_darkest'])

        ctk.set_appearance_mode("dark")

        # Initialize
        self.project_manager = ProjectManager()
        self.behance_engine = BehanceEngine()
        self.dribbble_engine = DribbbleEngine()
        self.pinterest_engine = PinterestEngine()

        self.selected_folder = None
        self.selected_system_folder = None  # Track selected system folder (name, path)
        self.download_folder = str(Path.home() / "Downloads" / "DesignDownloads")
        self.is_downloading = False
        self.stop_requested = False
        self.auto_folder_enabled = ctk.BooleanVar(value=False)
        self.thumbnail_cache = {}

        # Load logo
        self.logo_image = None
        self._load_logo()

        os.makedirs(self.download_folder, exist_ok=True)

        # Create UI
        self._create_ui()

    def _load_logo(self):
        """Load the app logo with proper aspect ratio (optional)"""
        try:
            logo_path = Path(__file__).parent / "logo.png"
            if logo_path.exists():
                img = Image.open(logo_path)

                # Calculate size maintaining aspect ratio
                target_height = 42
                aspect_ratio = img.width / img.height
                target_width = int(target_height * aspect_ratio)

                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=(target_width, target_height))
        except Exception as e:
            print(f"Logo load error: {e}")

    def _create_ui(self):
        """Create the main interface"""
        # Header
        self._create_header()

        # Main content area
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Top section (experimental search)
        self._create_search_section(content)

        # Middle section (folders and links)
        middle = ctk.CTkFrame(content, fg_color="transparent")
        middle.pack(fill="both", expand=True, pady=(15, 0))

        self._create_left_panel(middle)
        self._create_right_panel(middle)

        # Bottom panel
        self._create_bottom_panel()

    def _create_header(self):
        """Create header with logo and controls"""
        header = ctk.CTkFrame(self, fg_color=COLORS['bg_dark'], height=75, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=25, pady=12)

        # Logo and title
        title_frame = ctk.CTkFrame(inner, fg_color="transparent")
        title_frame.pack(side="left")

        if self.logo_image:
            logo_label = ctk.CTkLabel(title_frame, image=self.logo_image, text="")
            logo_label.pack(side="left", padx=(0, 15))
        else:
            # Fallback icon with glow effect
            ctk.CTkLabel(
                title_frame,
                text="◆",
                font=ctk.CTkFont(size=32),
                text_color=COLORS['purple_neon']
            ).pack(side="left", padx=(0, 12))

        # Title text
        text_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        text_frame.pack(side="left")

        ctk.CTkLabel(
            text_frame,
            text="Design Downloader",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS['text_primary']
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_frame,
            text="Behance • Dribbble • Pinterest",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['purple_glow']
        ).pack(anchor="w")

        # Auto-folder checkbox
        auto_frame = ctk.CTkFrame(inner, fg_color="transparent")
        auto_frame.pack(side="left", padx=(40, 0))

        self.auto_folder_check = ctk.CTkCheckBox(
            auto_frame,
            text="Auto Foldering",
            variable=self.auto_folder_enabled,
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_secondary'],
            fg_color=COLORS['purple_neon'],
            hover_color=COLORS['purple_bright'],
            checkmark_color=COLORS['bg_darkest'],
            border_color=COLORS['purple_deep']
        )
        self.auto_folder_check.pack(side="left")

        # Status indicator with glow
        self.status_indicator = ctk.CTkLabel(
            inner,
            text="● Ready",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS['neon_green']
        )
        self.status_indicator.pack(side="right")

    def _create_search_section(self, parent):
        """Create experimental search section with glow"""
        frame = GlowFrame(parent, title="Bulk Search & Download", glow_intensity=2)
        frame.pack(fill="x", pady=(0, 0))

        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=18, pady=(5, 15))

        # Search input row
        search_row = ctk.CTkFrame(content, fg_color="transparent")
        search_row.pack(fill="x")

        self.search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Enter search query (e.g., 'mobile app design', 'logo branding')...",
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color=COLORS['bg_dark'],
            border_color=COLORS['purple_deep'],
            text_color=COLORS['text_primary']
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.search_entry.bind("<Return>", lambda e: self._start_search())

        # Platform checkboxes
        self.search_behance = ctk.BooleanVar(value=True)
        self.search_dribbble = ctk.BooleanVar(value=True)
        self.search_pinterest = ctk.BooleanVar(value=True)

        platform_frame = ctk.CTkFrame(search_row, fg_color="transparent")
        platform_frame.pack(side="left", padx=(0, 12))

        ctk.CTkCheckBox(
            platform_frame,
            text="Behance",
            variable=self.search_behance,
            font=ctk.CTkFont(size=11),
            text_color=COLORS['behance'],
            fg_color=COLORS['behance'],
            hover_color=COLORS['purple_bright'],
            width=80
        ).pack(side="left", padx=(0, 6))

        ctk.CTkCheckBox(
            platform_frame,
            text="Dribbble",
            variable=self.search_dribbble,
            font=ctk.CTkFont(size=11),
            text_color=COLORS['dribbble'],
            fg_color=COLORS['dribbble'],
            hover_color=COLORS['purple_bright'],
            width=80
        ).pack(side="left", padx=(0, 6))

        ctk.CTkCheckBox(
            platform_frame,
            text="Pinterest",
            variable=self.search_pinterest,
            font=ctk.CTkFont(size=11),
            text_color=COLORS['pinterest'],
            fg_color=COLORS['pinterest'],
            hover_color=COLORS['purple_bright'],
            width=80
        ).pack(side="left")

        # Results count frame
        count_frame = ctk.CTkFrame(search_row, fg_color="transparent")
        count_frame.pack(side="left", padx=(12, 12))

        ctk.CTkLabel(
            count_frame,
            text="Results:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_dim']
        ).pack(side="left", padx=(0, 6))

        # Minus button
        ctk.CTkButton(
            count_frame,
            text="-",
            width=28,
            height=28,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['purple_deep'],
            command=lambda: self._adjust_search_count(-10)
        ).pack(side="left")

        # Count display
        self.search_count_var = ctk.StringVar(value="20")
        self.search_count_entry = ctk.CTkEntry(
            count_frame,
            textvariable=self.search_count_var,
            width=50,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS['bg_dark'],
            border_color=COLORS['purple_deep'],
            text_color=COLORS['purple_glow'],
            justify="center"
        )
        self.search_count_entry.pack(side="left", padx=4)

        # Plus button
        ctk.CTkButton(
            count_frame,
            text="+",
            width=28,
            height=28,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['purple_deep'],
            command=lambda: self._adjust_search_count(10)
        ).pack(side="left")

        # Search button with glow
        self.search_btn = ctk.CTkButton(
            search_row,
            text="🔍 Search & Download",
            width=180,
            height=42,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS['purple_neon'],
            hover_color=COLORS['purple_super_glow'],
            border_width=1,
            border_color=COLORS['purple_glow'],
            command=self._start_search
        )
        self.search_btn.pack(side="right")

        # Info label
        info = ctk.CTkLabel(
            content,
            text="Search selected platforms and download results to a new folder. Max 100 per platform.",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_dim']
        )
        info.pack(anchor="w", pady=(8, 0))

    def _adjust_search_count(self, delta):
        """Adjust search results count by delta"""
        try:
            current = int(self.search_count_var.get())
        except ValueError:
            current = 20
        new_val = max(5, min(100, current + delta))  # Clamp between 5 and 100
        self.search_count_var.set(str(new_val))

    def _get_search_count(self):
        """Get validated search count"""
        try:
            count = int(self.search_count_var.get())
            return max(5, min(100, count))  # Clamp between 5 and 100
        except ValueError:
            return 20

    def _create_left_panel(self, parent):
        """Create left panel with folders"""
        left = GlowFrame(parent, title="Project Folders", glow_intensity=1)
        left.pack(side="left", fill="y", padx=(0, 15))
        left.configure(width=340)
        left.pack_propagate(False)

        # New folder input
        input_frame = ctk.CTkFrame(left, fg_color="transparent")
        input_frame.pack(fill="x", padx=18, pady=(5, 12))

        self.folder_name_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="New folder name...",
            height=40,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS['bg_dark'],
            border_color=COLORS['purple_deep'],
            text_color=COLORS['text_primary']
        )
        self.folder_name_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.folder_name_entry.bind("<Return>", lambda e: self._create_folder())

        create_btn = ctk.CTkButton(
            input_frame,
            text="+",
            width=40,
            height=40,
            font=ctk.CTkFont(size=20),
            fg_color=COLORS['purple_neon'],
            hover_color=COLORS['purple_super_glow'],
            border_width=1,
            border_color=COLORS['purple_glow'],
            corner_radius=8,
            command=self._create_folder
        )
        create_btn.pack(side="right")

        # Keywords input
        keywords_frame = ctk.CTkFrame(left, fg_color="transparent")
        keywords_frame.pack(fill="x", padx=18, pady=(0, 10))

        self.keywords_entry = ctk.CTkEntry(
            keywords_frame,
            placeholder_text="Keywords for auto-folder (comma separated)...",
            height=32,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['bg_dark'],
            border_color=COLORS['border'],
            text_color=COLORS['text_dim']
        )
        self.keywords_entry.pack(fill="x")

        # Folders list (project folders)
        folders_label = ctk.CTkLabel(
            left,
            text="PROJECT FOLDERS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS['text_dim']
        )
        folders_label.pack(anchor="w", padx=18, pady=(5, 5))

        self.folders_container = ctk.CTkScrollableFrame(
            left,
            fg_color="transparent",
            height=200,
            scrollbar_fg_color=COLORS['bg_dark'],
            scrollbar_button_color=COLORS['purple_deep']
        )
        self.folders_container.pack(fill="x", padx=18, pady=(0, 10))

        # System folders (from output directory)
        system_label = ctk.CTkLabel(
            left,
            text="OUTPUT DIRECTORY",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS['text_dim']
        )
        system_label.pack(anchor="w", padx=18, pady=(5, 5))

        self.system_folders_container = ctk.CTkScrollableFrame(
            left,
            fg_color="transparent",
            scrollbar_fg_color=COLORS['bg_dark'],
            scrollbar_button_color=COLORS['purple_deep']
        )
        self.system_folders_container.pack(fill="both", expand=True, padx=18, pady=(0, 15))

        self._update_folders_list()
        self._update_system_folders()

    def _create_right_panel(self, parent):
        """Create right panel with links"""
        right = GlowFrame(parent, title="Links", glow_intensity=1)
        right.pack(side="left", fill="both", expand=True)

        # Folder title
        self.folder_title_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.folder_title_frame.pack(fill="x", padx=18, pady=(0, 10))

        self.folder_title = ctk.CTkLabel(
            self.folder_title_frame,
            text="Select a folder to add links",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS['text_dim']
        )
        self.folder_title.pack(side="left")

        # Add link section
        add_frame = ctk.CTkFrame(right, fg_color=COLORS['bg_dark'], corner_radius=10)
        add_frame.pack(fill="x", padx=18, pady=(0, 15))

        # URL row
        url_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        url_row.pack(fill="x", padx=14, pady=(14, 10))

        self.url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="Paste Behance, Dribbble or Pinterest URL...",
            height=42,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS['bg_medium'],
            border_color=COLORS['purple_deep'],
            text_color=COLORS['text_primary']
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.url_entry.bind("<Return>", lambda e: self._add_link())

        # Platform selector
        self.platform_var = ctk.StringVar(value="auto")

        platform_frame = ctk.CTkFrame(url_row, fg_color="transparent")
        platform_frame.pack(side="right")

        for val, text, color in [("auto", "Auto", COLORS['purple_glow']),
                                  ("behance", "BE", COLORS['behance']),
                                  ("dribbble", "DR", COLORS['dribbble']),
                                  ("pinterest", "PI", COLORS['pinterest'])]:
            ctk.CTkRadioButton(
                platform_frame,
                text=text,
                variable=self.platform_var,
                value=val,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=color,
                fg_color=color,
                hover_color=COLORS['purple_deep'],
                width=55
            ).pack(side="left", padx=3)

        # Add button
        btn_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 14))

        self.add_link_btn = ctk.CTkButton(
            btn_row,
            text="+ Add Link",
            height=38,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS['purple_neon'],
            hover_color=COLORS['purple_super_glow'],
            border_width=1,
            border_color=COLORS['purple_glow'],
            state="disabled",
            command=self._add_link
        )
        self.add_link_btn.pack(side="left", padx=(0, 8))

        self.clear_url_btn = ctk.CTkButton(
            btn_row,
            text="Clear",
            height=38,
            width=70,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['bg_lighter'],
            border_width=1,
            border_color=COLORS['purple_deep'],
            text_color=COLORS['text_secondary'],
            command=self._clear_url_entry
        )
        self.clear_url_btn.pack(side="left")

        # Links list
        self.links_container = ctk.CTkScrollableFrame(
            right,
            fg_color="transparent",
            scrollbar_fg_color=COLORS['bg_dark'],
            scrollbar_button_color=COLORS['purple_deep']
        )
        self.links_container.pack(fill="both", expand=True, padx=18, pady=(0, 15))

        # Empty state
        self._show_empty_state()

    def _show_empty_state(self):
        """Show empty state message"""
        for widget in self.links_container.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.links_container,
            text="No links added yet\nSelect a folder and paste URLs above",
            font=ctk.CTkFont(size=13),
            text_color=COLORS['text_dim'],
            justify="center"
        ).pack(expand=True, pady=50)

    def _create_bottom_panel(self):
        """Create bottom control panel"""
        bottom = ctk.CTkFrame(self, fg_color=COLORS['bg_dark'], height=110, corner_radius=0)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        inner = ctk.CTkFrame(bottom, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=25, pady=15)

        # Top row
        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 10))

        # Output folder
        ctk.CTkLabel(
            top_row,
            text="Output:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS['text_dim']
        ).pack(side="left", padx=(0, 10))

        self.output_entry = ctk.CTkEntry(
            top_row,
            height=34,
            width=400,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['bg_medium'],
            border_color=COLORS['purple_deep'],
            text_color=COLORS['purple_glow']
        )
        self.output_entry.insert(0, self.download_folder)
        self.output_entry.pack(side="left", padx=(0, 10))
        self.output_entry.bind("<FocusOut>", lambda e: self._update_system_folders())

        browse_btn = ctk.CTkButton(
            top_row,
            text="Browse",
            width=80,
            height=34,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['bg_lighter'],
            command=self._browse_output
        )
        browse_btn.pack(side="left")

        # Refresh button
        refresh_btn = ctk.CTkButton(
            top_row,
            text="↻",
            width=34,
            height=34,
            font=ctk.CTkFont(size=14),
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['purple_deep'],
            command=self._update_system_folders
        )
        refresh_btn.pack(side="left", padx=(8, 0))

        # Stats
        self.stats_label = ctk.CTkLabel(
            top_row,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_secondary']
        )
        self.stats_label.pack(side="right")

        # Bottom row
        bottom_row = ctk.CTkFrame(inner, fg_color="transparent")
        bottom_row.pack(fill="x")

        # Progress
        progress_frame = ctk.CTkFrame(bottom_row, fg_color="transparent")
        progress_frame.pack(side="left", fill="x", expand=True, padx=(0, 25))

        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="Ready to download",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_dim'],
            anchor="w"
        )
        self.progress_label.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=8,
            fg_color=COLORS['bg_medium'],
            progress_color=COLORS['purple_neon'],
            corner_radius=4
        )
        self.progress_bar.pack(fill="x", pady=(6, 0))
        self.progress_bar.set(0)

        # Buttons with glow
        btn_frame = ctk.CTkFrame(bottom_row, fg_color="transparent")
        btn_frame.pack(side="right")

        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="▶  Start Download",
            width=170,
            height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS['purple_neon'],
            hover_color=COLORS['purple_super_glow'],
            border_width=2,
            border_color=COLORS['purple_glow'],
            command=self._start_download
        )
        self.start_btn.pack(side="left", padx=(0, 12))

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="◼  Stop",
            width=110,
            height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS['bg_light'],
            hover_color=COLORS['error'],
            text_color=COLORS['text_secondary'],
            state="disabled",
            command=self._stop_download
        )
        self.stop_btn.pack(side="left")

        self._update_stats()

    # ═══════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════

    def _create_folder(self):
        """Create a new folder in both UI and filesystem"""
        name = self.folder_name_entry.get().strip()
        if not name:
            return

        keywords_text = self.keywords_entry.get().strip()
        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()] if keywords_text else []

        success = self.project_manager.create_folder(name, keywords)

        if success:
            # Also create the folder on disk
            safe_name = re.sub(r'[^\w\s-]', '', name)
            folder_path = os.path.join(self.download_folder, safe_name)
            os.makedirs(folder_path, exist_ok=True)

            self.folder_name_entry.delete(0, "end")
            self.keywords_entry.delete(0, "end")
            self._update_folders_list()
            self._select_folder(name)
            self._update_system_folders()  # Refresh system folders
            self._update_stats()
        else:
            CTkMessagebox(title="Error", message=f"Folder '{name}' already exists!", icon="cancel")

    def _delete_folder(self, name):
        """Delete a folder"""
        result = CTkMessagebox(
            title="Delete Folder",
            message=f"Delete folder '{name}' and all its links?",
            icon="warning",
            option_1="Cancel",
            option_2="Delete"
        )

        if result.get() == "Delete":
            self.project_manager.delete_folder(name)
            if self.selected_folder == name:
                self.selected_folder = None
            self._update_folders_list()
            self._update_links_list()
            self._update_stats()

    def _select_folder(self, name):
        """Select a project folder"""
        self.selected_folder = name
        self.selected_system_folder = None  # Deselect system folder
        self._update_folders_list()
        self._update_system_folders()
        self._update_links_list()

        self.folder_title.configure(
            text=f"📂 {name}",
            text_color=COLORS['text_primary']
        )
        self.add_link_btn.configure(state="normal")

    def _select_system_folder(self, name, path):
        """Select a system folder from output directory"""
        self.selected_system_folder = (name, path)
        self.selected_folder = None  # Deselect project folder

        # Create a project folder with same name if it doesn't exist
        if not self.project_manager.get_folder(name):
            self.project_manager.create_folder(name)

        self.selected_folder = name
        self._update_folders_list()
        self._update_system_folders()
        self._update_links_list()

        self.folder_title.configure(
            text=f"📂 {name}",
            text_color=COLORS['text_primary']
        )
        self.add_link_btn.configure(state="normal")

    def _clear_url_entry(self):
        """Clear URL entry and all links from selected folder"""
        # Clear URL entry
        self.url_entry.delete(0, "end")
        self.platform_var.set("auto")

        # Clear all links from selected folder
        if self.selected_folder:
            folder = self.project_manager.get_folder(self.selected_folder)
            if folder:
                folder.links.clear()
                self._update_links_list()
                self._update_stats()

    def _add_link(self):
        """Add a link to selected folder"""
        url = self.url_entry.get().strip()
        if not url:
            return

        # Detect platform
        platform = self.platform_var.get()
        if platform == "auto":
            if 'behance.net' in url:
                platform = 'behance'
            elif 'dribbble.com' in url:
                platform = 'dribbble'
            elif 'pinterest.com' in url or 'pinterest.' in url:
                platform = 'pinterest'
            else:
                CTkMessagebox(title="Invalid URL", message="URL must be from Behance, Dribbble or Pinterest", icon="cancel")
                return

        # Validate
        if platform == 'behance' and 'behance.net/gallery/' not in url:
            CTkMessagebox(title="Invalid URL", message="Invalid Behance gallery URL", icon="cancel")
            return

        if platform == 'dribbble' and 'dribbble.com/shots/' not in url:
            CTkMessagebox(title="Invalid URL", message="Invalid Dribbble shot URL", icon="cancel")
            return

        if platform == 'pinterest' and not ('pinterest.com/pin/' in url or 'pinterest.' in url):
            CTkMessagebox(title="Invalid URL", message="Invalid Pinterest URL", icon="cancel")
            return

        # Auto-foldering
        target_folder = self.selected_folder

        if self.auto_folder_enabled.get():
            if platform == 'behance':
                _, name = self.behance_engine.extract_info(url)
            elif platform == 'dribbble':
                _, name = self.dribbble_engine.extract_info(url)
            else:
                _, name = self.pinterest_engine.extract_info(url)

            if name:
                matched = self.project_manager.find_matching_folder(name)
                if matched:
                    target_folder = matched
                    self._select_folder(matched)

        if not target_folder:
            CTkMessagebox(title="Error", message="Please select or create a folder first!", icon="cancel")
            return

        folder = self.project_manager.get_folder(target_folder)
        folder.add_link(url, platform)

        self.url_entry.delete(0, "end")
        self._update_links_list()
        self._update_folders_list()
        self._update_stats()

        # Load thumbnail async
        self._load_thumbnail_async(len(folder.links) - 1, url, platform)

    def _load_experimental_thumbnails(self, folder_name):
        """Load thumbnails for all links in a folder (used for experimental search results)"""
        def load_all():
            folder = self.project_manager.get_folder(folder_name)
            if not folder:
                return

            for idx, link in enumerate(folder.links):
                if self.stop_requested:
                    break

                try:
                    url = link['url']
                    platform = link['platform']

                    # For direct images (Pinterest search), use the URL directly
                    if link.get('is_direct_image') or link.get('thumbnail_url'):
                        thumb_url = link.get('thumbnail_url', url)
                        # Get smaller version for thumbnail
                        thumb_url = re.sub(r'/originals/', '/236x/', thumb_url)
                        thumbnail = self._fetch_thumbnail(thumb_url)
                        if thumbnail:
                            folder.links[idx]['thumbnail'] = thumbnail
                            self.after(0, self._update_links_list)
                        continue

                    # For regular links, try to get thumbnail from page
                    if platform == 'behance':
                        engine = self.behance_engine
                    elif platform == 'dribbble':
                        engine = self.dribbble_engine
                    else:
                        engine = self.pinterest_engine

                    engine.init_driver()
                    engine.driver.get(url)
                    time.sleep(1.5)

                    soup = BeautifulSoup(engine.driver.page_source, 'html.parser')
                    img_url = None

                    if platform == 'behance':
                        for img in soup.find_all('img'):
                            src = img.get('src') or img.get('data-src')
                            if src and 'mir-s3-cdn-cf.behance.net' in src and '/project_modules/' in src:
                                if not any(p in src.lower() for p in ['/50/', '/100/', '/115/', '/130/']):
                                    img_url = re.sub(r'/(source|fs|1400|1200|808)/', '/404/', src)
                                    break
                    elif platform == 'dribbble':
                        for img in soup.find_all('img'):
                            src = img.get('src') or img.get('data-src')
                            if src and 'dribbble' in src.lower():
                                if not any(p in src.lower() for p in ['/avatars/', '/mini/', '50x50', '80x80']):
                                    img_url = src
                                    break
                    else:  # Pinterest
                        for img in soup.find_all('img'):
                            src = img.get('src') or img.get('data-src')
                            if src and 'pinimg.com' in src:
                                if not any(p in src.lower() for p in ['/75x/', '/140x/', '/avatars/']):
                                    img_url = re.sub(r'/originals/', '/236x/', src)
                                    break

                    if img_url:
                        thumbnail = self._fetch_thumbnail(img_url)
                        if thumbnail:
                            folder.links[idx]['thumbnail'] = thumbnail
                            self.after(0, self._update_links_list)

                except Exception as e:
                    print(f"Thumbnail error for {idx}: {e}")

        thread = threading.Thread(target=load_all, daemon=True)
        thread.start()

    def _fetch_thumbnail(self, url, size=(40, 40)):
        """Fetch and create thumbnail image"""
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            data = BytesIO(response.content)
            img = Image.open(data)
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Make it square with padding
            square = Image.new('RGBA', size, (0, 0, 0, 0))
            offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
            if img.mode == 'RGBA':
                square.paste(img, offset, img)
            else:
                square.paste(img, offset)

            return ctk.CTkImage(light_image=square, dark_image=square, size=size)
        except Exception as e:
            print(f"Thumbnail fetch error: {e}")
            return None

    def _load_thumbnail_async(self, link_index, url, platform):
        """Load thumbnail in background by fetching first image from the link"""
        def load():
            try:
                if platform == 'behance':
                    engine = self.behance_engine
                elif platform == 'dribbble':
                    engine = self.dribbble_engine
                else:
                    engine = self.pinterest_engine

                # Quick page load to get first image
                engine.init_driver()
                engine.driver.get(url)
                time.sleep(2)

                soup = BeautifulSoup(engine.driver.page_source, 'html.parser')
                img_url = None

                if platform == 'behance':
                    for img in soup.find_all('img'):
                        src = img.get('src') or img.get('data-src')
                        if src and 'mir-s3-cdn-cf.behance.net' in src and '/project_modules/' in src:
                            if not any(p in src.lower() for p in ['/50/', '/100/', '/115/', '/130/']):
                                # Get small version for thumbnail
                                img_url = re.sub(r'/(source|fs|1400|1200|808)/', '/404/', src)
                                break
                elif platform == 'dribbble':
                    for img in soup.find_all('img'):
                        src = img.get('src') or img.get('data-src')
                        if src and 'dribbble' in src.lower():
                            if not any(p in src.lower() for p in ['/avatars/', '/mini/', '50x50', '80x80']):
                                img_url = src
                                break
                else:  # Pinterest
                    for img in soup.find_all('img'):
                        src = img.get('src') or img.get('data-src')
                        if src and 'pinimg.com' in src:
                            if not any(p in src.lower() for p in ['/75x/', '/140x/', '/avatars/']):
                                img_url = src
                                break

                if img_url:
                    # Download and create thumbnail
                    thumbnail = engine.get_thumbnail(img_url, size=(40, 40))
                    if thumbnail and self.selected_folder:
                        folder = self.project_manager.get_folder(self.selected_folder)
                        if folder and link_index < len(folder.links):
                            folder.links[link_index]['thumbnail'] = thumbnail
                            self.after(0, self._update_links_list)

            except Exception as e:
                print(f"Thumbnail load error: {e}")

        thread = threading.Thread(target=load, daemon=True)
        thread.start()

    def _delete_link(self, index):
        """Delete a link"""
        if self.selected_folder:
            folder = self.project_manager.get_folder(self.selected_folder)
            folder.remove_link(index)
            self._update_links_list()
            self._update_folders_list()
            self._update_stats()

    def _browse_output(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder)
            self._update_system_folders()

    def _update_system_folders(self):
        """Update system folders from output directory"""
        for widget in self.system_folders_container.winfo_children():
            widget.destroy()

        # Use download_folder if output_entry doesn't exist yet
        if hasattr(self, 'output_entry'):
            output_path = Path(self.output_entry.get().strip())
        else:
            output_path = Path(self.download_folder)

        if not output_path.exists():
            ctk.CTkLabel(
                self.system_folders_container,
                text="Directory not found",
                font=ctk.CTkFont(size=11),
                text_color=COLORS['text_dim']
            ).pack(pady=10)
            return

        folders = []
        try:
            for item in output_path.iterdir():
                if item.is_dir():
                    # Count files in folder
                    file_count = sum(1 for f in item.rglob('*') if f.is_file())
                    folders.append((item.name, str(item), file_count))
        except Exception as e:
            ctk.CTkLabel(
                self.system_folders_container,
                text=f"Error: {e}",
                font=ctk.CTkFont(size=11),
                text_color=COLORS['error']
            ).pack(pady=10)
            return

        if not folders:
            ctk.CTkLabel(
                self.system_folders_container,
                text="No folders in output directory",
                font=ctk.CTkFont(size=11),
                text_color=COLORS['text_dim']
            ).pack(pady=10)
            return

        # Sort by name
        folders.sort(key=lambda x: x[0].lower())

        for name, path, file_count in folders[:20]:  # Limit to 20
            is_selected = self.selected_system_folder and self.selected_system_folder[0] == name
            item = SystemFolderItem(
                self.system_folders_container,
                name=name,
                path=path,
                file_count=file_count,
                selected=is_selected,
                on_click=self._select_system_folder
            )
            item.pack(fill="x", pady=(0, 4))

    def _start_search(self):
        """Start experimental search"""
        query = self.search_entry.get().strip()
        if not query:
            CTkMessagebox(title="Error", message="Please enter a search query!", icon="cancel")
            return

        if not self.search_behance.get() and not self.search_dribbble.get() and not self.search_pinterest.get():
            CTkMessagebox(title="Error", message="Select at least one platform!", icon="cancel")
            return

        self.search_btn.configure(state="disabled")
        self.status_indicator.configure(text="● Searching", text_color=COLORS['neon_cyan'])

        thread = threading.Thread(target=self._search_worker, args=(query,), daemon=True)
        thread.start()

    def _search_worker(self, query):
        """Background search worker"""
        results = []
        limit = self._get_search_count()

        try:
            if self.search_behance.get():
                self.after(0, lambda: self.progress_label.configure(text=f"Searching Behance (top {limit})..."))
                behance_results = self.behance_engine.search(
                    query, limit=limit,
                    callback=lambda m: self.after(0, lambda msg=m: self.progress_label.configure(text=msg))
                )
                for url in behance_results:
                    results.append({'url': url, 'platform': 'behance'})

            if self.search_dribbble.get():
                self.after(0, lambda: self.progress_label.configure(text=f"Searching Dribbble (top {limit})..."))
                dribbble_results = self.dribbble_engine.search(
                    query, limit=limit,
                    callback=lambda m: self.after(0, lambda msg=m: self.progress_label.configure(text=msg))
                )
                for url in dribbble_results:
                    results.append({'url': url, 'platform': 'dribbble'})

            if self.search_pinterest.get():
                self.after(0, lambda: self.progress_label.configure(text=f"Searching Pinterest (top {limit})..."))
                # For Pinterest, search returns direct image URLs
                pinterest_images = self.pinterest_engine.search(
                    query, limit=limit,
                    callback=lambda m: self.after(0, lambda msg=m: self.progress_label.configure(text=msg))
                )
                # Store images directly for Pinterest
                for img_url in pinterest_images:
                    results.append({'url': img_url, 'platform': 'pinterest', 'is_direct_image': True})

            if results:
                # Build folder name with platforms
                platforms_used = []
                if self.search_behance.get() and any(r['platform'] == 'behance' for r in results):
                    platforms_used.append("BE")
                if self.search_dribbble.get() and any(r['platform'] == 'dribbble' for r in results):
                    platforms_used.append("DR")
                if self.search_pinterest.get() and any(r['platform'] == 'pinterest' for r in results):
                    platforms_used.append("PI")

                platform_str = "+".join(platforms_used) if platforms_used else "Search"
                folder_name = f"[{platform_str}] {query[:25]}"

                self.project_manager.create_folder(folder_name)
                folder = self.project_manager.get_folder(folder_name)

                for idx, item in enumerate(results):
                    folder.add_link(item['url'], item['platform'])
                    # Mark direct images
                    if item.get('is_direct_image'):
                        folder.links[-1]['is_direct_image'] = True
                    # Store thumbnail URL for direct images
                    if item.get('is_direct_image'):
                        folder.links[-1]['thumbnail_url'] = item['url']

                self.after(0, lambda: self._select_folder(folder_name))
                self.after(0, self._update_folders_list)
                self.after(0, self._update_stats)

                # Load thumbnails for experimental results
                self.after(0, lambda: self._load_experimental_thumbnails(folder_name))

                self.after(500, self._start_download)

        except Exception as e:
            self.after(0, lambda: self.progress_label.configure(text=f"Search error: {e}"))

        self.after(0, lambda: self.search_btn.configure(state="normal"))

    def _start_download(self):
        """Start downloading"""
        total = self.project_manager.get_total_links()
        if total == 0:
            CTkMessagebox(title="Warning", message="No links to download!", icon="warning")
            return

        self.download_folder = self.output_entry.get().strip()
        os.makedirs(self.download_folder, exist_ok=True)

        self.is_downloading = True
        self.stop_requested = False

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.search_btn.configure(state="disabled")
        self.status_indicator.configure(text="● Downloading", text_color=COLORS['purple_neon'])

        thread = threading.Thread(target=self._download_worker, daemon=True)
        thread.start()

    def _stop_download(self):
        """Stop downloading"""
        self.stop_requested = True
        self.progress_label.configure(text="Stopping...")

    def _download_worker(self):
        """Background download worker"""
        total_downloaded = 0
        total_errors = 0

        all_folders = self.project_manager.get_all_folders()
        total_links = self.project_manager.get_total_links()
        processed = 0

        for folder_name in all_folders:
            if self.stop_requested:
                break

            folder = self.project_manager.get_folder(folder_name)

            safe_name = re.sub(r'[^\w\s-]', '', folder_name)
            folder_path = os.path.join(self.download_folder, safe_name)
            os.makedirs(folder_path, exist_ok=True)

            for link_idx, link in enumerate(folder.links):
                if self.stop_requested:
                    break

                url = link['url']
                platform = link['platform']

                folder.links[link_idx]['status'] = 'downloading'
                self.after(0, self._update_links_list)
                self.after(0, lambda n=folder_name: self.progress_label.configure(text=f"Processing: {n}"))

                try:
                    # Check if this is a direct image URL (from Pinterest search)
                    is_direct_image = link.get('is_direct_image', False)

                    if is_direct_image:
                        # Direct image download (Pinterest search results)
                        self.after(0, lambda: self.progress_label.configure(text=f"Downloading Pinterest image..."))

                        ext = os.path.splitext(urlparse(url).path)[1] or '.jpg'
                        img_hash = re.search(r'/([a-f0-9]+)\.', url)
                        filename = img_hash.group(1)[:12] if img_hash else f"pin_{link_idx}"
                        filepath = os.path.join(folder_path, f"{filename}{ext}")

                        if not os.path.exists(filepath):
                            success, _ = self.pinterest_engine.download_image(url, filepath)
                            if success:
                                total_downloaded += 1

                        folder.links[link_idx]['status'] = 'complete'
                        folder.links[link_idx]['progress'] = 100
                        processed += 1
                        self.after(0, self._update_links_list)
                        continue

                    # Regular link processing
                    if platform == 'behance':
                        engine = self.behance_engine
                    elif platform == 'dribbble':
                        engine = self.dribbble_engine
                    else:
                        engine = self.pinterest_engine
                    item_id, item_name = engine.extract_info(url)

                    if not item_id:
                        folder.links[link_idx]['status'] = 'error'
                        total_errors += 1
                        processed += 1
                        continue

                    images = engine.get_images(url, callback=lambda m: self.after(0, lambda msg=m: self.progress_label.configure(text=msg)))

                    if not images:
                        folder.links[link_idx]['status'] = 'error'
                        total_errors += 1
                        processed += 1
                        continue

                    link_folder = os.path.join(folder_path, f"{item_id}_{re.sub(r'[^a-zA-Z0-9 ]', '', item_name or '')[:30]}")
                    os.makedirs(link_folder, exist_ok=True)

                    for img_idx, img_url in enumerate(images):
                        if self.stop_requested:
                            break

                        ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                        filepath = os.path.join(link_folder, f"image_{img_idx+1:03d}{ext}")

                        if not os.path.exists(filepath):
                            success, _ = engine.download_image(img_url, filepath)
                            if success:
                                total_downloaded += 1

                        link_progress = (img_idx + 1) / len(images)
                        folder.links[link_idx]['progress'] = link_progress * 100

                        overall = (processed + link_progress) / total_links
                        self.after(0, lambda p=overall: self.progress_bar.set(p))

                    folder.links[link_idx]['status'] = 'complete'

                except Exception as e:
                    folder.links[link_idx]['status'] = 'error'
                    total_errors += 1

                processed += 1
                self.after(0, self._update_links_list)
                self.after(0, lambda d=total_downloaded, e=total_errors: self.stats_label.configure(
                    text=f"Downloaded: {d}  •  Errors: {e}"
                ))

        self.behance_engine.close_driver()
        self.dribbble_engine.close_driver()
        self.pinterest_engine.close_driver()

        self.after(0, self._download_complete)
        self.after(0, self._update_system_folders)

    # ═══════════════════════════════════════════════════════════════
    # UI UPDATES
    # ═══════════════════════════════════════════════════════════════

    def _update_folders_list(self):
        """Update folders list"""
        for widget in self.folders_container.winfo_children():
            widget.destroy()

        folders = self.project_manager.get_all_folders()

        if not folders:
            ctk.CTkLabel(
                self.folders_container,
                text="No folders yet\nCreate one above",
                font=ctk.CTkFont(size=12),
                text_color=COLORS['text_dim'],
                justify="center"
            ).pack(expand=True, pady=20)
            return

        for name in folders:
            folder = self.project_manager.get_folder(name)
            item = FolderItem(
                self.folders_container,
                name=name,
                link_count=len(folder.links),
                selected=(name == self.selected_folder),
                is_system=False,
                on_click=self._select_folder,
                on_delete=self._delete_folder
            )
            item.pack(fill="x", pady=(0, 6))

    def _update_links_list(self):
        """Update links list"""
        for widget in self.links_container.winfo_children():
            widget.destroy()

        if not self.selected_folder:
            self._show_empty_state()
            return

        folder = self.project_manager.get_folder(self.selected_folder)

        if not folder or not folder.links:
            ctk.CTkLabel(
                self.links_container,
                text="No links in this folder\nPaste URLs above to add",
                font=ctk.CTkFont(size=13),
                text_color=COLORS['text_dim'],
                justify="center"
            ).pack(expand=True, pady=50)
            return

        for idx, link in enumerate(folder.links):
            thumbnail = link.get('thumbnail')
            item = LinkItem(
                self.links_container,
                url=link['url'],
                platform=link['platform'],
                status=link['status'],
                index=idx,
                thumbnail=thumbnail,
                on_delete=self._delete_link if not self.is_downloading else None
            )
            item.pack(fill="x", pady=(0, 6))

    def _update_stats(self):
        """Update statistics"""
        folders = len(self.project_manager.get_all_folders())
        links = self.project_manager.get_total_links()
        self.stats_label.configure(text=f"📁 {folders} folders  •  🔗 {links} links")

    def _download_complete(self):
        """Called when download completes"""
        self.is_downloading = False
        self.stop_requested = False

        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.search_btn.configure(state="normal")
        self.progress_bar.set(0)

        self.status_indicator.configure(text="● Complete", text_color=COLORS['neon_green'])
        self.progress_label.configure(text="Download complete!")

        self._update_stats()

    def on_closing(self):
        """Handle window close"""
        if self.is_downloading:
            self.stop_requested = True
            time.sleep(0.5)
        self.behance_engine.close_driver()
        self.dribbble_engine.close_driver()
        self.pinterest_engine.close_driver()
        self.destroy()


def main():
    app = DesignDownloaderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
