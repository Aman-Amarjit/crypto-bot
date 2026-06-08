import time
import requests
from src.config import config

class ThreadsClient:
    def __init__(self):
        self.base_url = "https://graph.threads.net/v1.0"
        
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
        params = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": caption,
            "access_token": config.threads_access_token
        }
        
        print("Creating Threads media container...")
        response = requests.post(container_url, params=params, timeout=30)
        response.raise_for_status()
        
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
            status_response = requests.get(status_url, params=status_params, timeout=30)
            status_response.raise_for_status()
            
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
        publish_params = {
            "creation_id": container_id,
            "access_token": config.threads_access_token
        }
        
        print("Publishing container to Threads...")
        publish_response = requests.post(publish_url, params=publish_params, timeout=30)
        publish_response.raise_for_status()
        
        publish_data = publish_response.json()
        post_id = publish_data.get("id")
        if not post_id:
            raise KeyError(f"Threads publish response did not contain post id. Response: {publish_data}")
            
        print(f"Successfully published post to Threads! Post ID: {post_id}")
        return post_id

    def publish_text_post(self, text: str) -> str:
        """
        Publishes a text-only post to Threads (no image).
        Uses the same two-step container → publish flow as publish_post().
        """
        if not config.threads_user_id or not config.threads_access_token:
            raise ValueError("Threads User ID and Access Token must be set in configuration")

        # Step 1: Create text-only media container
        container_url = f"{self.base_url}/{config.threads_user_id}/threads"
        params = {
            "media_type": "TEXT",
            "text": text,
            "access_token": config.threads_access_token,
        }

        print("Creating Threads text container...")
        response = requests.post(container_url, params=params, timeout=30)
        response.raise_for_status()

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
            status_response = requests.get(status_url, params=status_params, timeout=30)
            status_response.raise_for_status()

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
        publish_params = {
            "creation_id": container_id,
            "access_token": config.threads_access_token,
        }

        print("Publishing text post to Threads...")
        publish_response = requests.post(publish_url, params=publish_params, timeout=30)
        publish_response.raise_for_status()

        publish_data = publish_response.json()
        post_id = publish_data.get("id")
        if not post_id:
            raise KeyError(f"Threads publish response did not contain post id. Response: {publish_data}")

        print(f"Successfully published text post to Threads! Post ID: {post_id}")
        return post_id
