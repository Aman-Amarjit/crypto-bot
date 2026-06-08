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
            "Your persona is an anonymous software engineer and freelance developer building AI infrastructure, "
            "robotics software, and cybersecurity systems for international clients. Keep your identity completely "
            "anonymous: never mention any personal names, specific usernames, locations, or private details. "
            "Your tone should be authentic, conversational, opinionated, and technical, avoiding corporate fluff. "
            "Never use advertisements, promotions, sponsor callouts, links, or marketing pitches."
        )
        
        system_prompt = (
            "You are a creative social media manager. Generate a Threads post based on the given instructions. "
            "You must return a raw JSON object with exactly two keys:\n"
            '1. "caption": A catchy, highly engaging, and viral caption up to 400 characters long. It must '
            "incorporate high-traffic, famous, and trending hashtags/keywords (e.g., #AI, #ArtificialIntelligence, "
            "#FutureTech, #TechTrends, #Robotics, #Cybersecurity, #Trending, #Viral) to maximize reach.\n"
            '2. "image_prompt": A descriptive, high-quality prompt for a text-to-image generator (Pollinations.ai) '
            "that captures the mood and message of the caption. Avoid generic styling terms; focus on visual "
            "elements, colors, lighting, and composition.\n"
            "Do not include any text before or after the JSON."
        )
        
        # Content Strategy Calendar
        if day_of_week in (0, 1): # Monday / Tuesday: Hot Take on News
            headlines = NewsFetcher.fetch_latest_headlines(topic)
            if headlines:
                headlines_str = "\n".join([f"- {h}" for h in headlines])
                user_prompt = (
                    f"{positioning}\n\n"
                    f"Format: Hot Take on Recent News regarding {topic}.\n"
                    f"Here are the latest real-time news headlines from the last 24 hours:\n"
                    f"{headlines_str}\n\n"
                    f"Select the most interesting headline. Do not just summarize it. Write a catchy, opinionated "
                    f"hot take detailing the 'real implication everyone is missing' (e.g. 'X just dropped, and the real implication "
                    f"everyone is missing is Y'). Speak from the perspective of a CS builder."
                )
            else:
                user_prompt = (
                    f"{positioning}\n\n"
                    f"Format: Hot Take on Recent News regarding {topic}.\n"
                    f"Write a catchy, opinionated hot take on a recent trend or release in the field of {topic}. "
                    f"Focus on the real implications that other people are missing. Speak from the perspective of a CS builder."
                )
                
        elif day_of_week in (2, 3): # Wednesday / Thursday: Project Update
            user_prompt = (
                f"{positioning}\n\n"
                f"Format: Project Update ('I built X, here's what I learned').\n"
                f"Write an anonymous post discussing a technical feature, challenge, or lesson learned while building AI software "
                f"(such as a legal AI assistant, a custom AI voice calling bot, or a multi-agent system security audit). "
                f"Do not mention any specific proprietary project names or private client names. "
                f"Write in 2-3 short, engaging paragraphs. Be specific and authentic about the engineering process."
            )
            
        elif day_of_week in (4, 5): # Friday / Saturday: Tech Explainer / Tip
            user_prompt = (
                f"{positioning}\n\n"
                f"Format: Tech Explainer or Tip.\n"
                f"Explain a technical concept or share an actionable coding/architecture tip related to {topic} "
                f"in plain language. Structure it like an educational explainer ('How [thing] actually works'). "
                f"Keep it clear, concise, and highly useful for other developers."
            )
            
        else: # Sunday: Behind-the-Scenes
            user_prompt = (
                f"{positioning}\n\n"
                f"Format: Behind-the-Scenes / The Messy Middle.\n"
                f"Write an authentic post showing a behind-the-scenes look at building software. Focus on a late-night debugging session, "
                f"dealing with a difficult client architecture decision, or solving an optimization problem. "
                f"Keep it highly relatable and conversational, showing the reality of being a freelance developer and student."
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
