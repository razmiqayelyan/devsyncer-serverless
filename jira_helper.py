import os
import json
import base64
import urllib.request
import urllib.error

class JiraClient:
    def __init__(self):
        # Load Config
        domain = os.environ.get('JIRA_DOMAIN')
        if not domain: raise ValueError("Missing JIRA_DOMAIN")
        
        self.domain = domain.replace('https://', '').strip('/')
        self.user = os.environ.get('JIRA_USER')
        self.token = os.environ.get('JIRA_TOKEN')
        self.project_key = os.environ.get('JIRA_PROJECT_KEY', 'KAN')
        
        if not self.user or not self.token:
            raise ValueError("Missing Jira Credentials")

        # Prepare Auth Header
        auth_str = f"{self.user}:{self.token}"
        self.auth_header = f"Basic {base64.b64encode(auth_str.encode()).decode()}"
        self.base_url = f"https://{self.domain}/rest/api/3"

    def _request(self, method, endpoint, payload=None):
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.auth_header
        }
        data = json.dumps(payload).encode('utf-8') if payload else None
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode()
            print(f"Jira API Error {e.code}: {error_msg}")
            raise RuntimeError(f"Jira API Error: {error_msg}")

    def ticket_exists(self, commit_id):
        jql = f'project = "{self.project_key}" AND description ~ "Commit ID: {commit_id}"'
        payload = {
            "jql": jql,
            "fields": ["key"],
            "maxResults": 1
        }
        try:
            response = self._request("POST", "/search", payload)
            return len(response.get('issues', [])) > 0
        except Exception as e:
            print(f"Warning: Deduplication check failed: {e}")
            return False

    def create_task(self, summary, author, commit_id, link):
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
        # Truncate to ensure it fits
        safe_trace = error_trace[-1800:] 
        
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
                "issuetype": {"name": "Task"}
                # REMOVED PRIORITY FIELD TO PREVENT CRASHES
            }
        }
        resp = self._request("POST", "/issue", payload)
        return resp['key']