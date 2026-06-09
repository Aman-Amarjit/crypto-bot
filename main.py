import os
import sys
import json
import argparse
import traceback
from datetime import datetime, timezone, timedelta

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


def _load_history(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


def check_recent_post(window_hours: int = 2) -> bool:
    """
    Returns True if a post (either news post or thought) was published within
    the last `window_hours`.  Checks both data/history.json and
    data/thought_history.json.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    for path in ("data/history.json", "data/thought_history.json"):
        history = _load_history(path)
        for entry in history:
            ts_str = entry.get("timestamp", "")
            if not ts_str:
                continue
            try:
                # Timestamps are stored as naive UTC ISO strings
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    age_mins = int((datetime.now(timezone.utc) - ts).total_seconds() / 60)
                    print(
                        f"⚠️  A post was published {age_mins} min ago "
                        f"(from {path}). Use --force to override."
                    )
                    return True
            except ValueError:
                continue
    return False


def save_to_history(
    topic: str,
    caption: str,
    image_prompt: str,
    image_url: str,
    post_id: str,
    source_url: str = "",
    source_title: str = "",
):
    history_file = "data/history.json"
    history = _load_history(history_file)

    new_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "caption": caption,
        "image_prompt": image_prompt,
        "image_url": image_url,
        "post_id": post_id,
        "source_url": source_url,
        "source_title": source_title,
    }
    history.append(new_entry)

    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)


def run_post(topic: str = None, force: bool = False) -> str:
    """
    Core posting routine.  Importable by other modules (e.g. app.py can call
    this directly rather than spawning a subprocess).

    Args:
        topic:  Optional topic override.  When None, the TopicManager rotates.
        force:  When True, skips the 4-hour recency check.

    Returns:
        The published Threads post ID as a string.

    Raises:
        SystemExit on configuration errors or if automation is paused in CI.
    """
    print("=" * 60)
    print(
        f"Threads Auto-Poster Bot Execution Started: "
        f"{datetime.now(timezone.utc).isoformat()} UTC"
    )
    print("=" * 60)

    # Check if automation is paused and we are running inside GitHub Actions
    if config.automation_paused and os.environ.get("GITHUB_ACTIONS") == "true":
        print(
            "🛑 Automation is currently PAUSED via configuration. "
            "Skipping automatic daily post in GitHub Actions."
        )
        print("=" * 60)
        sys.exit(0)

    # 1. Validate configuration
    print("Validating environment configuration...")
    config.validate()
    print("Configuration validated successfully.")

    # 2. Rate-limit check (2-hour window - TEMPORARILY DISABLED FOR TESTING)
    if False:  # not force and check_recent_post(window_hours=2):
        print("🛑 Skipping run to avoid spammy posting. Use --force to override.")
        print("=" * 60)
        return ""

    # 3. Determine topic (argument override OR sequential rotation)
    if topic and topic.strip():
        topic = topic.strip()
        print(f"Using manual topic override: '{topic}'")
    else:
        topic_manager = TopicManager()
        topic = topic_manager.get_next_topic()
        print(f"Using rotating topic: '{topic}'")

    # 4. Generate content (Caption and Image Prompt)
    print(f"Requesting content generation for topic: '{topic}'...")
    groq = GroqClient()
    content = groq.generate_content(topic)
    caption = content["caption"]
    image_prompt = content["image_prompt"]
    # Extract source URL/title if the LLM embedded them in the structured content
    source_url = content.get("source_url", "")
    source_title = content.get("source_title", "")

    print("\nGenerated Content:")
    print(f"  - Caption: {caption}")
    print(f"  - Image Prompt: {image_prompt}\n")

    # 5. Download image from Pollinations.ai
    print("Generating and downloading image from Pollinations.ai...")
    generator = ImageGenerator()
    image_bytes = generator.generate_image(image_prompt)

    # 6. Upload image to Cloudinary
    uploader = ImageUploader()
    public_url = uploader.upload_image(image_bytes)

    # 7. Publish to Threads
    print("Initiating Threads publication...")
    threads = ThreadsClient()
    post_id = threads.publish_post(public_url, caption)

    # 8. Save to execution history (including source URL for deduplication)
    print("Saving execution metadata to history log...")
    save_to_history(
        topic=topic,
        caption=caption,
        image_prompt=image_prompt,
        image_url=public_url,
        post_id=post_id,
        source_url=source_url,
        source_title=source_title,
    )

    print("=" * 60)
    print("Execution Completed Successfully!")
    print(f"Published Post ID: {post_id}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()} UTC")
    print("=" * 60)

    return post_id


def main():
    # Set up logging Tee
    log_file = "data/bot.log"
    sys.stdout = Tee(log_file)
    sys.stderr = sys.stdout

    parser = argparse.ArgumentParser(description="Threads Auto-Poster Bot")
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Optional topic override. If omitted, the topic rotates automatically.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the 4-hour recency check and post immediately.",
    )
    args = parser.parse_args()

    try:
        run_post(topic=args.topic, force=args.force)
    except SystemExit:
        raise
    except Exception as e:
        print("\n" + "!" * 60)
        print("Execution Failed with Error:")
        print(str(e))
        print("!" * 60)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
