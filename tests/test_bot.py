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
from src.fact_checker import FactChecker
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
    def test_has_closing_question_detects_last_line(self):
        caption_yes = "A breach hit 500k records.\nWas this preventable?"
        caption_no = "A breach hit 500k records.\nPatch CVE-2026-1234 immediately."
        caption_mid_question = "Why does this happen? It's because of weak TLS.\nApply the patch."

        self.assertTrue(GroqClient._has_closing_question(caption_yes))
        self.assertFalse(GroqClient._has_closing_question(caption_no))
        # Mid-post question must NOT trigger the guardrail
        self.assertFalse(GroqClient._has_closing_question(caption_mid_question))

    def test_has_closing_question_empty_string(self):
        self.assertFalse(GroqClient._has_closing_question(""))
        self.assertFalse(GroqClient._has_closing_question("   "))

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
                        "caption": "Critical flaw in OpenSSL 3.x allows RCE.\nAttackers exploit the heap overflow via crafted TLS handshake.\nCVE-2026-5678, CVSS 9.8. Was this preventable?\nSource: https://example.com/1",
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
        self.assertTrue(GroqClient._has_closing_question(result["caption"]))

    @patch("src.groq_client.NewsFetcher.filter_seen_headlines")
    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    @patch("src.fact_checker.FactChecker.check", return_value={"passed": True, "issues": []})
    def test_generate_content_retries_on_missing_closing_question(
        self, _mock_fc_check, mock_post, mock_fetch, mock_filter
    ):
        """
        If the LLM returns a caption missing a closing '?', the client should retry.
        On the second attempt it should return a caption with a closing question.
        """
        mock_fetch.return_value = [{"title": "H1", "link": "https://ex.com/1"}]
        mock_filter.return_value = [{"title": "H1", "link": "https://ex.com/1"}]

        bad_caption = json.dumps({
            "caption": "A flaw was found in Apache HTTP Server.\nApply patch CVE-2026-0001 immediately.\nAffects versions <2.4.60.",
            "image_prompt": "diagram"
        })
        good_caption = json.dumps({
            "caption": "A flaw was found in Apache.\nDetails are unclear.\nShould you patch now?",
            "image_prompt": "diagram"
        })
        bad_resp = MagicMock()
        bad_resp.json.return_value = {"choices": [{"message": {"content": bad_caption}}]}
        good_resp = MagicMock()
        good_resp.json.return_value = {"choices": [{"message": {"content": good_caption}}]}
        mock_post.side_effect = [bad_resp, good_resp]

        config.groq_api_key = "test_key"
        client = GroqClient()
        result = client.generate_content("Apache")
        self.assertTrue(GroqClient._has_closing_question(result["caption"]))
        # 2 LLM calls: 1 bad (no question) + 1 good
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
            "choices": [{"message": {"content": '```json\n{"caption": "Clean? Was this preventable?", "image_prompt": "Image"}\n```'}}]
        }
        mock_post.return_value = mock_response

        config.groq_api_key = "test_key"
        client = GroqClient()
        result = client.generate_content("test topic")
        self.assertEqual(result["caption"], "Clean? Was this preventable?")

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

    @patch("src.thought_generator.requests.post")
    def test_generate_thought_success(self, mock_post):
        from src.thought_generator import ThoughtGenerator
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "thought": "LockBit uses double extortion.\nThey exfiltrate data and encrypt systems.\nCVE-2026-1234. How are you preventing double extortion?"
                    })
                }
            }]
        }
        mock_post.return_value = mock_response

        config.groq_api_key = "test_key"
        generator = ThoughtGenerator()
        thought = generator.generate_thought()
        self.assertEqual(thought, "LockBit uses double extortion.\nThey exfiltrate data and encrypt systems.\nCVE-2026-1234. How are you preventing double extortion?")

    @patch("src.thought_generator.requests.post")
    def test_generate_thought_retries_on_missing_closing_question(self, mock_post):
        from src.thought_generator import ThoughtGenerator
        
        bad_thought = json.dumps({
            "thought": "LockBit uses double extortion.\nThey exfiltrate data and encrypt systems.\nCVE-2026-1234."
        })
        good_thought = json.dumps({
            "thought": "LockBit uses double extortion.\nThey exfiltrate data and encrypt systems.\nCVE-2026-1234. How are you protecting systems?"
        })
        
        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"choices": [{"message": {"content": bad_thought}}]}
        
        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.json.return_value = {"choices": [{"message": {"content": good_thought}}]}
        
        mock_post.side_effect = [bad_resp, good_resp]

        config.groq_api_key = "test_key"
        generator = ThoughtGenerator()
        thought = generator.generate_thought()
        
        self.assertEqual(thought, "LockBit uses double extortion.\nThey exfiltrate data and encrypt systems.\nCVE-2026-1234. How are you protecting systems?")
        # Should have called LLM twice
        self.assertEqual(mock_post.call_count, 2)


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

    @patch("src.reply_manager.random.random")
    @patch("src.reply_manager.requests.request")
    def test_generate_reply_success(self, mock_request, mock_random):
        from src.reply_manager import ReplyManager
        mock_resp_no_q = MagicMock()
        mock_resp_no_q.status_code = 200
        mock_resp_no_q.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hello commenter!"}]}}]
        }
        
        mock_resp_with_q = MagicMock()
        mock_resp_with_q.status_code = 200
        mock_resp_with_q.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hello commenter! How is it going?"}]}}]
        }
        
        # Test case 1: reply without question mark, random returns < 0.75 so end_with_q = True, fallback is appended
        mock_random.return_value = 0.1
        mock_request.return_value = mock_resp_no_q
        manager = ReplyManager(self.db_path)
        reply = manager.generate_reply("Post context about CVE-2026-1234", "User comment")
        self.assertEqual(reply, "Hello commenter! What are your thoughts on this?")
        
        # Test case 2: reply with question mark, end_with_q = True, no fallback appended because it already ends with "?"
        mock_request.return_value = mock_resp_with_q
        reply_q = manager.generate_reply("Post context about CVE-2026-1234", "User comment")
        self.assertEqual(reply_q, "Hello commenter! How is it going?")

        # Test case 3: reply with question mark, but random returns >= 0.75 so end_with_q = False, question mark is stripped
        mock_random.return_value = 0.8
        reply_no_q = manager.generate_reply("Post context about CVE-2026-1234", "User comment")
        self.assertEqual(reply_no_q, "Hello commenter! How is it going.")


# ---------------------------------------------------------------------------
# FactChecker
# ---------------------------------------------------------------------------

class TestFactChecker(unittest.TestCase):
    HEADLINES = [
        {"title": "Acme Corp suffers 200k record breach via GTI vendor",
         "link": "https://example.com/acme-breach"}
    ]

    def _make_mock_response(self, passed: bool, issues: list) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({"passed": passed, "issues": issues})
                }
            }]
        }
        return mock_resp

    @patch("src.fact_checker.requests.post")
    def test_passes_accurate_caption(self, mock_post):
        mock_post.return_value = self._make_mock_response(
            passed=True, issues=[]
        )
        fc = FactChecker()
        config.groq_api_key = "test_key"
        result = fc.check(
            caption="GTI vendor breach exposed 200k Acme Corp records. Patch applied.",
            headlines=self.HEADLINES,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["issues"], [])

    @patch("src.fact_checker.requests.post")
    def test_fails_on_wrong_attribution(self, mock_post):
        mock_post.return_value = self._make_mock_response(
            passed=False,
            issues=["Caption says 'Acme Corp systems were breached' but headline "
                    "attributes the breach to GTI vendor, not Acme's own systems."]
        )
        fc = FactChecker()
        config.groq_api_key = "test_key"
        result = fc.check(
            caption="Acme Corp systems were directly breached, exposing 1 million records.",
            headlines=self.HEADLINES,
        )
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["issues"]), 1)
        self.assertIn("GTI vendor", result["issues"][0])

    @patch("src.fact_checker.requests.post")
    def test_fails_on_fabricated_stat(self, mock_post):
        mock_post.return_value = self._make_mock_response(
            passed=False,
            issues=["Caption states '70% of EU businesses affected' — "
                    "this figure does not appear in any source headline."]
        )
        fc = FactChecker()
        config.groq_api_key = "test_key"
        result = fc.check(
            caption="Breach hit 70% of EU businesses. CVE-2026-9999.",
            headlines=self.HEADLINES,
        )
        self.assertFalse(result["passed"])
        self.assertIn("70%", result["issues"][0])

    @patch("src.fact_checker.requests.post")
    def test_soft_pass_on_api_error(self, mock_post):
        """A fact-checker crash must never block publication."""
        mock_post.side_effect = Exception("Network error")
        fc = FactChecker()
        config.groq_api_key = "test_key"
        result = fc.check(
            caption="Some caption.",
            headlines=self.HEADLINES,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["issues"], [])

    @patch("src.fact_checker.requests.post")
    def test_soft_pass_on_malformed_response(self, mock_post):
        """Malformed fact-checker JSON must soft-pass, not crash."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"unexpected_key": true}'}}]
        }
        mock_post.return_value = mock_resp
        fc = FactChecker()
        config.groq_api_key = "test_key"
        result = fc.check(caption="Some caption.", headlines=self.HEADLINES)
        self.assertTrue(result["passed"])

    @patch("src.fact_checker.requests.post")
    def test_shallow_check_used_when_no_headlines(self, mock_post):
        """When headlines list is empty, falls back to internal consistency check."""
        mock_post.return_value = self._make_mock_response(
            passed=False,
            issues=["Suspiciously precise stat: '73% of companies' not traceable."]
        )
        fc = FactChecker()
        config.groq_api_key = "test_key"
        result = fc.check(caption="73% of companies hit. CVE-2026-0001.", headlines=[])
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["issues"]), 1)

    @patch("src.groq_client.NewsFetcher.filter_seen_headlines")
    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    @patch("src.fact_checker.FactChecker.check")
    def test_groq_client_retries_with_fact_check_feedback(
        self, mock_fc_check, mock_groq_post, mock_fetch, mock_filter
    ):
        """
        When the first generation fails fact-checking, the second attempt
        should include the correction feedback in the prompt and pass.
        """
        mock_fetch.return_value = self.HEADLINES
        mock_filter.return_value = self.HEADLINES

        # First LLM response: fabricated stat
        bad = MagicMock()
        bad.json.return_value = {"choices": [{"message": {"content": json.dumps({
            "caption": "Acme Corp breach hit 70% EU businesses. CVE-2026-9999. Was this preventable?",
            "image_prompt": "diagram"
        })}}]}

        # Second LLM response: corrected
        good = MagicMock()
        good.json.return_value = {"choices": [{"message": {"content": json.dumps({
            "caption": "GTI vendor breach exposed 200k Acme Corp records. Patch now. How are you securing dependencies?",
            "image_prompt": "diagram"
        })}}]}

        mock_groq_post.side_effect = [bad, good]

        # Fact-checker: first call fails, second passes
        mock_fc_check.side_effect = [
            {"passed": False, "issues": ["'70% EU businesses' not in source headline."]},
            {"passed": True, "issues": []},
        ]

        config.groq_api_key = "test_key"
        client = GroqClient()
        result = client.generate_content("data breach")

        # Should have retried once and returned the corrected caption
        self.assertEqual(mock_groq_post.call_count, 2)
        self.assertEqual(mock_fc_check.call_count, 2)
        self.assertIn("200k", result["caption"])



# ---------------------------------------------------------------------------
# QuestionGenerator & Question Timing Guardrails
# ---------------------------------------------------------------------------

class TestQuestionGenerator(unittest.TestCase):
    @patch("src.question_generator.requests.post")
    def test_generate_question_success(self, mock_post):
        from src.question_generator import QuestionGenerator
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "How do you handle dependency validation?"
                }
            }]
        }
        mock_post.return_value = mock_response

        config.groq_api_key = "test_key"
        generator = QuestionGenerator()
        question = generator.generate_question()
        self.assertEqual(question, "How do you handle dependency validation?")

class TestQuestionTiming(unittest.TestCase):
    def test_check_recent_question_returns_true_when_within_window(self):
        from question import check_recent_question
        
        recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        entries = [{"timestamp": recent_ts, "question": "Test", "post_id": "abc"}]

        with patch("question._load_history", return_value=entries):
            result = check_recent_question(window_hours=4)
        self.assertTrue(result)

    def test_check_recent_question_returns_false_when_outside_window(self):
        from question import check_recent_question
        
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        entries = [{"timestamp": old_ts, "question": "Test", "post_id": "abc"}]

        with patch("question._load_history", return_value=entries):
            result = check_recent_question(window_hours=4)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# External Replies
# ---------------------------------------------------------------------------

class TestExternalReplies(unittest.TestCase):
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

    def test_extract_shortcode_from_url(self):
        from src.reply_manager import ReplyManager
        shortcode1 = ReplyManager.extract_shortcode_from_url("https://www.threads.net/@user/post/Cw123_abc-")
        self.assertEqual(shortcode1, "Cw123_abc-")

        shortcode2 = ReplyManager.extract_shortcode_from_url("https://www.threads.net/t/Cw123_abc-")
        self.assertEqual(shortcode2, "Cw123_abc-")

        with self.assertRaises(ValueError):
            ReplyManager.extract_shortcode_from_url("https://example.com/not-threads")

    def test_resolve_threads_url_to_media_id_cache_hit(self):
        from src.reply_manager import ReplyManager
        manager = ReplyManager(self.db_path)
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO resolved_posts_cache (url, media_id, cached_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            ("https://www.threads.net/t/123", "99999")
        )
        conn.commit()
        conn.close()

        media_id = manager.resolve_threads_url_to_media_id("https://www.threads.net/t/123", "token123")
        self.assertEqual(media_id, "99999")

    @patch("src.reply_manager.requests.get")
    def test_resolve_threads_url_to_media_id_oembed_success(self, mock_get):
        from src.reply_manager import ReplyManager
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"media_id": "88888"}'
        mock_resp.json.return_value = {"html": '<blockquote class="instagram-media" data-instgrm-payload-id="88888"></blockquote>'}
        mock_get.return_value = mock_resp

        manager = ReplyManager(self.db_path)
        media_id = manager.resolve_threads_url_to_media_id("https://www.threads.net/t/xyz", "token123")
        self.assertEqual(media_id, "88888")

        # Verify cached
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT media_id FROM resolved_posts_cache WHERE url = ?", ("https://www.threads.net/t/xyz",))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "88888")
        conn.close()

    @patch("src.reply_manager.requests.get")
    def test_resolve_threads_url_to_media_id_fallback_to_math(self, mock_get):
        from src.reply_manager import ReplyManager
        mock_get.side_effect = Exception("API Timeout")

        manager = ReplyManager(self.db_path)
        # shortcode 'B' -> index 1
        media_id = manager.resolve_threads_url_to_media_id("https://www.threads.net/t/B", "token123")
        self.assertEqual(media_id, "1")

    @patch("src.reply_manager.requests.get")
    def test_verify_media_accessible_success(self, mock_get):
        from src.reply_manager import ReplyManager
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "123", "username": "aman", "text": "Hello world"}
        mock_get.return_value = mock_resp

        manager = ReplyManager(self.db_path)
        res = manager.verify_media_accessible("123", "token123")
        self.assertTrue(res["accessible"])
        self.assertEqual(res["username"], "aman")
        self.assertEqual(res["text"], "Hello world")

    @patch("src.reply_manager.requests.get")
    def test_verify_media_accessible_failed(self, mock_get):
        from src.reply_manager import ReplyManager
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"error": {"message": "Private media"}}
        mock_get.return_value = mock_resp

        manager = ReplyManager(self.db_path)
        res = manager.verify_media_accessible("123", "token123")
        self.assertFalse(res["accessible"])
        self.assertIn("Private media", res["error"])

    @patch("src.reply_manager.random.random")
    @patch("src.reply_manager.requests.request")
    def test_generate_external_post_reply(self, mock_request, mock_random):
        from src.reply_manager import ReplyManager
        mock_resp_no_q = MagicMock()
        mock_resp_no_q.status_code = 200
        mock_resp_no_q.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Very clean explanation!"}]}}]
        }
        mock_request.return_value = mock_resp_no_q

        # Case 1: end_with_q = True, fallback is appended
        mock_random.return_value = 0.1
        manager = ReplyManager(self.db_path)
        reply = manager.generate_external_post_reply("Secure your code", "someone", "123")
        self.assertEqual(reply, "Very clean explanation! What do you think?")

        # Case 2: end_with_q = False, trailing "?" is stripped
        mock_random.return_value = 0.8
        mock_resp_with_q = MagicMock()
        mock_resp_with_q.status_code = 200
        mock_resp_with_q.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Is this secure?"}]}}]
        }
        mock_request.return_value = mock_resp_with_q
        reply2 = manager.generate_external_post_reply("Secure your code", "someone", "123")
        self.assertEqual(reply2, "Is this secure.")

    def test_external_daily_ceiling(self):
        from src.reply_manager import ReplyManager
        import sqlite3
        manager = ReplyManager(self.db_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for i in range(9):
            cursor.execute(
                "INSERT INTO replied_comments (comment_id, status, is_external) VALUES (?, 'success', 1)",
                (f"ext_{i}",)
            )
        conn.commit()
        conn.close()

        self.assertTrue(manager._check_external_daily_ceiling())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO replied_comments (comment_id, status, is_external) VALUES ('ext_9', 'success', 1)")
        conn.commit()
        conn.close()

        self.assertFalse(manager._check_external_daily_ceiling())


if __name__ == "__main__":
    unittest.main()
