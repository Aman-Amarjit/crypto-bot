import json
import requests
from datetime import datetime
from src.config import config
from src.news_fetcher import NewsFetcher

class GroqClient:
    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        
    def generate_content(self, topic: str) -> dict:
        """
        Sends a request to Groq API to generate post caption and image prompt,
        implementing the user's specific content strategy calendar and student builder positioning.
        """
        if not config.groq_api_key:
            raise ValueError("Groq API Key is not set in configuration")
            
        headers = {
            "Authorization": f"Bearer {config.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        # Determine day of the week (0 = Monday, 6 = Sunday)
        day_of_week = datetime.utcnow().weekday()
        
        # Base positioning context for the LLM - Anonymous Developer Persona
        positioning = (
            "Your persona is an anonymous software engineer and open-source developer building AI infrastructure, "
            "robotics software, and cybersecurity systems. Keep your identity completely anonymous: never mention "
            "any personal names, specific usernames, locations, private details, client names, freelance contracts, "
            "or partner companies. Talk strictly about abstract technical concepts, programming tips, general coding lessons, "
            "and software architecture. Your tone should be authentic, conversational, opinionated, and technical, avoiding corporate fluff. "
            "Never use advertisements, promotions, sponsor callouts, links, or marketing pitches."
        )
        
        system_prompt = (
            "You are a rigorous, highly specialized cybersecurity news analyst. Generate a factually precise social media post based on the provided topic. "
            "You must return a raw JSON object with exactly two keys:\n"
            '1. "caption": A clean, informative caption under 400 characters that strictly follows a 3-part layout:\n'
            "- Part 1 (News/Fact hook, exactly 1 line): Start with a compelling news/fact hook under 80 characters. Rotate between these styles:\n"
            "  * 'Nobody's talking about [precise cybersecurity concept/news]'\n"
            "  * 'Hot take: [bold, defensible cybersecurity claim/finding]'\n"
            "  * Lead directly with a provocative, concrete news fact (no meta-framing like 'Here is why...' or 'The real implication...').\n"
            "- Part 2 (What it means, 2-3 lines): A clear, technical explanation of the implications in your own words.\n"
            "- Part 3 (Concrete proof, exactly 1 line): Present one concrete number, metric, statistic, or CVE identifier (e.g. CVE-2026-1234, patch version, size of a data breach, specific bytes/percentage) as proof.\n"
            "Enforce strictly:\n"
            "- NO closing question of any kind at the end of the post.\n"
            "- NO 'hot take' labels inside the caption body. Just the clean information.\n"
            "- Do not use multiple hashtags. Limit to at most 1 relevant hashtag (e.g., #Cybersecurity, #Infosec) or omit them entirely.\n"
            '2. "image_prompt": A descriptive, high-quality prompt for a text-to-image generator (Pollinations.ai) '
            "that captures the theme of the caption using a consistent, high-end developer/terminal aesthetic.\n"
            "Follow these styling rules:\n"
            "- Frame the image strictly as a Terminal/CRT mockup style.\n"
            "- Describe screenshots of clean terminal windows displaying monospaced compiler/security logs, "
            "mock code blocks (e.g., C/Rust memory safety checks, Python security scanning functions) with syntax highlighting on a pitch-black background, "
            "or retro-style CRT monitor screens displaying green/amber phosphor monospaced output.\n"
            "- Explicitly avoid stock-looking, high-saturation, generic colorful hacker concepts like 'glowing digital shields', 'sci-fi corridors', or 'purple hacker rooms'.\n"
            "- Do NOT include any legible text, words, or specific brand logos.\n"
            "Do not include any text before or after the JSON."
        )
        
        headlines = NewsFetcher.fetch_latest_headlines(topic)
        if headlines:
            headlines_str = "\n".join([f"- {h}" for h in headlines])
            user_prompt = (
                f"{positioning}\n\n"
                f"Today's Niche: Cybersecurity News.\n"
                f"Today's Topic: {topic}.\n"
                f"Current Date: June 8, 2026.\n\n"
                f"Here are the latest headline news items from verified tech sources:\n"
                f"{headlines_str}\n\n"
                f"Select the most interesting and technically relevant headline. Write an informative, factually precise take on it "
                f"strictly in the requested 3-part caption format. Fact-check the headline and use concrete numbers, statistics, or CVE details."
            )
        else:
            user_prompt = (
                f"{positioning}\n\n"
                f"Today's Niche: Cybersecurity News.\n"
                f"Today's Topic: {topic}.\n"
                f"Current Date: June 8, 2026.\n\n"
                f"No live headlines were found for today. Generate an informative post detailing a critical technical concept, "
                f"historical cybersecurity breach, known vulnerability (e.g., Log4Shell, Heartbleed), or regulatory policy associated with {topic}. "
                f"Ensure the post strictly follows the 3-part caption format with concrete numbers, statistics, or CVE details."
            )
            
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7
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
            raise ValueError(f"Failed to parse Groq response as JSON. Cleaned response was: {cleaned_text}") from e
            
        if "caption" not in parsed or "image_prompt" not in parsed:
            raise KeyError(f"Groq response JSON missing 'caption' or 'image_prompt' keys. Got: {parsed}")
            
        return parsed
