import os
import sys
import json
import traceback
from datetime import datetime

from src.config import config
from src.groq_client import GroqClient
from src.image_generator import ImageGenerator
from src.image_uploader import ImageUploader
from src.threads_client import ThreadsClient
from src.topic_manager import TopicManager

class Tee:
    def __init__(self, filename):
        self.terminal = sys.stdout
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.log = open(filename, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

def save_to_history(topic, caption, image_prompt, image_url, post_id):
    history_file = "data/history.json"
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except Exception:
            history = []
            
    new_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "topic": topic,
        "caption": caption,
        "image_prompt": image_prompt,
        "image_url": image_url,
        "post_id": post_id
    }
    history.append(new_entry)
    
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)

def main():
    # Set up logging Tee
    log_file = "data/bot.log"
    sys.stdout = Tee(log_file)
    sys.stderr = sys.stdout

    print("=" * 60)
    print(f"Threads Auto-Poster Bot Execution Started: {datetime.utcnow().isoformat()} UTC")
    print("=" * 60)
    
    try:
        # 1. Validate configuration
        print("Validating environment configuration...")
        config.validate()
        print("Configuration validated successfully.")
        
        # 2. Determine topic (CLI arg override OR sequential rotation)
        if len(sys.argv) > 1 and sys.argv[1].strip():
            topic = sys.argv[1].strip()
            print(f"Using manual topic override: '{topic}'")
        else:
            topic_manager = TopicManager()
            topic = topic_manager.get_next_topic()
            print(f"Using rotating topic: '{topic}'")
        
        # 3. Generate content (Caption and Image Prompt)
        print(f"Requesting content generation for topic: '{topic}'...")
        groq = GroqClient()
        content = groq.generate_content(topic)
        caption = content["caption"]
        image_prompt = content["image_prompt"]
        
        print("\nGenerated Content:")
        print(f"  - Caption: {caption}")
        print(f"  - Image Prompt: {image_prompt}\n")
        
        # 4. Download image from Pollinations.ai
        print("Generating and downloading image from Pollinations.ai...")
        generator = ImageGenerator()
        image_bytes = generator.generate_image(image_prompt)
        
        # 5. Upload image to Cloudinary
        uploader = ImageUploader()
        public_url = uploader.upload_image(image_bytes)
        
        # 6. Publish to Threads
        print("Initiating Threads publication...")
        threads = ThreadsClient()
        post_id = threads.publish_post(public_url, caption)
        
        # 7. Save to execution history
        print("Saving execution metadata to history log...")
        save_to_history(topic, caption, image_prompt, public_url, post_id)
        
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
