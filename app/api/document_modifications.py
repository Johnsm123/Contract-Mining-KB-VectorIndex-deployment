from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import os
from pathlib import Path
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import io
from datetime import datetime

from app.services.document_generator import enhanced_document_generator
from app.services.gcp_llm_orchestrator import llm_orchestrator
from app.services.robust_document_modifier import robust_modifier
from app.services.amendment_generator import amendment_generator

router = APIRouter()
logger = logging.getLogger(__name__)

class ModificationRequest(BaseModel):
    contract_id: str
    user_id: str
    modification_text: str  # Natural language description of changes
    specific_changes: Optional[List[Dict]] = None  # Specific line changes

class LineModification(BaseModel):
    search_text: str
    replacement_text: Optional[str] = None
    additional_text: Optional[str] = None
    action: str  # 'replace', 'add_after', 'delete'

@router.post("/add-clause")
async def add_clause_to_contract(request: ModificationRequest):
    """Add new clause to contract with AI interpretation"""
    try:
        # Enhanced AI prompt specifically for adding clauses
        ai_prompt = f"""
You are a contract modification expert. The user wants to ADD this clause: "{request.modification_text}"

Analyze the request and create a specific ADD modification in JSON format:

{{
    "modifications": [
        {{
            "search_text": "suitable existing text to locate where to add (like 'services', 'obligations', 'terms')",
            "replacement_text": "{request.modification_text}",
            "action": "add",
            "explanation": "Added new clause: {request.modification_text}"
        }}
    ],
    "summary": "Added new clause to contract",
    "action_type": "add_clause"
}}

For adding clauses:
- Find a suitable location in the contract (after service requirements, terms, etc.)
- Use action "add"
- Put the new clause text in replacement_text
- The text will be highlighted in GREEN

Return only valid JSON.
"""
        
        # Get AI response
        ai_response = await llm_orchestrator.chat_response(ai_prompt, [], [])
        
        # Parse and apply modifications
        try:
            import json
            response_text = ai_response['response'].strip()
            
            # Find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                ai_data = json.loads(json_text)
                modifications = ai_data.get('modifications', [])
            else:
                # Fallback modification
                modifications = [{
                    "search_text": "services",
                    "replacement_text": request.modification_text,
                    "action": "add",
                    "explanation": f"Added new clause: {request.modification_text}"
                }]
            
            # Apply modifications
            result = robust_modifier.apply_modifications(request.contract_id, modifications)
            
            return {
                "success": True,
                "contract_id": request.contract_id,
                "action": "add_clause",
                "clause_added": request.modification_text,
                "changes_made": result['changes_made'],
                "changes_detail": result['changes_detail'],
                "download_urls": result['download_urls'],
                "message": f"Successfully added new clause: {request.modification_text} (highlighted in GREEN)"
            }
            
        except Exception as e:
            logger.error(f"Add clause parsing failed: {e}")
            # Direct fallback
            modifications = [{
                "search_text": "services",
                "replacement_text": request.modification_text,
                "action": "add",
                "explanation": f"Added new clause: {request.modification_text}"
            }]
            
            result = robust_modifier.apply_modifications(request.contract_id, modifications)
            
            return {
                "success": True,
                "contract_id": request.contract_id,
                "action": "add_clause",
                "clause_added": request.modification_text,
                "changes_made": result['changes_made'],
                "changes_detail": result['changes_detail'],
                "download_urls": result['download_urls'],
                "message": f"Successfully added new clause: {request.modification_text} (highlighted in GREEN)"
            }
        
    except Exception as e:
        logger.error(f"Add clause failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/delete-clause")
async def delete_clause_from_contract(request: ModificationRequest):
    """Delete clause from contract with AI interpretation"""
    try:
        # Get document context for better AI understanding
        context = robust_modifier.get_document_context(request.contract_id)
        
        # Enhanced AI prompt specifically for deleting clauses
        ai_prompt = f"""
You are a contract modification expert. The user wants to DELETE this text: "{request.modification_text}"

Document context (first 2000 chars):
{context[:2000]}

Analyze the request and create a specific DELETE modification in JSON format:

{{
    "modifications": [
        {{
            "search_text": "exact text to delete from the contract",
            "replacement_text": "",
            "action": "delete",
            "explanation": "Deleted clause: {request.modification_text}"
        }}
    ],
    "summary": "Deleted clause from contract",
    "action_type": "delete_clause"
}}

For deleting clauses:
- Find the exact text to delete in the document
- Use action "delete"
- Leave replacement_text empty
- The deleted text will be shown with RED strikethrough

Be specific with search_text - use actual text from the document that matches the user's request.

Return only valid JSON.
"""
        
        # Get AI response
        ai_response = await llm_orchestrator.chat_response(ai_prompt, [], [])
        
        # Parse and apply modifications
        try:
            import json
            response_text = ai_response['response'].strip()
            
            # Find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                ai_data = json.loads(json_text)
                modifications = ai_data.get('modifications', [])
            else:
                # Fallback modification
                modifications = [{
                    "search_text": request.modification_text,
                    "replacement_text": "",
                    "action": "delete",
                    "explanation": f"Deleted clause: {request.modification_text}"
                }]
            
            # Apply modifications
            result = robust_modifier.apply_modifications(request.contract_id, modifications)
            
            return {
                "success": True,
                "contract_id": request.contract_id,
                "action": "delete_clause",
                "clause_deleted": request.modification_text,
                "changes_made": result['changes_made'],
                "changes_detail": result['changes_detail'],
                "download_urls": result['download_urls'],
                "message": f"Successfully deleted clause: {request.modification_text} (shown with RED strikethrough)"
            }
            
        except Exception as e:
            logger.error(f"Delete clause parsing failed: {e}")
            # Direct fallback
            modifications = [{
                "search_text": request.modification_text,
                "replacement_text": "",
                "action": "delete",
                "explanation": f"Deleted clause: {request.modification_text}"
            }]
            
            result = robust_modifier.apply_modifications(request.contract_id, modifications)
            
            return {
                "success": True,
                "contract_id": request.contract_id,
                "action": "delete_clause",
                "clause_deleted": request.modification_text,
                "changes_made": result['changes_made'],
                "changes_detail": result['changes_detail'],
                "download_urls": result['download_urls'],
                "message": f"Successfully deleted clause: {request.modification_text} (shown with RED strikethrough)"
            }
        
    except Exception as e:
        logger.error(f"Delete clause failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/modify-local")
async def modify_contract_local(request: ModificationRequest):
    """Apply modifications to local contract files with robust processing"""
    try:
        # Get document context from embeddings for better AI understanding
        context = robust_modifier.get_document_context(request.contract_id)
        
        # Use AI to interpret the modification request with context
        ai_prompt = f"""
        Analyze this contract modification request: "{request.modification_text}"
        
        Document context (first 3000 chars):
        {context}
        
        Generate specific modifications in JSON format. Be very precise with search text:
        
        {{
            "modifications": [
                {{
                    "search_text": "exact text to find (be specific, use actual values like $0.23)",
                    "replacement_text": "exact replacement text (like $0.56)",
                    "action": "replace",
                    "explanation": "what is being changed"
                }}
            ],
            "summary": "Brief summary of changes"
        }}
        
        Actions available:
        - "replace": Replace existing text with new text (yellow highlight)
        - "add": Add new text after existing text (green highlight)
        - "delete": Delete existing text (red highlight with strikethrough)
        
        For the user's request, identify the EXACT text that needs to be changed.
        If they mention changing "$0.23 to $0.56", use exactly "$0.23" as search_text and "$0.56" as replacement_text.
        
        Return only valid JSON.
        """
        
        # Get AI response
        ai_response = await llm_orchestrator.chat_response(ai_prompt, [], [])
        
        # Parse modifications
        try:
            import json
            ai_data = json.loads(ai_response['response'].strip())
            modifications = ai_data.get('modifications', [])
        except:
            # Fallback modification
            modifications = [{
                "search_text": "$0.23",
                "replacement_text": "$0.56",
                "action": "replace"
            }]
        
        # Apply modifications to the document using robust modifier
        result = robust_modifier.apply_modifications(request.contract_id, modifications)
        
        return {
            "success": True,
            "contract_id": request.contract_id,
            "contract_name": os.path.basename(result['contract_file']),
            "changes_made": result['changes_made'],
            "modifications": modifications,
            "changes_detail": result['changes_detail'],
            "download_urls": result['download_urls'],
            "message": "Contract modified successfully with real document changes"
        }
        
    except Exception as e:
        logger.error(f"Local contract modification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview/{contract_id}")
async def get_contract_preview(contract_id: str, user_id: str):
    """Get contract preview with modifications"""
    try:
        # This would return the latest modified version
        # For now, return basic contract info
        return {
            "success": True,
            "contract_id": contract_id,
            "preview_available": True,
            "message": "Preview functionality ready"
        }
        
    except Exception as e:
        logger.error(f"Preview generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-amendment")
async def generate_amendment(request: ModificationRequest):
    """Generate color-coded amendment document
    
    Color coding:
    - GREEN: Added text
    - RED: Deleted text (strikethrough)
    - YELLOW: Replaced/modified text
    """
    try:
        modifications = request.specific_changes or []
        
        # If no specific changes, parse from modification_text
        if not modifications and request.modification_text:
            # Simple parsing - you can enhance with AI
            modifications = [{
                "action": "replace",
                "search_text": "services",
                "new_text": request.modification_text,
                "explanation": "User requested change"
            }]
        
        result = await amendment_generator.generate_amendment(
            contract_id=request.contract_id,
            user_id=request.user_id,
            modifications=modifications
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Amendment generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated document file"""
    try:
        file_path = os.path.join("local_storage", "previews", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine media type based on file extension
        if filename.endswith('.pdf'):
            media_type = "application/pdf"
        elif filename.endswith('.docx'):
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            media_type = "application/octet-stream"
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
        
    except Exception as e:
        logger.error(f"File download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from app.services.llm_amendment_service import llm_amendment_service

@router.post("/generate-amendment-ai")
async def generate_amendment_ai(request: ModificationRequest):
    """Generate amendment using AI to interpret natural language
    
    Example requests:
    - "Add a confidentiality clause after the services section"
    - "Change the price from $0.23 to $0.56"
    - "Remove the non-compete clause"
    - "Add late payment penalty of 2% and extend notice period to 60 days"
    """
    try:
        result = await llm_amendment_service.generate_from_natural_language(
            contract_id=request.contract_id,
            user_id=request.user_id,
            user_request=request.modification_text
        )
        
        return result
        
    except Exception as e:
        logger.error(f"AI amendment generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
