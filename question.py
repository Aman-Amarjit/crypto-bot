import os
import sys
import json
import argparse
import traceback
from datetime import datetime, timezone, timedelta

from src.config import config
from src.question_generator import QuestionGenerator
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


def check_recent_question(window_hours: int = 4) -> bool:
    """
    Returns True if a question was published within the last `window_hours`.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    history = _load_history("data/question_history.json")
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
                    f"⚠️  A question was published {age_mins} min ago. Use --force to override."
                )
                return True
        except ValueError:
            continue
    return False


def save_question_to_history(question: str, post_id: str):
    history_file = "data/question_history.json"
    history = _load_history(history_file)

    new_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "post_id": post_id,
    }
    history.append(new_entry)

    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)


def run_question(force: bool = False) -> str:
    """
    Core daily-question posting routine.
    """
    print("=" * 60)
    print(
        f"Threads Daily Question Bot Execution Started: "
        f"{datetime.now(timezone.utc).isoformat()} UTC"
    )
    print("=" * 60)

    # Check if automation is paused and we are running inside GitHub Actions
    if config.automation_paused and os.environ.get("GITHUB_ACTIONS") == "true":
        print(
            "🛑 Automation is currently PAUSED via configuration. "
            "Skipping automatic question post in GitHub Actions."
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
    if not force and check_recent_question(window_hours=4):
        print("🛑 Skipping run to avoid spammy posting. Use --force to override.")
        print("=" * 60)
        return ""

    # 3. Generate the daily question
    print("Generating daily question via Groq...")
    generator = QuestionGenerator()
    question = generator.generate_question()

    print("\nGenerated Question:")
    print(f"  {question}\n")

    # 4. Publish as a standard text post to Threads
    print("Publishing question post to Threads...")
    threads = ThreadsClient()
    post_id = threads.publish_text_post(question, is_ghost_post=False)

    # 5. Save to question history
    print("Saving question to history log...")
    save_question_to_history(question, post_id)

    print("=" * 60)
    print("Daily Question Posted Successfully!")
    print(f"Post ID: {post_id}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()} UTC")
    print("=" * 60)

    return post_id


def main():
    # Set up logging Tee
    log_file = "data/bot.log"
    sys.stdout = Tee(log_file)
    sys.stderr = sys.stdout

    parser = argparse.ArgumentParser(description="Threads Daily Question Bot")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the 4-hour recency check and post immediately.",
    )
    args = parser.parse_args()

    try:
        run_question(force=args.force)
    except SystemExit:
        raise
    except Exception as e:
        print("\n" + "!" * 60)
        print("Daily Question Bot Failed with Error:")
        print(str(e))
        print("!" * 60)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
