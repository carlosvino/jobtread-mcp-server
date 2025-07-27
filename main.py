#!/usr/bin/env python3
"""
Simplified JobTread MCP Server for Railway deployment
"""

import os
import json
import logging
from typing import Any, Dict, List
import asyncio
import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="JobTread MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JobTreadAPI:
    def __init__(self):
        self.api_key = os.getenv('JOBTREAD_API_KEY', 'demo_key')
        self.org_id = os.getenv('JOBTREAD_ORG_ID', 'demo_org')
        self.base_url = "https://api.jobtread.com/pave"
        logger.info(f"JobTread API initialized")
    
    async def search_projects(self, query: str) -> List[Dict]:
        """Search for projects - simplified for testing"""
        # For now, return mock data until we get real API credentials
        return [
            {
                "id": "job_demo_1",
                "title": f"Demo Project: Kitchen Remodel (searched: {query})",
                "text": "Demo construction project for testing MCP connector",
                "url": "https://app.jobtread.com/jobs/demo_1",
                "metadata": {"type": "demo", "budget": 50000}
            },
            {
                "id": "customer_demo_1", 
                "title": f"Demo Customer: John Smith (searched: {query})",
                "text": "Demo customer for testing MCP connector",
                "url": "https://app.jobtread.com/customers/demo_1",
                "metadata": {"type": "demo", "projects": 3}
            }
        ]
    
    async def fetch_item(self, item_id: str) -> Dict:
        """Fetch item details - simplified for testing"""
        if item_id.startswith('job_'):
            return {
                "id": item_id,
                "title": "Demo Construction Project",
                "text": """# Demo Kitchen Remodel Project

## Project Details
- **Budget:** $50,000
- **Status:** In Progress
- **Customer:** John Smith
- **Location:** 123 Main St, Dallas, TX

## Tasks
- Demolition (Completed)
- Electrical work (In Progress)
- Plumbing (Pending)
- Installation (Pending)

## Materials
- Cabinets: $15,000
- Appliances: $12,000
- Countertops: $8,000
- Labor: $15,000
""",
                "url": f"https://app.jobtread.com/jobs/{item_id}",
                "metadata": {"budget": 50000, "status": "in_progress"}
            }
        else:
            return {
                "id": item_id,
                "title": "Demo Customer",
                "text": "Demo customer information for testing",
                "url": f"https://app.jobtread.com/customers/{item_id}",
                "metadata": {"type": "customer"}
            }

# Initialize API client
api_client = JobTreadAPI()

@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "JobTread MCP Server is running", "version": "1.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "JobTread MCP Server"}

@app.post("/mcp/search")
async def mcp_search(request: Dict[str, Any]):
    """MCP search endpoint"""
    try:
        query = request.get("query", "")
        results = await api_client.search_projects(query)
        return {"results": results}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"error": str(e)}

@app.post("/mcp/fetch") 
async def mcp_fetch(request: Dict[str, Any]):
    """MCP fetch endpoint"""
    try:
        item_id = request.get("id", "")
        result = await api_client.fetch_item(item_id)
        return result
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return {"error": str(e)}

@app.get("/sse/")
async def sse_endpoint():
    """SSE endpoint for MCP protocol"""
    return {"message": "MCP SSE endpoint - use POST for actual MCP calls"}

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"Starting JobTread MCP Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
