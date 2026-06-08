import time
import urllib.parse
import requests
from src.config import config

class ImageGenerator:
    def __init__(self):
        # Free public endpoint — no API key, no credits required
        # 402 from this endpoint means IP queue is full (transient), not a payment issue
        self.base_url = "https://image.pollinations.ai/prompt"
        self.timeout = 90

    def generate_image(self, prompt: str) -> bytes:
        """
        Constructs the Pollinations.ai free-tier URL and downloads the image bytes.
        The free tier allows 1 concurrent request per IP — retries handle queue-full (402).
        Up to 5 attempts with exponential backoff: 10s, 20s, 40s, 80s.
        """
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"{self.base_url}/{encoded_prompt}?model=flux&nologo=true&width=1024&height=1024"

        print(f"Constructed Pollinations URL: {url}")
        print("Starting image download from Pollinations.ai (free tier)...")

        headers = {"User-Agent": "ThreadsBot/1.0"}
        max_attempts = 5
        wait_time = 10  # seconds, doubles each attempt

        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout)

                # 402 means the free IP queue is full — back off and retry
                if response.status_code == 402:
                    if attempt < max_attempts:
                        print(f"Attempt {attempt}/{max_attempts}: Pollinations queue full (402). "
                              f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        wait_time *= 2
                        continue
                    else:
                        raise RuntimeError(
                            "Pollinations.ai free queue is full after all retries. "
                            "The GitHub Actions runner (different IP) will not have this problem."
                        )

                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "")
                if "image" not in content_type:
                    print(f"Warning: Unexpected content-type '{content_type}' returned by Pollinations.ai")

                print("Successfully downloaded image bytes.")
                return response.content

            except RuntimeError:
                raise
            except Exception as e:
                print(f"Attempt {attempt}/{max_attempts} failed: {e}")
                if attempt < max_attempts:
                    print(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    wait_time *= 2
                else:
                    raise RuntimeError(
                        f"Failed to download image from Pollinations after {max_attempts} attempts."
                    ) from e
