import sys
import os
import asyncio
import aiohttp
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QMessageBox,
    QLineEdit, QLabel, QCheckBox, QProgressBar, QSpinBox, QHBoxLayout
)
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import threading

class SiteCloner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DevTools Site Cloner")
        self.resize(400, 250)

        layout = QVBoxLayout()

        # URL input
        self.url_label = QLabel("Site URL:")
        self.url_input = QLineEdit()
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)

        # Resource type selection
        self.img_cb = QCheckBox("Images")
        self.css_cb = QCheckBox("CSS")
        self.js_cb = QCheckBox("JS")
        self.font_cb = QCheckBox("Fonts")
        self.img_cb.setChecked(True)
        self.css_cb.setChecked(True)
        self.js_cb.setChecked(True)
        self.font_cb.setChecked(True)
        res_layout = QHBoxLayout()
        res_layout.addWidget(self.img_cb)
        res_layout.addWidget(self.css_cb)
        res_layout.addWidget(self.js_cb)
        res_layout.addWidget(self.font_cb)
        layout.addLayout(res_layout)

        # Depth selection
        self.depth_label = QLabel("Max Depth:")
        self.depth_spin = QSpinBox()
        self.depth_spin.setMinimum(1)
        self.depth_spin.setMaximum(10)
        self.depth_spin.setValue(2)
        depth_layout = QHBoxLayout()
        depth_layout.addWidget(self.depth_label)
        depth_layout.addWidget(self.depth_spin)
        layout.addLayout(depth_layout)

        # Progress bar
        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        # Start/Stop buttons
        self.start_btn = QPushButton("Start Extraction")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_extraction)
        self.stop_btn.clicked.connect(self.stop_extraction)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.should_stop = False

    def start_extraction(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save Site")
        if not folder:
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a site URL.")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setValue(0)
        self.should_stop = False

        # Resource types
        exts = []
        if self.img_cb.isChecked():
            exts += [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]
        if self.css_cb.isChecked():
            exts += [".css"]
        if self.js_cb.isChecked():
            exts += [".js"]
        if self.font_cb.isChecked():
            exts += [".woff", ".woff2", ".ttf"]

        depth = self.depth_spin.value()

        # Run in a thread to avoid blocking UI
        threading.Thread(target=self.run_clone, args=(folder, url, exts, depth)).start()

    def stop_extraction(self):
        self.should_stop = True
        self.stop_btn.setEnabled(False)

    def run_clone(self, folder, url, exts, max_depth):
        try:
            clone_site(
                folder, url, exts, max_depth,
                progress_callback=self.update_progress,
                stop_flag=lambda: self.should_stop
            )
            if not self.should_stop:
                QMessageBox.information(self, "Done", "✅ Site cloned successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress.setValue(0)

    def update_progress(self, value, total):
        self.progress.setMaximum(total)
        self.progress.setValue(value)

def clone_site(save_path, start_url, exts, max_depth, progress_callback=None, stop_flag=None):
    visited = set()
    to_visit = [(start_url, 0)]
    total = 1
    count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        domain = urlparse(start_url).netloc
        base_dir = os.path.join(save_path, domain)
        os.makedirs(base_dir, exist_ok=True)

        while to_visit:
            if stop_flag and stop_flag():
                print("🛑 Extraction stopped by user.")
                break

            current_url, depth = to_visit.pop(0)
            if current_url in visited or depth > max_depth:
                continue
            visited.add(current_url)
            count += 1
            if progress_callback:
                progress_callback(count, total)

            print(f"🔍 Visiting: {current_url}")
            try:
                page.goto(current_url, timeout=30000)
                page.wait_for_load_state("networkidle")
                html = page.content()

                parsed_url = urlparse(current_url)
                rel_path = parsed_url.path.strip("/")
                if not rel_path or rel_path.endswith("/"):
                    rel_path += "index.html"
                elif not rel_path.endswith(".html"):
                    rel_path += ".html"

                file_path = os.path.join(base_dir, rel_path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                soup = BeautifulSoup(html, "html.parser")
                resource_links = extract_resources(soup, current_url, exts)
                asyncio.run(download_resources(resource_links, base_dir, soup, current_url))

                # بازنویسی لینک‌های <a href="...">
                for a in soup.find_all("a"):
                    href = a.get("href")
                    if href:
                        full_url = urljoin(current_url, href)
                        if domain in urlparse(full_url).netloc:
                            a['href'] = local_path_from_url(full_url)
                            if full_url not in visited and all(full_url != u for u, _ in to_visit):
                                to_visit.append((full_url, depth + 1))
                                total += 1

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(soup.prettify())

            except Exception as e:
                print(f"⚠️ Error fetching {current_url}: {e}")

        browser.close()

def extract_resources(soup, base_url, exts):
    tags_attrs = {
        'script': 'src',
        'link': 'href',
        'img': 'src',
        'source': 'src',
        'video': 'src',
        'iframe': 'src'
    }
    resources = set()
    for tag, attr in tags_attrs.items():
        for el in soup.find_all(tag):
            link = el.get(attr)
            if link:
                full_url = urljoin(base_url, link)
                if any(full_url.lower().endswith(ext) for ext in exts):
                    resources.add(full_url)
    return resources

async def download_resources(urls, base_dir, soup, base_url):
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                parsed = urlparse(url)
                rel_path = parsed.path.lstrip("/")
                if not rel_path:
                    continue

                local_path = os.path.join(base_dir, rel_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                async with session.get(url, timeout=20) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        with open(local_path, "wb") as f:
                            f.write(content)

                        # جایگزینی لینک در HTML
                        rel_link = os.path.relpath(local_path, base_dir).replace("\\", "/")
                        for tag in soup.find_all(True):
                            for attr in ['src', 'href']:
                                if tag.has_attr(attr) and urljoin(base_url, tag[attr]) == url:
                                    tag[attr] = rel_link
            except Exception as e:
                print(f"❌ Error downloading {url}: {e}")

def local_path_from_url(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path or path.endswith("/"):
        path += "index.html"
    elif not path.endswith(".html"):
        path += ".html"
    return path

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SiteCloner()
    win.show()
    sys.exit(app.exec_())