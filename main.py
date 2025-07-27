from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
import json
import logging

app = FastAPI()

# Logging
logging.basicConfig(level=logging.INFO)

# Allow everything
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ready"}

@app.post("/sse/")
async def sse(request: Request):
    body = await request.json()
    logging.info(f"Incoming: {body}")

    method = body.get("method")
    rpc_id = body.get("id", None)

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

    elif method == "tools/call":
        tool = body["params"]["name"]
        args = body["params"]["arguments"]
        query = args.get("query", "").lower()

        try:
            token = os.environ["JOBTREAD_ACCESS_TOKEN"]
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                r = await client.get("https://api.jobtread.com/v1/projects", headers=headers)
                data = r.json()
        except Exception as e:
            logging.error(f"JobTread API error: {e}")
            data = [{"id": "demo", "name": "Demo Project", "budget": 50000}]

        # Filter results
        results = [
            p for p in data if query in json.dumps(p).lower()
        ][:5]

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

    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {
            "code": -32601,
            "message": "Method not found"
        }
    }
