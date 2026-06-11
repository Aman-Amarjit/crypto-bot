# Thread Manager for Cybersecurity

Thread Manager for Cybersecurity is an automated bot designed to post, reply, and generate cybersecurity-related content directly to Meta's Threads platform. 

The bot runs on a schedule and automates tasks such as:
1. **Daily Auto-Posts:** Curates the latest news in cybersecurity, fact-checks it, generates AI-driven images, and publishes them.
2. **Daily Thoughts:** Posts single text-only insights about various cybersecurity topics depending on the day of the week (e.g. Threat Intelligence, Vulnerability Analysis, etc.).
3. **Daily Questions:** Asks engaging questions to spark discussions within the community.
4. **Auto-Replies:** Detects user comments and leverages AI (Gemini) to craft organic, human-like responses.

## Key Features
* **AI Integration:** Uses a stack of AI platforms including Groq (Llama 3) for text generation, Pollinations.ai / Cloudflare Workers AI for images, and Gemini for dynamic auto-replies.
* **GitHub Actions Support:** Fully automated through GitHub Actions cron jobs (`.github/workflows/`), saving local compute resources.
* **Dashboard App:** Includes a local dashboard via `app.py` built on Flask to monitor logs, configure secrets (`.env`), manage persona parameters, and trigger actions manually.
* **Safety Guards:** Rate-limiting checks prevent automated spamming, keeping the account compliant with platform rules.

## Setup Instructions
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the local Flask dashboard:
   ```bash
   python app.py
   ```
3. Configure the Bot:
   Access `http://localhost:5000` to add your necessary API keys (Threads, Groq, Gemini, Cloudflare, etc.) and define your persona.

## Manual Executions
You can trigger any function manually through the terminal (using the `--force` flag to bypass safety rate limits):
* Post daily news: `python main.py --force`
* Post daily thought: `python thought.py --force`
* Post daily question: `python question.py --force`
* Process replies: `python reply.py`

## Automation
The bot operates strictly via predefined GitHub Actions workflows. If you push the changes to GitHub and input the required repository secrets, the workflows will run on their specific cron schedules automatically.
