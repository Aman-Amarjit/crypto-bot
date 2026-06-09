import json
import os
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from bs4 import BeautifulSoup


class NewsFetcher:
    @staticmethod
    def fetch_latest_headlines(topic: str, max_results: int = 5) -> list:
        """
        Fetches the latest news headlines from Google News RSS feed for the given topic.
        Only retrieves news from the last 24 hours (when:1d) to ensure it is fresh.
        Returns a list of dicts: [{"title": str, "link": str}, ...]
        """
        query = (
            f"{topic} (site:bleepingcomputer.com OR site:thehackernews.com OR "
            f"site:arstechnica.com OR site:theverge.com OR site:wired.com OR "
            f"site:darkreading.com) when:1d"
        )
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        print(f"Fetching latest news headlines from Google News for query: '{query}'...")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            items = root.findall(".//item")

            headlines = []
            for item in items[:max_results]:
                title_el = item.find("title")
                link_el = item.find("link")
                title = title_el.text if title_el is not None else ""
                link = link_el.text if link_el is not None else ""
                # Remove source publication name usually appended after ' - '
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                
                # Decode Google News redirect URL to its direct canonical publisher URL
                decoded_link = link
                if link.startswith("https://news.google.com/"):
                    print(f"Decoding Google News URL: {link}")
                    try:
                        from googlenewsdecoder import gnewsdecoder
                        decoded_res = gnewsdecoder(link)
                        if decoded_res.get("status"):
                            decoded_link = decoded_res["decoded_url"]
                            print(f"Decoded successfully to: {decoded_link}")
                        else:
                            print(f"Failed to decode URL: {decoded_res.get('message')}")
                    except Exception as e:
                        print(f"Error during Google News URL decoding: {e}")

                headlines.append({"title": title.strip(), "link": decoded_link.strip()})

            print(f"Successfully retrieved {len(headlines)} headlines.")
            return headlines

        except Exception as e:
            print(f"Warning: Failed to fetch latest news headlines. Details: {e}")
            return []

    @staticmethod
    def filter_seen_headlines(headlines: list, history_file: str = "data/history.json") -> list:
        """
        Filters out headlines whose source URL or title has already appeared in a
        previously published post (cross-referenced against history.json).
        Returns a filtered list of headline dicts.
        """
        if not os.path.exists(history_file):
            return headlines

        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception:
            return headlines

        # Build sets of seen source URLs and normalised title substrings
        seen_urls = set()
        seen_titles = set()
        for entry in history:
            src = entry.get("source_url", "")
            if src:
                seen_urls.add(src.strip().lower())
            src_title = entry.get("source_title", "")
            if src_title:
                seen_titles.add(src_title.strip().lower())

        filtered = []
        for h in headlines:
            link_norm = h.get("link", "").strip().lower()
            title_norm = h.get("title", "").strip().lower()
            if link_norm in seen_urls:
                print(f"  [Dedup] Skipping already-published headline URL: {h['link']}")
                continue
            if title_norm in seen_titles:
                print(f"  [Dedup] Skipping already-published headline title: {h['title']}")
                continue
            filtered.append(h)

        print(f"  [Dedup] {len(headlines) - len(filtered)} headline(s) filtered out as already published.")
        return filtered

    @staticmethod
    def fetch_article_content(url: str) -> str:
        """
        Fetches the HTML from the given publisher URL and extracts the main text content.
        Only keeps paragraphs that are likely to contain the actual article content.
        Returns the first 4000 characters of clean text.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        print(f"Fetching article content from URL: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Decompose script, style, nav, header, footer, aside, ads elements
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()
                
            # Extract paragraphs
            paragraphs = []
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                # Exclude empty paragraphs, ads, sharing links, or newsletter subscription prompts
                if len(text) > 40 and not any(phrase in text.lower() for phrase in [
                    "sign up", "newsletter", "subscribe", "cookies", "privacy policy", 
                    "all rights reserved", "advertisement", "share on", "follow us"
                ]):
                    paragraphs.append(text)
                    
            content = "\n\n".join(paragraphs)
            if not content.strip():
                # Fallback to body text if paragraphs were filtered out
                body = soup.find('body')
                content = body.get_text() if body else soup.get_text()
                
            # Clean up excessive whitespace/newlines
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            clean_text = " ".join(lines)
            
            # Limit to 4000 characters to keep context size reasonable and fast
            return clean_text[:4000]
            
        except Exception as e:
            print(f"Warning: Failed to fetch article content for {url}. Details: {e}")
            return ""
