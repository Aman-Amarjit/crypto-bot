import json
import requests
from datetime import datetime
from src.config import config


THOUGHT_STYLES = {
    0: {  # Monday
        "name": "Threat Intelligence",
        "instruction": (
            "Share a precise fact about threat intelligence, active ransomware campaigns, or malware family behavior (e.g. LockBit, BlackCat). "
            "Strictly follow the 3-part layout: 1-line news/fact hook, 2-3 lines of actual technical explanation, and 1-line concrete example/number/stat."
        ),
    },
    1: {  # Tuesday
        "name": "Vulnerability Analysis",
        "instruction": (
            "Explain a critical security vulnerability type or specific zero-day/CVE (e.g. memory safety in C/C++, buffer overflows). "
            "Strictly follow the 3-part layout: 1-line news/fact hook, 2-3 lines of actual technical explanation, and 1-line concrete example/number/stat (like a specific CVE ID)."
        ),
    },
    2: {  # Wednesday
        "name": "Infrastructure Security",
        "instruction": (
            "Explain an infrastructure security best practice, network protocol vulnerability, or configuration leak (e.g., open S3 buckets, BGP hijacking). "
            "Strictly follow the 3-part layout: 1-line news/fact hook, 2-3 lines of actual technical explanation, and 1-line concrete example/number/stat."
        ),
    },
    3: {  # Thursday
        "name": "Incident Response",
        "instruction": (
            "Share a technical lesson or metric from a famous historical data breach or security incident. "
            "Strictly follow the 3-part layout: 1-line news/fact hook, 2-3 lines of actual technical explanation, and 1-line concrete example/number/stat (like breach count or cost)."
        ),
    },
    4: {  # Friday
        "name": "Cryptographic Protocols",
        "instruction": (
            "Share a fact or insight about cryptography, key exchange vulnerabilities, TLS standards, or encryption mechanisms. "
            "Strictly follow the 3-part layout: 1-line news/fact hook, 2-3 lines of actual technical explanation, and 1-line concrete example/number/stat."
        ),
    },
    5: {  # Saturday
        "name": "Compliance & Regulations",
        "instruction": (
            "Detail a specific technical requirement or impact of cybersecurity regulations (e.g., EU Cybersecurity Act, CERT-In rules, GDPR, DORA). "
            "Strictly follow the 3-part layout: 1-line news/fact hook, 2-3 lines of actual technical explanation, and 1-line concrete example/number/stat."
        ),
    },
    6: {  # Sunday
        "name": "Authentication & IAM",
        "instruction": (
            "Explain a vulnerability or pattern in identity management, OAuth/OIDC flows, or authentication mechanisms (e.g., token leakage, MFA bypass). "
            "Strictly follow the 3-part layout: 1-line news/fact hook, 2-3 lines of actual technical explanation, and 1-line concrete example/number/stat."
        ),
    },
}


class ThoughtGenerator:
    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"

    def generate_thought(self) -> str:
        """
        Generates a daily text-only 'developer thought' post for Threads via Groq.
        Returns the thought as a plain string (the caption text).
        """
        if not config.groq_api_key:
            raise ValueError("Groq API Key is not set in configuration")

        day_of_week = datetime.utcnow().weekday()
        style = THOUGHT_STYLES[day_of_week]

        positioning = (
            "Your persona is an anonymous software engineer and cybersecurity researcher. "
            "Keep your identity completely anonymous: never mention names, locations, private details, client names, or freelance contracts. "
            "Talk strictly about abstract technical concepts, programming lessons, security audits, and software architecture. "
            "Your tone should be authentic, technical, precise, and direct — avoiding corporate fluff or hype."
        )

        system_prompt = (
            "You are a rigorous cybersecurity researcher who shares one fact-checked security insight per day on Threads. "
            "Generate a short, text-only post — no hashtags, no emojis, no links, no promotions. "
            "You must return a raw JSON object with exactly one key:\n"
            '1. "thought": A clean, informative post under 350 characters that strictly follows a 3-part layout:\n'
            "- Part 1 (News/Fact hook, exactly 1 line): Start with a compelling hook under 80 characters. Rotate between these styles:\n"
            "  * 'Nobody's talking about [precise cybersecurity concept]'\n"
            "  * 'Hot take: [bold, defensible cybersecurity claim]'\n"
            "  * Lead directly with a provocative, concrete security fact (no meta-framing like 'Here is why...' or 'The real implication...').\n"
            "- Part 2 (What it means, 2-3 lines): A clear, technical explanation of the concept or implications in your own words.\n"
            "- Part 3 (Concrete proof, exactly 1 line): Present one concrete number, metric, statistic, or CVE identifier (e.g. CVE-2026-1234, breach size, port number) as proof.\n"
            "Enforce strictly:\n"
            "- NO closing question of any kind at the end of the post.\n"
            "- NO 'hot take' labels inside the post body. Just the clean information.\n"
            "- Do not include any text before or after the JSON."
        )

        user_prompt = (
            f"{positioning}\n\n"
            f"Today's topic format: {style['name']}.\n"
            f"{style['instruction']}"
        )

        headers = {
            "Authorization": f"Bearer {config.groq_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.85,
        }

        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        response_data = response.json()
        raw_text = response_data["choices"][0]["message"]["content"]

        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("```"):
            lines = cleaned_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_text = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse Groq response as JSON. Cleaned response was: {cleaned_text}"
            ) from e

        if "thought" not in parsed:
            raise KeyError(
                f"Groq response JSON missing 'thought' key. Got: {parsed}"
            )

        return parsed["thought"]
