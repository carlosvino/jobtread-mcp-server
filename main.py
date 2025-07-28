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

# JobTread Schema Mapping (subset for brevity, expand as needed)
JOBTREAD_SCHEMA = {
    "queries": {
        "account": {"input": {"id": "string"}, "output": {"id": "string", "name": "string", "isTaxable": "boolean"}},
        "job": {"input": {"id": "string"}, "output": {"id": "string", "name": "string", "description": "string"}},
        "document": {"input": {"id": "string"}, "output": {"id": "string", "name": "string", "type": "string"}},
    },
    "mutations": {
        "createAccount": {"input": {"organizationId": "string", "name": "string", "type": "string"}, "output": {"id": "string", "name": "string"}},
        "createJob": {"input": {"name": "string", "description": "string", "organizationId": "string"}, "output": {"id": "string", "name": "string"}},
        "updateAccount": {"input": {"id": "string", "name": "string"}, "output": {"id": "string", "name": "string"}},
        "deleteAccount": {"input": {"id": "string"}, "output": {"success": "boolean"}},
    },
    "other": {
        "signQuery": {"input": {"query": "string"}, "output": {"token": "string"}},
    }
}

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

    if method == "notifications/initialized":
        logging.info("[MCP] Received 'notifications/initialized'")
        return {}

    if method == "tools/list":
        logging.info("[MCP] Tools/list requested")
        tools = []
        for category, operations in JOBTREAD_SCHEMA.items():
            for op_name, op_details in operations.items():
                tool = {
                    "name": op_name,
                    "description": f"Perform {category.replace('queries', 'query').replace('mutations', 'action')} {op_name} on JobTread",
                    "inputSchema": {
                        "type": "object",
                        "properties": {k: {"type": v} for k, v in op_details["input"].items()},
                        "required": list(op_details["input"].keys()),
                        "additionalProperties": False
                    },
                    "responseSchema": {
                        "type": "object" if category == "mutations" or category == "other" else "array",
                        "properties": op_details["output"] if category in ["mutations", "other"] else {"items": {"type": "object", "properties": op_details["output"]}}
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
                grant_key = os.getenv("JOBTREAD_GRANT_KEY")
                org_id = os.getenv("JOBTREAD_ORG_ID")
                logging.info(f"[MCP] Detected JOBTREAD_GRANT_KEY: {grant_key or 'None'}, JOBTREAD_ORG_ID: {org_id or 'None'}")
                if not grant_key or not org_id:
                    logging.warning("[MCP] Missing JOBTREAD credentials, using demo data")
                    data = DEMO_PROJECTS if tool_name in JOBTREAD_SCHEMA["queries"] else [{"error": "Cannot proceed without credentials"}] if tool_name in JOBTREAD_SCHEMA["mutations"] else [{}]
                else:
                    payload = {}
                    if tool_name in JOBTREAD_SCHEMA["queries"]:
                        payload = {
                            "organization": {
                                "$": {"grantKey": grant_key, "id": org_id},
                                tool_name: {
                                    "$": {k: v for k, v in args.items() if k in JOBTREAD_SCHEMA["queries"][tool_name]["input"]},
                                    "nodes": JOBTREAD_SCHEMA["queries"][tool_name]["output"]
                                }
                            }
                        }
                    elif tool_name in JOBTREAD_SCHEMA["mutations"]:
                        payload = {
                            tool_name: {
                                "$": {"grantKey": grant_key, **{k: v for k, v in args.items() if k in JOBTREAD_SCHEMA["mutations"][tool_name]["input"]}},
                                JOBTREAD_SCHEMA["mutations"][tool_name]["output"].keys(): {}
                            }
                        }
                    elif tool_name in JOBTREAD_SCHEMA["other"]:
                        payload = {
                            tool_name: {
                                "$": args,
                                JOBTREAD_SCHEMA["other"][tool_name]["output"].keys(): {}
                            }
                        }
                    logging.info(f"[MCP] Sending payload to JobTread: {json.dumps(payload, indent=2)}")
                    async with httpx.AsyncClient() as client:
                        r = await client.post("https://api.jobtread.com/pave", json=payload, timeout=10.0)
                        try:
                            r.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            logging.error(f"[JobTread API error {e.response.status_code}]: {e.response.text}")
                            raise
                        response_data = r.json()
                        logging.info(f"[MCP] JobTread API response: {json.dumps(response_data, indent=2)}")
                        if tool_name in JOBTREAD_SCHEMA["queries"]:
                            data = response_data.get("organization", {}).get(tool_name, {}).get("nodes", [])
                            if not data:
                                data = response_data.get("data", {}).get(tool_name, {}).get("nodes", [])
                        elif tool_name in JOBTREAD_SCHEMA["mutations"]:
                            data = response_data.get(tool_name, {})
                        else:
                            data = response_data.get(tool_name, {})

                results = [data] if isinstance(data, dict) else data
                if tool_name in JOBTREAD_SCHEMA["queries"] and not results:
                    results = []  # Ensure empty list for no matches
                elif tool_name in JOBTREAD_SCHEMA["queries"] and len(results) > 1 and "id" in args:
                    results = [r for r in results if r.get("id") == args.get("id", "")]  # Filter by ID for fetch-like queries

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
                    await asyncio.sleep(0.1)

            except Exception as e:
                logging.error(f"[MCP] Unexpected error: {e}")
                yield json.dumps({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32000, "message": f"Internal error: {str(e)}"}
                }) + "\n"

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
