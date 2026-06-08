import os
import json

class TopicManager:
    TOPICS = [
        "tech news",
        "robotics",
        "artificial intelligence",
        "cybersecurity"
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
            last_index = self.TOPICS.index(last_topic.lower())
            next_index = (last_index + 1) % len(self.TOPICS)
            return self.TOPICS[next_index]
        except ValueError:
            # If the last topic isn't in our list (e.g. legacy topic like cryptocurrency),
            # default back to the first topic.
            return self.TOPICS[0]
