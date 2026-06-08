import unittest
from unittest.mock import patch, MagicMock
import json
import sys

# Add the workspace directory to path to import src modules
sys.path.insert(0, "/home/aman-amarjit/Desktop/crypto bot")

from src.config import config
from src.groq_client import GroqClient
from src.image_generator import ImageGenerator
from src.image_uploader import ImageUploader
from src.threads_client import ThreadsClient

class TestConfig(unittest.TestCase):
    def test_validation_fails_when_missing(self):
        # Temporarily clear required env vars
        old_user_id = config.threads_user_id
        config.threads_user_id = None
        
        with self.assertRaises(ValueError):
            config.validate()
            
        config.threads_user_id = old_user_id

class TestGroqClient(unittest.TestCase):
    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    def test_generate_content_success(self, mock_post, mock_fetch):
        mock_fetch.return_value = ["Headlines 1", "Headlines 2"]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"caption": "Cool caption! #crypto", "image_prompt": "A cool image prompt"}'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        # Inject API key to satisfy config validation in client
        config.groq_api_key = "test_key"
        
        client = GroqClient()
        result = client.generate_content("Bitcoin")
        self.assertEqual(result["caption"], "Cool caption! #crypto")
        self.assertEqual(result["image_prompt"], "A cool image prompt")

    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    def test_generate_content_handles_markdown_code_fences(self, mock_post, mock_fetch):
        mock_fetch.return_value = ["Headlines 1"]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '```json\n{"caption": "Cool!", "image_prompt": "Image"}\n```'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        config.groq_api_key = "test_key"
        client = GroqClient()
        result = client.generate_content("Bitcoin")
        self.assertEqual(result["caption"], "Cool!")
        self.assertEqual(result["image_prompt"], "Image")

    @patch("src.groq_client.NewsFetcher.fetch_latest_headlines")
    @patch("src.groq_client.requests.post")
    def test_generate_content_fails_on_malformed_json(self, mock_post, mock_fetch):
        mock_fetch.return_value = []
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": 'not a json'
                }
            }]
        }
        mock_post.return_value = mock_response
        
        config.groq_api_key = "test_key"
        client = GroqClient()
        with self.assertRaises(ValueError):
            client.generate_content("Bitcoin")

class TestImageGenerator(unittest.TestCase):
    @patch("src.image_generator.requests.get")
    def test_image_generator_encodes_and_downloads(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b"fakeimagebytes"
        mock_response.headers = {"Content-Type": "image/png"}
        mock_get.return_value = mock_response
        
        generator = ImageGenerator()
        image_bytes = generator.generate_image("Bitcoin & Ethereum, crypto currency")
        
        # Verify prompt is URL encoded
        expected_url = "https://gen.pollinations.ai/image/Bitcoin%20%26%20Ethereum%2C%20crypto%20currency"
        expected_headers = {}
        if config.pollinations_api_key:
            expected_headers["Authorization"] = f"Bearer {config.pollinations_api_key}"
        mock_get.assert_called_with(expected_url, headers=expected_headers, timeout=30)
        self.assertEqual(image_bytes, b"fakeimagebytes")

    @patch("src.image_generator.requests.get")
    @patch("src.image_generator.time.sleep") # mock sleep to speed up test
    def test_image_generator_retries_on_failure(self, mock_sleep, mock_get):
        mock_fail = MagicMock()
        mock_fail.raise_for_status.side_effect = Exception("HTTP Error")
        
        mock_success = MagicMock()
        mock_success.content = b"retrybytes"
        mock_success.headers = {"Content-Type": "image/png"}
        
        mock_get.side_effect = [mock_fail, mock_success]
        
        generator = ImageGenerator()
        image_bytes = generator.generate_image("Bitcoin")
        
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(image_bytes, b"retrybytes")

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

class TestThreadsClient(unittest.TestCase):
    @patch("src.threads_client.requests.post")
    @patch("src.threads_client.requests.get")
    @patch("src.threads_client.time.sleep")
    def test_publish_post_success_flow(self, mock_sleep, mock_get, mock_post):
        config.threads_user_id = "user123"
        config.threads_access_token = "token123"
        
        # Mock container creation POST
        mock_container_res = MagicMock()
        mock_container_res.json.return_value = {"id": "container_abc"}
        
        # Mock publish POST
        mock_publish_res = MagicMock()
        mock_publish_res.json.return_value = {"id": "post_999"}
        
        mock_post.side_effect = [mock_container_res, mock_publish_res]
        
        # Mock status check GETs: First IN_PROGRESS, second FINISHED
        mock_status_in_progress = MagicMock()
        mock_status_in_progress.json.return_value = {"status": "IN_PROGRESS"}
        
        mock_status_finished = MagicMock()
        mock_status_finished.json.return_value = {"status": "FINISHED"}
        
        mock_get.side_effect = [mock_status_in_progress, mock_status_finished]
        
        client = ThreadsClient()
        post_id = client.publish_post("https://res.cloudinary.com/img.jpg", "Hello #world")
        
        self.assertEqual(post_id, "post_999")
        self.assertEqual(mock_get.call_count, 2)

    @patch("src.threads_client.requests.post")
    @patch("src.threads_client.requests.get")
    @patch("src.threads_client.time.sleep")
    def test_publish_post_fails_on_status_error(self, mock_sleep, mock_get, mock_post):
        config.threads_user_id = "user123"
        config.threads_access_token = "token123"
        
        # Mock container creation POST
        mock_container_res = MagicMock()
        mock_container_res.json.return_value = {"id": "container_abc"}
        mock_post.return_value = mock_container_res
        
        # Mock status check GET: ERROR status
        mock_status_err = MagicMock()
        mock_status_err.json.return_value = {"status": "ERROR", "error_message": "Meta download failed"}
        mock_get.return_value = mock_status_err
        
        client = ThreadsClient()
        with self.assertRaises(RuntimeError) as context:
            client.publish_post("https://res.cloudinary.com/img.jpg", "Hello")
            
        self.assertIn("Meta download failed", str(context.exception))


class TestReplyManager(unittest.TestCase):
    def setUp(self):
        import tempfile
        # Create a temporary file for database testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        config.gemini_api_key = "test_gemini_key"
        config.threads_user_id = "user123"
        config.threads_access_token = "token123"
        config.automation_paused = False

    def tearDown(self):
        import os
        os.close(self.db_fd)
        try:
            os.remove(self.db_path)
        except Exception:
            pass

    def test_database_initialization(self):
        from src.reply_manager import ReplyManager
        manager = ReplyManager(self.db_path)
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='replied_comments'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        conn.close()

    def test_reserve_comment(self):
        from src.reply_manager import ReplyManager
        manager = ReplyManager(self.db_path)
        # First reservation should succeed
        res = manager._reserve_comment("comment_1", "post_1", "user_1", "hello")
        self.assertTrue(res)
        
        # Second reservation on same ID should fail (already reserved/pending)
        res2 = manager._reserve_comment("comment_1", "post_1", "user_1", "hello")
        self.assertFalse(res2)

    def test_save_replied_status(self):
        from src.reply_manager import ReplyManager
        manager = ReplyManager(self.db_path)
        manager._save_replied_status("comment_2", "success", "post_1", "user_2", "hello", "reply_text")
        
        import sqlite3
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
        manager = ReplyManager(self.db_path)
        # Add 19 successful replies
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for i in range(19):
            cursor.execute("INSERT INTO replied_comments (comment_id, status) VALUES (?, 'success')", (f"c_{i}",))
        conn.commit()
        conn.close()
        
        # Ceiling should allow it (19 < 20)
        self.assertTrue(manager._check_daily_ceiling())
        
        # Add 1 more (total 20)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO replied_comments (comment_id, status) VALUES ('c_20', 'success')")
        conn.commit()
        conn.close()
        
        # Ceiling should halt it (20 is not < 20)
        self.assertFalse(manager._check_daily_ceiling())

    @patch("src.reply_manager.requests.request")
    def test_backoff_retry_on_429(self, mock_request):
        from src.reply_manager import ReplyManager
        mock_429 = MagicMock()
        mock_429.status_code = 429
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        
        # Return 429 once, then 200
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
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello commenter!"}]
                }
            }]
        }
        mock_request.return_value = mock_resp
        
        manager = ReplyManager(self.db_path)
        reply = manager.generate_reply("Post context", "User comment")
        self.assertEqual(reply, "Hello commenter!")

if __name__ == "__main__":
    unittest.main()

