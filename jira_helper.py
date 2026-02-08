import os
import json
import base64
import urllib.request
import urllib.error

class JiraClient:
    def __init__(self):
        # Load Config inside the class so it validates immediately
        self.domain = os.environ.get('JIRA_DOMAIN').replace('https://', '').strip('/')
        self.user = os.environ.get('JIRA_USER')
        self.token = os.environ.get('JIRA_TOKEN')
        self.project_key = os.environ.get('JIRA_PROJECT_KEY', 'KAN')
        
        # Prepare Auth Header
        auth_str = f"{self.user}:{self.token}"
        self.auth_header = f"Basic {base64.b64encode(auth_str.encode()).decode()}"
        self.base_url = f"https://{self.domain}/rest/api/3"

    def _request(self, method, endpoint, payload=None):
        """Internal helper for making safe HTTP requests"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.auth_header
        }
        data = json.dumps(payload).encode('utf-8') if payload else None
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())

    def ticket_exists(self, commit_id):
        """
        Checks if a ticket already exists for this commit ID.
        Returns: True (exists) or False (safe to create).
        """
        jql = f'project = {self.project_key} AND description ~ "Commit ID: {commit_id}"'
        payload = {
            "jql": jql,
            "fields": ["key"],
            "maxResults": 1
        }
        try:
            # We use the search endpoint
            response = self._request("POST", "/search", payload)
            return len(response.get('issues', [])) > 0
        except Exception as e:
            print(f"Warning: Deduplication check failed: {e}")
            return False

    def create_task(self, summary, author, commit_id, link):
        """Creates the standard task"""
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": f"DevSyncer: {summary[:60]}...",
                "description": {
                    "type": "doc", 
                    "version": 1, 
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Author: {author}", "marks": [{"type": "strong"}]}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"AI Summary: {summary}"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Commit ID: {commit_id}"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": f"Link: {link}"}]}
                    ]
                },
                "issuetype": {"name": "Task"}
            }
        }
        resp = self._request("POST", "/issue", payload)
        return resp['key']

    def create_crash_report(self, error_trace):
        """
        Saves the last 50 lines of error to Jira as a High Priority Bug.
        """
        # Truncate to ensure it fits (Jira has limits)
        safe_trace = error_trace[-2000:] 
        
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": "🚨 DevSyncer System Failure",
                "description": {
                    "type": "doc", 
                    "version": 1, 
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "The Lambda function crashed. Here is the traceback:"}]},
                        {"type": "codeBlock", "attrs": {"language": "python"}, "content": [{"type": "text", "text": safe_trace}]}
                    ]
                },
                "issuetype": {"name": "Task"}, 
                "priority": {"name": "High"} # Ensure your Jira has 'High' priority enabled, or remove this line
            }
        }
        resp = self._request("POST", "/issue", payload)
        print(f"Created Crash Report: {resp['key']}")
        return resp['key']