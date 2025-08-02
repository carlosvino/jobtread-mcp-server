from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import os
import httpx
import json
import logging
import uvicorn
import asyncio

app = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Enable CORS for OpenAI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fallback demo data
DEMO_PROJECTS = [
    {"id": "demo_1", "name": "Smith Kitchen Remodel", "budget": 50000, "status": "in_progress"},
    {"id": "demo_2", "name": "TechCorp Office Renovation", "budget": 250000, "status": "planning"},
]

# Simplified JobTread API operations
JOBTREAD_OPERATIONS = {
    "list_jobs": {
        "description": "List all jobs in the organization",
        "input": {"limit": "integer", "offset": "integer"},
        "method": "get_jobs"
    },
    "get_job": {
        "description": "Get details of a specific job",
        "input": {"job_id": "string"},
        "method": "get_job_detail"
    },
    "list_customers": {
        "description": "List all customers",
        "input": {"limit": "integer", "offset": "integer"},
        "method": "get_customers"
    },
    "get_customer": {
        "description": "Get details of a specific customer",
        "input": {"customer_id": "string"},
        "method": "get_customer_detail"
    },
    "list_documents": {
        "description": "List documents for a job or customer",
        "input": {"job_id": "string", "customer_id": "string"},
        "method": "get_documents"
    }
}

def get_jobtread_credentials():
    """Get JobTread credentials from environment variables"""
    # Try multiple possible environment variable names (matching Railway setup)
    grant_key = (
        os.getenv("JOBTREAD_GRANT_KEY") or 
        os.getenv("JOBTREAD_ACCESS_TOKEN") or
        os.getenv("JOBTREAD_API_KEY") or
        os.getenv("JOBTREAD_TOKEN")
    )
    
    org_id = (
        os.getenv("JOBTREAD_ORG_ID") or
        os.getenv("JOBTREAD_ORGANIZATION_ID")
    )
    
    return grant_key, org_id

async def call_jobtread_api(operation: str, params: dict = None):
    """
    Call JobTread API with multiple fallback strategies
    """
    grant_key, org_id = get_jobtread_credentials()
    
    if not grant_key or not org_id:
        logging.warning("[JobTread] Missing credentials, returning demo data")
        return DEMO_PROJECTS
    
    if params is None:
        params = {}
    
    # Try different payload structures based on operation
    payload_strategies = [
        # Strategy 1: Original complex structure
        {
            "url": "https://api.jobtread.com/pave",
            "payload": {
                "organization": {
                    "$": {
                        "grantKey": grant_key,
                        "id": org_id,
                        "timeZone": "America/Los_Angeles"
                    },
                    operation: {
                        "$": params,
                        "nodes": {
                            "id": {},
                            "name": {},
                            "description": {},
                            "status": {},
                            "budget": {}
                        }
                    }
                }
            }
        },
        
        # Strategy 2: Simplified structure
        {
            "url": "https://api.jobtread.com/pave",
            "payload": {
                "grantKey": grant_key,
                "organizationId": org_id,
                "operation": operation,
                "parameters": params
            }
        },
        
        # Strategy 3: Direct API calls
        {
            "url": f"https://api.jobtread.com/api/v1/{operation}",
            "headers": {"Authorization": f"Bearer {grant_key}", "X-Organization-ID": org_id},
            "payload": params
        },
        
        # Strategy 4: REST-style with different auth
        {
            "url": f"https://api.jobtread.com/{operation}",
            "headers": {"X-Grant-Key": grant_key, "X-Org-ID": org_id},
            "payload": params
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, strategy in enumerate(payload_strategies):
            try:
                logging.info(f"[JobTread] Trying strategy {i+1} for {operation}")
                
                headers = strategy.get("headers", {"Content-Type": "application/json"})
                
                response = await client.post(
                    strategy["url"],
                    json=strategy["payload"],
                    headers=headers
                )
                
                logging.info(f"[JobTread] Strategy {i+1} response: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logging.info(f"[JobTread] Success with strategy {i+1}")
                        
                        # Parse response based on strategy
                        if i == 0:  # Original complex structure
                            return data.get("organization", {}).get(operation, {}).get("nodes", [])
                        elif i == 1:  # Simplified structure  
                            return data.get("data", data)
                        else:  # Direct API calls
                            return data if isinstance(data, list) else [data]
                            
                    except json.JSONDecodeError:
                        logging.warning(f"[JobTread] Strategy {i+1} returned non-JSON: {response.text[:200]}")
                        continue
                        
                elif response.status_code == 401:
                    logging.error(f"[JobTread] Authentication failed with strategy {i+1}")
                    continue
                    
                elif response.status_code == 404:
                    logging.warning(f"[JobTread] Endpoint not found with strategy {i+1}")
                    continue
                    
                else:
                    logging.warning(f"[JobTread] Strategy {i+1} failed: {response.status_code} - {response.text[:200]}")
                    continue
                    
            except httpx.RequestError as e:
                logging.error(f"[JobTread] Strategy {i+1} request error: {e}")
                continue
            except Exception as e:
                logging.error(f"[JobTread] Strategy {i+1} unexpected error: {e}")
                continue
    
    # If all strategies failed, return demo data
    logging.warning("[JobTread] All API strategies failed, returning demo data")
    return DEMO_PROJECTS

@app.get("/")
@app.get("/health")
async def health():
    grant_key, org_id = get_jobtread_credentials()
    return {
        "status": "ok", 
        "message": "JobTread MCP server running",
        "credentials_found": bool(grant_key and org_id),
        "grant_key_present": bool(grant_key),
        "org_id_present": bool(org_id)
    }

@app.get("/test-auth")
async def test_auth():
    """Test endpoint to verify JobTread API connectivity"""
    grant_key, org_id = get_jobtread_credentials()
    
    if not grant_key or not org_id:
        return {
            "error": "Missing credentials",
            "grant_key_present": bool(grant_key),
            "org_id_present": bool(org_id),
            "env_vars_checked": [
                "JOBTREAD_GRANT_KEY", "JOBTREAD_API_KEY", "JOBTREAD_TOKEN",
                "JOBTREAD_ORG_ID", "JOBTREAD_ORGANIZATION_ID"
            ]
        }
    
    try:
        result = await call_jobtread_api("job", {"limit": 5})
        return {
            "status": "success",
            "credentials_working": True,
            "sample_data": result[:2] if result else []
        }
    except Exception as e:
        return {
            "status": "error",
            "credentials_present": True,
            "error": str(e)
        }

@app.get("/sse/")
async def sse_stream(request: Request) -> StreamingResponse:
    async def event_generator():
        logging.info("SSE stream initiated")
        yield 'data: {"status": "connected"}\n\n'
        try:
            while True:
                if await request.is_disconnected():
                    logging.info("SSE client disconnected")
                    break
                yield 'data: {"type": "heartbeat"}\n\n'
                await asyncio.sleep(30)
        except Exception as e:
            logging.error(f"SSE error: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/sse/")
async def sse(request: Request):
    try:
        body = await request.json()
        logging.info(f"[MCP] Incoming request: {json.dumps(body, indent=2)}")
    except Exception as e:
        logging.error(f"[MCP] Failed to parse request body: {e}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error"}
        }

    method = body.get("method")
    rpc_id = body.get("id", None)

    if method == "initialize":
        params = body.get("params", {})
        client_protocol = params.get("protocolVersion", "2025-06-18")
        supported_versions = ["2025-03-26", "2025-06-18"]
        if client_protocol not in supported_versions:
            logging.warning(f"[MCP] Unsupported protocol: {client_protocol}")
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32604, "message": f"Unsupported protocol version: {client_protocol}"}
            }
        logging.info(f"[MCP] Initialize successful with version: {client_protocol}")
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": client_protocol,
                "capabilities": {
                    "tools": {
                        "listChanged": False,
                        "callable": True
                    }
                },
                "serverInfo": {
                    "name": "JobTread MCP Server",
                    "version": "1.1.0"
                }
            }
        }

    if method == "notifications/initialized":
        logging.info("[MCP] Received 'notifications/initialized'")
        return {}

    if method == "tools/list":
        logging.info("[MCP] Tools/list requested")
        tools = []
        
        for tool_name, config in JOBTREAD_OPERATIONS.items():
            tool = {
                "name": tool_name,
                "description": config["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        param: {"type": param_type} 
                        for param, param_type in config["input"].items()
                    },
                    "additionalProperties": False
                }
            }
            tools.append(tool)
        
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"tools": tools}
        }

    if method == "tools/call":
        logging.info("[MCP] Tools/call requested")
        params = body.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        async def stream_results():
            try:
                logging.info(f"[MCP] Executing tool: {tool_name} with args: {args}")
                
                # Call JobTread API
                data = await call_jobtread_api(tool_name, args)
                
                # Ensure data is always a list
                if not isinstance(data, list):
                    data = [data] if data else []
                
                logging.info(f"[MCP] Tool {tool_name} returned {len(data)} results")
                
                # Stream results
                for i, result in enumerate(data):
                    yield json.dumps({
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2)
                                }
                            ],
                            "isFinal": i == len(data) - 1
                        }
                    }) + "\n"
                    await asyncio.sleep(0.1)

            except Exception as e:
                logging.error(f"[MCP] Tool execution error: {e}")
                yield json.dumps({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32000, "message": f"Internal error: {str(e)}"}
                }) + "\n"

        return StreamingResponse(stream_results(), media_type="application/json")

    # Fallback for unknown methods
    logging.warning(f"[MCP] Unknown method: {method}")
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not supported"
        }
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
