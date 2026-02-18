from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging

from app.services.gcp_llm_orchestrator import llm_orchestrator
from app.services.rag_service import rag_service

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    query: str
    user_id: str
    contract_id: Optional[str] = None
    history: Optional[List[Dict]] = None

@router.post("/")
async def chat(request: ChatRequest):
    """Chat with AI using GCP Gemini models"""
    try:
        # Use RAG service for retrieval and generation
        result = await rag_service.retrieve_and_generate(request.query, top_k=5)
        
        return {
            "success": True,
            "documents_found": len(result.get("relevant_chunks", [])),
            "response": result.get("response", ""),
            "model": result.get("model", "gemini-1.5-pro"),
            "tokens": len(result.get("response", "").split()),
            "source": "gcp_vertex_ai"
        }
        
    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        return {
            "success": True,
            "response": f"I received your query: '{request.query}'. Unable to process at this time.",
            "model": "fallback",
            "tokens": len(request.query.split()),
            "documents_found": 0,
            "source": "gcp_vertex_ai",
            "error_detail": str(e)
        }

@router.post("/analyze")
async def analyze_contract(contract_id: str, analysis_type: str = "summary"):
    """Analyze contract"""
    try:
        # Get contract from GCS
        from app.services.gcp_knowledge_base import GCPKnowledgeBase
        from app.config.settings import settings
        
        kb = GCPKnowledgeBase(
            settings.gcp_project_id,
            settings.gcp_region,
            settings.gcs_embeddings_bucket
        )
        
        # Search for contract
        results = await kb.search(contract_id, top_k=10)
        contract_text = "\n\n".join([r["text"] for r in results])
        
        # Analyze
        analysis = await llm_orchestrator.analyze_contract(contract_text, analysis_type)
        
        return {
            "success": True,
            "contract_id": contract_id,
            **analysis
        }
        
    except Exception as e:
        logger.error(f"Contract analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    query: str
    user_id: str
    contract_id: Optional[str] = None
    history: Optional[List[Dict]] = None

@router.post("/")
async def chat(request: ChatRequest):
    """Chat with AI using Bedrock Mistral 7B (no approval required)"""
    try:
        # Check if this is a document modification request
        query_lower = request.query.lower()
        modification_keywords = ['add', 'delete', 'remove', 'modify', 'change', 'replace', 'update', 'insert']
        
        if any(keyword in query_lower for keyword in modification_keywords):
            # Extract contract ID from query or use provided contract_id
            contract_id = request.contract_id
            
            # Try to extract contract ID from the query text
            import re
            contract_match = re.search(r'contract[:\s]+([a-zA-Z0-9_]+)', request.query, re.IGNORECASE)
            if contract_match:
                contract_id = contract_match.group(1)
            
            if not contract_id:
                # Find first available contract
                from pathlib import Path
                from app.config.settings import settings
                upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
                if upload_dir.exists():
                    contract_files = list(upload_dir.glob("*.docx"))
                    if contract_files:
                        filename = contract_files[0].stem
                        if '_' in filename:
                            contract_id = filename.split('_')[-1]
            
            if contract_id:
                # Determine the type of modification
                if 'add' in query_lower and 'delete' not in query_lower:
                    # This is an ADD request - use STRICT format: "add [TEXT] after [LOCATION]"
                    import re
                    
                    # Remove the contract reference first
                    query_clean = re.sub(r'\s+to\s+contract\s+[a-zA-Z0-9_]+', '', request.query, flags=re.IGNORECASE)
                    
                    logger.info(f"ADD request - query_clean: '{query_clean}'")
                    
                    # STRICT FORMAT: "add [CLAUSE] after [LOCATION]"
                    # Pattern: add ... after ... (non-greedy to stop at first 'after')
                    add_pattern = re.search(r'add\s+(.+?)\s+after\s+(.+)', query_clean, re.IGNORECASE | re.DOTALL)
                    
                    if add_pattern:
                        text_to_add = add_pattern.group(1).strip()
                        location = add_pattern.group(2).strip()
                        context_hint = f"after {location}"
                        
                        logger.info(f"Extracted - text_to_add: '{text_to_add}', location: '{location}'")
                    else:
                        # Fallback: if no "after" found, show error message
                        return {
                            "success": False,
                            "response": "Please use the format: add [your clause text] after [location in contract]\n\nExample: add HealthCard provided by the insurance company after Copies of the following:",
                            "model": "format_error",
                            "tokens": 0,
                            "documents_found": 0
                        }
                    
                    # Return suggestion for frontend confirmation
                    return {
                        "success": True,
                        "action_type": "add_clause_suggestion",
                        "requires_confirmation": True,
                        "clause_to_add": text_to_add,
                        "context_hint": context_hint,
                        "contract_id": contract_id,
                        "message": "AI is analyzing the best location to insert this clause..."
                    }
                
                elif 'delete' in query_lower or 'remove' in query_lower:
                    # This is a DELETE request - route to delete-clause endpoint
                    from app.api.document_modifications import delete_clause_from_contract
                    from app.api.document_modifications import ModificationRequest
                    
                    # Extract the text to delete
                    delete_match = re.search(r'(?:delete|remove)\s+(?:the\s+)?(.+)', request.query, re.IGNORECASE)
                    if delete_match:
                        text_to_delete = delete_match.group(1).strip()
                        # Remove quotes and any trailing contract references
                        text_to_delete = text_to_delete.strip('"\'')
                        text_to_delete = re.sub(r'\s+(?:from|in|to)\s+contract.*$', '', text_to_delete, flags=re.IGNORECASE).strip()
                        
                        # Get contract name
                        from pathlib import Path
                        from app.services.robust_document_modifier import robust_modifier
                        contract_file = robust_modifier.find_contract_file(contract_id)
                        contract_name = contract_file.name if contract_file else contract_id
                        
                        mod_request = ModificationRequest(
                            contract_id=contract_id,
                            user_id=request.user_id,
                            modification_text=text_to_delete
                        )
                        
                        try:
                            result = await delete_clause_from_contract(mod_request)
                            return {
                                "success": True,
                                "response": f"Clause Deleted Successfully!\n\nContract: {contract_name}\n\nDeleted Clause:\n{text_to_delete}\n\nRed strikethrough shows the deleted text in the Word document.",
                                "model": "delete_clause_direct",
                                "tokens": 100,
                                "documents_found": 1,
                                "action_type": "delete_clause",
                                "download_urls": result.get('download_urls', {})
                            }
                        except Exception as e:
                            return {
                                "success": True,
                                "response": f"Failed to delete clause: {str(e)}",
                                "model": "delete_clause_error",
                                "tokens": 50,
                                "documents_found": 0
                            }
                
                else:
                    # General modification - route to modify-local endpoint
                    from app.api.document_modifications import modify_contract_local
                    from app.api.document_modifications import ModificationRequest
                    
                    # Remove 'modify ' prefix if present
                    query_for_parsing = request.query
                    if query_for_parsing.lower().startswith('modify '):
                        query_for_parsing = query_for_parsing[7:].strip()
                    
                    # Try to extract "change X to Y" pattern
                    if 'change' in query_for_parsing.lower():
                        # Remove contract reference first
                        query_clean = re.sub(r'\s+(?:in|to)\s+contract.*$', '', query_for_parsing, flags=re.IGNORECASE).strip()
                        
                        # Remove 'change ' prefix
                        change_match = re.search(r'^change\s+(.+)$', query_clean, re.IGNORECASE)
                        if change_match:
                            text_part = change_match.group(1)
                            
                            # Try to find ' - ' separator first (cleaner format)
                            if ' - ' in text_part:
                                parts = text_part.split(' - ', 1)
                                old_text = parts[0].strip().strip('"\'')
                                new_text = parts[1].strip().strip('"\'')
                            else:
                                # Fallback: find ' to ' followed by a capital letter
                                to_pattern = re.compile(r'\s+to\s+(?=[A-Z])', re.IGNORECASE)
                                matches = list(to_pattern.finditer(text_part))
                                
                                if not matches:
                                    # Fallback: find any ' to '
                                    to_pattern = re.compile(r'\s+to\s+', re.IGNORECASE)
                                    matches = list(to_pattern.finditer(text_part))
                                
                                if matches:
                                    # Use the FIRST match (most likely the separator)
                                    first_match = matches[0]
                                    old_text = text_part[:first_match.start()].strip().strip('"\'')
                                    new_text = text_part[first_match.end():].strip().strip('"\'')
                                else:
                                    old_text = text_part
                                    new_text = ""
                            
                            if old_text and new_text:
                                # Get contract name
                                from pathlib import Path
                                from app.services.robust_document_modifier import robust_modifier
                                contract_file = robust_modifier.find_contract_file(contract_id)
                                contract_name = contract_file.name if contract_file else contract_id
                                
                                # Create direct modification without AI
                                modifications = [{
                                    "search_text": old_text,
                                    "replacement_text": new_text,
                                    "action": "replace",
                                    "explanation": f"Changed {old_text} to {new_text}"
                                }]
                                
                                try:
                                    result = robust_modifier.apply_modifications(contract_id, modifications)
                                    return {
                                        "success": True,
                                        "response": f"Contract Modified Successfully!\n\nContract: {contract_name}\n\nModification:\nChanged '{old_text}' to '{new_text}'\n\nChanges Made: {result['changes_made']}\n\nYellow highlighting shows modifications in the Word document.",
                                        "model": "modify_contract_direct",
                                        "tokens": 100,
                                        "documents_found": 1,
                                        "action_type": "modify_contract",
                                        "download_urls": result.get('download_urls', {})
                                    }
                                except Exception as e:
                                    logger.error(f"Modification failed: {str(e)}")
                                    return {
                                        "success": True,
                                        "response": f"Failed to modify contract: {str(e)}",
                                        "model": "modify_contract_error",
                                        "tokens": 50,
                                        "documents_found": 0
                                    }
                    
                    # Fallback to AI interpretation
                    mod_request = ModificationRequest(
                        contract_id=contract_id,
                        user_id=request.user_id,
                        modification_text=request.query
                    )
                    
                    # Get contract name
                    from pathlib import Path
                    from app.services.robust_document_modifier import robust_modifier
                    contract_file = robust_modifier.find_contract_file(contract_id)
                    contract_name = contract_file.name if contract_file else contract_id
                    
                    try:
                        result = await modify_contract_local(mod_request)
                        return {
                            "success": True,
                            "response": f"Contract Modified Successfully!\n\nContract: {contract_name}\n\nChanges Made: {result['changes_made']}\n\nYellow highlighting shows modifications in the Word document.",
                            "model": "modify_contract_direct",
                            "tokens": 100,
                            "documents_found": 1,
                            "action_type": "modify_contract",
                            "download_urls": result.get('download_urls', {})
                        }
                    except Exception as e:
                        return {
                            "success": True,
                            "response": f"Failed to modify contract: {str(e)}",
                            "model": "modify_contract_error",
                            "tokens": 50,
                            "documents_found": 0
                        }
            
            # If no contract ID found
            return {
                "success": True,
                "response": f"Please specify a contract ID in your request. Example: 'Add new clause to contract 6bc49695'",
                "model": "modification_helper",
                "tokens": 30,
                "documents_found": 0
            }
        
        # Regular chat request - proceed with normal flow
        context = await local_doc_processor.search_similar_documents(request.query, top_k=6)
        
        # Try Bedrock first (Mistral 7B available without approval)
        if bedrock_orchestrator.model_available:
            response = await bedrock_orchestrator.chat_response(
                request.query,
                context,
                request.history
            )
        else:
            # Fallback to Gemini if Bedrock unavailable
            response = await llm_orchestrator.chat_response(
                request.query,
                context,
                request.history
            )
        
        return {
            "success": True,
            "documents_found": len(context),
            "source": "bedrock_mistral" if bedrock_orchestrator.model_available else "gemini_fallback",
            **response
        }
        
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return {
            "success": True,
            "response": f"I received your query: '{request.query}'. Error: {str(e)}",
            "model": "error_fallback",
            "tokens": 0,
            "documents_found": 0
        }

@router.post("/analyze")
async def analyze_contract(contract_id: str, user_id: str):
    """Analyze entire contract"""
    try:
        db_pool = await get_db_pool()
        async with db_pool.acquire() as conn:
            contract = await conn.fetchrow("""
                SELECT * FROM contracts 
                WHERE contract_id = $1 AND user_id = $2
            """, contract_id, user_id)
            
            if not contract:
                raise HTTPException(status_code=404, detail="Contract not found")
            
            # Get all lines
            lines = await conn.fetch("""
                SELECT line_text FROM contract_lines
                WHERE contract_id = $1
                ORDER BY line_number
            """, contract['id'])
            
            contract_text = "\n".join([line['line_text'] for line in lines])
            
            # Analyze with AI
            analysis = await llm_orchestrator.analyze_contract(contract_text)
            
            return {
                "success": True,
                "contract_id": contract_id,
                "contract_name": contract['name'],
                **analysis
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contract analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
