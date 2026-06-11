import os
import sys
import time
import random
import traceback
import argparse
from datetime import datetime, timezone

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
    parser.add_argument("--external-url", type=str, help="Reply to an external Threads post URL manually")
    parser.add_argument("--external-text", type=str, help="Override text context for the external post (required with --external-url)")
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
        if args.random_delay and not args.external_url:
            delay_seconds = random.randint(0, 900)  # 0 to 15 minutes
            print(f"[{datetime.now().isoformat()}] Organic check scheduled. Delaying startup for {delay_seconds}s (max 15 mins)...")
            time.sleep(delay_seconds)

        print("=" * 60)
        print(f"Threads Comment-Reply Runner Execution Started: {datetime.now(timezone.utc).isoformat()} UTC")
        print("=" * 60)

        # 4. Trigger auto-reply routine or external reply
        manager = ReplyManager()
        if args.external_url:
            if not args.external_text:
                raise ValueError("--external-text is required when --external-url is specified.")
            
            # Resolve access token
            access_token = os.environ.get("THREADS_ACCESS_TOKEN")
            if not access_token:
                from src.config import config
                access_token = config.threads_access_token
                
            media_id = manager.resolve_threads_url_to_media_id(args.external_url, access_token)
            
            # Pre-flight check
            verification = manager.verify_media_accessible(media_id, access_token)
            author_username = "creator"
            if verification["accessible"]:
                author_username = verification["username"]
                
            print(f"Generating and posting external reply to @{author_username}'s post (ID: {media_id})...")
            
            typing_delay = random.randint(10, 30)
            print(f"[CLI Jitter] Simulating typing... sleeping {typing_delay}s")
            time.sleep(typing_delay)
            
            reply_text = manager.generate_external_post_reply(args.external_text, author_username, media_id)
            thread_id = manager.publish_reply(media_id, reply_text)
            
            # Save status
            manager._save_replied_status(
                comment_id=thread_id,
                status="success",
                post_id=media_id,
                commenter_username=author_username,
                comment_text=args.external_text,
                reply_text=reply_text,
                is_external=1
            )
            print(f"Successfully posted manual external reply! Reply Thread ID: {thread_id}")
        else:
            manager.check_and_reply_to_comments()

        print("=" * 60)
        print(f"Comment-Reply Execution Completed Successfully!")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()} UTC")
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
