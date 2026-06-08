import io
import cloudinary
import cloudinary.uploader
from src.config import config

class ImageUploader:
    def __init__(self):
        # Configure Cloudinary credentials
        cloudinary.config(
            cloud_name=config.cloudinary_cloud_name,
            api_key=config.cloudinary_api_key,
            api_secret=config.cloudinary_api_secret,
            secure=True
        )
        
    def upload_image(self, image_bytes: bytes) -> str:
        """
        Uploads in-memory image bytes to Cloudinary.
        Returns the secure HTTPS URL of the uploaded image.
        """
        print("Uploading image to Cloudinary...")
        
        # Convert bytes to a file-like object
        file_obj = io.BytesIO(image_bytes)
        
        try:
            # Execute upload
            upload_result = cloudinary.uploader.upload(
                file_obj,
                resource_type="image",
                folder="threads_bot"
            )
            
            secure_url = upload_result.get("secure_url")
            if not secure_url:
                raise ValueError("Cloudinary response did not contain secure_url")
                
            print(f"Cloudinary upload successful. Public URL: {secure_url}")
            return secure_url
        except Exception as e:
            raise RuntimeError(f"Failed to upload image to Cloudinary. Error: {e}") from e
