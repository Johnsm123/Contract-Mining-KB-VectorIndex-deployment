from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from app.services.rag_service import rag_service

router = APIRouter()
logger = logging.getLogger(__name__)

class SemanticSearchRequest(BaseModel):
    query: str
    user_id: str
    top_k: int = 10

@router.post("/semantic")
async def semantic_search(request: SemanticSearchRequest):
    """Semantic search using GCP Knowledge Base"""
    try:
        result = await rag_service.retrieve_and_generate(request.query, request.top_k)
        
        return {
            "success": True,
            "query": request.query,
            "results": result.get("relevant_chunks", []),
            "count": len(result.get("relevant_chunks", []))
        }
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class MetadataSearchRequest(BaseModel):
    user_id: str
    contract_id: Optional[str] = None
    year: Optional[int] = None
    payer_id: Optional[str] = None
    hospital_id: Optional[str] = None

class SemanticSearchRequest(BaseModel):
    query: str
    user_id: str
    top_k: int = 10

@router.post("/metadata")
async def search_by_metadata(request: MetadataSearchRequest):
    """Search contracts by metadata"""
    try:
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            query = "SELECT * FROM contracts WHERE user_id = $1"
            params = [request.user_id]
            
            if request.contract_id:
                query += f" AND contract_id ILIKE ${len(params) + 1}"
                params.append(f"%{request.contract_id}%")
            
            if request.year:
                query += f" AND year = ${len(params) + 1}"
                params.append(request.year)
            
            if request.payer_id:
                query += f" AND payer_id ILIKE ${len(params) + 1}"
                params.append(f"%{request.payer_id}%")
            
            if request.hospital_id:
                query += f" AND hospital_id ILIKE ${len(params) + 1}"
                params.append(f"%{request.hospital_id}%")
            
            query += " ORDER BY created_at DESC"
            
            contracts = await conn.fetch(query, *params)
            
            return {
                "success": True,
                "results": [dict(c) for c in contracts],
                "count": len(contracts)
            }
            
    except Exception as e:
        logger.error(f"Metadata search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/semantic")
async def semantic_search(request: SemanticSearchRequest):
    """Semantic search using vector embeddings"""
    try:
        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(request.query)
        
        if not query_embedding:
            raise HTTPException(status_code=503, detail="Embedding service unavailable")
        
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            # Vector similarity search
            results = await conn.fetch("""
                SELECT 
                    cl.contract_id,
                    c.contract_id as contract_name,
                    c.name,
                    cl.line_text,
                    cl.line_number,
                    cl.page_number,
                    (cl.embedding_vector <=> $1::vector) as distance
                FROM contract_lines cl
                JOIN contracts c ON cl.contract_id = c.id
                WHERE c.user_id = $2 
                    AND cl.embedding_vector IS NOT NULL
                ORDER BY cl.embedding_vector <=> $1::vector
                LIMIT $3
            """, query_embedding, request.user_id, request.top_k)
            
            formatted_results = []
            for row in results:
                formatted_results.append({
                    "contract_id": row["contract_name"],
                    "contract_name": row["name"],
                    "line_text": row["line_text"],
                    "line_number": row["line_number"],
                    "page_number": row["page_number"],
                    "similarity_score": float(1 - row["distance"])
                })
            
            return {
                "success": True,
                "query": request.query,
                "results": formatted_results,
                "count": len(formatted_results)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contract/{contract_id}/lines")
async def get_contract_lines(contract_id: str, user_id: str):
    """Get all lines from a contract"""
    try:
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            # Get contract
            contract = await conn.fetchrow("""
                SELECT * FROM contracts 
                WHERE contract_id = $1 AND user_id = $2
            """, contract_id, user_id)
            
            if not contract:
                raise HTTPException(status_code=404, detail="Contract not found")
            
            # Get lines
            lines = await conn.fetch("""
                SELECT line_number, line_text, page_number
                FROM contract_lines
                WHERE contract_id = $1
                ORDER BY line_number
            """, contract['id'])
            
            return {
                "success": True,
                "contract_id": contract_id,
                "contract_name": contract['name'],
                "lines": [dict(line) for line in lines],
                "count": len(lines)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get contract lines failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
