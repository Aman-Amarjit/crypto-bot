import io
import time
import urllib.parse
import requests
from src.config import config


class ImageGenerator:
    def __init__(self):
        self.pollinations_url = "https://image.pollinations.ai/prompt"
        self.hf_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
        self.timeout = 120

    def generate_image(self, prompt: str) -> bytes:
        """
        Generates an image for the given prompt.
        Primary:  Pollinations.ai (Flux, authenticated if API key present)
        Fallback: Hugging Face Inference API (FLUX.1-schnell, free)
        """
        # --- Primary: Pollinations ---
        try:
            return self._generate_pollinations(prompt)
        except Exception as e:
            print(f"\n[ImageGenerator] Pollinations failed: {e}")
            print("[ImageGenerator] Falling back to Hugging Face FLUX.1-schnell...\n")

        # --- Fallback: Hugging Face ---
        return self._generate_huggingface(prompt)

    # ------------------------------------------------------------------ #
    #  Pollinations                                                        #
    # ------------------------------------------------------------------ #
    def _generate_pollinations(self, prompt: str) -> bytes:
        encoded_prompt = urllib.parse.quote(prompt)
        url = (
            f"{self.pollinations_url}/{encoded_prompt}"
            "?model=flux&nologo=true&width=1024&height=1024"
        )
        if config.pollinations_api_key:
            url += f"&key={config.pollinations_api_key}"

        headers = {"User-Agent": "ThreadsBot/1.0"}
        if config.pollinations_api_key:
            headers["Authorization"] = f"Bearer {config.pollinations_api_key}"
            print("Using Pollinations API key for priority access.")

        print(f"Constructed Pollinations URL: {url}")
        print("Starting image download from Pollinations.ai...")

        max_attempts = 5
        wait_time = 10

        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout)

                if response.status_code == 402:
                    if attempt < max_attempts:
                        print(
                            f"Attempt {attempt}/{max_attempts}: Pollinations queue full (402). "
                            f"Waiting {wait_time}s before retry..."
                        )
                        time.sleep(wait_time)
                        wait_time *= 2
                        continue
                    else:
                        raise RuntimeError("Pollinations queue full after all retries (402).")

                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "")
                if "image" not in content_type:
                    print(f"Warning: Unexpected content-type '{content_type}' from Pollinations.")

                print("Successfully downloaded image from Pollinations.")
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
                        f"Pollinations failed after {max_attempts} attempts."
                    ) from e

    # ------------------------------------------------------------------ #
    #  Hugging Face fallback                                               #
    # ------------------------------------------------------------------ #
    def _generate_huggingface(self, prompt: str) -> bytes:
        if not config.hf_api_token:
            raise RuntimeError(
                "HF_API_TOKEN is not set. Cannot use Hugging Face fallback."
            )

        headers = {
            "Authorization": f"Bearer {config.hf_api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "width": 1024,
                "height": 1024,
                "num_inference_steps": 4,   # FLUX.1-schnell works great at 4 steps
            },
        }

        max_attempts = 4
        wait_time = 20  # HF cold-starts can take ~20s

        for attempt in range(1, max_attempts + 1):
            print(f"[HuggingFace] Attempt {attempt}/{max_attempts}...")
            try:
                response = requests.post(
                    self.hf_url, headers=headers, json=payload, timeout=self.timeout
                )

                # 503 = model loading (cold start) — wait and retry
                if response.status_code == 503:
                    estimated = response.json().get("estimated_time", wait_time)
                    wait_sec = min(float(estimated), 60)
                    print(f"[HuggingFace] Model loading (503). Waiting {wait_sec:.0f}s...")
                    time.sleep(wait_sec)
                    continue

                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "")
                if "image" not in content_type:
                    raise RuntimeError(
                        f"HuggingFace returned unexpected content-type: {content_type}. "
                        f"Body: {response.text[:200]}"
                    )

                print("Successfully generated image via Hugging Face FLUX.1-schnell.")
                return response.content

            except RuntimeError:
                raise
            except Exception as e:
                print(f"[HuggingFace] Attempt {attempt}/{max_attempts} failed: {e}")
                if attempt < max_attempts:
                    print(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    wait_time *= 2
                else:
                    raise RuntimeError(
                        f"Hugging Face fallback also failed after {max_attempts} attempts."
                    ) from e
