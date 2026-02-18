"""GCP Knowledge Base with Vector Storage in GCS"""
import logging
import json
from typing import List, Dict
from pathlib import Path
from google.cloud import storage
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
import numpy as np
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

class GCPKnowledgeBase:
    """Knowledge Base using GCS for vector storage and Vertex AI for embeddings"""
    
    def __init__(self, project_id: str, region: str, embeddings_bucket: str):
        self.project_id = project_id
        self.region = region
        self.embeddings_bucket = embeddings_bucket
        
        # Initialize clients
        self.storage_client = storage.Client(project=project_id)
        aiplatform.init(project=project_id, location=region)
        
        # Initialize embedding model
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        
        logger.info(f"Knowledge Base initialized with bucket: {embeddings_bucket}")
    
    async def add_document(self, file_path: Path, text_content: str, metadata: Dict = None) -> Dict:
        """Add document to knowledge base"""
        try:
            # Split into chunks
            chunks = self._split_into_chunks(text_content, file_path.name)
            
            # Generate embeddings
            embeddings_data = []
            for chunk in chunks:
                embedding = self.embedding_model.get_embeddings([chunk["text"]])[0].values
                embeddings_data.append({
                    "chunk_id": chunk["chunk_id"],
                    "contract_name": chunk["contract_name"],
                    "text": chunk["text"],
                    "section": chunk["section"],
                    "embedding": list(embedding),
                    "metadata": metadata or {},
                    "created_at": datetime.utcnow().isoformat()
                })
            
            # Store in GCS
            bucket = self.storage_client.bucket(self.embeddings_bucket)
            blob_name = f"kb/embeddings/{file_path.stem}_embeddings.json"
            blob = bucket.blob(blob_name)
            blob.upload_from_string(
                json.dumps(embeddings_data, indent=2),
                content_type="application/json"
            )
            
            # Store original document
            doc_blob_name = f"kb/documents/{file_path.name}"
            doc_blob = bucket.blob(doc_blob_name)
            with open(file_path, 'rb') as f:
                doc_blob.upload_from_file(f)
            
            logger.info(f"Added document to KB: {file_path.name} ({len(chunks)} chunks)")
            
            return {
                "success": True,
                "filename": file_path.name,
                "chunks": len(chunks),
                "embeddings_path": blob_name,
                "document_path": doc_blob_name
            }
            
        except Exception as e:
            logger.error(f"Error adding document to KB: {e}")
            return {"success": False, "error": str(e)}
    
    async def search(self, query: str, top_k: int = 5, filters: Dict = None) -> List[Dict]:
        """Search knowledge base using semantic similarity"""
        try:
            # Generate query embedding
            query_embedding = np.array(
                self.embedding_model.get_embeddings([query])[0].values
            )
            
            # Load embeddings from both kb/embeddings/ and kb/amendments/
            bucket = self.storage_client.bucket(self.embeddings_bucket)
            
            all_chunks = []
            
            # Search in kb/embeddings/
            embeddings_blobs = bucket.list_blobs(prefix="embeddings/")
            for blob in embeddings_blobs:
                if blob.name.endswith(".json"):
                    content = blob.download_as_text()
                    chunks = json.loads(content)
                    if filters:
                        chunks = [c for c in chunks if self._match_filters(c, filters)]
                    all_chunks.extend(chunks)
            
            # Search in kb/amendments/
            amendments_blobs = bucket.list_blobs(prefix="kb/amendments/")
            for blob in amendments_blobs:
                if blob.name.endswith(".json"):
                    content = blob.download_as_text()
                    chunks = json.loads(content)
                    if filters:
                        chunks = [c for c in chunks if self._match_filters(c, filters)]
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
                chunk.pop("embedding", None)  # Remove embedding from response
            
            # Sort by similarity and return top_k
            all_chunks.sort(key=lambda x: x["similarity"], reverse=True)
            
            logger.info(f"KB search found {len(all_chunks)} results for: {query[:50]}")
            return all_chunks[:top_k]
            
        except Exception as e:
            logger.error(f"KB search error: {e}")
            return []
    
    async def list_documents(self) -> List[Dict]:
        """List all documents in knowledge base"""
        try:
            bucket = self.storage_client.bucket(self.embeddings_bucket)
            blobs = bucket.list_blobs(prefix="kb/documents/")
            
            documents = []
            for blob in blobs:
                documents.append({
                    "name": blob.name.split("/")[-1],
                    "path": blob.name,
                    "size": blob.size,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []
    
    async def delete_document(self, filename: str) -> bool:
        """Delete document from knowledge base"""
        try:
            bucket = self.storage_client.bucket(self.embeddings_bucket)
            
            # Delete embeddings
            embedding_blob = bucket.blob(f"kb/embeddings/{Path(filename).stem}_embeddings.json")
            if embedding_blob.exists():
                embedding_blob.delete()
            
            # Delete document
            doc_blob = bucket.blob(f"kb/documents/{filename}")
            if doc_blob.exists():
                doc_blob.delete()
            
            logger.info(f"Deleted document from KB: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False
    
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
    
    def _match_filters(self, chunk: Dict, filters: Dict) -> bool:
        """Check if chunk matches filters"""
        for key, value in filters.items():
            if key in chunk and chunk[key] != value:
                return False
        return True
