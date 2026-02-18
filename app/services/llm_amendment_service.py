"""LLM-powered amendment generation using Vertex AI"""
import logging
import json
import re
from typing import Dict, List
from docx import Document

from app.services.gcp_llm_orchestrator import llm_orchestrator
from app.services.amendment_generator import amendment_generator

logger = logging.getLogger(__name__)

class LLMAmendmentService:
    """Generate amendments using LLM to interpret natural language"""
    
    async def generate_from_natural_language(self, contract_id: str, user_id: str, user_request: str) -> Dict:
        """Convert natural language to structured amendments using LLM"""
        try:
            # Get contract context
            contract_text = self._get_contract_text(contract_id)
            
            # LLM prompt to extract modifications
            prompt = f"""You are a contract amendment expert. Analyze the user's request and the contract text.

CONTRACT TEXT (first 2000 chars):
{contract_text[:2000]}

USER REQUEST:
{user_request}

Extract the specific modifications needed. Return ONLY valid JSON in this exact format:
{{
  "modifications": [
    {{
      "action": "add|delete|replace",
      "search_text": "exact text from contract to find",
      "new_text": "new text to add/replace (empty for delete)",
      "explanation": "what this change does"
    }}
  ],
  "summary": "brief summary of all changes"
}}

RULES:
- action: "add" = insert new text, "delete" = remove text, "replace" = change text
- search_text: MUST be exact text from the contract
- For "add": search_text is where to insert, new_text is what to add
- For "delete": search_text is what to remove, new_text is empty
- For "replace": search_text is old text, new_text is replacement
- Be specific with search_text - use actual contract text

Return ONLY the JSON, no other text."""

            # Get LLM response
            response = await llm_orchestrator.chat_response(prompt, [], [])
            llm_text = response.get('response', '')
            
            # Extract JSON from response
            modifications = self._extract_json(llm_text)
            
            if not modifications or 'modifications' not in modifications:
                raise ValueError("LLM did not return valid modifications")
            
            # Generate amendment using extracted modifications
            result = await amendment_generator.generate_amendment(
                contract_id=contract_id,
                user_id=user_id,
                modifications=modifications['modifications']
            )
            
            # Add LLM summary
            result['llm_summary'] = modifications.get('summary', 'Changes applied')
            result['original_request'] = user_request
            result['llm_interpretation'] = modifications['modifications']
            
            logger.info(f"LLM amendment generated: {result['amendment_id']}")
            return result
            
        except Exception as e:
            logger.error(f"LLM amendment generation failed: {e}")
            raise
    
    def _get_contract_text(self, contract_id: str) -> str:
        """Get contract text for context"""
        try:
            import os
            contract_path = os.path.join("local_storage", "contracts", f"{contract_id}.docx")
            doc = Document(contract_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception as e:
            logger.error(f"Failed to read contract: {e}")
            return ""
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response"""
        try:
            # Try direct parse
            return json.loads(text.strip())
        except:
            # Find JSON in text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except:
                    pass
            
            # Fallback: parse manually
            logger.warning("Could not parse LLM JSON, using fallback")
            return {"modifications": [], "summary": "Failed to parse"}

llm_amendment_service = LLMAmendmentService()
