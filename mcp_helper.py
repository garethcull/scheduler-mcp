# Install Modules
import os
import json
import base64
import requests
from google.oauth2 import service_account as gcp_service_account
from google.cloud import scheduler_v1
from google.protobuf.json_format import MessageToDict
from google.protobuf import field_mask_pb2


# =============================================================================
# Variables
# =============================================================================

# Google Cloud Scheduler Settings
project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
cloud_run_url = os.getenv('GOOGLE_CLOUD_RUN_URL')
SERVICE_ACCOUNT_EMAIL = os.getenv('SERVICE_ACCOUNT_EMAIL')

# Location setttings default to EST
location = "us-east1"
parent = f"projects/{project_id}/locations/{location}"
time_zone = "America/New_York"

# Create the client with the base64
key_data = os.getenv('GOOGLE_CLOUD_SCHEDULER_KEY')

# Decode the base64 key data into a dict and create credentials
_decoded_key_bytes = base64.b64decode(key_data)
_key_info = json.loads(_decoded_key_bytes.decode("utf-8"))
credentials = gcp_service_account.Credentials.from_service_account_info(_key_info)

# Use the credentials when creating the client
client = scheduler_v1.CloudSchedulerClient(credentials=credentials)


# =============================================================================
# Helper Functions
# =============================================================================

def decode_key(base64_key: str):
    """
    Decode a base64-encoded service account JSON string into a dict.
    """
    encoded_key = base64_key

    if not encoded_key:
        raise ValueError("Base64-encoded service account key is missing or empty.")

    decoded_bytes = base64.b64decode(encoded_key)
    key_info = json.loads(decoded_bytes.decode("utf-8"))
    return key_info


# =============================================================================
# MCP Protocol Request Routing
# =============================================================================

def handle_request(method, params):
    """
    Main request router for MCP (Model Context Protocol) JSON-RPC methods.
    Supported:
      - initialize
      - tools/list
      - tools/call
    Notifications (notifications/*) are handled in app.py (204 No Content).
    """
    if method == "initialize":
        return handle_initialize()
    elif method == "tools/list":
        return handle_tools_list()
    elif method == "tools/call":
        return handle_tool_call(params)
    else:
        # Let app.py wrap unknown methods into a proper JSON-RPC error
        raise ValueError(f"Method not found: {method}")


# =============================================================================
# MCP Protocol Handlers
# =============================================================================

def handle_initialize():
    """
    JSON-RPC initialize response.
    Keep protocolVersion consistent with your current implementation.
    """
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": {
            "name": "gcloud-scheduler-mcp",
            "version": "0.1.0",
        },
        "capabilities": {
            "tools": {}
        },
    }


def handle_tools_list():
    """
    JSON-RPC tools/list result.
    IMPORTANT: For JSON-RPC MCP, schema field is camelCase: inputSchema
    """
    return {
        "tools": [
            {
                "name": "create_new_scheduled_job",
                "description": (
                    "Create a Google Cloud Scheduler HTTP job that calls an endpoint "
                    "on a schedule. Supports Cloud Run (OIDC), other Google services (OAuth), "
                    "and external APIs (custom headers or no auth)."
                ),
                "annotations": {"read_only": False},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the scheduled job. The string should always be hyphenated. (e.g. 'my-scheduled-job')",
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable description of what the scheduled job does.",
                        },
                        "schedule": {
                            "type": "string",
                            "description": "Cron schedule, e.g. '0 9 * * *' for every day at 09:00.",
                        },
                        "endpoint_url": {
                            "type": "string",
                            "description": "The HTTPS URL that Cloud Scheduler will call.",
                        },
                        "auth_type": {
                            "type": "string",
                            "enum": ["oidc", "oauth", "none"],
                            "description": (
                                "Authentication type for the target endpoint. "
                                "Defaults to 'oidc' if not specified. Use 'oidc' when the "
                                "endpoint is a Google Cloud Run service. Use 'oauth' when "
                                "targeting other Google Cloud services like Cloud Functions. "
                                "Use 'none' when calling external APIs, webhooks, or any "
                                "non-Google endpoint — pair with 'custom_headers' if the "
                                "external API requires an API key or token."
                            ),
                        },
                        "cloud_run_audience": {
                            "type": "string",
                            "description": (
                                "The base Cloud Run URL used as the OIDC audience. "
                                "Only required when auth_type is 'oidc'. If omitted, "
                                "derived from endpoint_url by stripping the path."
                            ),
                        },
                        "custom_headers": {
                            "type": "object",
                            "description": (
                                "Additional headers to include in the request. Useful for "
                                "API keys, e.g. {'X-API-Key': 'my-key'}. "
                                "Content-Type: application/json is always included."
                            ),
                        },
                        "http_method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                            "description": "HTTP method for the request. Defaults to 'POST'.",
                        },
                        "body": {
                            "type": "object",
                            "description": "JSON body payload to send with the request.",
                        },
                    },
                    "required": [
                        "name",
                        "description",
                        "schedule",
                        "endpoint_url",
                        "http_method",
                    ],
                    "additionalProperties": False
                }
            },                
            {
                "name": "list_current_scheduled_jobs",
                "description": (
                    "List the current scheduled jobs that are enabled in Google Cloud Scheduler."                    
                ),
                "annotations": {"read_only": False},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The full user query requesting the list of active jobs",
                        }
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
            {
                "name": "update_a_scheduled_job",
                "description": (
                    "Update a scheduled job by name"                    
                ),
                "annotations": {"read_only": False},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the scheduled job to be udated. The string should always be hyphenated. (e.g. 'my-scheduled-job')",
                        },
                        "schedule": {
                            "type": "string",
                            "description": "Cron schedule, e.g. '0 9 * * *' for every day at 09:00.",
                        }
                    }
                },
                "required": [
                    "name",                        
                    "schedule"
                ],
                "additionalProperties": False,
            },
            {
                "name": "pause_a_scheduled_job",
                "description": (
                    "Pause a scheduled job by name"                    
                ),
                "annotations": {"read_only": False},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the scheduled job to pause. The string should always be hyphenated. (e.g. 'my-scheduled-job')",
                        }
                    }
                },
                "required": [
                    "name"                                            
                ],
                "additionalProperties": False,
            },
            {
                "name": "resume_a_scheduled_job",
                "description": (
                    "Resume a scheduled job that was paused by name"                    
                ),
                "annotations": {"read_only": False},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the scheduled job to be resumed. The string should always be hyphenated. (e.g. 'my-scheduled-job')",
                        }
                    }
                },
                "required": [
                    "name"                    
                ],
                "additionalProperties": False,
            },
            {
                "name": "delete_a_scheduled_job",
                "description": (
                    "Delete a scheduled job in Google Cloud Scheduler"                    
                ),
                "annotations": {"read_only": False},
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the scheduled job to be deleted. The string should always be hyphenated. (e.g. 'my-scheduled-job')",
                        }
                    }
                },
                "required": [
                    "name"                    
                ],
                "additionalProperties": False,
            }               
            
        ]
    }

def handle_tool_call(params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    # Decode string args if needed
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return {
                "isError": True,
                "content": [{"type": "text", "text": "Invalid arguments: expected object or JSON string."}]
            }

    if tool_name == "create_new_scheduled_job":
        data = create_new_scheduled_job(arguments)
        return {"content": [{"type": "text", "text": str(data)}]}

    elif tool_name == "list_current_scheduled_jobs":
        data = list_current_scheduled_jobs(arguments)
        return {"content": [{"type": "text", "text": str(data)}]}

    elif tool_name == "update_a_scheduled_job":
        data = updated_scheduled_job(arguments)
        return {"content": [{"type": "text", "text": str(data)}]}

    elif tool_name == "pause_a_scheduled_job":
        data = pause_a_scheduled_job(arguments)
        return {"content": [{"type": "text", "text": str(data)}]}

    elif tool_name == "resume_a_scheduled_job":
        data = resume_a_scheduled_job(arguments)
        return {"content": [{"type": "text", "text": str(data)}]}

    elif tool_name == "delete_a_scheduled_job":
        data = delete_a_scheduled_job(arguments)
        return {"content": [{"type": "text", "text": str(data)}]}

    else:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Tool not found: {tool_name}"}]
        }


# =============================================================================
# Cloud Scheduler Functions
# =============================================================================


def build_scheduler_message(job: dict) -> str:

    """
    Build a message for the mcp client detailing the scheduled job.
    
    Args:
        job: dict - The details of the job that has been created.

    Returns:
        formatted_output string - A summary of the job that was created to be returned
        to the mcp client.
    """

    name = job.get("name", "Unknown")
    description = job.get("description", "No description provided")
    state = job.get("state", "Unknown")
    schedule = job.get("schedule", "Unknown")
    time_zone = job.get("timeZone", "UTC")
    attempt_deadline = job.get("attemptDeadline", "Unknown")
    schedule_time = job.get("scheduleTime", "Unknown")

    http_target = job.get("httpTarget", {})
    target_uri = http_target.get("uri", "Unknown")
    http_method = http_target.get("httpMethod", "Unknown")

    auth_detail = "No authentication token configuration was provided."
    if "oidcToken" in http_target:
        service_account = http_target["oidcToken"].get("serviceAccountEmail", "Unknown")
        audience = http_target["oidcToken"].get("audience", "Unknown")
        auth_detail = (
            f"The authentication type is OIDC using the service account "
            f"{service_account} with audience {audience}."
        )

    formatted_output = (
        f"Your Google Cloud Scheduler job has been created successfully and is {state}.<br><br>"
        f"Here are the details of the job:<br><br>"
        f"The job name is {name}.<br><br>"
        f"The description is {description}.<br><br>"
        f"The target URI is {target_uri}.<br><br>"
        f"The HTTP method is {http_method}.<br><br>"
        f"The schedule is {schedule}, and is run in the {time_zone} time zone. Please ensure you communicate to the user what the frequency of the job is in plain English.<br><br>"
        f"The next scheduled run time returned by Google Cloud Scheduler is {schedule_time}.<br><br>"                             
    )

    return formatted_output


def create_new_scheduled_job(arguments: dict):
    """
    Create a Cloud Scheduler HTTP job that supports three auth modes:
    - oidc: For Cloud Run endpoints (uses OIDC token)
    - oauth: For other Google services (uses OAuth token)
    - none: For external APIs (custom headers or no auth)

    Args:
        arguments: dict - The arguments for the tool call.

    Returns:
        A JSON-serializable dict summarizing the created job.
    """

    # Extract arguments
    name = arguments.get("name")
    description = arguments.get("description")
    schedule = arguments.get("schedule")
    endpoint_url = arguments.get("endpoint_url")
    auth_type = arguments.get("auth_type", "oidc")
    cloud_run_audience = arguments.get("cloud_run_audience")
    custom_headers = arguments.get("custom_headers", {})
    http_method_str = arguments.get("http_method", "POST").upper()
    body = arguments.get("body", {})

    # Map string method to enum
    method_map = {
        "GET": scheduler_v1.HttpMethod.GET,
        "POST": scheduler_v1.HttpMethod.POST,
        "PUT": scheduler_v1.HttpMethod.PUT,
        "DELETE": scheduler_v1.HttpMethod.DELETE,
        "PATCH": scheduler_v1.HttpMethod.PATCH,
    }
    http_method = method_map.get(http_method_str, scheduler_v1.HttpMethod.POST)

    # Build headers — always include Content-Type
    headers = {"Content-Type": "application/json"}
    if custom_headers:
        headers.update(custom_headers)

    # Build the http_target
    http_target = {
        "uri": endpoint_url,
        "http_method": http_method,
        "headers": headers,
    }

    # Only include body for methods that support it
    if http_method_str in ("POST", "PUT", "PATCH") and body:
        http_target["body"] = json.dumps(body).encode("utf-8")

    # Configure authentication based on auth_type
    if auth_type == "oidc":
        # Derive audience from endpoint_url if not provided
        if not cloud_run_audience:
            from urllib.parse import urlparse
            parsed = urlparse(endpoint_url)
            cloud_run_audience = f"{parsed.scheme}://{parsed.netloc}"

        http_target["oidc_token"] = {
            "service_account_email": SERVICE_ACCOUNT_EMAIL,
            "audience": cloud_run_audience,
        }

    elif auth_type == "oauth":
        http_target["oauth_token"] = {
            "service_account_email": SERVICE_ACCOUNT_EMAIL,
        }

    # auth_type == "none" — no token added, just custom headers if any

    # Build the job
    job = {
        "name": f"{parent}/jobs/{name}",
        "description": description,
        "schedule": schedule,
        "time_zone": time_zone,
        "http_target": http_target,
    }

    # Create the job
    response = client.create_job(
        request={
            "parent": parent,
            "job": job,
        }
    )

        # Step 1: Convert Protobuf object to a plain Python dict
    response_dict = MessageToDict(response._pb)

    # Step 2: Now json.dumps works fine on a regular dict
    print(json.dumps(response_dict, indent=2))

    # Compose final formatted report
    formatted_output = build_scheduler_message(response_dict)

    return formatted_output


def list_current_scheduled_jobs(arguments: dict):
    """
    returns a list of the current scheduled jobs

    Args:
        arguments: dict - The arguments for the tool call.

    Returns:
        a list of the current scheduled jobs as a string
    """

    # Extract arguments
    user_query = arguments.get("query")

    jobs = client.list_jobs(request={"parent": parent})

    job_list = []
    for job in jobs:
        job_list.append({
            "Name": job.name.split("/")[-1],
            "Schedule": job.schedule,
            "Time Zone": job.time_zone,
            "State": "Enabled" if job.state == 1 else "Paused" if job.state == 2 else "Unknown",
            "Last Attempt": job.last_attempt_time,
            "Target URL": job.http_target.uri,
        })

    return job_list


def updated_scheduled_job(arguments: dict): 

    """
    Updates a current job based on the name

    Args:
        arguments: dict - The arguments for the tool call

    Returns: 
        a success message on update of the job
    
    """

    name = arguments.get('name',"")
    updated_schedule = arguments.get('schedule',"")

    job_name = f"projects/{project_id}/locations/{location}/jobs/{name}"

    updated_job = {
        "name": job_name,
        "schedule": updated_schedule,  # e.g., every 2 hours
    }

    update_mask = field_mask_pb2.FieldMask(paths=["schedule"])

    response = client.update_job(
        request={
            "job": updated_job,
            "update_mask": update_mask,
        }
    )

    update_msg = f"Updated schedule: {response.schedule}"

    return update_msg



def pause_a_scheduled_job(arguments: dict): 

    """
    Pauses a current job based on the name

    Args:
        arguments: dict - The arguments for the tool call

    Returns: 
        a success message on update of the job
    
    """

    name = arguments.get('name',"")    

    job_name = f"projects/{project_id}/locations/{location}/jobs/{name}"

    client.pause_job(request={"name": job_name})

    pause_msg = f"The following job has been paused: {job_name}"

    return pause_msg



def resume_a_scheduled_job(arguments: dict): 

    """
    Resume a paused current job based on the name

    Args:
        arguments: dict - The arguments for the tool call

    Returns: 
        a success message on resume of the job
    
    """

    name = arguments.get('name',"")    

    job_name = f"projects/{project_id}/locations/{location}/jobs/{name}"

    client.resume_job(request={"name": job_name})

    msg = f"The following job has been resumed: {job_name}"

    return msg


def resume_a_scheduled_job(arguments: dict): 

    """
    Resume a paused current job based on the name

    Args:
        arguments: dict - The arguments for the tool call

    Returns: 
        a success message on resume of the job
    
    """

    name = arguments.get('name',"")    

    job_name = f"projects/{project_id}/locations/{location}/jobs/{name}"

    client.resume_job(request={"name": job_name})

    msg = f"The following job has been resumed: {job_name}"

    return msg


def delete_a_scheduled_job(arguments: dict): 

    """
    Delete a paused current job based on the name

    Args:
        arguments: dict - The arguments for the tool call

    Returns: 
        a success message on deletion of the job
    
    """

    name = arguments.get('name',"")    

    job_name = f"projects/{project_id}/locations/{location}/jobs/{name}"

    client.delete_job(request={"name": job_name})

    msg = f"The following job has been deleted: {job_name}"

    return msg


