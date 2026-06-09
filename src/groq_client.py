import json
import requests
from datetime import datetime, timezone
from src.config import config
from src.news_fetcher import NewsFetcher
from src.fact_checker import FactChecker


class GroqClient:
    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self.max_retries = 3
        self.fact_checker = FactChecker()

    # ------------------------------------------------------------------ #
    #  Guardrail: ensure caption ends with a question                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _has_closing_question(caption: str) -> bool:
        """
        Returns True if the caption contains an engaging question (ending with '?')
        just before the Source line, or at the end of the text.
        """
        stripped = caption.strip()
        if not stripped:
            return False
        lines = [l.strip() for l in stripped.splitlines() if l.strip()]
        if not lines:
            return False
        
        # If the last line is the Source line, check the line before it
        if lines[-1].lower().startswith("source:"):
            if len(lines) >= 2:
                return lines[-2].endswith("?")
            return False
        else:
            return lines[-1].endswith("?")

    # ------------------------------------------------------------------ #
    #  Main generation method                                             #
    # ------------------------------------------------------------------ #
    def generate_content(self, topic: str) -> dict:
        """
        Sends a request to the Groq API to generate a post caption and image
        prompt.  Headlines are deduplicated against previously published posts
        before being passed to the LLM.  The caption is validated to ensure it
        ends with a closing question; up to max_retries attempts are
        made before raising.
        """
        if not config.groq_api_key:
            raise ValueError("Groq API Key is not set in configuration")

        headers = {
            "Authorization": f"Bearer {config.groq_api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "You are a rigorous, highly specialised cybersecurity news analyst. "
            "Generate a factually precise social media post based on the provided topic. "
            "You must return a raw JSON object with exactly two keys:\n"
            '1. "caption": A clean, informative caption under 450 characters that strictly '
            "follows a 4-part layout:\n"
            "- Part 1 (News hook, exactly 1 line, under 80 characters): Open directly with "
            "an active-voice factual statement about the specific incident, breach, or "
            "vulnerability. Do NOT use clickbait starters like 'Nobody's talking about', "
            "'Hot take:', 'The real implication', or 'Here is why'. No meta-framing.\n"
            "- Part 2 (What it means, 2–3 lines): A clear, technical explanation of the "
            "implications in your own words. Be precise about attribution — if a third-party "
            "vendor was breached, name the vendor, not just the affected organisation.\n"
            "- Part 3 (Concrete proof, exactly 1 line): One concrete number, metric, "
            "statistic, or CVE identifier directly sourced from the headline (e.g. "
            "CVE-2026-1234, patch version, breach size, specific bytes/percentage). "
            "Do NOT fabricate statistics, dates, or percentages not present in the source "
            "headline.\n"
            "- Part 4 (Engaging Question, exactly 1 line): Close the post with an engaging, "
            "thought-provoking question directed at the audience regarding the global security "
            "situation, the news itself, or its broader technical implications.\n"
            "Enforce strictly:\n"
            "- The caption MUST end with the engaging question (ending with a question mark) "
            "just before the 'Source:' line. Do NOT omit this closing question.\n"
            "- Do not use 'Hot take', 'Myth:', or 'Reality:' labels in the caption body.\n"
            "- Limit to at most 1 relevant hashtag (e.g. #Cybersecurity, #Infosec) "
            "or omit entirely.\n"
            "- Append 'Source: <url>' as the very last element, using the link from the "
            "selected headline. This must always be present.\n"
            '2. "image_prompt": A descriptive prompt for a text-to-image generator '
            "(Pollinations.ai / Flux) that visually represents the theme of the post.\n"
            "Follow these styling rules strictly:\n"
            "- Frame the image as an **abstract technical schematic or network topology "
            "diagram** — boxes, nodes, arrows, and flow lines representing the incident "
            "(e.g. attacker→server flows, breach vectors, network segments).\n"
            "- Use keywords: 'abstract schematic', 'wireframe topology', 'system block "
            "diagram', 'no text characters', 'no legible labels', 'dark navy background', "
            "'cyan and white lines', 'red alert nodes'. Do NOT say 'diagram with labels'.\n"
            "- Explicitly forbid: glowing shields, purple hacker rooms, sci-fi corridors, "
            "binary rain, padlocks, generic stock-image cybersecurity visuals.\n"
            "- Do NOT include any legible text, words, or brand logos in the prompt.\n"
            "- Accept that diagram rendering will be approximate; describe the layout "
            "spatially (e.g. 'three interconnected node clusters', 'central server block "
            "flanked by two breach-vector arrows') rather than labelled elements.\n"
            "Do not include any text before or after the JSON."
        )

        # Fetch and deduplicate headlines
        raw_headlines = NewsFetcher.fetch_latest_headlines(topic)
        headlines = NewsFetcher.filter_seen_headlines(raw_headlines)

        if headlines:
            headlines_str = "\n".join(
                [f"- {h['title']} (source: {h['link']})" for h in headlines]
            )
            user_prompt = (
                f"Today's Niche: Cybersecurity News.\n"
                f"Today's Topic: {topic}.\n"
                f"Current Date: {datetime.now(timezone.utc).strftime('%B %-d, %Y')}.\n\n"
                f"Here are the latest headline news items from verified tech sources:\n"
                f"{headlines_str}\n\n"
                f"Select the single most interesting and technically relevant headline. "
                f"Do NOT mix details from multiple headlines. Write an informative, "
                f"factually precise post strictly in the requested 4-part caption format. "
                f"Use concrete numbers or CVE details directly from that one headline. "
                f"Attribute the breach or incident to the correct party — if a vendor or "
                f"intermediary was breached rather than the named organisation directly, "
                f"reflect that distinction. "
                f"Append 'Source: <url>' using the link from the selected headline."
            )
        else:
            user_prompt = (
                f"Today's Niche: Cybersecurity News.\n"
                f"Today's Topic: {topic}.\n"
                f"Current Date: {datetime.now(timezone.utc).strftime('%B %-d, %Y')}.\n\n"
                f"No live headlines were found for today. Generate an informative post "
                f"detailing a critical technical concept, historical cybersecurity breach, "
                f"or known vulnerability (e.g. Log4Shell, Heartbleed) associated with "
                f"{topic}. Ensure the post strictly follows the 4-part caption format with "
                f"concrete numbers, statistics, or CVE details. Omit the Source line when "
                f"no URL is available."
            )

        # Track any fact-check issues from the previous attempt so they can
        # be injected as correction context into the next generation call.
        fact_check_feedback: str = ""

        for attempt in range(1, self.max_retries + 1):
            # If a previous fact-check flagged specific issues, append them
            # to the user prompt so the LLM can self-correct.
            augmented_user_prompt = user_prompt
            if fact_check_feedback:
                augmented_user_prompt += (
                    f"\n\n--- FACT-CHECK CORRECTION (attempt {attempt}) ---\n"
                    f"Your previous caption failed fact-checking. Fix ONLY these "
                    f"specific issues and regenerate the caption:\n"
                    f"{fact_check_feedback}\n"
                    f"Do not change anything else about the format."
                )

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": augmented_user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
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

            if "caption" not in parsed or "image_prompt" not in parsed:
                raise KeyError(
                    f"Groq response JSON missing 'caption' or 'image_prompt' keys. "
                    f"Got: {parsed}"
                )

            caption = parsed["caption"]

            # --- Guardrail 1: closing question check ---
            if not self._has_closing_question(caption):
                print(
                    f"  [Guardrail] Caption attempt {attempt}/{self.max_retries} "
                    f"does not end with a question. Retrying..."
                )
                if attempt < self.max_retries:
                    fact_check_feedback = ""  # reset; this is a format issue not a fact issue
                    continue
                else:
                    lines = [l.strip() for l in caption.strip().splitlines() if l.strip()]
                    if lines and lines[-1].lower().startswith("source:"):
                        lines.insert(-1, "How is your team securing against this type of threat?")
                    else:
                        lines.append("How is your team securing against this type of threat?")
                    parsed["caption"] = "\n".join(lines)
                    caption = parsed["caption"]
                    print(
                        "  [Guardrail] Max retries reached. "
                        "Appended default closing question."
                    )

            # --- Guardrail 2: fact-check against source headlines ---
            print(f"  [FactChecker] Running fact-check on attempt {attempt}...")
            fc_result = self.fact_checker.check(caption, headlines)

            if fc_result["passed"]:
                print("  [FactChecker] ✅ Passed.")
                return parsed
            else:
                issues_text = "\n".join(
                    [f"  - {i}" for i in fc_result["issues"]]
                )
                print(
                    f"  [FactChecker] ❌ Failed (attempt {attempt}/{self.max_retries}). "
                    f"Issues:\n{issues_text}"
                )
                if attempt < self.max_retries:
                    # Build correction feedback for the next generation attempt
                    fact_check_feedback = "\n".join(
                        [f"- {i}" for i in fc_result["issues"]]
                    )
                    continue
                else:
                    # Final attempt still failed — log a warning and raise so
                    # the caller can decide whether to abort or publish anyway.
                    raise ValueError(
                        f"Caption failed fact-checking after {self.max_retries} attempts. "
                        f"Final issues:\n{issues_text}\n\n"
                        f"Caption was:\n{caption}"
                    )

        # Should not reach here
        raise RuntimeError("generate_content exhausted all retries unexpectedly.")

