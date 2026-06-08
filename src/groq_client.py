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
            "You are a creative and highly rigorous social media manager. Generate a Threads post based on the given topic. "
            "You must return a raw JSON object with exactly two keys:\n"
            '1. "caption": A highly engaging, punchy, and factually rigorous caption under 400 characters. '
            "Follow these structural growth guidelines:\n"
            "- First line hook: Start with a highly compelling, punchy first line (under 80 characters) that grabs attention "
            "and makes users click 'more'.\n"
            "- Question ending: Always close the post with a genuine, thought-provoking question to drive comment engagement.\n"
            "- Spam prevention: Do not use multiple hashtags. Limit to at most 1 highly relevant hashtag (e.g., #AI, #Cybersecurity) or omit them entirely.\n"
            "- Content depth: Avoid shallow, vague opinions. Ground your claims in precise technical details and express "
            "a well-reasoned, defensible developer stance. Do not include ads, promotions, or call-to-actions.\n"
            '2. "image_prompt": A descriptive, high-quality prompt for a text-to-image generator (Pollinations.ai) '
            "that captures the mood and message of the caption. Avoid generic styling terms; focus on visual "
            "elements, colors, lighting, and composition. DO NOT include legible text, words, or specific brand logos "
            "(e.g., do not ask to write 'Gemini' or 'GPT-5'), as image generators cannot render text properly. "
            "Instead, use high-tech visual metaphors (e.g., glowing nodes, server racks, abstract neural network webs, "
            "binary code patterns, futuristic interfaces).\n"
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
                    f"Current Date context: June 8, 2026. (Orient all temporal expressions relative to this date).\n"
                    f"Here are the latest real-time news headlines from the last 24 hours:\n"
                    f"{headlines_str}\n\n"
                    f"Select the most interesting headline. Write an opinionated, factually rigorous, and precise "
                    f"take on it. Do not invent details, and do not imply older projects/collaborations in the headlines are 'new' "
                    f"or 'just released' if the text doesn't indicate that. Focus on the actual event (e.g., conferences, streams, etc.) "
                    f"and provide a well-reasoned developer perspective on the real implication everyone is missing (implied: 'X just dropped, "
                    f"and the real implication everyone is missing is Y'). Your insight must be a solid, defensible tech claim."
                )
            else:
                user_prompt = (
                    f"{positioning}\n\n"
                    f"Format: Hot Take on Recent News regarding {topic}.\n"
                    f"Current Date context: June 8, 2026.\n"
                    f"Write an opinionated, factually precise hot take on a recent developer trend or tool release in the field of {topic}. "
                    f"Avoid vague buzzwords and focus on concrete, defensible implications."
                )
                
        elif day_of_week in (2, 3): # Wednesday / Thursday: Project Update
            user_prompt = (
                f"{positioning}\n\n"
                f"Format: Engineering Update ('I built X, here's what I learned').\n"
                f"Write an anonymous post discussing a technical feature, challenge, or lesson learned while building open-source software "
                f"(such as a legal AI parser, implementing real-time websocket audio streaming, or auditing code security of a multi-agent system). "
                f"Focus strictly on the open-source engineering aspect. Do not mention any companies, client names, freelance contracts, "
                f"or specific proprietary products. Write in 2-3 short, engaging paragraphs. Be specific and authentic about the engineering process."
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
