import sys
import traceback
from datetime import datetime

from src.config import config
from src.groq_client import GroqClient
from src.image_generator import ImageGenerator
from src.image_uploader import ImageUploader
from src.threads_client import ThreadsClient

def main():
    print("=" * 60)
    print(f"Threads Auto-Poster Bot Execution Started: {datetime.utcnow().isoformat()} UTC")
    print("=" * 60)
    
    try:
        # 1. Validate configuration
        print("Validating environment configuration...")
        config.validate()
        print("Configuration validated successfully.")
        
        # 2. Generate content (Caption and Image Prompt)
        print(f"Requesting content generation for topic: '{config.post_topic}'...")
        groq = GroqClient()
        content = groq.generate_content(config.post_topic)
        caption = content["caption"]
        image_prompt = content["image_prompt"]
        
        print("\nGenerated Content:")
        print(f"  - Caption: {caption}")
        print(f"  - Image Prompt: {image_prompt}\n")
        
        # 3. Download image from Pollinations.ai
        print("Generating and downloading image from Pollinations.ai...")
        generator = ImageGenerator()
        image_bytes = generator.generate_image(image_prompt)
        
        # 4. Upload image to Cloudinary
        uploader = ImageUploader()
        public_url = uploader.upload_image(image_bytes)
        
        # 5. Publish to Threads
        print("Initiating Threads publication...")
        threads = ThreadsClient()
        post_id = threads.publish_post(public_url, caption)
        
        print("=" * 60)
        print(f"Execution Completed Successfully!")
        print(f"Published Post ID: {post_id}")
        print(f"Timestamp: {datetime.utcnow().isoformat()} UTC")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "!" * 60)
        print("Execution Failed with Error:")
        print(str(e))
        print("!" * 60)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
