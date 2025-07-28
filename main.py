from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
import logging
import uvicorn
from fastmcp import FastMCP

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

# Initialize FastMCP
mcp = FastMCP(name="JobTread MCP Server")

@app.get("/")
@app.get("/health")
async def health():
    logging.info("Health check accessed")
    return {"status": "ok", "message": "JobTread MCP server running"}

@mcp.tool()
async def search(query: str) -> str:
    """Search JobTread construction projects by keyword"""
    logging.info(f"[MCP] Search tool called with query: {query}")
    try:
        token = os.getenv("JOBTREAD_ACCESS_TOKEN")
        if not token:
            logging.warning("[MCP] No JOBTREAD_ACCESS_TOKEN set, using demo data")
            data = DEMO_PROJECTS
        else:
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                r = await client.get("https://api.jobtread.com/v1/projects", headers=headers)
                r.raise_for_status()
                data = r.json()
    except Exception as e:
        logging.warning(f"[JobTread API error, using fallback]: {e}")
        data = DEMO_PROJECTS

    results = [p for p in data if query.lower() in str(p).lower()][:5]
    return str(results)

@mcp.tool()
async def fetch(id: str) -> str:
    """Fetch a specific JobTread project by ID"""
    logging.info(f"[MCP] Fetch tool called with id: {id}")
    try:
        token = os.getenv("JOBTREAD_ACCESS_TOKEN")
        if not token:
            logging.warning("[MCP] No JOBTREAD_ACCESS_TOKEN set, using demo data")
            data = DEMO_PROJECTS
        else:
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                r = await client.get("https://api.jobtread.com/v1/projects", headers=headers)
                r.raise_for_status()
                data = r.json()
    except Exception as e:
        logging.warning(f"[JobTread API error, using fallback]: {e}")
        data = DEMO_PROJECTS

    results = [p for p in data if p.get("id") == id]
    return str(results)

# Mount FastMCP onto FastAPI at /sse/
app.include_router(mcp.fastapi(), prefix="/sse")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
