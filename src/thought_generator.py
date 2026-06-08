import json
import requests
from datetime import datetime, timezone
from src.config import config


THOUGHT_STYLES = {
    0: {  # Monday
        "name": "Threat Intelligence",
        "instruction": (
            "Share a precise, technically accurate fact about an active threat actor "
            "campaign, ransomware family behaviour (e.g. LockBit, BlackCat/ALPHV), "
            "or malware persistence technique. "
            "Strictly follow the 3-part layout: 1-line active-voice news hook, "
            "2–3 lines of technical explanation, "
            "and 1 final line with a concrete number, stat, or CVE as proof."
        ),
    },
    1: {  # Tuesday
        "name": "Vulnerability Analysis",
        "instruction": (
            "Explain a critical security vulnerability class or a specific recent CVE "
            "(e.g. memory unsafety in C/C++, buffer overflows, use-after-free, "
            "integer truncation). "
            "Strictly follow the 3-part layout: 1-line active-voice news hook, "
            "2–3 lines of technical explanation, "
            "and 1 final line with a specific CVE ID, affected version, or CVSS score."
        ),
    },
    2: {  # Wednesday
        "name": "Infrastructure Security",
        "instruction": (
            "Explain an infrastructure security best practice, network protocol "
            "vulnerability, or misconfiguration class (e.g. open S3 buckets, BGP "
            "hijacking, exposed Kubernetes API servers). "
            "Strictly follow the 3-part layout: 1-line active-voice news hook, "
            "2–3 lines of technical explanation, "
            "and 1 final line with a concrete example, metric, or number."
        ),
    },
    3: {  # Thursday
        "name": "Incident Response",
        "instruction": (
            "Share a specific technical lesson or metric from a well-documented "
            "historical data breach or security incident — use only verified, "
            "publicly documented information. "
            "Strictly follow the 3-part layout: 1-line active-voice news hook, "
            "2–3 lines of technical explanation, "
            "and 1 final line with the verified breach record count, cost, or timeline."
        ),
    },
    4: {  # Friday
        "name": "Cryptographic Protocols",
        "instruction": (
            "Share a technically precise insight about cryptography, key exchange "
            "vulnerabilities, TLS version security, cipher suite weaknesses, or "
            "quantum-resistant algorithm adoption. "
            "Strictly follow the 3-part layout: 1-line active-voice news hook, "
            "2–3 lines of technical explanation, "
            "and 1 final line with a concrete algorithm name, key size, or RFC number."
        ),
    },
    5: {  # Saturday
        "name": "Compliance & Regulations",
        "instruction": (
            "Detail a specific technical requirement, deadline, or enforcement action "
            "from a major cybersecurity regulation (e.g. EU Cybersecurity Act, NIS2, "
            "CERT-In incident reporting rules, GDPR Art.32, DORA RTS). "
            "Strictly follow the 3-part layout: 1-line active-voice news hook, "
            "2–3 lines of technical explanation, "
            "and 1 final line with the specific article number, fine amount, or deadline."
        ),
    },
    6: {  # Sunday
        "name": "Authentication & IAM",
        "instruction": (
            "Explain a vulnerability or attack pattern in identity management, OAuth 2.0 "
            "/ OIDC flows, or authentication mechanisms (e.g. token leakage, MFA bypass "
            "via SIM swap, session fixation, OAuth redirect hijacking). "
            "Strictly follow the 3-part layout: 1-line active-voice news hook, "
            "2–3 lines of technical explanation, "
            "and 1 final line with a CVE identifier, affected library, or a concrete "
            "exploitability metric."
        ),
    },
}


class ThoughtGenerator:
    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self.max_retries = 3

    # ------------------------------------------------------------------ #
    #  Guardrail: reject thoughts that end with a question                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ends_with_question(text: str) -> bool:
        """
        Returns True only if the very last sentence/line of the thought ends
        with a question mark.  A mid-post rhetorical '?' will not trigger this.
        """
        stripped = text.strip()
        if not stripped:
            return False
        lines = [l.strip() for l in stripped.splitlines() if l.strip()]
        last_line = lines[-1] if lines else stripped
        return last_line.endswith("?")

    def generate_thought(self) -> str:
        """
        Generates a daily text-only cybersecurity insight post for Threads via
        Groq.  Returns the thought as a plain string (the caption text).
        """
        if not config.groq_api_key:
            raise ValueError("Groq API Key is not set in configuration")

        day_of_week = datetime.now(timezone.utc).weekday()
        style = THOUGHT_STYLES[day_of_week]

        positioning = (
            "Your persona is an anonymous software engineer and cybersecurity researcher. "
            "Keep your identity completely anonymous: never mention names, locations, "
            "private details, client names, or freelance contracts. "
            "Talk strictly about technical security concepts, vulnerability analysis, "
            "threat intelligence, and software security architecture. "
            "Your tone should be authentic, technical, precise, and direct — avoiding "
            "corporate fluff or hype. "
            "Stay strictly within cybersecurity topics. Do NOT opine on AI workforce "
            "trends, model releases, general tech company news, or startup culture."
        )

        system_prompt = (
            "You are a rigorous cybersecurity researcher who shares one fact-checked "
            "security insight per day on Threads. "
            "Generate a short, text-only post — no hashtags, no emojis, no links, "
            "no promotions. "
            "You must return a raw JSON object with exactly one key:\n"
            '1. "thought": A clean, informative post under 350 characters that strictly '
            "follows a 3-part layout:\n"
            "- Part 1 (News hook, exactly 1 line, under 80 characters): Open with an "
            "active-voice, factual cybersecurity statement about the specific topic. "
            "Do NOT use 'Nobody's talking about', 'Hot take:', 'Myth:', 'Reality:', "
            "or any meta-framing opener.\n"
            "- Part 2 (What it means, 2–3 lines): A clear, technical explanation of the "
            "concept or implications in your own words.\n"
            "- Part 3 (Concrete proof, exactly 1 line): One concrete number, metric, "
            "statistic, CVE identifier, or verified technical detail as proof.\n"
            "Enforce strictly:\n"
            "- The final line of the post MUST NOT be a question. No closing questions, "
            "no rhetorical engagement bait at the end.\n"
            "- Do NOT use 'Hot take', 'Myth:', or 'Reality:' labels.\n"
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

        for attempt in range(1, self.max_retries + 1):
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                # 0.55: enough variety to avoid repetitive phrasing over weeks,
                # while still producing structured, factual output.
                "temperature": 0.55,
            }

            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=30
            )
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
                    f"Failed to parse Groq response as JSON. "
                    f"Cleaned response was: {cleaned_text}"
                ) from e

            if "thought" not in parsed:
                raise KeyError(
                    f"Groq response JSON missing 'thought' key. Got: {parsed}"
                )

            thought = parsed["thought"]

            # Guardrail: retry if the final line ends with a question mark
            if self._ends_with_question(thought):
                print(
                    f"  [Guardrail] Thought attempt {attempt}/{self.max_retries} "
                    f"ends with a question. Retrying..."
                )
                if attempt < self.max_retries:
                    continue
                else:
                    # Strip offending closing question line as last resort
                    t_lines = [l.strip() for l in thought.strip().splitlines() if l.strip()]
                    thought = "\n".join(t_lines[:-1])
                    print(
                        "  [Guardrail] Max retries reached. "
                        "Stripped closing question line."
                    )

            return thought

        raise RuntimeError("generate_thought exhausted all retries unexpectedly.")
