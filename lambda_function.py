import json
import os
import urllib.request
import base64

# --- CONFIGURATION (Loaded from AWS Environment Variables) ---
JIRA_DOMAIN = os.environ.get('JIRA_DOMAIN')       # e.g., your-domain.atlassian.net
JIRA_USER = os.environ.get('JIRA_USER')           # Your email
JIRA_TOKEN = os.environ.get('JIRA_TOKEN')         # Your Atlassian API Token
OPENAI_KEY = os.environ.get('OPENAI_KEY')         # Your OpenAI API Key
JIRA_PROJECT_KEY = os.environ.get('JIRA_PROJECT_KEY', 'KAN') # Your Project Key (e.g., KAN, DS)

def call_openai(commit_msg):
    """
    Sends the commit message to OpenAI to get a non-technical summary.
    Uses urllib to avoid external dependencies like 'requests' in AWS Lambda.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_KEY}"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant for a project manager."},
            {"role": "user", "content": f"Summarize this technical commit message into one simple sentence for a non-technical manager: {commit_msg}"}
        ],
        "max_tokens": 60
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return "Automatic summary unavailable."

def create_jira_ticket(summary, author):
    """
    Creates a Jira ticket using the Atlassian Cloud REST API.
    """
    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue"
    
    # Create Basic Auth Header (Email:Token encoded in Base64)
    auth_str = f"{JIRA_USER}:{JIRA_TOKEN}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {b64_auth}"
    }
    
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": f"DevSyncer: Review Code by {author}",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": f"AI Analysis: {summary}"}]
                }]
            },
            "issuetype": {"name": "Task"} # Ensure 'Task' is a valid type in your Jira
        }
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Jira Error: {e}")
        return None

def lambda_handler(event, context):
    """
    Main entry point for AWS Lambda.
    """
    print("Received event:", event)
    
    try:
        # 1. Parse the Body (API Gateway can send body as a string or dict)
        body = event.get('body', '{}')
        if isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body
            
        # 2. Extract Data from GitHub Webhook Payload
        # Note: 'head_commit' is standard for 'push' events
        commit_msg = payload.get('head_commit', {}).get('message', 'No message provided')
        author = payload.get('pusher', {}).get('name', 'Unknown Dev')
        
        print(f"Processing commit: '{commit_msg}' by {author}")
        
        # 3. Generate AI Summary
        summary = call_openai(commit_msg)
        
        # 4. Create Jira Ticket
        ticket = create_jira_ticket(summary, author)
        
        if ticket:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Success', 'ticket_key': ticket['key'], 'ticket_url': f"https://{JIRA_DOMAIN}/browse/{ticket['key']}"})
            }
        else:
             return {'statusCode': 500, 'body': json.dumps({'message': 'Failed to create Jira ticket'})}

    except Exception as e:
        print(f"Critical Error: {str(e)}")
        return {'statusCode': 400, 'body': json.dumps({'error': str(e)})}