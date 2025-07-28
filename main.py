from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx
import json
import logging
import uvicorn
from fastapi_mcp import FastApiMCP

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Enable CORS for all origins (including OpenAI)
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

# Health check endpoint
@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "message": "JobTread MCP server running"}

# Define the search input model
class SearchInput(BaseModel):
    query: str

# Search endpoint (exposed as MCP tool)
@app.post("/search")
async def search_projects(input: SearchInput):
    query = input.query.lower()
    try:
        token = os.getenv("JOBTREAD_ACCESS_TOKEN")
        if not token:
            raise ValueError("No JOBTREAD_ACCESS_TOKEN found, using demo data")
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.jobtread.com/v1/projects", headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logging.warning(f"[JobTread API fallback] {e}")
        data = DEMO_PROJECTS

    results = [p for p in data if query in json.dumps(p).lower()][:5]
    return {"results": results}

# Initialize and mount MCP
mcp = FastApiMCP(
    app,
    name="JobTread Connector",
    description="Search JobTread construction projects",
    # base_url can be set if needed, but Railway will handle it dynamically
)

mcp.mount()  # Mounts MCP at /mcp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
