import io
import time
import urllib.parse
import requests
import urllib3.util.connection as urllib3_connection
from src.config import config

# Store the original socket connection function
_orig_create_connection = urllib3_connection.create_connection
_resolved_ips = {}


def doh_resolve(hostname: str) -> str:
    """
    Resolves a hostname to an IP address using DNS-over-HTTPS (DoH) via Cloudflare
    or Google. Bypasses ISP DNS blocking/censorship.
    """
    global _resolved_ips
    if hostname in _resolved_ips:
        return _resolved_ips[hostname]

    providers = [
        ("https://cloudflare-dns.com/dns-query", "cloudflare-dns.com"),
        ("https://dns.google/resolve", "dns.google"),
    ]

    headers = {"Accept": "application/dns-json"}

    for url, provider_name in providers:
        print(f"[DoH] Attempting to resolve '{hostname}' via {provider_name}...")
        try:
            # We must use verify=True. The DoH providers have standard SSL certs
            # that resolve fine.
            response = requests.get(
                url,
                params={"name": hostname, "type": "A"},
                headers=headers,
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()

            if "Answer" in data and len(data["Answer"]) > 0:
                # Find the first 'A' record (type 1)
                for record in data["Answer"]:
                    if record.get("type") == 1:
                        ip = record.get("data")
                        if ip:
                            print(f"[DoH] Successfully resolved '{hostname}' to IP: {ip}")
                            _resolved_ips[hostname] = ip
                            return ip
        except Exception as e:
            print(f"[DoH] Provider {provider_name} failed: {e}")

    return None


def patched_create_connection(address, *args, **kwargs):
    """
    A custom socket connector that intercepts connection requests to specific
    blocked hostnames and redirects them to IPs resolved via DoH.
    """
    host, port = address
    if host == "api-inference.huggingface.co":
        ip = doh_resolve(host)
        if ip:
            print(f"[Socket] Intercepting connection to {host} -> Routing to {ip}:{port}")
            return _orig_create_connection((ip, port), *args, **kwargs)
    return _orig_create_connection(address, *args, **kwargs)


# Apply the monkey patch to urllib3
urllib3_connection.create_connection = patched_create_connection


class ImageGenerator:
    def __init__(self):
        self.pollinations_url = "https://image.pollinations.ai/prompt"
        self.hf_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
        self.timeout = 120

    def generate_image(self, prompt: str) -> bytes:
        """
        Generates an image for the given prompt.
        Primary:  Pollinations.ai (Flux -> Turbo -> Default fallback chain)
        Fallback: Hugging Face Inference API (FLUX.1-schnell, free)
        """
        # --- Primary: Pollinations ---
        try:
            return self._generate_pollinations(prompt)
        except Exception as e:
            print(f"\n[ImageGenerator] All Pollinations models failed: {e}")
            print("[ImageGenerator] Falling back to Hugging Face FLUX.1-schnell...\n")

        # --- Fallback: Hugging Face ---
        return self._generate_huggingface(prompt)

    # ------------------------------------------------------------------ #
    #  Pollinations Multi-Model Fallback                                  #
    # ------------------------------------------------------------------ #
    def _generate_pollinations(self, prompt: str) -> bytes:
        # We try 'flux' (highest quality), then 'turbo' (high speed/low queue),
        # then '' (which omits the model parameter to let Pollinations default)
        models = ["flux", "turbo", ""]
        
        for model in models:
            model_name = model if model else "default"
            encoded_prompt = urllib.parse.quote(prompt)
            url = f"{self.pollinations_url}/{encoded_prompt}?nologo=true&width=1024&height=1024"
            
            if model:
                url += f"&model={model}"
            if config.pollinations_api_key:
                url += f"&key={config.pollinations_api_key}"

            headers = {"User-Agent": "ThreadsBot/1.0"}
            if config.pollinations_api_key:
                headers["Authorization"] = f"Bearer {config.pollinations_api_key}"

            print(f"\n[Pollinations] Trying model '{model_name}'...")
            print(f"URL: {url}")

            max_attempts = 2
            wait_time = 5

            for attempt in range(1, max_attempts + 1):
                try:
                    response = requests.get(url, headers=headers, timeout=self.timeout)

                    if response.status_code == 402:
                        print(f"Attempt {attempt}/{max_attempts}: Model '{model_name}' queue full (402).")
                        if attempt < max_attempts:
                            print(f"Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            wait_time *= 2
                            continue
                        else:
                            print(f"Model '{model_name}' queue limits reached. Trying next fallback model...")
                            break

                    response.raise_for_status()

                    content_type = response.headers.get("Content-Type", "")
                    if "image" not in content_type:
                        print(f"Warning: Unexpected content-type '{content_type}' from Pollinations.")

                    print(f"Successfully downloaded image from Pollinations using model '{model_name}'.")
                    return response.content

                except Exception as e:
                    print(f"Attempt {attempt}/{max_attempts} for model '{model_name}' failed: {e}")
                    if attempt < max_attempts:
                        print(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        wait_time *= 2
                    else:
                        print(f"Model '{model_name}' failed. Trying next fallback model...")
                        break

        raise RuntimeError("All models in the Pollinations chain failed.")

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
