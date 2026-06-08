import os
import sys
import time
import random
import traceback
import argparse
from datetime import datetime

from src.reply_manager import ReplyManager

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

def main():
    parser = argparse.ArgumentParser(description="Threads Comments Auto-Reply Runner")
    parser.add_argument("--random-delay", action="store_true", help="Introduce a random startup delay (0-15 minutes)")
    args = parser.parse_args()

    # 1. Setup logging Tee
    log_file = "data/bot.log"
    sys.stdout = Tee(log_file)
    sys.stderr = sys.stdout

    # 2. Lockfile Check
    lock_file = "data/reply.lock"
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    # Check if lock exists and is stale (older than 20 minutes)
    if os.path.exists(lock_file):
        stale_threshold = 20 * 60  # 20 minutes
        try:
            mtime = os.path.getmtime(lock_file)
            if time.time() - mtime > stale_threshold:
                print(f"[{datetime.now().isoformat()}] Removing stale lockfile from previous run.")
                os.remove(lock_file)
        except Exception as e:
            print(f"Warning: Could not check or remove lockfile: {e}")

    # Create lock file exclusively
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
    except FileExistsError:
        print(f"[{datetime.now().isoformat()}] Another comment reply job is already running. Exiting.")
        sys.exit(0)

    try:
        # 3. Optional Startup Delay (for natural organic check schedules)
        if args.random_delay:
            delay_seconds = random.randint(0, 900)  # 0 to 15 minutes
            print(f"[{datetime.now().isoformat()}] Organic check scheduled. Delaying startup for {delay_seconds}s (max 15 mins)...")
            time.sleep(delay_seconds)

        print("=" * 60)
        print(f"Threads Comment-Reply Runner Execution Started: {datetime.utcnow().isoformat()} UTC")
        print("=" * 60)

        # 4. Trigger auto-reply routine
        manager = ReplyManager()
        manager.check_and_reply_to_comments()

        print("=" * 60)
        print(f"Comment-Reply Execution Completed Successfully!")
        print(f"Timestamp: {datetime.utcnow().isoformat()} UTC")
        print("=" * 60)

    except Exception as e:
        print("\n" + "!" * 60)
        print("Comment-Reply Runner Failed with Error:")
        print(str(e))
        print("!" * 60)
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 5. Clean up lock file
        try:
            os.remove(lock_file)
        except Exception:
            pass

if __name__ == "__main__":
    main()
