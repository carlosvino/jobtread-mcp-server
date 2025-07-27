from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
import json
import logging

app = FastAPI()

# Logging
logging.basicConfig(level=logging.INFO)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health route for Railway
@app.get("/")
async def root():
    return {"status": "ok", "message": "JobTread MCP server running"}

# MCP entry point
@app.post("/sse/")
async def sse(request: Request):
    body = await request.json()
    logging.info(f"Incoming MCP: {body}")

    method = body.get("method")
    rpc_id = body.get("id")

    # Tool registration
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
                                    "description": "Keywords to search"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        }

    # Tool execution
    elif method == "tools/call":
        try:
            tool = body["params"]["name"]
            args = body["params"]["arguments"]
            query = args.get("query", "").lower()

            token = os.environ["JOBTREAD_ACCESS_TOKEN"]
            headers = {"Authorization": f"Bearer {token}"}

            async with httpx.AsyncClient() as client:
                r = await client.get("https://api.jobtread.com/v1/projects", headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logging.error(f"[JobTread API error] {e}")
            data = [{"id": "demo", "name": "Demo Project", "budget": 50000}]

        # Basic keyword filtering
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

    # Fallback
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not found"
        }
    }
@app.get("/health")
async def health():
    return {"status": "healthy"}
