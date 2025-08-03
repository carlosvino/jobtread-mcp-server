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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo data
DEMO_PROJECTS = [
    {"id": "demo_1", "name": "Smith Kitchen Remodel", "budget": 50000, "status": "in_progress"},
    {"id": "demo_2", "name": "TechCorp Office Renovation", "budget": 250000, "status": "planning"}
]

# Tools for ChatGPT
TOOLS = [
    {
        "name": "search",
        "description": "Search construction projects",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"}
            },
            "additionalProperties": False
        }
    },
    {
        "name": "list_jobs",
        "description": "List all jobs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"}
            },
            "additionalProperties": False
        }
    }
]

def get_credentials():
    grant_key = os.getenv("JOBTREAD_GRANT_KEY") or os.getenv("JOBTREAD_ACCESS_TOKEN")
    org_id = os.getenv("JOBTREAD_ORG_ID")
    return grant_key, org_id

async def handle_search(query="", limit=10):
    logging.info(f"Search: {query}")
    if not query:
        return DEMO_PROJECTS[:limit]
    
    results = []
    for project in DEMO_PROJECTS:
        if query.lower() in project['name'].lower():
            results.append(project)
    return results[:limit] if results else DEMO_PROJECTS[:limit]

async def handle_list_jobs(limit=10):
    logging.info(f"List jobs: {limit}")
    return DEMO_PROJECTS[:limit]

@app.get("/")
@app.get("/health")
async def health():
    grant_key, org_id = get_credentials()
    return {
        "status": "ok",
        "credentials_found": bool(grant_key and org_id)
    }

@app.get("/sse/")
async def sse_stream(request: Request):
    async def generator():
        yield 'data: {"status": "connected"}\n\n'
        while True:
            if await request.is_disconnected():
                break
            yield 'data: {"type": "heartbeat"}\n\n'
            await asyncio.sleep(30)
    return StreamingResponse(generator(), media_type="text/event-stream")

@app.post("/sse/")
async def mcp_handler(request: Request):
    try:
        body = await request.json()
        method = body.get("method")
        rpc_id = body.get("id")
        
        logging.info(f"MCP: {method}")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False, "callable": True}},
                    "serverInfo": {"name": "JobTread MCP Server", "version": "2.0.0"}
                }
            }
        
        if method == "notifications/initialized":
            return {}
        
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": TOOLS}
            }
        
        if method == "tools/call":
            params = body.get("params", {})
            tool_name = params.get("name")
            args = params.get("arguments", {})
            
            if tool_name == "search":
                result = await handle_search(args.get("query", ""), args.get("limit", 10))
            elif tool_name == "list_jobs":
                result = await handle_list_jobs(args.get("limit", 10))
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }
            
            async def stream_result():
                yield json.dumps({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }],
                        "isFinal": True
                    }
                }) + "\n"
            
            return StreamingResponse(stream_result(), media_type="application/json")
        
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }
        
    except Exception as e:
        logging.error(f"MCP Error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error"}
        }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
