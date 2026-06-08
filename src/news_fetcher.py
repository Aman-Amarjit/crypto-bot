import requests
import xml.etree.ElementTree as ET
import urllib.parse

class NewsFetcher:
    @staticmethod
    def fetch_latest_headlines(topic: str, max_results: int = 5) -> list:
        """
        Fetches the latest news headlines from Google News RSS feed for the given topic.
        Only retrieves news from the last 24 hours (when:1d) to ensure it is fresh.
        """
        query = f"{topic} (site:bleepingcomputer.com OR site:thehackernews.com OR site:arstechnica.com OR site:theverge.com OR site:wired.com OR site:darkreading.com) when:1d"
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        print(f"Fetching latest news headlines from Google News for query: '{query}'...")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            items = root.findall(".//item")
            
            headlines = []
            for item in items[:max_results]:
                title = item.find("title").text
                # Remove source publication name usually appended after ' - '
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                headlines.append(title)
                
            print(f"Successfully retrieved {len(headlines)} headlines.")
            return headlines
            
        except Exception as e:
            print(f"Warning: Failed to fetch latest news headlines. Details: {e}")
            return []
