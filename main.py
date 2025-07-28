from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
import json
import logging
import uvicorn

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Enable CORS (required for ChatGPT MCP)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sample fallback projects (for when JobTread API fails)
DEMO_PROJECTS = [
    {"id": "demo_1", "name": "Smith Kitchen Remodel", "budget": 50000, "status": "in_progress"},
    {"id": "demo_2", "name": "TechCorp Office Renovation", "budget": 250000, "status": "planning"},
]

@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "message": "JobTread MCP server running"}

@app.post("/sse/")
async def sse(request: Request):
    body = await request.json()
    logging.info(f"[MCP] Incoming: {json.dumps(body)}")

    method = body.get("method")
    rpc_id = body.get("id", "unknown")

    # MCP Handshake
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "title": "JobTread Connector",
                "description": "Search JobTread project data",
                "version": "1.0.0",
                "capabilities": {
                    "callable": True
                },
                "serverInfo": {
                    "name": "JobTread MCP Server",
                    "version": "1.0.0"
                }
            }
        }

    # Register tool(s)
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

    # Execute tool
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
            logging.warning(f"[JobTread fallback] {e}")
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

    # Unsupported methods
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
