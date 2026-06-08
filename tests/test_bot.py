import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Add the workspace directory to path to import src modules
sys.path.insert(0, "/home/aman-amarjit/Desktop/crypto bot")

from src.config import config
from src.groq_client import GroqClient
from src.image_generator import ImageGenerator
from src.image_uploader import ImageUploader
from src.threads_client import ThreadsClient


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig(unittest.TestCase):
    def test_validation_fails_when_missing(self):
        old_user_id = config.threads_user_id
        config.threads_user_id = None

        with self.assertRaises(ValueError):
            config.validate()

        config.threads_user_id = old_user_id


# ---------------------------------------------------------------------------
# NewsFetcher — headline deduplication
# ---------------------------------------------------------------------------

class TestNewsFetcher(unittest.TestCase):
    def test_filter_seen_headlines_removes_known_url(self):
        from src.news_fetcher import NewsFetcher

        headlines = [
            {"title": "Breach at Acme Corp", "link": "https://example.com/story1"},
            {"title": "New CVE disclosed", "link": "https://example.com/story2"},
        ]

        history = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_url": "https://example.com/story1",
                "source_title": "Breach at Acme Corp",
            }
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(history, f)
            tmp_path = f.name

        try:
            filtered = NewsFetcher.filter_seen_headlines(headlines, history_file=tmp_path)
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["link"], "https://example.com/story2")
        finally:
            os.remove(tmp_path)

    def test_filter_seen_headlines_empty_history(self):
        from src.news_fetcher import NewsFetcher

        headlines = [
            {"title": "Story A", "link": "https://example.com/a"},
            {"title": "Story B", "link": "https://example.com/b"},
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump([], f)
            tmp_path = f.name

        try:
            filtered = NewsFetcher.filter_seen_headlines(headlines, history_file=tmp_path)
            self.assertEqual(len(filtered), 2)
        finally:
            os.remove(tmp_path)

    def test_filter_seen_headlines_no_history_file(self):
        from src.news_fetcher import NewsFetcher

        headlines = [{"title": "Story A", "link": "https://example.com/a"}]
        filtered = NewsFetcher.filter_seen_headlines(
            headlines, history_file="/nonexistent/path.json"
        )
        self.assertEqual(len(filtered), 1)


# ---------------------------------------------------------------------------
# GroqClient — guardrail: last-sentence question detection
# ---------------------------------------------------------------------------

class TestGroqClientGuardrail(unittest.TestCase):
    def test_ends_with_question_detects_last_line(self):
        caption_yes = "A breach hit 500k records.\nWas this preventable?"
        caption_no = "A breach hit 500k records.\nPatch CVE-2026-1234 immediately."
        caption_mid_question = "Why does this happen? It's because of weak TLS.\nApply the patch."

        self.assertTrue(GroqClient._ends_with_question(caption_yes))
        self.assertFalse(GroqClient._ends_with_question(caption_no))
        # Mid-post question must NOT trigger the guardrail
        self.assertFalse(GroqClient._ends_with_question(caption_mid_question))

    def test_ends_with_question_empty_string(self):
        self.assertFalse(GroqClient._ends_with_question(""))
        self.assertFalse(GroqClient._ends_with_question("   "))

    @patch("src.groq_client.NewsFetcher.filter_seen_headlines")
    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    def test_generate_content_success(self, mock_post, mock_fetch, mock_filter):
        mock_fetch.return_value = [
            {"title": "Headline 1", "link": "https://example.com/1"}
        ]
        mock_filter.return_value = [
            {"title": "Headline 1", "link": "https://example.com/1"}
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "caption": "Critical flaw in OpenSSL 3.x allows RCE.\nAttackers exploit the heap overflow via crafted TLS handshake.\nCVE-2026-5678, CVSS 9.8. Source: https://example.com/1",
                        "image_prompt": "Abstract network topology diagram"
                    })
                }
            }]
        }
        mock_post.return_value = mock_response

        config.groq_api_key = "test_key"
        client = GroqClient()
        result = client.generate_content("OpenSSL vulnerability")
        self.assertIn("caption", result)
        self.assertIn("image_prompt", result)
        self.assertFalse(GroqClient._ends_with_question(result["caption"]))

    @patch("src.groq_client.NewsFetcher.filter_seen_headlines")
    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    def test_generate_content_retries_on_closing_question(
        self, mock_post, mock_fetch, mock_filter
    ):
        """
        If the LLM returns a caption ending with '?', the client should retry.
        On the second attempt it should return a clean caption.
        """
        mock_fetch.return_value = [{"title": "H1", "link": "https://ex.com/1"}]
        mock_filter.return_value = [{"title": "H1", "link": "https://ex.com/1"}]

        bad_caption = json.dumps({
            "caption": "A flaw was found in Apache.\nDetails are unclear.\nShould you patch now?",
            "image_prompt": "diagram"
        })
        good_caption = json.dumps({
            "caption": "A flaw was found in Apache HTTP Server.\nApply patch CVE-2026-0001 immediately.\nAffects versions <2.4.60.",
            "image_prompt": "diagram"
        })

        bad_resp = MagicMock()
        bad_resp.json.return_value = {
            "choices": [{"message": {"content": bad_caption}}]
        }
        good_resp = MagicMock()
        good_resp.json.return_value = {
            "choices": [{"message": {"content": good_caption}}]
        }

        mock_post.side_effect = [bad_resp, good_resp]

        config.groq_api_key = "test_key"
        client = GroqClient()
        result = client.generate_content("Apache")
        self.assertFalse(GroqClient._ends_with_question(result["caption"]))
        self.assertEqual(mock_post.call_count, 2)

    @patch("src.groq_client.NewsFetcher.filter_seen_headlines")
    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    def test_generate_content_handles_markdown_code_fences(
        self, mock_post, mock_fetch, mock_filter
    ):
        mock_fetch.return_value = [{"title": "H1", "link": "https://ex.com/1"}]
        mock_filter.return_value = [{"title": "H1", "link": "https://ex.com/1"}]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '```json\n{"caption": "Clean!", "image_prompt": "Image"}\n```'}}]
        }
        mock_post.return_value = mock_response

        config.groq_api_key = "test_key"
        client = GroqClient()
        result = client.generate_content("test topic")
        self.assertEqual(result["caption"], "Clean!")

    @patch("src.groq_client.NewsFetcher.filter_seen_headlines")
    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    def test_generate_content_fails_on_malformed_json(
        self, mock_post, mock_fetch, mock_filter
    ):
        mock_fetch.return_value = []
        mock_filter.return_value = []
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not a json"}}]
        }
        mock_post.return_value = mock_response

        config.groq_api_key = "test_key"
        client = GroqClient()
        with self.assertRaises(ValueError):
            client.generate_content("any topic")


# ---------------------------------------------------------------------------
# ThoughtGenerator — guardrail
# ---------------------------------------------------------------------------

class TestThoughtGeneratorGuardrail(unittest.TestCase):
    def test_ends_with_question_static_method(self):
        from src.thought_generator import ThoughtGenerator
        self.assertTrue(ThoughtGenerator._ends_with_question("Interesting insight.\nBut is it secure?"))
        self.assertFalse(ThoughtGenerator._ends_with_question("Interesting insight.\nApply the patch."))
        self.assertFalse(ThoughtGenerator._ends_with_question("Why? Because TLS 1.0 is broken.\nDisable it."))


# ---------------------------------------------------------------------------
# Timing guardrails — main.py check_recent_post
# ---------------------------------------------------------------------------

class TestTimingGuardrail(unittest.TestCase):
    def _write_tmp_history(self, entries: list) -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(entries, f)
        f.close()
        return f.name

    def test_check_recent_post_returns_true_when_within_window(self):
        from main import check_recent_post

        recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        entries = [{"timestamp": recent_ts, "topic": "test", "post_id": "abc"}]

        tmp = self._write_tmp_history(entries)
        try:
            # Monkey-patch the files the function checks
            with patch("main._load_history", side_effect=lambda p: entries if "history" in p else []):
                result = check_recent_post(window_hours=4)
            self.assertTrue(result)
        finally:
            os.remove(tmp)

    def test_check_recent_post_returns_false_when_outside_window(self):
        from main import check_recent_post

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        entries = [{"timestamp": old_ts, "topic": "test", "post_id": "abc"}]

        with patch("main._load_history", return_value=entries):
            result = check_recent_post(window_hours=4)
        self.assertFalse(result)

    def test_check_recent_post_returns_false_when_no_history(self):
        from main import check_recent_post

        with patch("main._load_history", return_value=[]):
            result = check_recent_post(window_hours=4)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# ImageGenerator
# ---------------------------------------------------------------------------

class TestImageGenerator(unittest.TestCase):
    @patch("src.image_generator.requests.get")
    def test_image_generator_encodes_and_downloads(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b"fakeimagebytes"
        mock_response.headers = {"Content-Type": "image/png"}
        mock_get.return_value = mock_response

        old_key = config.pollinations_api_key
        config.pollinations_api_key = None
        try:
            generator = ImageGenerator()
            image_bytes = generator.generate_image("Abstract schematic diagram navy background")
            self.assertEqual(image_bytes, b"fakeimagebytes")
        finally:
            config.pollinations_api_key = old_key

    @patch("src.image_generator.requests.get")
    @patch("src.image_generator.time.sleep")
    def test_image_generator_retries_on_failure(self, mock_sleep, mock_get):
        mock_fail = MagicMock()
        mock_fail.status_code = 500
        mock_fail.raise_for_status.side_effect = Exception("HTTP Error")

        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.content = b"retrybytes"
        mock_success.headers = {"Content-Type": "image/png"}

        mock_get.side_effect = [mock_fail, mock_success]

        generator = ImageGenerator()
        image_bytes = generator.generate_image("Test prompt")

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(image_bytes, b"retrybytes")


# ---------------------------------------------------------------------------
# ImageUploader
# ---------------------------------------------------------------------------

class TestImageUploader(unittest.TestCase):
    @patch("src.image_uploader.cloudinary.uploader.upload")
    def test_upload_image_success(self, mock_upload):
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test/image.jpg"}

        config.cloudinary_cloud_name = "test_cloud"
        config.cloudinary_api_key = "test_key"
        config.cloudinary_api_secret = "test_secret"

        uploader = ImageUploader()
        url = uploader.upload_image(b"fakebytes")
        self.assertEqual(url, "https://res.cloudinary.com/test/image.jpg")


# ---------------------------------------------------------------------------
# ThreadsClient
# ---------------------------------------------------------------------------

class TestThreadsClient(unittest.TestCase):
    @patch("src.threads_client.requests.post")
    @patch("src.threads_client.requests.get")
    @patch("src.threads_client.time.sleep")
    def test_publish_post_success_flow(self, mock_sleep, mock_get, mock_post):
        config.threads_user_id = "user123"
        config.threads_access_token = "token123"

        mock_container_res = MagicMock()
        mock_container_res.json.return_value = {"id": "container_abc"}

        mock_publish_res = MagicMock()
        mock_publish_res.json.return_value = {"id": "post_999"}

        mock_post.side_effect = [mock_container_res, mock_publish_res]

        mock_status_in_progress = MagicMock()
        mock_status_in_progress.json.return_value = {"status": "IN_PROGRESS"}

        mock_status_finished = MagicMock()
        mock_status_finished.json.return_value = {"status": "FINISHED"}

        mock_get.side_effect = [mock_status_in_progress, mock_status_finished]

        client = ThreadsClient()
        post_id = client.publish_post("https://res.cloudinary.com/img.jpg", "Hello #Cybersecurity")

        self.assertEqual(post_id, "post_999")
        self.assertEqual(mock_get.call_count, 2)

    @patch("src.threads_client.requests.post")
    @patch("src.threads_client.requests.get")
    @patch("src.threads_client.time.sleep")
    def test_publish_post_fails_on_status_error(self, mock_sleep, mock_get, mock_post):
        config.threads_user_id = "user123"
        config.threads_access_token = "token123"

        mock_container_res = MagicMock()
        mock_container_res.json.return_value = {"id": "container_abc"}
        mock_post.return_value = mock_container_res

        mock_status_err = MagicMock()
        mock_status_err.json.return_value = {"status": "ERROR", "error_message": "Meta download failed"}
        mock_get.return_value = mock_status_err

        client = ThreadsClient()
        with self.assertRaises(RuntimeError) as context:
            client.publish_post("https://res.cloudinary.com/img.jpg", "Hello")

        self.assertIn("Meta download failed", str(context.exception))


# ---------------------------------------------------------------------------
# ReplyManager
# ---------------------------------------------------------------------------

class TestReplyManager(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        config.gemini_api_key = "test_gemini_key"
        config.threads_user_id = "user123"
        config.threads_access_token = "token123"
        config.automation_paused = False

    def tearDown(self):
        os.close(self.db_fd)
        try:
            os.remove(self.db_path)
        except Exception:
            pass

    def test_database_initialization(self):
        from src.reply_manager import ReplyManager
        import sqlite3
        manager = ReplyManager(self.db_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='replied_comments'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        conn.close()

    def test_reserve_comment(self):
        from src.reply_manager import ReplyManager
        manager = ReplyManager(self.db_path)
        res = manager._reserve_comment("comment_1", "post_1", "user_1", "hello")
        self.assertTrue(res)
        res2 = manager._reserve_comment("comment_1", "post_1", "user_1", "hello")
        self.assertFalse(res2)

    def test_save_replied_status(self):
        from src.reply_manager import ReplyManager
        import sqlite3
        manager = ReplyManager(self.db_path)
        manager._save_replied_status("comment_2", "success", "post_1", "user_2", "hello", "reply_text")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, reply_text FROM replied_comments WHERE comment_id = 'comment_2'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "success")
        self.assertEqual(row[1], "reply_text")
        conn.close()

    def test_daily_ceiling(self):
        from src.reply_manager import ReplyManager
        import sqlite3
        manager = ReplyManager(self.db_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for i in range(19):
            cursor.execute(
                "INSERT INTO replied_comments (comment_id, status) VALUES (?, 'success')",
                (f"c_{i}",)
            )
        conn.commit()
        conn.close()

        self.assertTrue(manager._check_daily_ceiling())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO replied_comments (comment_id, status) VALUES ('c_20', 'success')")
        conn.commit()
        conn.close()

        self.assertFalse(manager._check_daily_ceiling())

    @patch("src.reply_manager.requests.request")
    def test_backoff_retry_on_429(self, mock_request):
        from src.reply_manager import ReplyManager
        mock_429 = MagicMock()
        mock_429.status_code = 429

        mock_200 = MagicMock()
        mock_200.status_code = 200

        mock_request.side_effect = [mock_429, mock_200]

        manager = ReplyManager(self.db_path)
        with patch("src.reply_manager.time.sleep") as mock_sleep:
            resp = manager._request_with_backoff("GET", "https://test.api")
            self.assertEqual(resp.status_code, 200)
            mock_sleep.assert_called_once_with(2)

    @patch("src.reply_manager.requests.request")
    def test_generate_reply_success(self, mock_request):
        from src.reply_manager import ReplyManager
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hello commenter!"}]}}]
        }
        mock_request.return_value = mock_resp

        manager = ReplyManager(self.db_path)
        reply = manager.generate_reply("Post context about CVE-2026-1234", "User comment")
        self.assertEqual(reply, "Hello commenter!")


if __name__ == "__main__":
    unittest.main()
