"""RAG service using Vertex AI Vector Search and GCP Knowledge Base"""
import logging
from typing import List, Dict
from google.cloud import storage
import json
from app.services.vertex_vector_search import vertex_vector_search
from app.services.gcp_knowledge_base import GCPKnowledgeBase
from app.services.gcp_llm_orchestrator import llm_orchestrator
from app.config.settings import settings

logger = logging.getLogger(__name__)

class RAGService:
    """RAG with Vector Search endpoint"""
    
    def __init__(self):
        self.vector_search = vertex_vector_search
        self.kb = GCPKnowledgeBase(
            project_id=settings.gcp_project_id,
            region=settings.gcp_region,
            embeddings_bucket=settings.gcs_embeddings_bucket
        )
        self.llm = llm_orchestrator
        self.storage_client = storage.Client(project=settings.gcp_project_id)
    
    async def retrieve_and_generate(self, query: str, top_k: int = 5) -> Dict:
        """Retrieve using Vector Search, then generate response"""
        try:
            # Step 1: Vector Search finds similar document IDs
            if self.vector_search.endpoint:
                vector_results = await self.vector_search.search(query, top_k)
                
                if vector_results:
                    # Step 2: Fetch actual text from bucket using IDs
                    relevant_chunks = self._fetch_chunks_by_ids(vector_results)
                else:
                    # Fallback to direct KB search
                    logger.warning("Vector Search returned no results, using KB fallback")
                    relevant_chunks = await self.kb.search(query, top_k)
            else:
                # No Vector Search configured, use KB directly
                logger.info("Using Knowledge Base search (Vector Search not configured)")
                relevant_chunks = await self.kb.search(query, top_k)
            
            # Step 3: LLM generates answer from chunks
            response = await self.llm.chat_response(query, relevant_chunks)
            
            return {
                "query": query,
                "relevant_chunks": relevant_chunks,
                "response": response["response"],
                "model": response["model"],
                "search_method": "vector_search" if self.vector_search.endpoint else "knowledge_base",
                "chunks_found": len(relevant_chunks)
            }
            
        except Exception as e:
            logger.error(f"RAG error: {e}")
            return {"error": str(e)}
    
    def _fetch_chunks_by_ids(self, vector_results: List[Dict]) -> List[Dict]:
        """Fetch actual document chunks from bucket using Vector Search IDs"""
        chunks = []
        bucket = self.storage_client.bucket(settings.gcs_embeddings_bucket)
        
        # Group IDs by file
        file_map = {}
        for result in vector_results:
            doc_id = result["id"]
            # ID format: "filename_chunkid"
            parts = doc_id.rsplit("_", 1)
            if len(parts) == 2:
                filename = parts[0]
                if filename not in file_map:
                    file_map[filename] = []
                file_map[filename].append({"id": doc_id, "similarity": result["similarity"]})
        
        # Fetch chunks from each file
        for filename, ids in file_map.items():
            try:
                blob = bucket.blob(f"embeddings/{filename}.json")
                if blob.exists():
                    content = blob.download_as_text()
                    data = json.loads(content)
                    
                    # Find matching chunks
                    for item in data:
                        chunk_id = item.get("chunk_id")
                        for id_info in ids:
                            if chunk_id in id_info["id"]:
                                chunks.append({
                                    "contract_name": item.get("contract_name", filename),
                                    "text": item.get("text", ""),
                                    "section": item.get("section", "N/A"),
                                    "chunk_id": chunk_id,
                                    "similarity": id_info["similarity"]
                                })
                                break
            except Exception as e:
                logger.error(f"Error fetching chunks from {filename}: {e}")
        
        logger.info(f"Fetched {len(chunks)} chunks from bucket")
        return chunks

# Global instance
rag_service = RAGService()
