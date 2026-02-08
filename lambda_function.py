import json
import os
import urllib.request
import urllib.error
import base64
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_env_variable(name):
    """Helper to ensure all keys exist before we start."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"CRITICAL ERROR: Missing Environment Variable: {name}")
    return value

def safe_request(url, method, headers, data=None):
    """
    Robust HTTP request handler with timeout and error reading.
    """
    try:
        if data:
            data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        # 10-second timeout to prevent hanging
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        logger.error(f"HTTP Error {e.code} from {url}: {error_body}")
        return {"error": True, "status": e.code, "message": error_body}
    except Exception as e:
        logger.error(f"Network Error: {str(e)}")
        return {"error": True, "message": str(e)}

def lambda_handler(event, context):
    logger.info("🚀 DevSyncer started processing...")
    
    try:
        # --- 1. CONFIGURATION CHECK ---
        # We strip 'https://' and '/' to prevent user configuration errors
        domain_raw = get_env_variable('JIRA_DOMAIN')
        JIRA_DOMAIN = domain_raw.replace('https://', '').replace('http://', '').strip('/')
        
        JIRA_USER = get_env_variable('JIRA_USER')
        JIRA_TOKEN = get_env_variable('JIRA_TOKEN')
        OPENAI_KEY = get_env_variable('OPENAI_KEY')
        JIRA_PROJECT_KEY = os.environ.get('JIRA_PROJECT_KEY', 'KAN')

        # --- 2. PARSE INPUT ---
        body = event.get('body', '{}')
        if isinstance(body, str):
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid JSON body'})}
        else:
            payload = body

        # --- 3. HANDLE GITHUB "PING" EVENT ---
        if 'zen' in payload:
            logger.info("Received GitHub Ping event.")
            return {'statusCode': 200, 'body': json.dumps({'message': 'Ping received. Webhook is active!'})}

        # --- 4. EXTRACT DATA ---
        head_commit = payload.get('head_commit')
        if not head_commit:
            logger.warning("No head_commit found. Ignoring non-push event.")
            return {'statusCode': 200, 'body': json.dumps({'message': 'Ignored non-push event'})}

        commit_msg = head_commit.get('message', 'No message')
        author = payload.get('pusher', {}).get('name', 'Unknown')
        commit_url = head_commit.get('url', 'No URL')

        logger.info(f"Processing commit by {author}: {commit_msg}")

        # --- 5. CALL OPENAI ---
        openai_url = "https://api.openai.com/v1/chat/completions"
        openai_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_KEY}"
        }
        # Using gpt-4o-mini if available (cheaper/faster), falling back to 3.5 is fine too
        openai_payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a concise technical writer."},
                {"role": "user", "content": f"Summarize this git commit in 1 sentence for a manager: {commit_msg}"}
            ],
            "max_tokens": 100
        }

        ai_response = safe_request(openai_url, "POST", openai_headers, openai_payload)
        
        if ai_response.get("error"):
            summary = f"Automatic summary failed. Original message: {commit_msg}"
        else:
            summary = ai_response['choices'][0]['message']['content']

        # --- 6. CREATE JIRA TICKET ---
        jira_url = f"https://{JIRA_DOMAIN}/rest/api/3/issue"
        auth_str = f"{JIRA_USER}:{JIRA_TOKEN}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        
        jira_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {b64_auth}"
        }
        
        # Professional Jira ADF Formatting (Separate Paragraphs)
        jira_payload = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": f"DevSyncer: {summary[:60]}...", 
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": f"Author: {author}", "marks": [{"type": "strong"}]}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": f"AI Analysis: {summary}"}]
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": f"Commit Link: {commit_url}"}]
                        }
                    ]
                },
                "issuetype": {"name": "Task"} 
            }
        }

        jira_response = safe_request(jira_url, "POST", jira_headers, jira_payload)

        if jira_response.get("error"):
            logger.error(f"Jira Failed: {jira_response}")
            return {'statusCode': 500, 'body': json.dumps({'error': 'Jira creation failed', 'details': jira_response})}

        logger.info(f"Ticket Created: {jira_response.get('key')}")
        return {
            'statusCode': 200, 
            'body': json.dumps({
                'message': 'Success', 
                'ticket': jira_response.get('key'),
                'link': f"https://{JIRA_DOMAIN}/browse/{jira_response.get('key')}"
            })
        }

    except ValueError as ve:
        return {'statusCode': 500, 'body': json.dumps({'error': 'Configuration Error', 'details': str(ve)})}
    except Exception as e:
        logger.error(f"Unhandled Error: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal Server Error', 'details': str(e)})}