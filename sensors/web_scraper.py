import os
import re
import json
import sqlite3
import shutil
import tempfile
import datetime
import logger

try:
    import requests as http_requests
except ImportError:
    http_requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import websocket
except ImportError:
    websocket = None


class WebScraper:
    def __init__(self, config, api_client):
        self.config = config
        self.client = api_client
        self.max_text_length = config.chrome_scrape_max_text_length
        self.chrome_history_path = config.chrome_history_path
        self.cdp_port = config.chrome_cdp_port
        self.scrape_log_path = config.scrape_log_path

        self._init_log()

    def _init_log(self):
        if self.scrape_log_path:
            os.makedirs(os.path.dirname(self.scrape_log_path) if os.path.dirname(self.scrape_log_path) else ".", exist_ok=True)
            if not os.path.exists(self.scrape_log_path):
                with open(self.scrape_log_path, 'w', encoding='utf-8') as f:
                    f.write(f"=== SCRAPE LOG INITIALIZED {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")

    def _log_scrape(self, title, url, raw_text, summary):
        if not self.scrape_log_path:
            return
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.scrape_log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"[{ts}] TITLE: {title}\n")
                f.write(f"URL: {url}\n")
                f.write(f"RAW TEXT LENGTH: {len(raw_text)} chars\n")
                f.write(f"{'='*80}\n")
                f.write(f"--- RAW CONTENT ---\n")
                f.write(raw_text[:self.max_text_length])
                f.write(f"\n\n--- SUMMARY ---\n")
                f.write(summary if summary else "[NO SUMMARY GENERATED]")
                f.write(f"\n{'='*80}\n\n")
        except Exception as e:
            logger.log(f"[SCRAPER] Log write failed: {e}")

    def scrape_and_summarize(self, tab_title):
        if not http_requests:
            return {"error": "requests library not installed"}
        if not BeautifulSoup:
            return {"error": "beautifulsoup4 library not installed"}

        cleaned_title = self._clean_tab_title(tab_title)

        page_text = None
        url = ""

        if self.cdp_port:
            url, page_text = self._try_cdp_extraction(cleaned_title)

        if not page_text:
            url = self._resolve_url_from_title(cleaned_title)
            if not url:
                url = self._resolve_url_from_title(tab_title)
            if not url:
                return {"error": "could_not_resolve_url", "title": tab_title}
            page_text = self._fetch_and_extract(url)

        if not page_text:
            return {"error": "fetch_failed", "url": url, "title": tab_title}

        summary = self._summarize_text(tab_title, url, page_text)

        self._log_scrape(tab_title, url, page_text, summary)

        return {
            "title": tab_title,
            "url": url,
            "text_length": len(page_text),
            "summary": summary
        }

    def _clean_tab_title(self, title):
        cleaned = re.sub(r'^\(\d+\)\s*', '', title)
        cleaned = re.sub(r'^\u200e', '', cleaned)
        cleaned = re.sub(r'^\*\s*', '', cleaned)
        cleaned = re.sub(r'^●\s*', '', cleaned)
        return cleaned.strip()

    def _try_cdp_extraction(self, title):
        if not http_requests:
            return "", None

        try:
            resp = http_requests.get(f"http://127.0.0.1:{self.cdp_port}/json", timeout=3)
            tabs = resp.json()
        except Exception as e:
            logger.log(f"[SCRAPER] CDP connection failed (port {self.cdp_port}): {e}")
            return "", None

        target_tab = None
        title_lower = title.lower()

        for tab in tabs:
            if tab.get("type") != "page":
                continue
            tab_title = tab.get("title", "")
            if title_lower in tab_title.lower() or tab_title.lower() in title_lower:
                target_tab = tab
                break

        if not target_tab:
            for tab in tabs:
                if tab.get("type") != "page":
                    continue
                tab_title = tab.get("title", "")
                if self._fuzzy_title_match(title_lower, tab_title.lower()):
                    target_tab = tab
                    break

        if not target_tab:
            return "", None

        ws_url = target_tab.get("webSocketDebuggerUrl", "")
        page_url = target_tab.get("url", "")

        if not ws_url:
            return page_url, None

        if not websocket:
            logger.log("[SCRAPER] CDP websocket extraction skipped - websocket-client not installed")
            return page_url, None

        try:
            ws = websocket.create_connection(ws_url, timeout=10)

            cmd = json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.body.innerText",
                    "returnByValue": True
                }
            })
            ws.send(cmd)
            result = json.loads(ws.recv())
            ws.close()

            text = result.get("result", {}).get("result", {}).get("value", "")
            if text and len(text) > 100:
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = re.sub(r'[ \t]{2,}', ' ', text)
                if len(text) > self.max_text_length:
                    text = text[:self.max_text_length]
                logger.log(f"[SCRAPER] CDP extracted {len(text)} chars from live tab: {title[:50]}...")
                return page_url, text

        except Exception as e:
            logger.log(f"[SCRAPER] CDP websocket extraction failed: {e}")

        return page_url, None

    def _fuzzy_title_match(self, query, candidate):
        query_words = set(query.split())
        candidate_words = set(candidate.split())
        if not query_words:
            return False
        overlap = len(query_words & candidate_words) / len(query_words)
        return overlap > 0.6

    def _resolve_url_from_title(self, title):
        if not self.chrome_history_path or not os.path.exists(self.chrome_history_path):
            return None

        temp_db = os.path.join(tempfile.gettempdir(), "scail_scraper_chrome.sqlite")
        try:
            shutil.copy2(self.chrome_history_path, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT url FROM urls WHERE title = ? ORDER BY last_visit_time DESC LIMIT 1",
                (title,)
            )
            row = cursor.fetchone()

            if not row:
                cursor.execute(
                    "SELECT url FROM urls WHERE title LIKE ? ORDER BY last_visit_time DESC LIMIT 1",
                    (f"%{title[:40]}%",)
                )
                row = cursor.fetchone()

            if not row:
                words = title.split()
                if len(words) >= 3:
                    core = " ".join(words[:3])
                    cursor.execute(
                        "SELECT url FROM urls WHERE title LIKE ? ORDER BY last_visit_time DESC LIMIT 1",
                        (f"%{core}%",)
                    )
                    row = cursor.fetchone()

            conn.close()
            if os.path.exists(temp_db):
                os.remove(temp_db)

            return row[0] if row else None

        except Exception as e:
            logger.log(f"[SCRAPER] URL resolve failed: {e}")
            if os.path.exists(temp_db):
                os.remove(temp_db)
            return None

    def _fetch_and_extract(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = http_requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()

            article = soup.find("article")
            if article:
                text = article.get_text(separator="\n", strip=True)
            else:
                main = soup.find("main")
                if main:
                    text = main.get_text(separator="\n", strip=True)
                else:
                    body = soup.find("body")
                    text = body.get_text(separator="\n", strip=True) if body else ""

            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]{2,}', ' ', text)

            if len(text) > self.max_text_length:
                text = text[:self.max_text_length]

            if len(text) < 100:
                return None

            return text

        except Exception as e:
            logger.log(f"[SCRAPER] Fetch failed for {url[:80]}: {e}")
            return None

    def _summarize_text(self, title, url, text):
        # self.client is the shared llm.LLM; the "phone" role is the closest
        # fit (short plain description of what he is looking at).
        if not self.client:
            return None
        user_content = ("Describe in two plain sentences what this web page is about, for someone glancing at it over his shoulder." + "\n"
                        + f"PAGE TITLE: {title}\nURL: {url}\n\nPAGE CONTENT:\n{text}")
        try:
            content = self.client.call("phone", [{"role": "user", "content": user_content}], max_tokens=300)
            logger.log(f"[SCRAPER] Summarized: {title[:50]}... ({len(content)} chars)")
            return content.strip()

        except Exception as e:
            logger.log(f"[SCRAPER] Summarization API failed: {e}")
            return None