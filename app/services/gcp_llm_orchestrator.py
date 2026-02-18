"""Enhanced Multi-LLM Orchestrator with Vertex AI Fallback"""
import logging
from typing import Dict, List, Optional
import google.generativeai as genai
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from app.config.settings import settings

logger = logging.getLogger(__name__)

class GCPLLMOrchestrator:
    """Multi-LLM orchestrator with Vertex AI fallback for maximum accuracy"""
    
    def __init__(self): 
        # Primary: Google AI Studio API (Gemini 2.5 Flash)
        api_key = settings.google_api_key
        genai.configure(api_key=api_key)
        self.primary_model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Fallback: Vertex AI Gemini Pro (more accurate)
        try:
            vertexai.init(project=settings.gcp_project_id, location=settings.vertex_ai_location)
            self.fallback_model = GenerativeModel("gemini-1.5-pro")
            self.vertex_available = True
            logger.info("Vertex AI fallback initialized successfully")
        except Exception as e:
            logger.warning(f"Vertex AI fallback not available: {e}")
            self.fallback_model = None
            self.vertex_available = False
        
        # Fine-tuned generation configs for healthcare contracts
        self.configs = {
            "precise": {
                "temperature": 0.1,
                "max_output_tokens": 8192,
                "top_p": 0.85,
                "top_k": 40
            },
            "balanced": {
                "temperature": 0.2,
                "max_output_tokens": 4096,
                "top_p": 0.9,
                "top_k": 30
            },
            "creative": {
                "temperature": 0.5,
                "max_output_tokens": 2048,
                "top_p": 0.95,
                "top_k": 20
            }
        }
        
        logger.info("Enhanced LLM Orchestrator initialized with Vertex AI fallback")
    
    async def chat_response(self, query: str, context: List[Dict], history: List[Dict] = None, mode: str = "precise") -> Dict:
        """Generate chat response with automatic fallback"""
        try:
            # Try primary model (Gemini 2.5 Flash)
            prompt = self._build_enhanced_prompt(query, context, history)
            config = self.configs[mode]
            
            response = self.primary_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=config["temperature"],
                    max_output_tokens=config["max_output_tokens"],
                    top_p=config["top_p"],
                    top_k=config["top_k"]
                )
            )
            
            # Clean response text
            cleaned_response = self._clean_response_text(response.text)
            
            return {
                "response": cleaned_response,
                "model": "gemini-2.5-flash",
                "tokens": len(cleaned_response.split()),
                "structured": True,
                "accuracy_mode": "high"
            }
            
        except Exception as e:
            logger.warning(f"Primary model failed: {e}, switching to Vertex AI fallback")
            return await self._vertex_ai_fallback(query, context, history, mode)
    
    async def _vertex_ai_fallback(self, query: str, context: List[Dict], history: List[Dict] = None, mode: str = "precise") -> Dict:
        """Fallback to Vertex AI Gemini Pro for maximum accuracy"""
        if not self.vertex_available or self.fallback_model is None:
            return self._emergency_fallback(query)
        
        try:
            prompt = self._build_enhanced_prompt(query, context, history)
            config = self.configs[mode]
            
            vertex_config = GenerationConfig(
                temperature=config["temperature"],
                max_output_tokens=config["max_output_tokens"],
                top_p=config["top_p"],
                top_k=config["top_k"]
            )
            
            response = self.fallback_model.generate_content(
                prompt,
                generation_config=vertex_config
            )
            
            # Clean response text
            cleaned_response = self._clean_response_text(response.text)
            
            return {
                "response": cleaned_response,
                "model": "gemini-1.5-pro-vertex",
                "tokens": len(cleaned_response.split()),
                "structured": True,
                "accuracy_mode": "maximum"
            }
            
        except Exception as e:
            logger.error(f"Vertex AI fallback failed: {e}")
            return self._emergency_fallback(query)
    
    async def quick_search(self, query: str) -> Dict:
        """Quick search with fallback"""
        try:
            prompt = f"Extract key search terms from: {query}\nReturn as comma-separated list."
            response = self.primary_model.generate_content(prompt)
            
            return {
                "search_terms": response.text.strip().split(","),
                "model": "gemini-2.5-flash"
            }
        except Exception as e:
            logger.error(f"Quick search error: {e}")
            return {"search_terms": query.split(), "model": "fallback"}
    
    async def analyze_contract(self, contract_text: str, analysis_type: str = "summary") -> Dict:
        """Enhanced contract analysis with fallback"""
        try:
            prompt = self._build_analysis_prompt(contract_text, analysis_type)
            
            # Use primary model
            response = self.primary_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                    top_p=0.85
                )
            )
            
            return {
                "analysis": response.text,
                "type": analysis_type,
                "model": "gemini-2.5-flash"
            }
            
        except Exception as e:
            logger.warning(f"Primary analysis failed: {e}, using Vertex AI")
            
            if self.vertex_available and self.fallback_model:
                try:
                    prompt = self._build_analysis_prompt(contract_text, analysis_type)
                    response = self.fallback_model.generate_content(
                        prompt,
                        generation_config=GenerationConfig(
                            temperature=0.1,
                            max_output_tokens=8192,
                            top_p=0.85,
                            top_k=40
                        )
                    )
                    
                    return {
                        "analysis": response.text,
                        "type": analysis_type,
                        "model": "gemini-1.5-pro-vertex"
                    }
                except Exception as e2:
                    logger.error(f"Vertex AI analysis failed: {e2}")
            
            return {"analysis": "Analysis unavailable at this time.", "type": analysis_type, "model": "fallback"}
    
    async def suggest_amendment(self, original_text: str, intent: str) -> Dict:
        """Enhanced amendment suggestions with fallback"""
        try:
            prompt = f"""You are a healthcare contract legal expert. Analyze and suggest improvements.

ORIGINAL TEXT:
{original_text}

USER INTENT:
{intent}

REQUIREMENTS:
- Maintain legal precision and clarity
- Use healthcare industry standard terminology
- Ensure compliance with healthcare regulations
- Preserve contractual enforceability
- Address the user's intent completely

Provide ONLY the improved contract text in plain format without markdown or special characters."""

            # Try primary
            response = self.primary_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=4096,
                    top_p=0.85
                )
            )
            
            return {
                "suggested_text": response.text.strip(),
                "model": "gemini-2.5-flash"
            }
            
        except Exception as e:
            logger.warning(f"Primary amendment failed: {e}, using Vertex AI")
            
            if self.vertex_available and self.fallback_model:
                try:
                    response = self.fallback_model.generate_content(
                        prompt,
                        generation_config=GenerationConfig(
                            temperature=0.1,
                            max_output_tokens=4096,
                            top_p=0.85,
                            top_k=40
                        )
                    )
                    return {
                        "suggested_text": response.text.strip(),
                        "model": "gemini-1.5-pro-vertex"
                    }
                except Exception as e2:
                    logger.error(f"Vertex AI amendment failed: {e2}")
            
            return {"suggested_text": original_text, "model": "fallback"}
    
    def _clean_response_text(self, text: str) -> str:
        """Clean markdown and special characters from response"""
        import re
        
        # Remove markdown bold (**text**)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        
        # Remove markdown italic (*text* or _text_)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        
        # Remove markdown headers (### text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Remove markdown code blocks (```text```)
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        return text
    
    def _build_enhanced_prompt(self, query: str, context: List[Dict], history: List[Dict] = None) -> str:
        """Build enhanced prompt for healthcare contracts"""
        prompt_parts = []
        
        # System prompt with healthcare expertise
        prompt_parts.append("""You are an expert healthcare pharmacy contract analyst with deep knowledge of Medicare Part D, Medicaid, Commercial insurance, HIPAA compliance, and PBM contracts.

IMPORTANT RESPONSE RULES:
1. Answer ONLY what the user asks - be direct and concise
2. DO NOT use markdown formatting (no *, **, /, \, or special characters)
3. Use plain text with clear paragraph breaks
4. Cite document names and sections when available
5. If asked about document identification, clearly state which document contains the information
6. Use simple bullet points with hyphens (-) if listing items
7. Keep responses professional but conversational

Response Structure (use only when relevant to query):
SUMMARY: Brief direct answer
DETAILS: Specific information with document references
KEY POINTS: Important terms, dates, or obligations (if asked)
REFERENCES: Document names and sections cited
""")
        
        # Add context if available
        if context and len(context) > 0:
            prompt_parts.append("\n\nAVAILABLE CONTRACT DOCUMENTS:")
            for i, ctx in enumerate(context[:5], 1):
                doc_name = ctx.get('contract_name', 'Unknown')
                section = ctx.get('section', 'N/A')
                content = ctx.get('text', '')[:1500]
                prompt_parts.append(f"\nDocument {i}: {doc_name}")
                prompt_parts.append(f"Section: {section}")
                prompt_parts.append(f"Content: {content}")
        
        # Add conversation history
        if history and len(history) > 0:
            prompt_parts.append("\n\nPREVIOUS CONVERSATION:")
            for msg in history[-3:]:  # Last 3 messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                prompt_parts.append(f"{role.upper()}: {content}")
        
        # Add current query
        prompt_parts.append(f"\n\nUSER QUESTION: {query}")
        prompt_parts.append("\nProvide a clear, direct answer in plain text without markdown formatting:")
        
        return "\n".join(prompt_parts)
    
    def _build_analysis_prompt(self, contract_text: str, analysis_type: str) -> str:
        """Build enhanced analysis prompts"""
        base_instruction = "Provide your analysis in plain text without markdown formatting (no asterisks, slashes, or special characters). Use simple paragraph breaks and hyphens for lists.\n\n"
        
        prompts = {
            "summary": f"""{base_instruction}Analyze this healthcare pharmacy contract and provide a comprehensive summary.

CONTRACT TEXT:
{contract_text[:6000]}

Provide:
- Contract type and parties involved
- Key obligations and responsibilities
- Payment terms and financial arrangements
- Term and termination conditions
- Critical compliance requirements
- Notable clauses or provisions""",

            "risks": f"""{base_instruction}Identify and analyze potential risks in this healthcare pharmacy contract.

CONTRACT TEXT:
{contract_text[:6000]}

Analyze:
- Financial risks (payment terms, penalties, reimbursement)
- Compliance risks (HIPAA, Medicare, Medicaid)
- Operational risks (service requirements, performance metrics)
- Legal risks (liability, indemnification, termination)
- Reputational risks
- Mitigation recommendations""",

            "terms": f"""{base_instruction}Extract and analyze key terms and conditions from this healthcare pharmacy contract.

CONTRACT TEXT:
{contract_text[:6000]}

Extract:
- Effective dates and term duration
- Payment terms and rates
- Service level requirements
- Performance metrics and penalties
- Termination clauses
- Renewal conditions
- Key definitions""",

            "compliance": f"""{base_instruction}Assess compliance requirements in this healthcare pharmacy contract.

CONTRACT TEXT:
{contract_text[:6000]}

Review:
- HIPAA compliance requirements
- Medicare/Medicaid regulations
- State pharmacy laws
- Data security requirements
- Reporting obligations
- Audit rights
- Compliance gaps or concerns"""
        }
        
        return prompts.get(analysis_type, prompts["summary"])
    
    def _emergency_fallback(self, query: str) -> Dict:
        """Emergency fallback when all models fail"""
        return {
            "response": f"I apologize, but I'm experiencing technical difficulties processing your query: '{query}'. Please try again in a moment or rephrase your question.",
            "model": "emergency-fallback",
            "tokens": 0,
            "structured": False,
            "accuracy_mode": "none"
        }

# Global instance
llm_orchestrator = GCPLLMOrchestrator()
