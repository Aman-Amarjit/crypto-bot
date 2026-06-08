import os
import sys
import json
import traceback
from datetime import datetime

from src.config import config
from src.thought_generator import ThoughtGenerator
from src.threads_client import ThreadsClient


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


def save_thought_to_history(thought: str, post_id: str):
    history_file = "data/thought_history.json"
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception:
            history = []

    new_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "thought": thought,
        "post_id": post_id,
    }
    history.append(new_entry)

    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)


def main():
    # Set up logging Tee
    log_file = "data/bot.log"
    sys.stdout = Tee(log_file)
    sys.stderr = sys.stdout

    print("=" * 60)
    print(f"Threads Daily Thought Bot Execution Started: {datetime.utcnow().isoformat()} UTC")
    print("=" * 60)

    try:
        # 1. Validate configuration
        print("Validating environment configuration...")
        config.validate()
        print("Configuration validated successfully.")

        # 2. Generate the daily thought
        print("Generating daily thought via Groq...")
        generator = ThoughtGenerator()
        thought = generator.generate_thought()

        print("\nGenerated Thought:")
        print(f"  {thought}\n")

        # 3. Publish as a text-only post to Threads
        print("Publishing thought to Threads...")
        threads = ThreadsClient()
        post_id = threads.publish_text_post(thought)

        # 4. Save to thought history
        print("Saving thought to history log...")
        save_thought_to_history(thought, post_id)

        print("=" * 60)
        print("Daily Thought Posted Successfully!")
        print(f"Post ID: {post_id}")
        print(f"Timestamp: {datetime.utcnow().isoformat()} UTC")
        print("=" * 60)

    except Exception as e:
        print("\n" + "!" * 60)
        print("Daily Thought Bot Failed with Error:")
        print(str(e))
        print("!" * 60)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
