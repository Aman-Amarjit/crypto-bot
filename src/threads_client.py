import time
import requests
from src.config import config

MAX_RETRIES = 3
RETRY_STATUS_CODES = {500, 502, 503, 504}
BASE_BACKOFF = 2  # seconds, doubles each attempt

class ThreadsClient:
    def __init__(self):
        self.base_url = "https://graph.threads.net/v1.0"
        
    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Executes an HTTP request with exponential backoff retries on specific status codes
        and connection/timeout errors. Logs response details on failure.
        """
        attempt = 0
        backoff = BASE_BACKOFF
        
        while True:
            attempt += 1
            try:
                response = requests.request(method, url, **kwargs)
                
                # Check status code
                if response.status_code < 400 or response.status_code not in RETRY_STATUS_CODES:
                    return response
                
                print(f"⚠️ Request to {url} returned status code {response.status_code} on attempt {attempt}/{MAX_RETRIES + 1}.")
                if attempt > MAX_RETRIES:
                    print(f"Detailed Error Body from Threads API: {response.text}")
                    response.raise_for_status()
                    
            except requests.exceptions.HTTPError as e:
                # This is the HTTPError raised by response.raise_for_status() above.
                raise e
            except requests.exceptions.RequestException as e:
                # This catches other RequestExceptions like ConnectionError and Timeout.
                if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                    print(f"⚠️ Connection/Timeout error during request to {url} on attempt {attempt}/{MAX_RETRIES + 1}: {e}")
                    if attempt > MAX_RETRIES:
                        raise e
                else:
                    raise e
            
            # Wait with exponential backoff
            print(f"Waiting {backoff} seconds before retrying...")
            time.sleep(backoff)
            backoff *= 2
        
    def publish_post(self, image_url: str, caption: str) -> str:
        """
        Executes the two-step publication flow on Meta Threads Graph API:
        1. Create media container.
        2. Poll container status until FINISHED (up to 30s).
        3. Publish container.
        """
        if not config.threads_user_id or not config.threads_access_token:
            raise ValueError("Threads User ID and Access Token must be set in configuration")
            
        # Step 1: Create media container
        container_url = f"{self.base_url}/{config.threads_user_id}/threads"
        query_params = {"access_token": config.threads_access_token}
        
        if len(caption) > 500:
            print(f"⚠️ Warning: Caption length ({len(caption)}) exceeds Threads limit of 500 characters. Truncating to 500.")
            caption = caption[:500]
            
        payload = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": caption,
        }

        print("Creating Threads media container...")
        response = self._request_with_retry("POST", container_url, params=query_params, data=payload, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Threads API Error Details during container creation: {response.text}")
            raise e
        
        container_data = response.json()
        container_id = container_data.get("id")
        if not container_id:
            raise KeyError(f"Threads API response did not contain container id. Response: {container_data}")
            
        print(f"Container created successfully. ID: {container_id}")
        
        # Step 2: Poll container status
        status_url = f"{self.base_url}/{container_id}"
        status_params = {
            "fields": "status,error_message",
            "access_token": config.threads_access_token
        }
        
        print("Waiting 3 seconds before first status check...")
        time.sleep(3)
        
        max_attempts = 10
        poll_interval = 3
        container_finished = False
        
        for attempt in range(1, max_attempts + 1):
            print(f"Checking container status (Attempt {attempt}/{max_attempts})...")
            status_response = self._request_with_retry("GET", status_url, params=status_params, timeout=30)
            try:
                status_response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print(f"Threads API Error Details during status polling: {status_response.text}")
                raise e
            
            status_data = status_response.json()
            status = status_data.get("status")
            error_message = status_data.get("error_message")
            
            print(f"Container status: '{status}'")
            if status == "FINISHED":
                container_finished = True
                break
            elif status == "ERROR":
                raise RuntimeError(f"Threads media container processing failed. Error: {error_message}")
            elif status == "EXPIRED":
                raise RuntimeError("Threads media container expired before it could be published.")
            
            if attempt < max_attempts:
                print(f"Still processing. Waiting {poll_interval} seconds...")
                time.sleep(poll_interval)
                
        if not container_finished:
            raise TimeoutError(f"Threads media container processing timed out after {max_attempts * poll_interval} seconds.")
            
        # Step 3: Publish container
        publish_url = f"{self.base_url}/{config.threads_user_id}/threads_publish"
        publish_query = {"access_token": config.threads_access_token}
        publish_payload = {"creation_id": container_id}

        print("Publishing container to Threads...")
        publish_response = self._request_with_retry("POST", publish_url, params=publish_query, data=publish_payload, timeout=30)
        try:
            publish_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Threads API Error Details during publication: {publish_response.text}")
            raise e
        
        publish_data = publish_response.json()
        post_id = publish_data.get("id")
        if not post_id:
            raise KeyError(f"Threads publish response did not contain post id. Response: {publish_data}")
            
        print(f"Successfully published post to Threads! Post ID: {post_id}")
        return post_id

    def publish_text_post(self, text: str, is_ghost_post: bool = False) -> str:
        """
        Publishes a text-only post to Threads (no image).
        Set is_ghost_post=True to post as a ghost post (archived after 24h).
        Uses the same two-step container → publish flow as publish_post().
        """
        if not config.threads_user_id or not config.threads_access_token:
            raise ValueError("Threads User ID and Access Token must be set in configuration")

        # Step 1: Create text-only media container
        container_url = f"{self.base_url}/{config.threads_user_id}/threads"
        query_params = {"access_token": config.threads_access_token}
        
        if len(text) > 500:
            print(f"⚠️ Warning: Text length ({len(text)}) exceeds Threads limit of 500 characters. Truncating to 500.")
            text = text[:500]
            
        payload = {
            "media_type": "TEXT",
            "text": text,
        }

        if is_ghost_post:
            payload["is_ghost_post"] = "true"

        print("Creating Threads text container...")
        response = self._request_with_retry("POST", container_url, params=query_params, data=payload, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Threads API Error Details during text container creation: {response.text}")
            raise e

        container_data = response.json()
        container_id = container_data.get("id")
        if not container_id:
            raise KeyError(f"Threads API response did not contain container id. Response: {container_data}")

        print(f"Text container created successfully. ID: {container_id}")

        # Step 2: Poll container status
        status_url = f"{self.base_url}/{container_id}"
        status_params = {
            "fields": "status,error_message",
            "access_token": config.threads_access_token,
        }

        print("Waiting 3 seconds before first status check...")
        time.sleep(3)

        max_attempts = 10
        poll_interval = 3
        container_finished = False

        for attempt in range(1, max_attempts + 1):
            print(f"Checking container status (Attempt {attempt}/{max_attempts})...")
            status_response = self._request_with_retry("GET", status_url, params=status_params, timeout=30)
            try:
                status_response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print(f"Threads API Error Details during status polling: {status_response.text}")
                raise e

            status_data = status_response.json()
            status = status_data.get("status")
            error_message = status_data.get("error_message")

            print(f"Container status: '{status}'")
            if status == "FINISHED":
                container_finished = True
                break
            elif status == "ERROR":
                raise RuntimeError(f"Threads text container processing failed. Error: {error_message}")
            elif status == "EXPIRED":
                raise RuntimeError("Threads text container expired before it could be published.")

            if attempt < max_attempts:
                print(f"Still processing. Waiting {poll_interval} seconds...")
                time.sleep(poll_interval)

        if not container_finished:
            raise TimeoutError(f"Threads text container processing timed out after {max_attempts * poll_interval} seconds.")

        # Step 3: Publish container
        publish_url = f"{self.base_url}/{config.threads_user_id}/threads_publish"
        publish_query = {"access_token": config.threads_access_token}
        publish_payload = {"creation_id": container_id}

        print("Publishing text post to Threads...")
        publish_response = self._request_with_retry("POST", publish_url, params=publish_query, data=publish_payload, timeout=30)
        try:
            publish_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Threads API Error Details during text publication: {publish_response.text}")
            raise e

        publish_data = publish_response.json()
        post_id = publish_data.get("id")
        if not post_id:
            raise KeyError(f"Threads publish response did not contain post id. Response: {publish_data}")

        print(f"Successfully published text post to Threads! Post ID: {post_id}")
        return post_id
