import logging
from fastapi import APIRouter, status
from pydantic import BaseModel
from app.services.ai import parse_icp_query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["icp"])

class ParseICPRequest(BaseModel):
    query: str

@router.post("/icp/parse", status_code=status.HTTP_200_OK)
async def parse_icp_filters(request: ParseICPRequest):
    """
    Parses a natural language query into structured ICP filters using AI.
    """
    logger.info(f"Parsing ICP query: {request.query}")
    filters = await parse_icp_query(request.query)
    return {"status": "success", "filters": filters}
