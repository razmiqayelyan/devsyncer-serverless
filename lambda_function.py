import json
import logging
import traceback
from jira_helper import JiraClient
from ai_helper import AIClient

# Setup Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Main Orchestrator.
    """
    logger.info("🚀 DevSyncer Enterprise: Starting...")
    
    # Initialize Clients
    jira = JiraClient()
    ai = AIClient()

    try:
        # 1. Parse Input
        body = event.get('body', '{}')
        if isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body

        # 2. Handle GitHub Ping
        if 'zen' in payload:
            return {'statusCode': 200, 'body': 'Ping received.'}

        # 3. Extract Commit Data
        head_commit = payload.get('head_commit')
        if not head_commit:
            return {'statusCode': 200, 'body': 'Ignored: No commit data.'}

        commit_id = head_commit.get('id', 'unknown')[:7] # Short hash
        commit_msg = head_commit.get('message', 'No message')
        author = payload.get('pusher', {}).get('name', 'Unknown')
        
        logger.info(f"Processing Commit {commit_id} by {author}")

        # 4. DUPLICATE CHECK (The "Safety Valve")
        # We ask Jira: "Do you already have a ticket for Commit ID xxxxx?"
        if jira.ticket_exists(commit_id):
            logger.info(f"Duplicate detected for {commit_id}. Skipping.")
            return {
                'statusCode': 200, 
                'body': json.dumps({'message': 'Skipped: Ticket already exists', 'commit': commit_id})
            }

        # 5. AI Analysis
        summary = ai.summarize(commit_msg)

        # 6. Create Jira Ticket
        ticket_key = jira.create_task(summary, author, commit_id, head_commit.get('url'))

        return {
            'statusCode': 200, 
            'body': json.dumps({'message': 'Success', 'ticket': ticket_key})
        }

    except Exception as e:
        # --- SELF-REPORTING ERROR LOGIC ---
        # If ANYTHING crashes, we capture the traceback (last 50 lines of error)
        # and create a Jira ticket assigned to YOU.
        error_trace = traceback.format_exc()
        logger.error(f"CRITICAL FAILURE: {error_trace}")
        
        try:
            # Try to log the crash to Jira so you don't miss it
            bug_key = jira.create_crash_report(error_trace)
            return {
                'statusCode': 500, 
                'body': json.dumps({'error': 'Internal Crash', 'bug_ticket': bug_key})
            }
        except:
            # If even Jira fails, just return the error string
            return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}