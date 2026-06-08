import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv()

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
        
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        # Default to False if not present or disabled
        self.automation_paused = os.environ.get("AUTOMATION_PAUSED", "0").lower() in ("1", "true", "yes")
        
    def validate(self):
        missing = []
        if not self.threads_user_id:
            missing.append("THREADS_USER_ID")
        if not self.threads_access_token:
            missing.append("THREADS_ACCESS_TOKEN")
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if not self.post_topic:
            missing.append("POST_TOPIC")
        if not self.cloudinary_cloud_name:
            missing.append("CLOUDINARY_CLOUD_NAME")
        if not self.cloudinary_api_key:
            missing.append("CLOUDINARY_API_KEY")
        if not self.cloudinary_api_secret:
            missing.append("CLOUDINARY_API_SECRET")
            
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

config = Config()
