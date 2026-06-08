import os
import json

class TopicManager:
    # High-engagement target topic buckets for AI and Cybersecurity niches
    TOPICS = [
        # AI Buckets
        "AI model releases GPT Gemini Claude",
        "AI replacing jobs and roles",
        "AI in India",
        "Prompt engineering tips",
        "AI productivity tools",
        
        # Cybersecurity Buckets
        "data breaches security leaks",
        "government cyber regulations",
        "hacking incidents",
        "dark web leaks",
        "cyber warfare",
        
        # Crossover Buckets
        "AI used for cyberattacks",
        "deepfakes and fraud",
        "AI surveillance",
        "LLM jailbreaks vulnerabilities",
        
        # India-Specific Buckets
        "CERT-In advisories security",
        "Indian startup data breaches",
        "Digital India cybersecurity",
        "RBI SEBI tech security regulations"
    ]
    
    def __init__(self, history_file="data/history.json"):
        self.history_file = history_file

    def get_next_topic(self) -> str:
        """
        Retrieves the next topic in the rotation sequence by checking the last topic
        recorded in history_file.
        """
        if not os.path.exists(self.history_file):
            return self.TOPICS[0]
            
        try:
            with open(self.history_file, 'r') as f:
                history = json.load(f)
        except Exception:
            return self.TOPICS[0]

        if not isinstance(history, list) or len(history) == 0:
            return self.TOPICS[0]

        # Get the topic of the last execution
        last_entry = history[-1]
        last_topic = last_entry.get("topic")
        
        if not last_topic:
            return self.TOPICS[0]
            
        try:
            # Match case-insensitively
            last_index = -1
            for i, topic in enumerate(self.TOPICS):
                if topic.lower() == last_topic.lower():
                    last_index = i
                    break
            
            if last_index == -1:
                return self.TOPICS[0]
                
            next_index = (last_index + 1) % len(self.TOPICS)
            return self.TOPICS[next_index]
        except ValueError:
            return self.TOPICS[0]
