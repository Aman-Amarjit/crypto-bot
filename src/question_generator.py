import json
import requests
from src.config import config

class QuestionGenerator:
    def __init__(self):
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self.max_retries = 3

    def generate_question(self) -> str:
        if not config.groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        headers = {
            "Authorization": f"Bearer {config.groq_api_key}",
            "Content-Type": "application/json"
        }

        system_prompt = (
            "You are a senior cybersecurity researcher and systems architect.\n"
            "Your job is to generate a single, highly engaging, technically precise question of the day "
            "for a professional audience of software developers, DevOps engineers, and security professionals.\n\n"
            "Guidelines:\n"
            "- Focus on advanced security topics: secure coding, network protocols, cryptography, container security, "
            "CI/CD vulnerabilities, supply-chain exploits, or identity management.\n"
            "- The question must be open-ended, thought-provoking, and technical (e.g. 'How are you mitigating the risk "
            "of dependency confusion in your internal package feeds?' rather than 'What is cybersecurity?').\n"
            "- It must be concise and fit easily under 400 characters.\n"
            "- Do NOT include any introductory filler ('Here is the question of the day:', 'Hey everyone!').\n"
            "- Do NOT include hashtags, emojis, or formatting markdown.\n"
            "- Output ONLY the question text itself."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate today's technical cybersecurity/developer question of the day."}
            ],
            "temperature": 0.8
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                question = data["choices"][0]["message"]["content"].strip()
                
                # Basic validation: ensure it's not empty, under 450 chars, and ends with a question mark
                if question and len(question) < 450 and question.endswith("?"):
                    # Strip surrounding quotes if the model outputted them
                    if question.startswith('"') and question.endswith('"'):
                        question = question[1:-1].strip()
                    return question
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                
        # Default fallback question in case all attempts fail
        return "How are you validating the integrity of your third-party open-source dependencies in your deployment pipelines?"
