import json
import requests
from datetime import datetime
from src.config import config


THOUGHT_STYLES = {
    0: {  # Monday
        "name": "Contrarian Take",
        "instruction": (
            "Share a sharp, well-reasoned contrarian opinion that challenges a widely-held belief "
            "in software engineering or AI. State what most people believe, then argue why it's wrong "
            "or oversimplified. Be specific, opinionated, and bold. End with a question."
        ),
    },
    1: {  # Tuesday
        "name": "Hard Lesson",
        "instruction": (
            "Share a hard-earned technical lesson or engineering mistake you've made while building software. "
            "Be specific about the mistake (e.g., a bad architecture decision, a security oversight, a premature optimisation). "
            "What did it cost you? What would you do differently? Keep it raw and honest. End with a question."
        ),
    },
    2: {  # Wednesday
        "name": "Unpopular Truth",
        "instruction": (
            "Share an uncomfortable truth about the tech industry, software development culture, or AI hype "
            "that most developers are reluctant to say out loud. Ground it in concrete observations. "
            "Avoid vague platitudes — be precise and defensible. End with a question."
        ),
    },
    3: {  # Thursday
        "name": "Mini Mental Model",
        "instruction": (
            "Share a single, powerful mental model or framework that fundamentally changed how you think "
            "about building software, debugging systems, or approaching security. Name the model, explain it briefly "
            "with a concrete example, and say why it matters. End with a question."
        ),
    },
    4: {  # Friday
        "name": "Observation from the Trenches",
        "instruction": (
            "Share a candid observation from the reality of working as a developer — not advice, just an honest observation "
            "about how software actually gets built vs. how it's supposed to be built. "
            "Be specific, grounded, and relatable. End with a question."
        ),
    },
    5: {  # Saturday
        "name": "The Thing Nobody Talks About",
        "instruction": (
            "Share something important in software engineering, AI development, or cybersecurity that is severely under-discussed. "
            "Why is it ignored? Why does it matter more than people think? "
            "Be direct and precise. Avoid generic motivational content. End with a question."
        ),
    },
    6: {  # Sunday
        "name": "Builder's Reflection",
        "instruction": (
            "Share a reflective, introspective thought about the nature of building things — software, systems, or ideas. "
            "What motivates you, what frustrates you, or what surprised you this week as a developer. "
            "Keep it authentic and conversational, not motivational-poster-level. End with a question."
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
            "Your persona is an anonymous software engineer and open-source developer building AI infrastructure, "
            "robotics software, and cybersecurity systems. Keep your identity completely anonymous: never mention "
            "any personal names, specific usernames, locations, private details, client names, freelance contracts, "
            "or partner companies. Talk strictly about abstract technical concepts, programming lessons, and software architecture. "
            "Your tone should be authentic, conversational, opinionated, and technical — not corporate, not motivational-poster-level."
        )

        system_prompt = (
            "You are a thoughtful, senior software engineer who shares one genuine thought per day on Threads. "
            "Generate a short, text-only post — no hashtags, no emojis, no links, no promotions. "
            "The post should feel like a real person's honest reflection, not a social media template. "
            "You must return a raw JSON object with exactly one key:\n"
            '1. "thought": A concise, punchy, text-only post under 350 characters. '
            "First line must be a strong hook (under 80 characters). "
            "Close with a genuine, thought-provoking question. "
            "No hashtags. No emojis. No links. No promotional language.\n"
            "Do not include any text before or after the JSON."
        )

        user_prompt = (
            f"{positioning}\n\n"
            f"Today's thought format: {style['name']}.\n"
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
