from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict
import logging

from app.services.amendment_service import amendment_service
from app.services.document_generator import enhanced_document_generator

router = APIRouter()
logger = logging.getLogger(__name__)

class CreateAmendmentRequest(BaseModel):
    contract_id: str
    user_id: str
    changes: List[Dict]

@router.post("/create")
async def create_amendment(request: CreateAmendmentRequest):
    """Create new amendment"""
    try:
        result = await amendment_service.create_amendment(
            request.contract_id,
            request.user_id,
            request.changes
        )
        return {"success": True, **result}
        
    except Exception as e:
        logger.error(f"Create amendment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{amendment_id}")
async def get_amendment(amendment_id: str, user_id: str):
    """Get amendment details"""
    try:
        result = await amendment_service.get_amendment_details(amendment_id, user_id)
        return {"success": True, **result}
        
    except Exception as e:
        logger.error(f"Get amendment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contract/{contract_id}/list")
async def list_amendments(contract_id: str, user_id: str):
    """List all amendments for a contract"""
    try:
        amendments = await amendment_service.list_amendments(contract_id, user_id)
        return {
            "success": True,
            "amendments": amendments,
            "count": len(amendments)
        }
        
    except Exception as e:
        logger.error(f"List amendments failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{amendment_id}/generate-pdf")
async def generate_pdf(amendment_id: str, user_id: str):
    """Generate and download PDF with color-coded changes"""
    try:
        pdf_path = await enhanced_document_generator.generate_amendment_pdf(amendment_id, user_id)
        
        return FileResponse(
            pdf_path,
            media_type='application/pdf',
            filename=f"amendment_{amendment_id}.pdf"
        )
        
    except Exception as e:
        logger.error(f"Generate PDF failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{amendment_id}/approve")
async def approve_amendment(amendment_id: str, user_id: str):
    """Approve amendment"""
    try:
        from app.config.gcp_clients import get_db_pool
        import uuid
        
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            # Verify ownership
            amendment = await conn.fetchrow("""
                SELECT a.* FROM amendments a
                JOIN contracts c ON a.contract_id = c.id
                WHERE a.id = $1 AND c.user_id = $2
            """, uuid.UUID(amendment_id), user_id)
            
            if not amendment:
                raise HTTPException(status_code=404, detail="Amendment not found")
            
            # Update status
            await conn.execute("""
                UPDATE amendments SET status = 'approved' WHERE id = $1
            """, uuid.UUID(amendment_id))
        
        return {"success": True, "message": "Amendment approved"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve amendment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
