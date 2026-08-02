import json
import logging

import google.generativeai as genai
import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.auth import verify_tenant
from app.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.database import get_redis
from app.services.ai import parse_icp_query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["icp"])

class ParseICPRequest(BaseModel):
    query: str

class ICPQuery(BaseModel):
    prompt: str
    account_id: str | None = None

@router.post("/icp/parse", status_code=status.HTTP_200_OK)
async def parse_icp_filters(
    request: ParseICPRequest,
    tenant_id: str = Depends(verify_tenant),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Parses a natural language query into structured ICP filters using AI.
    Requires authentication, is rate-limited per tenant, and every request
    is audit-logged - same authorization model as /api/v1/apollo/search.
    """
    await enforce_rate_limit(
        redis,
        key=f"ratelimit:icp:{tenant_id}",
        limit=settings.ICP_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    logger.info(f"AUDIT icp_parse tenant_id={tenant_id}")

    logger.info(f"Parsing ICP query: {request.query}")
    filters = await parse_icp_query(request.query)
    return {"status": "success", "filters": filters}

@router.post("/icp/preview", status_code=status.HTTP_200_OK)
async def preview_icp(
    request: ICPQuery,
    tenant_id: str = Depends(verify_tenant),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Bypasses data broker limitations by generating a Unipile JSON payload via Gemini,
    then calling the Unipile LinkedIn search endpoint to fetch live data directly.
    Requires authentication, is rate-limited per tenant, and every request
    is audit-logged - same authorization model as /api/v1/apollo/search.
    """
    await enforce_rate_limit(
        redis,
        key=f"ratelimit:icp:{tenant_id}",
        limit=settings.ICP_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    logger.info(f"AUDIT icp_preview tenant_id={tenant_id}")

    if not settings.UNIPILE_API_KEY:
        raise HTTPException(status_code=500, detail="UNIPILE_API_KEY is not configured.")
        
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    account_id = request.account_id or settings.UNIPILE_ACCOUNT_ID
    if not account_id:
        raise HTTPException(status_code=400, detail="Unipile account_id must be provided.")

    logger.info(f"Generating Unipile preview for prompt: {request.prompt}")
    
    # Use Gemini to map the natural language query to a standard LinkedIn Search URL
    system_prompt = """
    You are an expert at mapping user intents to LinkedIn Search URLs.
    The user will give you a natural language prompt about who they want to find.
    You must construct a valid standard LinkedIn search URL.
    
    CRITICAL: Do not use too many facets or long lists of titles, as it will trigger a "Content too large" error from the provider.
    Keep the URL simple, mostly relying on the `keywords` parameter.
    
    Example output format:
    {
      "url": "https://www.linkedin.com/search/results/people/?keywords=software%20engineer"
    }
    
    Ensure you return a raw JSON object with NO markdown ticks.
    """
    
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        response = await model.generate_content_async(
            f"User Prompt: {request.prompt}",
            generation_config=genai.GenerationConfig(response_mime_type="application/json")
        )
        search_payload = json.loads(response.text.strip())
        
    except Exception as e:
        logger.error(f"Failed to generate Unipile payload via Gemini: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse search query")

    # Call Unipile LinkedIn Search API
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": settings.UNIPILE_API_KEY
    }
    url = f"{settings.UNIPILE_BASE_URL}/linkedin/search?account_id={account_id}"
    
    logger.info(f"Sending payload to Unipile: {search_payload}")
    
    try:
        async with httpx.AsyncClient() as client:
            unipile_res = await client.post(url, headers=headers, json=search_payload, timeout=30.0)
            
            if unipile_res.status_code != 200:
                logger.error(f"Unipile API error: {unipile_res.text}")
                raise HTTPException(status_code=unipile_res.status_code, detail="Error fetching from Unipile API")
                
            data = unipile_res.json()
            items = data.get("items", [])
            
            # Extract requested fields: id, first_name, last_name, title (from headline), linkedin_url
            preview_leads = []
            for p in items:
                # Unipile response often includes full name, we might need to split it if first/last aren't distinct
                first_name = p.get("first_name", "")
                last_name = p.get("last_name", "")
                name = p.get("name", "")
                if not first_name and name:
                    parts = name.split(" ", 1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ""

                headline = p.get("headline") or ""
                
                company = p.get("company_name", p.get("current_company_name", ""))
                company_domain = p.get("company_domain", p.get("current_company_domain", ""))
                if not company and " at " in headline:
                    company = headline.split(" at ")[-1].strip()
                
                preview_leads.append({
                    "id": p.get("id"), # Unipile search returns 'id' directly
                    "first_name": first_name,
                    "last_name": last_name,
                    "title": headline,
                    "company": company,
                    "company_domain": company_domain,
                    "linkedin_url": p.get("public_profile_url", p.get("profile_url", "")),
                    "email": "" 
                })
                
            return {"status": "success", "leads": preview_leads}
            
    except httpx.RequestError as e:
        logger.error(f"HTTP Request failed for Unipile: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to Unipile API")
