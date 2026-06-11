import os
import json
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv(override=True)

class Config:
    @staticmethod
    def sanitize_prompt_field(val: str, max_len: int) -> str:
        if not val:
            return ""
        # Strip newlines and carriage returns to mitigate prompt injection
        clean = val.replace("\n", " ").replace("\r", " ").strip()
        return clean[:max_len]

    def __init__(self):
        self.threads_user_id = os.environ.get("THREADS_USER_ID")
        self.threads_access_token = os.environ.get("THREADS_ACCESS_TOKEN")
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        self.post_topic = os.environ.get("POST_TOPIC")
        
        self.cloudinary_cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
        self.cloudinary_api_key = os.environ.get("CLOUDINARY_API_KEY")
        self.cloudinary_api_secret = os.environ.get("CLOUDINARY_API_SECRET")
        
        self.pollinations_api_key = os.environ.get("POLLINATIONS_API_KEY")
        self.hf_api_token = os.environ.get("HF_API_TOKEN")
        self.cloudflare_api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
        self.cloudflare_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        # Default to False if not present or disabled
        self.automation_paused = os.environ.get("AUTOMATION_PAUSED", "0").lower() in ("1", "true", "yes")

        # Load persona configuration from data/persona.json sidecar if it exists
        persona_data = {}
        persona_path = "data/persona.json"
        if os.path.exists(persona_path):
            try:
                with open(persona_path, "r", encoding="utf-8") as f:
                    persona_data = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load persona.json: {e}")

        # Set values with fallback cascade: persona.json -> environment -> default
        raw_name = persona_data.get("PERSONA_NAME") or os.environ.get("PERSONA_NAME") or "Aman"
        raw_bio = persona_data.get("PERSONA_BIO") or os.environ.get("PERSONA_BIO") or "independent cybersecurity researcher and software engineer"
        raw_tone = persona_data.get("PERSONA_TONE") or os.environ.get("PERSONA_TONE") or "conversational, direct, technical, humble, writing in first person ('I', 'my')"

        self.persona_name = self.sanitize_prompt_field(raw_name, 100)
        self.persona_bio = self.sanitize_prompt_field(raw_bio, 250)
        self.persona_tone = self.sanitize_prompt_field(raw_tone, 250)
        
    def validate(self, required_keys=None):
        if required_keys is None:
            required_keys = [
                "THREADS_USER_ID",
                "THREADS_ACCESS_TOKEN",
                "GROQ_API_KEY",
                "POST_TOPIC",
                "CLOUDINARY_CLOUD_NAME",
                "CLOUDINARY_API_KEY",
                "CLOUDINARY_API_SECRET"
            ]
        missing = []
        for key in required_keys:
            val = getattr(self, key.lower(), None)
            if not val:
                missing.append(key)
            
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

config = Config()
