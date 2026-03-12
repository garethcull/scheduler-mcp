# Google Cloud Scheduler MCP Server

A Model Context Protocol (MCP) server that exposes Google Cloud Scheduler management as tools consumable by an MCP Client such as OpenAI Responses API, Cursor or the prototypr.ai MCP Client.

This MCP Server was built as a Flask application and is deployable to Google Cloud Run or your own infrastructure.

# MCP Features

This Google Cloud Scheduler MCP Server features six MCP tools:

### create_new_scheduled_job
Create a Google Cloud Scheduler HTTP job that calls an endpoint on a schedule. Supports Cloud Run (OIDC), other Google services (OAuth), and external APIs (custom headers or no auth).

### list_current_scheduled_jobs
List the current scheduled jobs that are enabled in Google Cloud Scheduler.

### update_a_scheduled_job
Update the cron schedule of an existing scheduled job by name.

### pause_a_scheduled_job
Pause an active scheduled job by name.

### resume_a_scheduled_job
Resume a paused scheduled job by name.

### delete_a_scheduled_job
Delete a scheduled job from Google Cloud Scheduler by name.

---

It is a protected server, which requires the server operator to add an authorization token to gain access to the service. This auth token (MCP_TOKEN) is an environment variable that needs to be set.

Natural language requests are routed to the appropriate Cloud Scheduler tool, which then interacts with the Google Cloud Scheduler API to create, list, update, pause, resume, or delete scheduled jobs.

Response data is then fed back to the requesting user or agent as a formatted string detailing the result of the operation.

# MCP Architecture

This MCP server contains two files:
1. `app.py` - main Python file which authenticates and delegates requests to mcp_helper.py
2. `mcp_helper.py` - supporting helper functions to fulfill user requests

### app.py
- Flask app with `POST /mcp`
- Handles JSON-RPC notifications by returning `204 No Content`
- Delegates to `mcp_helper` for MCP method logic

### mcp_helper.py
- `handle_request` routes `initialize`, `tools/list`, `tools/call`
- `handle_tool_call` decodes arguments, dispatches to tools, and returns MCP-shaped results
- Cloud Scheduler functions handle job creation, listing, updating, pausing, resuming, and deletion
- `build_scheduler_message` formats job creation responses into human-readable summaries

### Authentication Modes for Scheduled Jobs

When creating a new scheduled job, the server supports three authentication modes for the target endpoint:

- **oidc** (default) — For Cloud Run endpoints. Uses an OIDC token signed by the service account.
- **oauth** — For other Google Cloud services like Cloud Functions. Uses an OAuth token.
- **none** — For external APIs, webhooks, or non-Google endpoints. Pair with `custom_headers` if the external API requires an API key or token.

# Endpoints and Protocol

**JSON-RPC MCP (preferred by this server)**

```
POST /mcp
Content-Type: application/json
Auth: Authorization: Bearer MCP_TOKEN
```

### Methods
- `initialize` → returns protocolVersion, serverInfo, capabilities
- `tools/list` → returns tools with inputSchema (camelCase)
- `tools/call` → returns result with content array
- `notifications/initialized` → must NOT return a JSON-RPC body; respond 204

# Environment Variables

This MCP server has environment variables that need to be set in Google Cloud Run or your hosted platform in order for it to work. They are:

| Variable | Description |
|---|---|
| `MCP_TOKEN` | Shared secret for Authorization header |
| `GOOGLE_CLOUD_PROJECT_ID` | Your Google Cloud project ID |
| `GOOGLE_CLOUD_RUN_URL` | The base URL of your Cloud Run service |
| `SERVICE_ACCOUNT_EMAIL` | The email address of the service account used for OIDC/OAuth tokens |
| `GOOGLE_CLOUD_SCHEDULER_KEY` | Base64-encoded Google service account JSON key for Cloud Scheduler |

**Note:** The service account key must be encoded as a base64 string. You can encode it using the following command:

```bash
base64 -i your-key-file.json | tr -d '\n'
```

Or in Python:

```python
import base64

with open("your-key-file.json", "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")
    print(encoded)
```

### Service Account Permissions

The service account used by this MCP server needs the following IAM roles:

1. **Cloud Scheduler Admin** (`roles/cloudscheduler.admin`) — to create, update, pause, resume, and delete jobs.
2. **Cloud Run Invoker** (`roles/run.invoker`) — to allow scheduled jobs to invoke Cloud Run endpoints.
3. **Service Account User** (`roles/iam.serviceAccountUser`) — to allow Cloud Scheduler to act as the service account when generating OIDC/OAuth tokens.

You can grant these via the `gcloud` CLI:

```bash
# Cloud Scheduler Admin
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \
    --role="roles/cloudscheduler.admin"

# Cloud Run Invoker
gcloud run services add-iam-policy-binding YOUR_SERVICE_NAME \
    --region=us-east1 \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \
    --role="roles/run.invoker"

# Service Account User
gcloud iam service-accounts add-iam-policy-binding \
    YOUR_SERVICE_ACCOUNT_EMAIL \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \
    --role="roles/iam.serviceAccountUser"
```

# Local Setup

### Python environment

I typically use Ananconda Navigator to create and manage my python environments. 

Open Ananconda > Create New Environment at python 3.11+ and then open the terminal for that env. 

Navigate to your folder where you cloned this repo and pip install the requirements as seen below. 

```bash
# Install dependencies
pip install -r requirements.txt
```

### Environment variables (example)

You'll need to set these environment variables locally and in Google Cloud Run.

```bash
export MCP_TOKEN="your-shared-token"
export GOOGLE_CLOUD_PROJECT_ID="your-project-id"
export GOOGLE_CLOUD_RUN_URL="https://your-cloud-run-url.run.app"
export SERVICE_ACCOUNT_EMAIL="your-service-account@your-project-id.iam.gserviceaccount.com"
export GOOGLE_CLOUD_SCHEDULER_KEY="your-service-key-as-a-base64-string"
```

### Run locally

With your environment loaded, navigate to your folder and then launch the flask app with the following run command.

```bash
flask run --debugger -h localhost -p 3000
```

## Quick Test of the mcp server

I use this function below to help me test that a given tool is working in the mcp server. Just copy and run in your own Jupyter notebook or Google Collab. 

```python
import os
import requests
import json

def call_tool(base_url):
    """
    Calls /mcp with tools/call - create_new_scheduled_job
    """
    
    # Variables
    token = os.environ.get('MCP_TOKEN')
    url = f"{base_url}/mcp"
    job_name = "agent-endpoint-test"
    job_description = "a test of a recurring job for an agent endpoint"
    cron_schedule = "0 9 * * *"
    endpoint_url = "<INSERT THE CLOUDRUN ENDPOINT URL FOR THE RECURRING JOB>"
    cloud_run_audience = "<INSERT THE BASE URL FOR YOUR CLOUD RUN APP>"
    http_method = "GET"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "create_new_scheduled_job",
            "arguments": {
                "name": job_name,
                "description": job_description,
                "schedule": cron_schedule,
                "endpoint_url": endpoint_url,
                "cloud_run_audience": cloud_run_audience,
                "http_method": http_method
            }
        },
        "id": 1
    }

    # Recommended: use json= instead of data=json.dumps(...)
    resp = requests.post(url, headers=headers, json=payload, timeout=20)

    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, resp.text

```

# OpenAI Responses API Tool Configuration

This MCP tool was initially designed to use with OpenAI Responses API as part of the protoypr.ai MCP Client. For more details about OpenAI's Responses API and MCP, please check out this cookbook:
https://cookbook.openai.com/examples/mcp/mcp_tool_guide

Configure an MCP tool in your Responses API request. Point server_url to your /mcp endpoint and include the Authorization header.

```python
tools = [
  {
    "type": "mcp",
    "server_label": "gcloud-scheduler-mcp",
    "server_url": "https://<your-cloud-run-host>/mcp",
    "headers": { "Authorization": "Bearer <your-mcp-token>" },
    "require_approval": "never"
  }
]
```

# How to connect this server to your MCP Client

As mentioned, this MCP server was originally designed for the prototypr.ai MCP client. In order to connect this server to the prototypr.ai MCP client or another client like Cursor, you need to use the following mcp.json structure:

```json
{
    "gcloud-scheduler-mcp": {
        "description": "An MCP server that schedules cron jobs using the Google Cloud Scheduler API",
        "displayName": "Google Cloud Scheduler MCP",
        "headers": {
            "Authorization": "Bearer <INSERT MCP_TOKEN>"
        },
        "icon": "<ADD ICON URL>",
        "transport": "stdio",
        "url": "<https://<your-cloud-run-host>/mcp>"
    }
}

```

# Cron Schedule Reference

Common cron expressions for the `schedule` field:

| Schedule | Description |
|---|---|
| `*/5 * * * *` | Every 5 minutes |
| `0 9 * * *` | Every day at 9:00 AM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `0 */2 * * *` | Every 2 hours |
| `0 9,17 * * *` | Twice a day at 9:00 AM and 5:00 PM |
| `0 0 1 * *` | First day of every month at midnight |

# Security Considerations

- Always require `Authorization: Bearer MCP_TOKEN` on `/mcp`
- Keep tool outputs reasonable in size and fully UTF-8
- Use OIDC tokens for Cloud Run endpoints instead of hardcoded tokens
- Store service account keys securely and never commit them to version control

# Deploying to Google Cloud Run

I initially built this MCP server to be deployed on Google Cloud Run.

Google Cloud Run is a serverless environment that can scale and is easy to deploy to.

Since Google Cloud Run is a paid service, you'll need to ensure your project is set and billing is enabled.

You will also need to add the Environment Variables to your Cloud Run instance.


### Helpful Resources
- Deploy a Python service to Cloud Run: https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service
- Cloud Scheduler documentation: https://cloud.google.com/scheduler/docs

# License
MIT (or your preferred license).

# Contributions & Support
Feedback, issues and PRs welcome. Due to bandwidth constraints, I can't offer any timelines for free updates to this codebase.

If you need help customizing this MCP server, I'm available for paid consulting and freelance projects. Feel free to reach out and connect w/ me on LinkedIn:
https://www.linkedin.com/in/garethcull/

Thanks for checking out this Google Cloud Scheduler MCP Server! I hope it helps you and your team.

Happy Scheduling! 🚀
