"""Vertex AI Vector Search Service"""
import logging
import os
import grpc
from typing import List, Dict
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
from app.config.settings import settings

# Disable gRPC SSL verification for development
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '1'
os.environ['GRPC_POLL_STRATEGY'] = 'poll'

logger = logging.getLogger(__name__)

class VertexAIVectorSearch:
    """Vector search using Vertex AI Vector Search endpoint"""
    
    def __init__(self):
        # Configure gRPC channel options for SSL
        channel_options = [
            ('grpc.ssl_target_name_override', 'aiplatform.googleapis.com'),
            ('grpc.default_authority', 'aiplatform.googleapis.com'),
        ]
        
        aiplatform.init(
            project=settings.gcp_project_id,
            location=settings.vertex_ai_location
        )
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        
        if settings.vector_search_index_endpoint:
            try:
                # Use public endpoint with proper configuration
                endpoint_name = f"projects/{settings.gcp_project_id}/locations/{settings.vertex_ai_location}/indexEndpoints/{settings.vector_search_index_endpoint}"
                
                self.endpoint = aiplatform.MatchingEngineIndexEndpoint(
                    index_endpoint_name=endpoint_name
                )
                self.deployed_index_id = settings.vector_search_deployed_index_id or "contract_mining_kb_deployed"
                logger.info(f"Vector Search initialized: {settings.vector_search_index_endpoint}")
            except Exception as e:
                logger.error(f"Vector Search init failed: {e}")
                self.endpoint = None
        else:
            self.endpoint = None
            logger.warning("Vector Search not configured")
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search using Vector Search endpoint"""
        if not self.endpoint:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.get_embeddings([query])[0].values
            
            # Search using endpoint
            response = self.endpoint.find_neighbors(
                deployed_index_id=self.deployed_index_id,
                queries=[query_embedding],
                num_neighbors=top_k
            )
            
            # Format results
            results = []
            for neighbor in response[0]:
                results.append({
                    "id": neighbor.id,
                    "distance": neighbor.distance,
                    "similarity": 1 - neighbor.distance
                })
            
            logger.info(f"Vector Search found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Vector Search error: {e}")
            return []

# Singleton
vertex_vector_search = VertexAIVectorSearch()
