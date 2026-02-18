from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # GCP Configuration
    gcp_project_id: str
    gcp_region: str = "us-central1"
    google_api_key: Optional[str] = None
    
    # GCS Buckets
    gcs_contracts_bucket: str
    gcs_amendments_bucket: str
    gcs_preview_buckets: str
    gcs_temp_bucket: str
    gcs_embeddings_bucket: str
    
    # Vertex AI
    vertex_ai_location: str = "us-central1"
    vertex_ai_model: str = "gemini-1.5-pro"
    vertex_ai_flash_model: str = "gemini-1.5-flash"
    embedding_model: str = "text-embedding-004"
    
    # Vertex AI Vector Search
    vector_search_index_endpoint: Optional[str] = None
    vector_search_index_id: Optional[str] = None
    vector_search_deployed_index_id: Optional[str] = None
    
    # Document AI
    document_ai_processor_id: str
    document_ai_location: str = "us"
    
    # Local Storage (fallback)
    local_storage_path: str = "./local_storage"
    
    # Application
    environment: str = "production"
    debug: bool = False
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
