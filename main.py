async def call_jobtread_api(operation: str, params: dict = None):
    """
    Call JobTread API with corrected payload format based on Railway logs
    """
    grant_key, org_id = get_jobtread_credentials()
    
    if not grant_key or not org_id:
        logging.warning("[JobTread] Missing credentials, returning demo data")
        return DEMO_PROJECTS
    
    if params is None:
        params = {}
    
    # Based on Railway logs, JobTread /pave endpoint expects GraphQL-style queries
    # The "A valid query is required" error suggests we need proper query structure
    
    payload_strategies = [
        # Strategy 1: Corrected GraphQL-style query for /pave endpoint
        {
            "url": "https://api.jobtread.com/pave",
            "payload": {
                "query": f"""
                {{
                    organization(grantKey: "{grant_key}", id: "{org_id}") {{
                        jobs(first: {params.get('limit', 10)}) {{
                            nodes {{
                                id
                                name
                                description
                                status
                                budget
                                createdAt
                                updatedAt
                            }}
                        }}
                    }}
                }}
                """.strip()
            }
        },
        
        # Strategy 2: Alternative GraphQL format
        {
            "url": "https://api.jobtread.com/pave",
            "payload": {
                "operationName": "GetJobs",
                "variables": {
                    "grantKey": grant_key,
                    "organizationId": org_id,
                    "first": params.get('limit', 10)
                },
                "query": """
                query GetJobs($grantKey: String!, $organizationId: String!, $first: Int) {
                    organization(grantKey: $grantKey, id: $organizationId) {
                        jobs(first: $first) {
                            nodes {
                                id
                                name
                                description
                                status
                                budget
                            }
                        }
                    }
                }
                """
            }
        },
        
        # Strategy 3: JobTread's custom query format (based on Zapier examples)
        {
            "url": "https://api.jobtread.com/pave",
            "payload": {
                "grantKey": grant_key,
                "organizationId": org_id,
                "query": {
                    "organization": {
                        "jobs": {
                            "nodes": {
                                "id": True,
                                "name": True,
                                "description": True,
                                "status": True,
                                "budget": True
                            }
                        }
                    }
                },
                "variables": params
            }
        },
        
        # Strategy 4: Simple REST-like format with proper headers
        {
            "url": "https://api.jobtread.com/graphql",  # Try GraphQL endpoint
            "headers": {
                "Authorization": f"Bearer {grant_key}",
                "X-Organization-ID": org_id,
                "Content-Type": "application/json"
            },
            "payload": {
                "query": f"""
                {{
                    jobs(first: {params.get('limit', 10)}) {{
                        id
                        name
                        description
                        status
                        budget
                    }}
                }}
                """
            }
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, strategy in enumerate(payload_strategies):
            try:
                logging.info(f"[JobTread] Trying corrected strategy {i+1} for {operation}")
                
                headers = strategy.get("headers", {"Content-Type": "application/json"})
                
                response = await client.post(
                    strategy["url"],
                    json=strategy["payload"],
                    headers=headers
                )
                
                logging.info(f"[JobTread] Strategy {i+1} response: {response.status_code}")
                logging.info(f"[JobTread] Response body preview: {response.text[:200]}...")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logging.info(f"[JobTread] SUCCESS with strategy {i+1}!")
                        
                        # Parse response based on strategy
                        if i == 0 or i == 1:  # GraphQL responses
                            jobs = data.get("data", {}).get("organization", {}).get("jobs", {}).get("nodes", [])
                            if jobs:
                                return jobs
                            else:
                                return data.get("data", data)
                        elif i == 2:  # Custom format
                            return data.get("organization", {}).get("jobs", {}).get("nodes", [])
                        else:  # REST GraphQL
                            return data.get("data", {}).get("jobs", [])
                            
                    except json.JSONDecodeError as e:
                        logging.warning(f"[JobTread] Strategy {i+1} returned non-JSON: {response.text[:200]}")
                        continue
                        
                elif response.status_code == 400:
                    error_text = response.text
                    logging.error(f"[JobTread] Strategy {i+1} bad request: {error_text}")
                    
                    # If it's still "valid query required", log the exact payload we sent
                    if "valid query" in error_text.lower():
                        logging.error(f"[JobTread] Payload that failed: {json.dumps(strategy['payload'], indent=2)}")
                    continue
                    
                elif response.status_code == 401:
                    logging.error(f"[JobTread] Authentication failed with strategy {i+1} - check Grant Key")
                    continue
                    
                elif response.status_code == 404:
                    logging.warning(f"[JobTread] Endpoint not found with strategy {i+1}: {strategy['url']}")
                    continue
                    
                else:
                    logging.warning(f"[JobTread] Strategy {i+1} failed: {response.status_code} - {response.text[:200]}")
                    continue
                    
            except httpx.RequestError as e:
                logging.error(f"[JobTread] Strategy {i+1} request error: {e}")
                continue
            except Exception as e:
                logging.error(f"[JobTread] Strategy {i+1} unexpected error: {e}")
                continue
    
    # If all strategies failed, return demo data
    logging.warning("[JobTread] All corrected API strategies failed, returning demo data")
    logging.info("[JobTread] Contact JobTread support for API documentation or check grant key permissions")
    return DEMO_PROJECTS

# Enhanced debugging endpoint
@app.get("/debug-jobtread")
async def debug_jobtread():
    """Enhanced debugging endpoint to test JobTread API with detailed logging"""
    grant_key, org_id = get_jobtread_credentials()
    
    if not grant_key or not org_id:
        return {
            "error": "Missing credentials",
            "grant_key_present": bool(grant_key),
            "org_id_present": bool(org_id)
        }
    
    # Test just the /pave endpoint with different payload formats
    test_payloads = [
        {
            "name": "Simple GraphQL",
            "payload": {
                "query": f'{{ organization(grantKey: "{grant_key}", id: "{org_id}") {{ id name }} }}'
            }
        },
        {
            "name": "Jobs Query",
            "payload": {
                "query": f"""
                {{
                    organization(grantKey: "{grant_key}", id: "{org_id}") {{
                        jobs(first: 3) {{
                            nodes {{
                                id
                                name
                            }}
                        }}
                    }}
                }}
                """
            }
        }
    ]
    
    results = []
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for test in test_payloads:
            try:
                response = await client.post(
                    "https://api.jobtread.com/pave",
                    json=test["payload"],
                    headers={"Content-Type": "application/json"}
                )
                
                results.append({
                    "test": test["name"],
                    "status": response.status_code,
                    "response": response.text[:300] + "..." if len(response.text) > 300 else response.text
                })
                
            except Exception as e:
                results.append({
                    "test": test["name"],
                    "error": str(e)
                })
    
    return {
        "credentials": {"grant_key_present": True, "org_id_present": True},
        "test_results": results
    }
