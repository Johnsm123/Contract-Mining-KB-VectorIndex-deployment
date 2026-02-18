"""Complete workflow: Chat with embeddings + Auto-embed amendments"""
import logging
from pathlib import Path
from google.cloud import storage
from datetime import datetime
from typing import Dict

from app.services.gcp_knowledge_base import GCPKnowledgeBase
from app.services.gcp_llm_orchestrator import llm_orchestrator
from app.config.settings import settings

logger = logging.getLogger(__name__)

class ContractWorkflowService:
    """Complete workflow for contract processing"""
    
    def __init__(self):
        self.kb = GCPKnowledgeBase(
            settings.gcp_project_id,
            settings.gcp_region,
            settings.gcs_embeddings_bucket
        )
        self.storage_client = storage.Client(project=settings.gcp_project_id)
    
    async def chat_with_contracts(self, query: str, top_k: int = 5) -> Dict:
        """Chat using embedded data from temps bucket"""
        try:
            # Search embeddings in temps bucket
            relevant_chunks = await self.kb.search(query, top_k)
            
            if not relevant_chunks:
                return {
                    "response": "No contract data found. Please upload contracts first.",
                    "source": "no_data"
                }
            
            # Generate response using LLM with context
            llm_response = await llm_orchestrator.chat_response(query, relevant_chunks)
            
            return {
                "response": llm_response["response"],
                "model": llm_response["model"],
                "relevant_chunks": relevant_chunks,
                "source": "temps_bucket_embeddings"
            }
            
        except Exception as e:
            logger.error(f"Chat workflow error: {e}")
            return {"response": f"Error: {str(e)}", "source": "error"}
    
    async def modify_and_store_amendment(self, contract_id: str, modified_docx_path: Path, modification_summary: str) -> Dict:
        """
        1. Store modified document in amendments bucket
        2. Generate embeddings for amendment
        3. Store embeddings in temps/amendments/ folder
        """
        try:
            # 1. Upload to amendments bucket
            amendments_bucket = self.storage_client.bucket(settings.gcs_amendments_bucket)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            amendment_filename = f"amendment_{contract_id}_{timestamp}.docx"
            
            blob = amendments_bucket.blob(amendment_filename)
            with open(modified_docx_path, 'rb') as f:
                blob.upload_from_file(f)
            
            logger.info(f"✅ Stored amendment: gs://{settings.gcs_amendments_bucket}/{amendment_filename}")
            
            # 2. Extract text from modified document
            from docx import Document
            doc = Document(modified_docx_path)
            text_content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            
            # 3. Generate embeddings and store in temps/amendments/
            embedding_result = await self._store_amendment_embeddings(
                amendment_filename,
                text_content,
                modification_summary
            )
            
            return {
                "success": True,
                "amendment_path": f"gs://{settings.gcs_amendments_bucket}/{amendment_filename}",
                "embeddings_path": embedding_result["embeddings_path"],
                "message": "Amendment stored and embedded successfully"
            }
            
        except Exception as e:
            logger.error(f"Amendment workflow error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _store_amendment_embeddings(self, filename: str, text_content: str, summary: str) -> Dict:
        """Store amendment embeddings in temps/amendments/ folder"""
        try:
            from vertexai.language_models import TextEmbeddingModel
            import json
            import hashlib
            
            # Initialize embedding model
            embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
            
            # Split into chunks
            chunks = self._split_text(text_content, filename)
            
            # Generate embeddings
            embeddings_data = []
            for chunk in chunks:
                embedding = embedding_model.get_embeddings([chunk["text"]])[0].values
                embeddings_data.append({
                    "chunk_id": chunk["chunk_id"],
                    "amendment_name": filename,
                    "text": chunk["text"],
                    "section": chunk["section"],
                    "embedding": list(embedding),
                    "modification_summary": summary,
                    "created_at": datetime.utcnow().isoformat()
                })
            
            # Store in temps bucket under amendments/ folder
            temps_bucket = self.storage_client.bucket(settings.gcs_embeddings_bucket)
            embeddings_path = f"kb/amendments/{Path(filename).stem}_embeddings.json"
            blob = temps_bucket.blob(embeddings_path)
            blob.upload_from_string(
                json.dumps(embeddings_data, indent=2),
                content_type="application/json"
            )
            
            logger.info(f"✅ Stored amendment embeddings: gs://{settings.gcs_embeddings_bucket}/{embeddings_path}")
            
            return {
                "embeddings_path": f"gs://{settings.gcs_embeddings_bucket}/{embeddings_path}",
                "chunks_count": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Amendment embedding error: {e}")
            raise e
    
    def _split_text(self, text: str, filename: str, chunk_size: int = 500):
        """Split text into chunks"""
        import hashlib
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size):
            chunk_text = " ".join(words[i:i + chunk_size])
            chunks.append({
                "text": chunk_text,
                "section": f"chunk_{i//chunk_size + 1}",
                "chunk_id": hashlib.md5(chunk_text.encode()).hexdigest()[:8]
            })
        
        return chunks

# Global instance
workflow_service = ContractWorkflowService()
