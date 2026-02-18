from typing import List, Optional
import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Generate embeddings using local models"""
    
    def __init__(self):
        self.model_name = settings.embedding_model
        logger.warning("Vertex AI embeddings not available, using local embeddings")
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for single text"""
        logger.warning("Embedding generation not available")
        return None
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts"""
        logger.warning("Batch embedding generation not available")
        return [None] * len(texts)

# Global instance
embedding_service = EmbeddingService()
