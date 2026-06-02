#!/usr/bin/env python3
"""
Design Downloader Server
Backend API for Chrome Extension - Behance, Dribbble & Pinterest Downloader
"""

import os
import re
import json
import time
import threading
import hashlib
from pathlib import Path
from urllib.parse import urlparse, quote
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify
from flask_cors import CORS

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image

app = Flask(__name__)
CORS(app)

# Global state
download_queue = []
download_status = {}
current_downloads = {}
driver_lock = threading.Lock()

# Default download folder
DEFAULT_DOWNLOAD_FOLDER = str(Path.home() / "Downloads" / "DesignDownloader")


# ═══════════════════════════════════════════════════════════════
# DOWNLOADER ENGINES
# ═══════════════════════════════════════════════════════════════

class BaseDownloader:
    def __init__(self):
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        })

    def init_driver(self):
        with driver_lock:
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
        with driver_lock:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def download_image(self, url, save_path, min_size=5000):
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


class BehanceEngine(BaseDownloader):
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

    def get_images(self, url):
        images = []
        try:
            self.init_driver()
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

            candidates = {}
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and 'mir-s3-cdn-cf.behance.net' in src and '/project_modules/' in src:
                    if any(p in src.lower() for p in ['/50/', '/100/', '/115/', '/130/', '/202/', '/230/']):
                        continue

                    img_hash = self._get_image_hash(src)
                    if img_hash not in candidates:
                        candidates[img_hash] = src

            for url in candidates.values():
                images.append(self._upgrade_url(url))

        except Exception as e:
            print(f"Behance error: {e}")

        return images

    def search(self, query, limit=20):
        results = []
        try:
            self.init_driver()
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
        except Exception as e:
            print(f"Behance search error: {e}")

        return results[:limit]


class DribbbleEngine(BaseDownloader):
    def extract_info(self, url):
        match = re.search(r'/shots/(\d+)(?:-([^/?]+))?', url)
        if match:
            shot_id = match.group(1)
            name = match.group(2).replace('-', ' ') if match.group(2) else f"Shot {shot_id}"
            return shot_id, name
        return None, None

    def _upgrade_url(self, url):
        url = re.sub(r'_teaser\.', '_4x.', url)
        url = re.sub(r'_small\.', '_4x.', url)
        url = re.sub(r'_1x\.', '_4x.', url)
        url = re.sub(r'\?.*$', '', url)
        return url

    def _get_image_hash(self, url):
        match = re.search(r'/([a-f0-9-]+)(?:_\d+x)?\.(?:jpg|jpeg|png|gif|webp)', url, re.I)
        if match:
            return match.group(1)
        return os.path.basename(urlparse(url).path)

    def get_images(self, url):
        images = []
        try:
            self.init_driver()
            shot_id, _ = self.extract_info(url)

            self.driver.get(url)
            time.sleep(3)

            for _ in range(2):
                self.driver.execute_script("window.scrollTo(0, 800);")
                time.sleep(0.3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            found = set()

            main_containers = soup.find_all(['div', 'figure', 'section'], class_=re.compile(
                r'media-shot|shot-media|mediabox|shot__media|media-content|shot-content|attachment|carousel',
                re.I
            ))

            for container in main_containers:
                container_class = ' '.join(container.get('class', []))
                if any(skip in container_class.lower() for skip in ['related', 'suggest', 'recommend']):
                    continue

                for img in container.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if not src:
                        continue

                    if 'dribbble' in src.lower() or 'cdn.dribbble.com' in src:
                        if any(p in src.lower() for p in ['/avatars/', '/mini/', '/small/', '/teaser/']):
                            continue

                        high_res = self._upgrade_url(src)
                        img_hash = self._get_image_hash(high_res)

                        if img_hash not in found:
                            found.add(img_hash)
                            images.append(high_res)

            if not images and shot_id:
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if not src:
                        continue

                    if shot_id in src and ('dribbble' in src.lower() or 'cdn.dribbble.com' in src):
                        if any(p in src.lower() for p in ['/avatars/', '/mini/', '/small/', '/teaser/']):
                            continue

                        high_res = self._upgrade_url(src)
                        img_hash = self._get_image_hash(high_res)

                        if img_hash not in found:
                            found.add(img_hash)
                            images.append(high_res)

        except Exception as e:
            print(f"Dribbble error: {e}")

        return images[:10]

    def search(self, query, limit=20):
        results = []
        try:
            self.init_driver()
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
        except Exception as e:
            print(f"Dribbble search error: {e}")

        return results[:limit]


class PinterestEngine(BaseDownloader):
    def extract_info(self, url):
        match = re.search(r'/pin/(\d+)', url)
        if match:
            return match.group(1), f"Pin {match.group(1)}"
        match = re.search(r'pinterest\.com/([^/]+)/([^/]+)', url)
        if match:
            return match.group(2), match.group(2).replace('-', ' ')
        return None, None

    def _upgrade_url(self, url):
        url = re.sub(r'/\d+x/', '/originals/', url)
        url = re.sub(r'/\d+x\d+/', '/originals/', url)
        url = re.sub(r'/236x/', '/originals/', url)
        url = re.sub(r'/474x/', '/originals/', url)
        url = re.sub(r'/736x/', '/originals/', url)
        return url

    def _get_image_hash(self, url):
        match = re.search(r'/([a-f0-9]+)(?:_[a-f0-9]+)?\.(?:jpg|jpeg|png|gif|webp)', url, re.I)
        if match:
            return match.group(1)
        return os.path.basename(urlparse(url).path)

    def get_images(self, url):
        images = []
        try:
            self.init_driver()
            self.driver.get(url)
            time.sleep(3)

            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            found = set()

            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if not src or 'pinimg.com' not in src:
                    continue

                if any(p in src.lower() for p in ['/75x/', '/140x/', '/avatars/', 'profile', 'user']):
                    continue

                high_res = self._upgrade_url(src)
                img_hash = self._get_image_hash(high_res)

                if img_hash not in found:
                    found.add(img_hash)
                    images.append(high_res)

        except Exception as e:
            print(f"Pinterest error: {e}")

        return images

    def search(self, query, limit=20):
        images = []
        try:
            self.init_driver()
            search_url = f"https://www.pinterest.com/search/pins/?q={quote(query)}"
            self.driver.get(search_url)
            time.sleep(4)

            scroll_count = min(limit // 10 + 2, 10)
            for _ in range(scroll_count):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            found = set()

            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if not src or 'pinimg.com' not in src:
                    continue

                if any(p in src.lower() for p in ['/75x/', '/140x/', '/avatars/', 'profile']):
                    continue

                high_res = self._upgrade_url(src)
                img_hash = self._get_image_hash(high_res)

                if img_hash not in found:
                    found.add(img_hash)
                    images.append(high_res)
                    if len(images) >= limit:
                        break
        except Exception as e:
            print(f"Pinterest search error: {e}")

        return images[:limit]


# Initialize engines
behance = BehanceEngine()
dribbble = DribbbleEngine()
pinterest = PinterestEngine()


def detect_platform(url):
    """Detect platform from URL"""
    url_lower = url.lower()
    if 'behance.net' in url_lower:
        return 'behance'
    elif 'dribbble.com' in url_lower:
        return 'dribbble'
    elif 'pinterest' in url_lower:
        return 'pinterest'
    return None


def get_engine(platform):
    """Get appropriate engine for platform"""
    engines = {
        'behance': behance,
        'dribbble': dribbble,
        'pinterest': pinterest
    }
    return engines.get(platform)


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get server status"""
    return jsonify({
        'status': 'running',
        'queue_length': len(download_queue),
        'active_downloads': len(current_downloads)
    })


@app.route('/api/detect', methods=['POST'])
def detect_url():
    """Detect platform and extract info from URL"""
    data = request.json
    url = data.get('url', '')

    platform = detect_platform(url)
    if not platform:
        return jsonify({'error': 'Unknown platform'}), 400

    engine = get_engine(platform)
    item_id, name = engine.extract_info(url)

    return jsonify({
        'platform': platform,
        'id': item_id,
        'name': name
    })


@app.route('/api/download', methods=['POST'])
def add_download():
    """Add URL to download queue"""
    data = request.json
    url = data.get('url', '')
    folder_name = data.get('folder_name', '')
    download_folder = data.get('download_folder', DEFAULT_DOWNLOAD_FOLDER)

    platform = detect_platform(url)
    if not platform:
        return jsonify({'error': 'Unknown platform'}), 400

    engine = get_engine(platform)
    item_id, name = engine.extract_info(url)

    if not item_id:
        return jsonify({'error': 'Invalid URL'}), 400

    download_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:8]

    download_entry = {
        'id': download_id,
        'url': url,
        'platform': platform,
        'item_id': item_id,
        'name': folder_name or name,
        'download_folder': download_folder,
        'status': 'queued',
        'progress': 0,
        'images_found': 0,
        'images_downloaded': 0,
        'created_at': datetime.now().isoformat()
    }

    download_queue.append(download_entry)
    download_status[download_id] = download_entry

    # Start download in background
    thread = threading.Thread(target=process_download, args=(download_id,))
    thread.daemon = True
    thread.start()

    return jsonify({
        'id': download_id,
        'status': 'queued',
        'message': f'Added to queue: {name}'
    })


@app.route('/api/download/<download_id>', methods=['GET'])
def get_download_status(download_id):
    """Get status of a download"""
    if download_id in download_status:
        return jsonify(download_status[download_id])
    return jsonify({'error': 'Download not found'}), 404


@app.route('/api/downloads', methods=['GET'])
def get_all_downloads():
    """Get all downloads"""
    return jsonify(list(download_status.values()))


@app.route('/api/search', methods=['POST'])
def search_platform():
    """Search on a platform"""
    data = request.json
    platform = data.get('platform', '')
    query = data.get('query', '')
    limit = data.get('limit', 20)

    if not platform or not query:
        return jsonify({'error': 'Platform and query required'}), 400

    engine = get_engine(platform)
    if not engine:
        return jsonify({'error': 'Unknown platform'}), 400

    try:
        results = engine.search(query, limit)
        return jsonify({
            'platform': platform,
            'query': query,
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear', methods=['POST'])
def clear_completed():
    """Clear completed downloads"""
    to_remove = []
    for did, entry in download_status.items():
        if entry['status'] in ['completed', 'error']:
            to_remove.append(did)

    for did in to_remove:
        del download_status[did]

    return jsonify({'cleared': len(to_remove)})


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    return jsonify({
        'download_folder': DEFAULT_DOWNLOAD_FOLDER
    })


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update settings"""
    global DEFAULT_DOWNLOAD_FOLDER
    data = request.json

    if 'download_folder' in data:
        DEFAULT_DOWNLOAD_FOLDER = data['download_folder']
        os.makedirs(DEFAULT_DOWNLOAD_FOLDER, exist_ok=True)

    return jsonify({'status': 'updated'})


def process_download(download_id):
    """Process a download in background"""
    global current_downloads

    entry = download_status.get(download_id)
    if not entry:
        return

    current_downloads[download_id] = True

    try:
        entry['status'] = 'scanning'

        platform = entry['platform']
        url = entry['url']
        engine = get_engine(platform)

        # Get images
        images = engine.get_images(url)
        entry['images_found'] = len(images)

        if not images:
            entry['status'] = 'error'
            entry['error'] = 'No images found'
            return

        # Create download folder
        download_folder = entry['download_folder']
        safe_name = re.sub(r'[^\w\s-]', '', entry['name'])[:50]
        item_folder = os.path.join(download_folder, f"{entry['item_id']}_{safe_name}")
        os.makedirs(item_folder, exist_ok=True)

        entry['status'] = 'downloading'

        # Download images
        downloaded = 0
        for i, img_url in enumerate(images):
            ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
            filename = f"image_{i+1:03d}{ext}"
            filepath = os.path.join(item_folder, filename)

            if os.path.exists(filepath):
                downloaded += 1
                continue

            success, msg = engine.download_image(img_url, filepath)
            if success:
                downloaded += 1

            entry['images_downloaded'] = downloaded
            entry['progress'] = int((i + 1) / len(images) * 100)

        entry['status'] = 'completed'
        entry['progress'] = 100

    except Exception as e:
        entry['status'] = 'error'
        entry['error'] = str(e)
    finally:
        if download_id in current_downloads:
            del current_downloads[download_id]


if __name__ == '__main__':
    os.makedirs(DEFAULT_DOWNLOAD_FOLDER, exist_ok=True)
    print(f"\n{'='*60}")
    print("  Design Downloader Server")
    print(f"  Download folder: {DEFAULT_DOWNLOAD_FOLDER}")
    print(f"{'='*60}")
    print("\n  Server running at http://localhost:5200")
    print("  Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=5200, debug=False, threaded=True)
