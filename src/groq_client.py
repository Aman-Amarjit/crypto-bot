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
        
        # Content Strategy Calendar (Aligning with High-Performance social formats)
        if day_of_week in (0, 1): # Monday / Tuesday: Hot Take on News -> Format: Sharable Infographics / Myths vs Reality
            headlines = NewsFetcher.fetch_latest_headlines(topic)
            if headlines:
                headlines_str = "\n".join([f"- {h}" for h in headlines])
                user_prompt = (
                    f"{positioning}\n\n"
                    f"Format: Hot Take on Recent News regarding {topic} as a Sharable Infographic / Myth vs Reality.\n"
                    f"Current Date context: June 8, 2026.\n"
                    f"Here are the latest news headlines:\n"
                    f"{headlines_str}\n\n"
                    f"Select the most interesting headline. Write an opinionated, factually precise take on it. "
                    f"Frame it under the concept of 'Industry Myths vs Reality' or 'Stop doing [Common Mistake]' related to this news. "
                    f"Orient the image_prompt to represent a 'Sharable Infographic'. Describe a split-image layout or side-by-side comparison "
                    f"graphic showing abstract technical structures (e.g., left half showing a chaotic system structure in red glow, "
                    f"right half showing a clean, optimized structure in green/blue glow) on a dark background. Remember: NO legible words or brand text."
                )
            else:
                user_prompt = (
                    f"{positioning}\n\n"
                    f"Format: Hot Take on Recent News regarding {topic} as a Sharable Infographic / Myth vs Reality.\n"
                    f"Current Date context: June 8, 2026.\n"
                    f"Write an opinionated take on a developer trend. Frame it as 'What people think [Niche] is like vs. What it's actually like' or 'Stop doing [Common Mistake]'. "
                    f"Orient the image_prompt to represent a 'Sharable Infographic' by describing a split-image layout or side-by-side comparison "
                    f"graphic showing abstract technical structures (e.g., left half showing a chaotic structure, right half showing an optimized "
                    f"structure) on a dark background. Remember: NO legible words or brand text."
                )
                
        elif day_of_week in (2, 3): # Wednesday / Thursday: Project Update -> Format: High-Value Carousel Step-by-Step "How-To"
            user_prompt = (
                f"{positioning}\n\n"
                f"Format: 'How-To' Step-by-Step Guide / Checklist (e.g., '3 Steps to [Goal]', 'How I fixed [Problem] in 24 hours', or 'A beginner's guide to [Skill]').\n"
                f"Write a tutorial/checklist post discussing a technical feature or lesson learned while building open-source software "
                f"(such as parser implementation, real-time audio streams, or security audits). "
                f"Start the caption with a bold, controversial, or highly intriguing headline hook (under 80 chars) on the first line. "
                f"Deliver the core step-by-step checklist on the middle lines. "
                f"Orient the image_prompt to represent a 'Carousel Hook Slide' by describing a high-contrast, bold graphic layout "
                f"with a single, striking central object (e.g., a glowing metallic key, a floating cyber security shield, a neon folder icon) "
                f"on a dark background with subtle lighting and shadow effects. Remember: NO legible words or brand text."
            )
            
        elif day_of_week in (4, 5): # Friday / Saturday: Tech Explainer / Tip -> Format: High-Contrast Text Graphic / Resource Lists
            user_prompt = (
                f"{positioning}\n\n"
                f"Format: Ultimate Resource List / Tools or Actionable Tip (e.g., '5 Free Tools I Use Every Day', 'The Only Books You Need to Read for [Topic]', or 'Top Websites for [Task]').\n"
                f"Write a resource-list post detailing useful tools, libraries, or actionable tips in your developer workflow. "
                f"Deliver a clean, bulleted list of 3-5 resources/tools in the caption. "
                f"Orient the image_prompt to represent a 'High-Contrast Text Graphic' style by describing a minimal, "
                f"high-contrast digital card layout on a solid black/dark background, featuring abstract glowing neon blocks, "
                f"minimalist line-art code brackets, or clean, glowing UI frame components. Remember: NO legible words or brand text."
            )
            
        else: # Sunday: Behind-the-Scenes -> Format: Relatable Mistakes & Lessons
            user_prompt = (
                f"{positioning}\n\n"
                f"Format: Relatable Mistakes & Lessons (e.g., '3 Mistakes I made when starting [X]', 'What I wish I knew at age 20', or 'Why your [X] isn't working').\n"
                f"Write an authentic post detailing developer lessons, failures, or workspace reflections. "
                f"Use the caption to tell a powerful story showing vulnerability that leaves the reader wanting to follow. "
                f"Orient the image_prompt to represent a 'High-Quality Aesthetic Photo' by describing a cozy, modern, and high-resolution "
                f"photograph of a software developer's desk setup (natural ambient light, warm wooden desk tones, a glowing mechanical keyboard, "
                f"a mug of coffee, blurred background bokeh). Remember: NO legible words or brand text."
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
