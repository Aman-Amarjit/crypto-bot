import time
import urllib.parse
import requests
from src.config import config

class ImageGenerator:
    def __init__(self):
        self.base_url = "https://gen.pollinations.ai/image"
        self.timeout = 30
        
    def generate_image(self, prompt: str) -> bytes:
        """
        Constructs the Pollinations.ai URL and downloads the image bytes.
        Includes a 30-second timeout and 1 retry on failure.
        """
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"{self.base_url}/{encoded_prompt}"
        
        print(f"Constructed Pollinations URL: {url}")
        print("Starting image download from Pollinations.ai...")
        
        headers = {}
        if config.pollinations_api_key:
            headers["Authorization"] = f"Bearer {config.pollinations_api_key}"
        
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                # Verify that the response content type looks like an image
                content_type = response.headers.get("Content-Type", "")
                if "image" not in content_type:
                    print(f"Warning: Unexpected content-type '{content_type}' returned by Pollinations.ai")
                
                print("Successfully downloaded image bytes.")
                return response.content
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code in (401, 402):
                    if not config.pollinations_api_key:
                        raise RuntimeError(
                            f"Pollinations.ai returned {e.response.status_code} ({e.response.reason}). "
                            "An API key is required. Please obtain a free API key from "
                            "https://enter.pollinations.ai and set it as POLLINATIONS_API_KEY in your .env file."
                        ) from e
                    else:
                        raise RuntimeError(
                            f"Pollinations.ai returned {e.response.status_code} ({e.response.reason}). "
                            "Please check that your POLLINATIONS_API_KEY in .env is correct "
                            "and has sufficient pollen credits."
                        ) from e
                
                print(f"Attempt {attempt}/{max_attempts} failed to download image. Error: {e}")
                if attempt < max_attempts:
                    print("Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    raise RuntimeError(f"Failed to generate and download image from Pollinations after {max_attempts} attempts.") from e
            except Exception as e:
                print(f"Attempt {attempt}/{max_attempts} failed to download image. Error: {e}")
                if attempt < max_attempts:
                    print("Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    raise RuntimeError(f"Failed to generate and download image from Pollinations after {max_attempts} attempts.") from e
