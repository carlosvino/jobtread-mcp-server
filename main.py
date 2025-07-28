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

@app.get("/")
@app.get("/health")
async def health():
    logging.info("Health check accessed")
    return {"status": "ok", "message": "JobTread MCP server running"}

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

    # 1. MCP Handshake (initialize)
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
                    "version": "1.0.0"
                }
            }
        }

    # 2. Handle 'notifications/initialized'
    if method == "notifications/initialized":
        logging.info("[MCP] Received 'notifications/initialized'")
        return {}

    # 3. Declare tools
    if method == "tools/list":
        logging.info("[MCP] Tools/list requested")
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "tools": [
                    {
                        "name": "search",
                        "description": "Search JobTread construction projects by keyword",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search term to filter projects"
                                }
                            },
                            "required": ["query"],
                            "additionalProperties": false
                        },
                        "responseSchema": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "budget": {"type": "number"},
                                    "status": {"type": "string"}
                                }
                            }
                        }
                    },
                    {
                        "name": "fetch",
                        "description": "Fetch a specific JobTread project by ID",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "Project ID to fetch"
                                }
                            },
                            "required": ["id"],
                            "additionalProperties": false
                        },
                        "responseSchema": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "budget": {"type": "number"},
                                    "status": {"type": "string"}
                                }
                            }
                        }
                    }
                ]
            }
        }

    # 4. Tool Execution with streaming
    if method == "tools/call":
        logging.info("[MCP] Tools/call requested")
        params = body.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        async def stream_results():
            try:
                grant_key = os.getenv("JOBTREAD_GRANT_KEY")
                org_id = os.getenv("JOBTREAD_ORG_ID")
                logging.info(f"[MCP] Detected JOBTREAD_GRANT_KEY: {grant_key or 'None'}, JOBTREAD_ORG_ID: {org_id or 'None'}")
                if not grant_key or not org_id:
                    logging.warning("[MCP] Missing JOBTREAD_GRANT_KEY or JOBTREAD_ORG_ID, using demo data")
                    data = DEMO_PROJECTS
                else:
                    payload = {
                        "query": {
                            "$": {"grantKey": grant_key},
                            "currentGrant": {"id": org_id}
                        }
                    }
                    async with httpx.AsyncClient() as client:
                        r = await client.post("https://api.jobtread.com/pave", json=payload, timeout=10.0)
                        r.raise_for_status()
                        response_data = r.json()
                        logging.info(f"[MCP] JobTread API response: {json.dumps(response_data, indent=2)}")
                        data = response_data.get("data", {}).get("projects", []) if "data" in response_data else []
                        if not data:
                            data = response_data.get("value", [])  # Fallback for Pave-like structure
            except httpx.RequestError as e:
                logging.warning(f"[JobTread API request error, using fallback]: {e}")
                data = DEMO_PROJECTS
            except Exception as e:
                logging.warning(f"[JobTread API error, using fallback]: {e}")
                data = DEMO_PROJECTS

            results = []
            if tool_name == "search":
                query = args.get("query", "").lower()
                results = [p for p in data if query in json.dumps(p).lower()][:5]
            elif tool_name == "fetch":
                project_id = args.get("id", "")
                results = [p for p in data if p.get("id") == project_id]
            else:
                logging.error(f"[MCP] Unknown tool: {tool_name}")
                yield json.dumps({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32600, "message": f"Invalid tool: {tool_name}"}
                }) + "\n"
                return

            logging.info(f"[MCP] Tool {tool_name} executed, results: {len(results)}")
            for i, result in enumerate(results):
                yield json.dumps({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps([result], indent=2)
                            }
                        ],
                        "isFinal": i == len(results) - 1
                    }
                }) + "\n"
                await asyncio.sleep(0.1)  # Simulate streaming delay

        return StreamingResponse(stream_results(), media_type="application/json")

    # 5. Fallback for unknown methods
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
