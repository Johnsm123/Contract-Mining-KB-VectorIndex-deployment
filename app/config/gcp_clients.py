"""GCP clients initialization - Pure GCP"""
import logging
from pathlib import Path
from .settings import settings

logger = logging.getLogger(__name__)

def init_local_storage():
    """Create local storage directories for fallback"""
    base_path = Path(settings.local_storage_path)
    directories = ['contracts', 'amendments', 'previews', 'temp', 'uploaded_contracts', 'embeddings']
    
    for dir_name in directories:
        dir_path = base_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("Local storage initialized")
