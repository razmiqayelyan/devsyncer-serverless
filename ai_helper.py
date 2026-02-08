import os
import json
import urllib.request

class AIClient:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_KEY')
        if not self.api_key:
            # We don't raise error here, we handle it in summarize to avoid crash on init
            print("Warning: OPENAI_KEY is missing")

    def summarize(self, text):
        if not self.api_key:
            return f"Summary unavailable (Missing API Key). Original: {text}"

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "Summarize this technical git commit message for a non-technical manager in one simple sentence."},
                {"role": "user", "content": text}
            ],
            "max_tokens": 80
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode())
                return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"AI Error: {e}")
            return f"Auto-summary failed. Original text: {text}"