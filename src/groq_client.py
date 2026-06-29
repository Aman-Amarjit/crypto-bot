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
            f"You are {config.persona_name}, a {config.persona_bio} writing a post based on the provided article content.\n"
            f"Write in the first person ('I', 'my') in a {config.persona_tone} tone.\n"
            "Your writing must feel authentic and human — completely avoid choppy, repetitive sentence structures, "
            "AI clichés, filler words, or scraper-like logging statements (e.g., do NOT write 'no CVE mentioned' or "
            "'they show no signs of slowing down'). If a specific detail is missing from the article, simply omit it.\n\n"
            "You must return a raw JSON object with exactly two keys:\n"
            '1. "caption": A cohesive, flowing paragraph under 420 characters that strictly follows these guidelines:\n'
            "- FLOWING SENTENCE STRUCTURE: Write 2–3 natural, flowing sentences. Avoid both single-sentence run-ons and short, choppy, repetitive subject-verb structures.\n"
            "- LEAD WITH THE INTERESTING ANGLE: Open with the most surprising, counterintuitive, or critical aspect "
            "of the story, rather than just rewriting the headline.\n"
            "- DEEP TECHNICAL DETAIL: Prioritize one highly specific technical detail (e.g., exact compromised component, "
            "exploit mechanism, or protocol weakness) over vague summaries.\n"
            "- NATURAL LINK INTEGRATION: Naturally cite the news outlet name in your text and embed the source URL "
            "directly (e.g., '...as documented by BleepingComputer (https://url.com)...' or 'According to Wired (https://url.com), ...'). "
            "Do NOT use a separate 'Source:' line or drop a raw link at the end.\n"
            "- NO DUPLICATION: Verify your text and ensure that no numbers, statistics, or details are repeated twice.\n"
            "- CLOSING QUESTION: Conclude the post with an engaging, thought-provoking technical question directed at the audience. "
            "The final character of the caption must be a question mark (?).\n\n"
            "EXAMPLE OF HIGH-QUALITY HUMAN WRITING STYLE:\n"
            "\"Citrix NetScaler gateways are facing active exploitation via a session hijacking bypass. Attackers are abusing CVE-2026-1234 by sending malformed HTTP requests to expose internal cookie headers. As reported by Ars Technica (https://arstechnica.com/url), how is your team monitoring NetScaler ingress logs for header anomalies?\"\n\n"
            '2. "image_prompt": A descriptive prompt for a text-to-image generator '
            "(Pollinations.ai / Flux) that visually represents the theme of the post.\n"
            "Follow these styling rules strictly:\n"
            "- Frame the image as a premium, modern editorial illustration, minimalist flat-vector graphic, or technology concept art that dynamically visualizes the theme of the article.\n"
            "- Tailor the visual metaphor, subjects, and color palette specifically to the news story (e.g., use warm alerts, cool cybernetic hues, or dark metallic accents depending on the topic).\n"
            "- Do NOT reuse identical prompt keywords like 'wireframe topology' or 'dark navy background with cyan and white lines' for every post. Make each prompt unique and descriptive of a distinct conceptual scene.\n"
            "- Explicitly forbid low-quality cybersecurity stock-image clichés: glowing shields, generic padlocks, binary code rain, a hacker in a dark room with a hoodie, or neon green terminal screens.\n"
            "- Do NOT include any legible text, words, or brand logos in the prompt.\n"
            "Do not include any text before or after the JSON."
        )

        # Fetch and deduplicate headlines
        raw_headlines = NewsFetcher.fetch_latest_headlines(topic)
        headlines = NewsFetcher.filter_seen_headlines(raw_headlines)

        article_text = ""
        selected_headline = None
        if headlines:
            selected_headline = headlines[0]
            article_text = NewsFetcher.fetch_article_content(selected_headline["link"])

        if selected_headline:
            if article_text:
                user_prompt = (
                    f"Today's Niche: Cybersecurity News.\n"
                    f"Today's Topic: {topic}.\n"
                    f"Current Date: {datetime.now(timezone.utc).strftime('%B %-d, %Y')}.\n\n"
                    f"ARTICLE SOURCE URL: {selected_headline['link']}\n"
                    f"ARTICLE HEADLINE: {selected_headline['title']}\n"
                    f"ARTICLE CONTENT:\n\"\"\"\n{article_text}\n\"\"\"\n\n"
                    f"Read and understand the article content above. Extract the key technical details, "
                    f"identify the most interesting angle, and write a high-quality, professional, and natural post following the system instructions. "
                    f"You MUST embed the source URL ({selected_headline['link']}) naturally into the text when citing the source. Do not use a separate Source: line."
                )
            else:
                user_prompt = (
                    f"Today's Niche: Cybersecurity News.\n"
                    f"Today's Topic: {topic}.\n"
                    f"Current Date: {datetime.now(timezone.utc).strftime('%B %-d, %Y')}.\n\n"
                    f"ARTICLE HEADLINE: {selected_headline['title']}\n"
                    f"ARTICLE URL: {selected_headline['link']}\n\n"
                    f"No full article body was retrieved, so write based on the headline above. "
                    f"Write a high-quality, professional, and natural post following the system instructions and embedding the URL naturally."
                )
        else:
            user_prompt = (
                f"Today's Niche: Cybersecurity News.\n"
                f"Today's Topic: {topic}.\n"
                f"Current Date: {datetime.now(timezone.utc).strftime('%B %-d, %Y')}.\n\n"
                f"No live headlines were found for today. Generate an informative post "
                f"detailing a critical technical concept, historical cybersecurity breach, "
                f"or known vulnerability (e.g. Log4Shell, Heartbleed) associated with "
                f"{topic}. Ensure the post strictly follows the guidelines and ends with an engaging question."
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
                    caption = caption.strip()
                    if caption.endswith("."):
                        caption += " How is your team securing against this type of threat?"
                    else:
                        caption += ". How is your team securing against this type of threat?"
                    parsed["caption"] = caption
                    print(
                        "  [Guardrail] Max retries reached. "
                        "Appended default closing question."
                    )

            # --- Guardrail 2: fact-check against selected source headline ---
            print(f"  [FactChecker] Running fact-check on attempt {attempt}...")
            fc_headlines = [selected_headline] if selected_headline else []
            fc_result = self.fact_checker.check(caption, fc_headlines, article_text)

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

