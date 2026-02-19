"""GCP-based document processing with Cloud Storage and Vertex AI"""
import logging
import json
from typing import List, Dict
from pathlib import Path
from google.cloud import storage
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
import hashlib
from datetime import datetime
import numpy as np
import asyncio

logger = logging.getLogger(__name__)

class GCPDocumentProcessor:
    """Process documents using GCS and Vertex AI"""
    
    def __init__(self, project_id: str, region: str):
        self.project_id = project_id
        self.region = region
        
        # Initialize clients
        self.storage_client = storage.Client(project=project_id)
        
        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=region)
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        
        # GCS buckets
        self.contracts_bucket = "contract-mining-assistant-contract"
        self.temp_bucket = "contract-mining-assistant-temps"
    
    async def process_uploaded_file(self, file_path: Path, text_content: str, is_amendment: bool = False) -> Dict:
        """Process file and store embeddings in GCS"""
        try:
            chunks = self._split_into_chunks(text_content, file_path.name)
            
            # Generate embeddings using Vertex AI
            embeddings_data = []
            for chunk in chunks:
                embedding = self.embedding_model.get_embeddings([chunk["text"]])[0].values
                embeddings_data.append({
                    "chunk_id": chunk["chunk_id"],
                    "contract_name": chunk["contract_name"],
                    "text": chunk["text"],
                    "section": chunk["section"],
                    "embedding": embedding,
                    "created_at": datetime.utcnow().isoformat()
                })
            
            # Store embeddings in GCS (embeddings/ for base contracts, kb/ for amendments)
            folder = "kb" if is_amendment else "embeddings"
            bucket = self.storage_client.bucket(self.temp_bucket)
            embeddings_filename = f"{file_path.stem}_embeddings.json"
            blob = bucket.blob(f"{folder}/{embeddings_filename}")
            blob.upload_from_string(json.dumps(embeddings_data), content_type="application/json")
            
            logger.info(f"Processed {file_path.name}: {len(chunks)} chunks in {folder}/")
            
            # Sync to Cloud SQL (non-blocking)
            asyncio.create_task(self._sync_to_sql(embeddings_filename, folder))
            
            return {"success": True, "filename": file_path.name, "chunks": len(chunks), "synced_to_sql": True}
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return {"success": False, "error": str(e)}
    
    def _split_into_chunks(self, text: str, filename: str, chunk_size: int = 500) -> List[Dict]:
        """Split text into chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size):
            chunk_text = " ".join(words[i:i + chunk_size])
            chunks.append({
                "contract_name": filename,
                "text": chunk_text,
                "section": f"chunk_{i//chunk_size + 1}",
                "chunk_id": hashlib.md5(chunk_text.encode()).hexdigest()[:8]
            })
        
        return chunks
    
    async def search_similar_documents(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search using Vertex AI embeddings and cosine similarity"""
        try:
            # Generate query embedding
            query_embedding = np.array(self.embedding_model.get_embeddings([query])[0].values)
            
            # Load embeddings from both folders in GCS
            bucket = self.storage_client.bucket(self.temp_bucket)
            all_chunks = []
            
            for folder in ["embeddings", "kb"]:
                blobs = bucket.list_blobs(prefix=f"{folder}/")
                for blob in blobs:
                    if blob.name.endswith(".json"):
                        content = blob.download_as_text()
                        chunks = json.loads(content)
                        all_chunks.extend(chunks)
            
            if not all_chunks:
                return []
            
            # Calculate cosine similarity
            for chunk in all_chunks:
                chunk_embedding = np.array(chunk["embedding"])
                similarity = np.dot(query_embedding, chunk_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
                )
                chunk["similarity"] = float(similarity)
                chunk.pop("embedding", None)
            
            # Sort and return top_k
            all_chunks.sort(key=lambda x: x["similarity"], reverse=True)
            return all_chunks[:top_k]
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        try:
            embedding = self.embedding_model.get_embeddings([text])[0].values
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return []
    
    async def _sync_to_sql(self, embeddings_filename: str, folder: str = "embeddings"):
        """Sync embeddings to Cloud SQL (called automatically after upload)"""
        try:
            from app.services.embeddings_sync_service import embeddings_sync_service
            result = await embeddings_sync_service.sync_to_sql(embeddings_filename, folder)
            if result["success"]:
                logger.info(f"Synced {folder}/{embeddings_filename} to SQL: {result['rows_synced']} rows")
            else:
                logger.error(f"Failed to sync {folder}/{embeddings_filename} to SQL: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error syncing to SQL: {str(e)}")

# Initialize singleton
from app.config.settings import settings
document_processor = GCPDocumentProcessor(settings.gcp_project_id, settings.gcp_region)
