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
logging.basicConfig(level=logging.INFO)

# Enable CORS for OpenAI Tools
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
    return {"status": "ok", "message": "JobTread MCP server running"}

@app.get("/sse/")
async def sse_stream(request: Request) -> StreamingResponse:
    async def event_generator():
        yield 'data: {"status": "connected"}\n\n'
        try:
            while True:
                if await request.is_disconnected():
                    break
                yield 'data: {"type": "heartbeat"}\n\n'
                await asyncio.sleep(30)
        except Exception as e:
            logging.error(f"SSE error: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/sse/")
async def sse(request: Request):
    body = await request.json()
    logging.info(f"[MCP] Incoming request: {json.dumps(body)}")

    method = body.get("method")
    rpc_id = body.get("id", None)  # Notifications may lack id

    # 1. MCP Handshake (initialize)
    if method == "initialize":
        params = body.get("params", {})
        client_protocol = params.get("protocolVersion", "2025-03-26")  # Default if missing
        # Echo the client's protocolVersion (assume supported; add version check if needed)
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": client_protocol,  # Echo or set to supported version
                "capabilities": {
                    "tools": {}  # Basic tools support; add "listChanged": true if you support notifications
                },
                "serverInfo": {
                    "name": "JobTread MCP Server",
                    "version": "1.0.0"
                },
                "instructions": "Search JobTread projects using the provided tools."  # Optional
            }
        }

    # Handle 'initialized' notification (client sends this after your response; no reply needed)
    if method == "initialized":
        logging.info("[MCP] Received 'initialized' notification from client")
        return {}  # No response for notifications

    # 2. Declare tools
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "tools": [
                    {
                        "name": "search",
                        "description": "Search JobTread construction projects",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search term"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        }

    # 3. Tool Execution
    if method == "tools/call":
        try:
            tool = body["params"]["name"]
            args = body["params"]["arguments"]
            query = args.get("query", "").lower()

            token = os.getenv("JOBTREAD_ACCESS_TOKEN")
            headers = {"Authorization": f"Bearer {token}"}

            async with httpx.AsyncClient() as client:
                r = await client.get("https://api.jobtread.com/v1/projects", headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logging.warning(f"[JobTread API fallback] {e}")
            data = DEMO_PROJECTS

        results = [p for p in data if query in json.dumps(p).lower()][:5]

        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(results, indent=2)
                    }
                ]
            }
        }

    # 4. Fallback for unknown methods
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
