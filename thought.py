import os
import sys
import json
import argparse
import traceback
from datetime import datetime, timezone, timedelta

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


def _load_history(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


def check_recent_thought(window_hours: int = 4) -> bool:
    """
    Returns True if a post (either thought or news post) was published within
    the last `window_hours`.  Mirrors the same logic as main.py so both
    pipelines share a consistent safety window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    for path in ("data/thought_history.json", "data/history.json"):
        history = _load_history(path)
        for entry in history:
            ts_str = entry.get("timestamp", "")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    age_mins = int(
                        (datetime.now(timezone.utc) - ts).total_seconds() / 60
                    )
                    print(
                        f"⚠️  A post was published {age_mins} min ago "
                        f"(from {path}). Use --force to override."
                    )
                    return True
            except ValueError:
                continue
    return False


def save_thought_to_history(thought: str, post_id: str):
    history_file = "data/thought_history.json"
    history = _load_history(history_file)

    new_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "thought": thought,
        "post_id": post_id,
    }
    history.append(new_entry)

    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)


def run_thought(force: bool = False) -> str:
    """
    Core daily-thought posting routine.  Importable by other modules.

    Args:
        force:  When True, skips the 4-hour recency check.

    Returns:
        The published Threads post ID as a string.

    Raises:
        SystemExit on configuration errors or if automation is paused in CI.
    """
    print("=" * 60)
    print(
        f"Thread Manager for Cybersecurity Execution Started: "
        f"{datetime.now(timezone.utc).isoformat()} UTC"
    )
    print("=" * 60)

    # Check if automation is paused and we are running inside GitHub Actions
    if config.automation_paused and os.environ.get("GITHUB_ACTIONS") == "true":
        print(
            "🛑 Automation is currently PAUSED via configuration. "
            "Skipping automatic thought post in GitHub Actions."
        )
        print("=" * 60)
        sys.exit(0)

    # 1. Validate configuration
    print("Validating environment configuration...")
    config.validate(
        required_keys=["THREADS_USER_ID", "THREADS_ACCESS_TOKEN", "GROQ_API_KEY"]
    )
    print("Configuration validated successfully.")

    # 2. Rate-limit check (4-hour window)
    if not force and check_recent_thought(window_hours=4):
        print("🛑 Skipping run to avoid spammy posting. Use --force to override.")
        print("=" * 60)
        return ""

    # 3. Generate the daily thought
    print("Generating daily thought via Groq...")
    generator = ThoughtGenerator()
    thought = generator.generate_thought()

    print("\nGenerated Thought:")
    print(f"  {thought}\n")

    # 4. Publish as a standard text post to Threads
    print("Publishing thought as standard post to Threads...")
    threads = ThreadsClient()
    post_id = threads.publish_text_post(thought, is_ghost_post=False)

    # 5. Save to thought history
    print("Saving thought to history log...")
    save_thought_to_history(thought, post_id)

    print("=" * 60)
    print("Daily Thought Posted Successfully!")
    print(f"Post ID: {post_id}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()} UTC")
    print("=" * 60)

    return post_id


def main():
    # Set up logging Tee
    log_file = "data/bot.log"
    sys.stdout = Tee(log_file)
    sys.stderr = sys.stdout

    parser = argparse.ArgumentParser(description="Thread Manager for Cybersecurity")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the 4-hour recency check and post immediately.",
    )
    args = parser.parse_args()

    try:
        run_thought(force=args.force)
    except SystemExit:
        raise
    except Exception as e:
        print("\n" + "!" * 60)
        print("Daily Thought Bot Failed with Error:")
        print(str(e))
        print("!" * 60)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
