#!/usr/bin/env python3
"""
MCP Protocol Compatible JobTread Server
Fully compatible with ChatGPT Connectors
"""

import os
import json
import logging
from typing import Any, Dict, List
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="JobTread MCP Server", version="1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo construction data
DEMO_PROJECTS = [
    {
        "id": "job_demo_1",
        "title": "Kitchen Remodel - Smith Residence",
        "text": "Complete kitchen renovation including new cabinets, countertops, and appliances. Budget: $50,000. Status: In Progress. Customer: John Smith. Location: 123 Oak Street, Dallas, TX.",
        "url": "https://app.jobtread.com/jobs/demo_1",
        "metadata": {"type": "residential", "budget": 50000, "status": "in_progress", "customer": "John Smith"}
    },
    {
        "id": "job_demo_2", 
        "title": "Office Building Renovation - Downtown",
        "text": "Commercial office space renovation for tech startup. Budget: $250,000. Status: Planning phase. Customer: TechCorp Inc. Location: Downtown Dallas Business District.",
        "url": "https://app.jobtread.com/jobs/demo_2",
        "metadata": {"type": "commercial", "budget": 250000, "status": "planning", "customer": "TechCorp Inc"}
    },
    {
        "id": "job_demo_3",
        "title": "Bathroom Remodel - Johnson Home",
        "text": "Master bathroom renovation with luxury finishes. Budget: $35,000. Status: Completed. Customer: Sarah Johnson. Project included new tile, vanity, and fixtures.",
        "url": "https://app.jobtread.com/jobs/demo_3", 
        "metadata": {"type": "residential", "budget": 35000, "status": "completed", "customer": "Sarah Johnson"}
    }
]

DEMO_CUSTOMERS = [
    {
        "id": "customer_demo_1",
        "title": "John Smith - Residential Customer",
        "text": "Long-term residential customer with 3 completed projects. Total project value: $125,000. Excellent payment history. Prefers modern design styles.",
        "url": "https://app.jobtread.com/customers/demo_1",
        "metadata": {"type": "residential", "projects": 3, "total_value": 125000, "status": "active"}
    },
    {
        "id": "customer_demo_2",
        "title": "TechCorp Inc - Commercial Client", 
        "text": "Growing tech company needing office renovations. Budget range: $200k-500k. Focus on modern, collaborative workspaces. Fast decision-making process.",
        "url": "https://app.jobtread.com/customers/demo_2",
        "metadata": {"type": "commercial", "projects": 1, "total_value": 250000, "status": "active"}
    }
]

def search_demo_data(query: str) -> List[Dict]:
    """Search through demo construction data"""
    query_lower = query.lower()
    results = []
    
    # Search projects
    for project in DEMO_PROJECTS:
        if (query_lower in project["title"].lower() or 
            query_lower in project["text"].lower() or
            query_lower in str(project["metadata"].get("budget", "")).lower() or
            query_lower in project["metadata"].get("status", "").lower() or
            query_lower in project["metadata"].get("customer", "").lower()):
            results.append(project)
    
    # Search customers
    for customer in DEMO_CUSTOMERS:
        if (query_lower in customer["title"].lower() or 
            query_lower in customer["text"].lower() or
            query_lower in customer["metadata"].get("type", "").lower()):
            results.append(customer)
    
    # If no matches, return some sample data
    if not results:
        results = DEMO_PROJECTS[:2]
    
    return results

def fetch_demo_item(item_id: str) -> Dict:
    """Fetch detailed information for a specific item"""
    # Find in projects
    for project in DEMO_PROJECTS:
        if project["id"] == item_id:
            # Return enhanced detail for fetch requests
            enhanced = project.copy()
            enhanced["text"] = f"""# {project['title']}

## Project Overview
- **Budget:** ${project['metadata']['budget']:,}
- **Status:** {project['metadata']['status'].title()}
- **Customer:** {project['metadata']['customer']}
- **Type:** {project['metadata']['type'].title()}

## Project Details
{project['text']}

## Recent Activity
- Project planning completed
- Materials ordered and delivered
- Work crew assigned
- Permits obtained

## Next Steps
- Continue with scheduled installation
- Quality control inspections
- Customer progress review meeting

*This is demo data for testing the MCP construction connector.*"""
            return enhanced
    
    # Find in customers
    for customer in DEMO_CUSTOMERS:
        if customer["id"] == item_id:
            enhanced = customer.copy()
            enhanced["text"] = f"""# {customer['title']}

## Customer Information
- **Type:** {customer['metadata']['type'].title()} Client
- **Total Projects:** {customer['metadata']['projects']}
- **Total Value:** ${customer['metadata']['total_value']:,}
- **Status:** {customer['metadata']['status'].title()}

## Details
{customer['text']}

## Project History
- All projects completed on time and within budget
- Excellent communication throughout projects
- Referred 2 new customers to Vino Design Build
- Prefers email communication for updates

*This is demo data for testing the MCP construction connector.*"""
            return enhanced
    
    # Default response if not found
    return {
        "id": item_id,
        "title": f"Demo Construction Item: {item_id}",
        "text": f"""# Demo Construction Project

## Project Overview
This is a demo construction project for testing the MCP connector.

**Item ID:** {item_id}
**Type:** Construction Project
**Status:** Demo Mode

## Features Demonstrated
- AI-powered search of construction data
- Detailed project information retrieval  
- Integration with ChatGPT for natural language queries
- Real-time access to project databases

## Business Value
- Instant project insights via AI
- Natural language business intelligence
- Competitive advantage through AI integration
- Enhanced client communication capabilities

*Connect your real JobTread API key to access live project data.*""",
        "url": f"https://app.jobtread.com/items/{item_id}",
        "metadata": {"type": "demo", "status": "testing"}
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "JobTread MCP Server is running",
        "version": "1.0",
        "protocol": "Model Context Protocol",
        "endpoints": ["/health", "/sse/", "/tools"],
        "description": "AI-powered construction data connector for ChatGPT"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "JobTread MCP Server"}

@app.get("/sse/")
async def sse_get():
    """SSE endpoint GET - return server info"""
    return {
        "protocol": "Model Context Protocol",
        "version": "1.0",
        "server": "JobTread Construction Data",
        "tools": ["search", "fetch"],
        "description": "Access construction project data and customer information"
    }

@app.post("/sse/")
async def sse_post(request: Request):
    """Main MCP protocol endpoint"""
    try:
        body = await request.json()
        logger.info(f"MCP Request: {body}")
        
        # Handle MCP protocol requests
        if "method" in body:
            method = body["method"]
            params = body.get("params", {})
            
            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "search",
                                "description": "Search construction projects, customers, and data",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "Search terms for construction data"
                                        }
                                    },
                                    "required": ["query"]
                                }
                            },
                            {
                                "name": "fetch",
                                "description": "Fetch detailed information about a specific construction item",
                                "inputSchema": {
                                    "type": "object", 
                                    "properties": {
                                        "id": {
                                            "type": "string",
                                            "description": "Unique identifier for the construction item"
                                        }
                                    },
                                    "required": ["id"]
                                }
                            }
                        ]
                    }
                }
                return response
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "search":
                    query = arguments.get("query", "")
                    results = search_demo_data(query)
                    response = {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(results, indent=2)
                                }
                            ]
                        }
                    }
                    return response
                
                elif tool_name == "fetch":
                    item_id = arguments.get("id", "")
                    result = fetch_demo_item(item_id)
                    response = {
                        "jsonrpc": "2.0", 
                        "id": body.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2)
                                }
                            ]
                        }
                    }
                    return response
        
        # Default response
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found"
            }
        }
        
    except Exception as e:
        logger.error(f"MCP Error: {e}")
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

@app.get("/tools")
async def list_tools():
    """List available tools"""
    return {
        "tools": [
            {
                "name": "search",
                "description": "Search construction projects and customers",
                "parameters": {"query": "string"}
            },
            {
                "name": "fetch", 
                "description": "Fetch detailed item information",
                "parameters": {"id": "string"}
            }
        ]
    }

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    host = "0.0.0.0"
    
    logger.info(f"Starting MCP-Compatible JobTread Server on {host}:{port}")
    logger.info("Demo mode - using sample construction data")
    logger.info("Ready for ChatGPT MCP connector integration")
    
    uvicorn.run(app, host=host, port=port, log_level="info")
