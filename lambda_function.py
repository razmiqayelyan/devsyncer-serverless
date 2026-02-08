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
    try:
        jira = JiraClient()
        ai = AIClient()
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': f"Init Failed: {str(e)} "})}

    try:
        # 1. Parse Input
        body = event.get('body', '{}')
        if isinstance(body, str):
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid JSON'})}
        else:
            payload = body

        # 2. Handle GitHub Ping
        if 'zen' in payload:
            return {'statusCode': 200, 'body': json.dumps({'message': 'Ping received.'})}

        # 3. Extract Commit Data
        head_commit = payload.get('head_commit')
        if not head_commit:
            return {'statusCode': 200, 'body': json.dumps({'message': 'Ignored: No commit data.'})}

        commit_id = head_commit.get('id', 'unknown')[:7]
        commit_msg = head_commit.get('message', 'No message')
        author = payload.get('pusher', {}).get('name', 'Unknown')
        commit_url = head_commit.get('url', 'No URL')
        
        logger.info(f"Processing Commit {commit_id} by {author}")

        # 4. DUPLICATE CHECK
        if jira.ticket_exists(commit_id):
            logger.info(f"Duplicate detected for {commit_id}. Skipping.")
            return {
                'statusCode': 200, 
                'body': json.dumps({'message': 'Skipped: Ticket already exists', 'commit': commit_id})
            }

        # 5. AI Analysis
        summary = ai.summarize(commit_msg)

        # 6. Create Jira Ticket
        ticket_key = jira.create_task(summary, author, commit_id, commit_url)

        return {
            'statusCode': 200, 
            'body': json.dumps({'message': 'Success', 'ticket': ticket_key})
        }

    except Exception as e:
        # --- SELF-REPORTING ERROR LOGIC ---
        error_trace = traceback.format_exc()
        logger.error(f"CRITICAL FAILURE: {error_trace}")
        
        try:
            # We attempt to log the crash. We REMOVED the priority field in the helper
            # to ensure this always succeeds regardless of Jira settings.
            bug_key = jira.create_crash_report(error_trace)
            return {
                'statusCode': 500, 
                'body': json.dumps({'error': 'Internal Crash', 'bug_ticket': bug_key})
            }
        except Exception as inner_e:
            # If reporting to Jira fails, return the raw error
            return {'statusCode': 500, 'body': json.dumps({'error': str(e), 'reporting_error': str(inner_e)})}