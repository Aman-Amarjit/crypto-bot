import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv(override=True)

class Config:
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
