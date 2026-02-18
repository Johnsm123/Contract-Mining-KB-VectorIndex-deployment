"""Local document processing with vectorization"""
import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
from docx import Document
import PyPDF2
import hashlib

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"SentenceTransformers not available: {e}")
    TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
    np = None
    cosine_similarity = None

from app.config.settings import settings

# Import GCP processor
try:
    from app.services.gcp_document_processor import GCPDocumentProcessor
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    logger.warning("GCP services not available, using local processing only")

class LocalDocumentProcessor:
    """Process documents locally with vectorization or GCP"""
    
    def __init__(self):
        self.upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
        self.embeddings_dir = Path(settings.local_storage_path) / "embeddings"
        self.upload_dir.mkdir(exist_ok=True)
        self.embeddings_dir.mkdir(exist_ok=True)
        
        # Initialize GCP processor if available
        if GCP_AVAILABLE and hasattr(settings, 'gcp_project_id'):
            try:
                self.gcp_processor = GCPDocumentProcessor(
                    settings.gcp_project_id,
                    settings.gcp_region
                )
                logger.info("GCP processor initialized")
            except Exception as e:
                logger.warning(f"GCP processor init failed: {e}")
                self.gcp_processor = None
        else:
            self.gcp_processor = None
        
        # Initialize local embedding model as fallback
        try:
            if TRANSFORMERS_AVAILABLE:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Local embedding model loaded")
            else:
                self.embedding_model = None
                logger.warning("SentenceTransformers not available, using keyword search only")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.embedding_model = None
    
    async def process_uploaded_file(self, file_path: Path) -> Dict:
        """Process a single uploaded file using GCP or local processing"""
        try:
            # Extract text
            text_content = self._extract_text_from_file(file_path)
            if not text_content:
                return {"success": False, "error": "Could not extract text"}
            
            # Use GCP processor if available
            if self.gcp_processor:
                return await self.gcp_processor.process_uploaded_file(file_path, text_content)
            
            # Fallback to local processing
            chunks = self._split_into_chunks(text_content, file_path.name)
            
            embeddings_data = []
            if self.embedding_model:
                for chunk in chunks:
                    embedding = self.embedding_model.encode(chunk["text"])
                    chunk["embedding"] = embedding.tolist()
                    embeddings_data.append(chunk)
            else:
                embeddings_data = chunks
            
            embedding_file = self.embeddings_dir / f"{file_path.stem}_embeddings.json"
            with open(embedding_file, 'w', encoding='utf-8') as f:
                json.dump(embeddings_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Processed {file_path.name}: {len(chunks)} chunks")
            
            return {
                "success": True,
                "filename": file_path.name,
                "chunks": len(chunks),
                "embeddings": len(embeddings_data)
            }
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return {"success": False, "error": str(e)}
    
    def _extract_text_from_file(self, file_path: Path) -> Optional[str]:
        """Extract text from various file formats"""
        try:
            if file_path.suffix.lower() == '.docx':
                doc = Document(file_path)
                return "\\n".join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])
            
            elif file_path.suffix.lower() == '.pdf':
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\\n"
                    return text
            
            elif file_path.suffix.lower() == '.txt':
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            
            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return None
    
    def _split_into_chunks(self, text: str, filename: str, chunk_size: int = 500) -> List[Dict]:
        """Split text into manageable chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            
            chunks.append({
                "contract_name": filename,
                "text": chunk_text,
                "section": f"chunk_{i//chunk_size + 1}",
                "page_number": str(i//chunk_size + 1),
                "source": "local_upload",
                "chunk_id": hashlib.md5(chunk_text.encode()).hexdigest()[:8]
            })
        
        return chunks
    
    async def search_similar_documents(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search using GCP Vector Search or local embeddings"""
        try:
            # Use GCP processor if available
            if self.gcp_processor:
                return await self.gcp_processor.search_similar_documents(query, top_k)
            
            # Fallback to local search
            if not self.embedding_model:
                return self._fallback_keyword_search(query, top_k)
            
            query_embedding = self.embedding_model.encode(query)
            
            all_chunks = []
            for embedding_file in self.embeddings_dir.glob("*_embeddings.json"):
                try:
                    with open(embedding_file, 'r', encoding='utf-8') as f:
                        chunks = json.load(f)
                        all_chunks.extend(chunks)
                except Exception as e:
                    logger.error(f"Error loading {embedding_file}: {e}")
            
            if not all_chunks:
                logger.warning("No embeddings found")
                return []
            
            similarities = []
            for chunk in all_chunks:
                if "embedding" in chunk and TRANSFORMERS_AVAILABLE and np is not None:
                    chunk_embedding = np.array(chunk["embedding"])
                    similarity = cosine_similarity([query_embedding], [chunk_embedding])[0][0]
                    chunk["similarity"] = float(similarity)
                    similarities.append(chunk)
            
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            for chunk in similarities[:top_k]:
                chunk.pop("embedding", None)
            
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return self._fallback_keyword_search(query, top_k)
    
    def _fallback_keyword_search(self, query: str, top_k: int) -> List[Dict]:
        """Fallback keyword-based search"""
        try:
            query_words = set(query.lower().split())
            all_chunks = []
            
            for embedding_file in self.embeddings_dir.glob("*_embeddings.json"):
                try:
                    with open(embedding_file, 'r', encoding='utf-8') as f:
                        chunks = json.load(f)
                        all_chunks.extend(chunks)
                except Exception as e:
                    logger.error(f"Error loading {embedding_file}: {e}")
            
            if not all_chunks:
                return []
            
            scored_chunks = []
            for chunk in all_chunks:
                chunk_words = set(chunk["text"].lower().split())
                score = len(query_words.intersection(chunk_words)) / len(query_words)
                if score > 0:
                    chunk["similarity"] = score
                    scored_chunks.append(chunk)
            
            scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
            return scored_chunks[:top_k]
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    async def get_contract_context(self, contract_id: str) -> str:
        """Get contract context for AI modification requests"""
        try:
            # Search for contract by ID
            results = await self.search_similar_documents(contract_id, top_k=3)
            
            if results:
                context_text = "\n\n".join([chunk["text"] for chunk in results])
                return context_text[:2000]  # Limit context size
            
            return "Contract context not available"
            
        except Exception as e:
            logger.error(f"Error getting contract context: {e}")
            return "Contract context not available"
    
    def get_uploaded_files(self) -> List[str]:
        """Get list of uploaded files"""
        return [f.name for f in self.upload_dir.glob("*") if f.is_file()]
    
    def get_processed_files(self) -> List[str]:
        """Get list of processed files with embeddings"""
        return [f.stem.replace("_embeddings", "") for f in self.embeddings_dir.glob("*_embeddings.json")]

# Global instance
local_doc_processor = LocalDocumentProcessor()