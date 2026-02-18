import os
from pathlib import Path
from typing import Optional
import logging

from app.config.settings import settings
from app.config.gcp_clients import get_storage_client

logger = logging.getLogger(__name__)

class HybridStorageService:
    """Handles both GCS (read) and local (write) storage"""
    
    def __init__(self):
        self.local_base = Path(settings.local_storage_path)
        self.storage_mode = settings.storage_mode
    
    async def read_from_gcs(self, bucket_name: str, file_path: str) -> bytes:
        """Read file from GCS (existing contracts)"""
        try:
            client = get_storage_client()
            if client is None:
                raise RuntimeError("GCS client not available. Check credentials.")
            
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(file_path)
            content = blob.download_as_bytes()
            logger.info(f"Read from GCS: gs://{bucket_name}/{file_path}")
            return content
        except Exception as e:
            logger.error(f"Failed to read from GCS: {e}")
            raise
    
    async def write_to_local(self, file_content: bytes, category: str, filename: str) -> str:
        """Write file to LOCAL storage (amendments, generated PDFs)"""
        try:
            local_path = self.local_base / category / filename
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"Saved locally: {local_path}")
            return str(local_path)
            
        except Exception as e:
            logger.error(f"Failed to write locally: {e}")
            raise
    
    async def read_from_local(self, file_path: str) -> bytes:
        """Read file from local storage"""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read local file: {e}")
            raise
    
    def get_local_path(self, category: str, filename: str) -> Path:
        """Get local file path"""
        return self.local_base / category / filename
    
    def file_exists_locally(self, category: str, filename: str) -> bool:
        """Check if file exists locally"""
        return self.get_local_path(category, filename).exists()
    
    async def list_gcs_files(self, bucket_name: str, prefix: str = "") -> list:
        """List files in GCS bucket"""
        try:
            client = get_storage_client()
            if client is None:
                return []
            
            bucket = client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Failed to list GCS files: {e}")
            return []

# Global instance
hybrid_storage = HybridStorageService()
