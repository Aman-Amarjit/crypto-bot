import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()

def refresh_token():
    current_token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not current_token:
        print("Error: THREADS_ACCESS_TOKEN environment variable is missing", file=sys.stderr)
        sys.exit(1)
        
    url = "https://graph.threads.net/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": current_token
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        new_token = data.get("access_token")
        if not new_token:
            print(f"Error: Response did not contain 'access_token'. Response: {data}", file=sys.stderr)
            sys.exit(1)
            
        # Write the new token to stdout so the workflow can capture it.
        print(new_token)
        
    except Exception as e:
        print(f"Error: Token refresh failed. {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    refresh_token()
