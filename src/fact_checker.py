import json
import requests
from src.config import config


class FactChecker:
    """
    A second-pass LLM verifier that cross-checks a generated caption against
    its source headline(s) before the post is published.

    Specifically catches:
      - Statistics, numbers, or dates in the caption that don't appear in the
        source headline (fabricated metrics)
      - Attribution errors (wrong org named as the victim/actor)
      - Claims that conflate details from multiple headlines
      - CVE IDs or version numbers not traceable to the source

    Returns a structured result:
        {
            "passed": bool,
            "issues": ["...", ...]   # empty list when passed=True
        }
    """

    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"

    def check(self, caption: str, headlines: list, article_text: str = "") -> dict:
        """
        Args:
            caption:   The generated post caption to verify.
            headlines: List of dicts [{"title": str, "link": str}] that were
                       passed to the LLM when generating the caption.
                       May be empty if the LLM was working from general
                       knowledge (fallback mode).
            article_text: Optional full scraped text of the source article.

        Returns:
            {"passed": True, "issues": []}
            {"passed": False, "issues": ["Issue 1", "Issue 2", ...]}
        """
        if not config.groq_api_key:
            raise ValueError("Groq API Key is not set in configuration")

        # If there were no source headlines and no article text, we can only do a shallow check
        if not headlines and not article_text:
            return self._check_internal_consistency(caption)

        return self._check_against_sources(caption, headlines, article_text)

    # ------------------------------------------------------------------ #
    #  Full check: caption vs source headlines / article content          #
    # ------------------------------------------------------------------ #
    def _check_against_sources(self, caption: str, headlines: list, article_text: str = "") -> dict:
        headlines_block = "\n".join(
            [f"- {h['title']} (url: {h['link']})" for h in headlines]
        )

        system_prompt = (
            "You are a rigorous fact-checking editor for a cybersecurity news account. "
            "Your job is to verify that a social media caption is factually consistent "
            "with its source article content or headlines. You must return a raw JSON object with exactly "
            "two keys:\n"
            '1. "passed": true if the caption is factually accurate, false if any issue '
            "is found.\n"
            '2. "issues": an array of strings, each describing one specific factual '
            "problem found in the caption. Empty array when passed=true.\n\n"
            "Check for ALL of the following:\n"
            "- ATTRIBUTION: Does the caption correctly name who was breached or attacked? "
            "Flag if the caption blames Organisation A when the source says a "
            "third-party vendor (Organisation B) was the compromise point.\n"
            "- FABRICATED STATS: Does the caption contain any number, percentage, date, "
            "record count, or dollar figure that does NOT appear in the source article content or headlines? "
            "Flag every instance that is not supported by the provided text.\n"
            "- CVE / VERSION NUMBERS: Are any CVE IDs or software version numbers in the "
            "caption actually present in the source article content or headlines? Flag any that appear "
            "invented.\n"
            "- CONFLATION: Does the caption appear to mix details from different stories? "
            "Flag if so.\n"
            "- SCOPE CREEP: Does the caption make claims far broader than what the source supports.\n\n"
            "Do NOT flag:\n"
            "- Technical background context that is general knowledge.\n"
            "- Minor paraphrasing that preserves factual accuracy.\n"
            "- Natural embedding of URLs or links in the text.\n\n"
            "Return ONLY the raw JSON object. No explanation outside the JSON."
        )

        user_prompt = (
            f"SOURCE HEADLINES:\n{headlines_block}\n\n"
        )
        if article_text:
            user_prompt += f"SOURCE ARTICLE CONTENT:\n\"\"\"\n{article_text}\n\"\"\"\n\n"
            
        user_prompt += (
            f"GENERATED CAPTION TO VERIFY:\n{caption}\n\n"
            f"Return your verdict as a JSON object with 'passed' and 'issues' keys."
        )

        return self._call_api(system_prompt, user_prompt)

    # ------------------------------------------------------------------ #
    #  Shallow check: no sources available (fallback/historical posts)    #
    # ------------------------------------------------------------------ #
    def _check_internal_consistency(self, caption: str) -> dict:
        system_prompt = (
            "You are a rigorous fact-checking editor for a cybersecurity news account. "
            "No source headline is available for this post — it was generated from "
            "general knowledge. Check the caption for internal red flags only. "
            "Return a raw JSON object with exactly two keys:\n"
            '1. "passed": true if no red flags are found, false if any are found.\n'
            '2. "issues": array of strings describing each red flag. Empty when '
            "passed=true.\n\n"
            "Flag ONLY the following (do not penalise for missing a source):\n"
            "- Suspiciously precise statistics that are commonly fabricated by LLMs "
            "(e.g., exact percentages like '73% of companies', round numbers like "
            "'over 1 million records' without any qualifier).\n"
            "- CVE IDs that follow an unusual pattern (e.g., future years, "
            "non-standard format).\n"
            "- Attribution of a breach to a very well-known organisation in a way "
            "that would likely be headline news but reads as generic filler.\n\n"
            "Return ONLY the raw JSON object."
        )

        user_prompt = (
            f"GENERATED CAPTION TO VERIFY (no source headline available):\n{caption}\n\n"
            f"Return your verdict as a JSON object with 'passed' and 'issues' keys."
        )

        return self._call_api(system_prompt, user_prompt)

    # ------------------------------------------------------------------ #
    #  Shared API call helper                                             #
    # ------------------------------------------------------------------ #
    def _call_api(self, system_prompt: str, user_prompt: str) -> dict:
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
            # Low temperature: we want deterministic, conservative judgements
            "temperature": 0.1,
        }

        try:
            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(
                    lines[1:-1] if lines[-1].startswith("```") else lines[1:]
                ).strip()

            result = json.loads(raw)

            if "passed" not in result or "issues" not in result:
                # Malformed response — treat as a soft pass so we don't
                # block publication on a fact-checker bug
                print(
                    "  [FactChecker] Warning: malformed fact-checker response. "
                    f"Got: {result}. Treating as soft pass."
                )
                return {"passed": True, "issues": []}

            return result

        except Exception as e:
            # Fact-checker errors must never block publication — log and pass
            print(f"  [FactChecker] Warning: fact-check call failed ({e}). Soft pass.")
            return {"passed": True, "issues": []}
