# DevSyncer: AI-Powered Jira Automation

## 🚀 Overview
DevSyncer is a serverless integration that bridges the gap between development and project management. It automatically tracks code changes pushed to GitHub, uses OpenAI to generate a human-readable summary, and creates a corresponding task in Jira for the project manager to review.

## 🏗 Architecture
* **Trigger:** GitHub Webhook (Push Event)
* **Ingestion:** AWS API Gateway
* **Processing:** AWS Lambda (Python 3.12)
* **Intelligence:** OpenAI GPT-3.5 Turbo
* **Output:** Atlassian Jira Cloud

## 🔧 Workflow
1.  **Code Push:** A developer pushes code to the repository.
2.  **Webhook:** GitHub sends a JSON payload to the AWS API Gateway endpoint.
3.  **Analysis:** The Lambda function parses the commit message and sends it to OpenAI to "translate" technical jargon into a simple summary.
4.  **Automation:** The function authenticates with Jira via the REST API and creates a new ticket containing the AI summary.

## 🛠 Deployment Instructions
1.  Create a new **AWS Lambda** function using Python 3.12.
2.  Copy the code from `lambda_function.py`.
3.  Set the following **Environment Variables** in AWS Configuration:
    * `JIRA_DOMAIN`: Your Atlassian domain (e.g., `company.atlassian.net`)
    * `JIRA_USER`: Your Atlassian email address.
    * `JIRA_TOKEN`: Your Atlassian API Token.
    * `OPENAI_KEY`: Your OpenAI API Key.
    * `JIRA_PROJECT_KEY`: The project key where tickets should be created (e.g., `KAN`).
4.  Add an **API Gateway** trigger to the Lambda function.
5.  Copy the API Gateway URL and add it to your GitHub Repository under **Settings > Webhooks**.

## 📂 Repository Structure
* `lambda_function.py`: The core serverless application logic.
* `sample_payload.json`: Example GitHub payload for testing.
* `architecture.md`: High-level design notes.

---
*Built by Razo*