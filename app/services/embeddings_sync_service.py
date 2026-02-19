"""Service to sync embeddings from GCS to Cloud SQL"""
import pandas as pd
from google.cloud import storage
from googleapiclient import discovery
import json
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

class EmbeddingsSyncService:
    """Sync embeddings JSON to Cloud SQL"""
    
    def __init__(self):
        self.storage_client = storage.Client(project=settings.gcp_project_id)
        self.sql_service = discovery.build('sqladmin', 'v1beta4')
    
    async def sync_to_sql(self, embeddings_file_name: str, folder: str = "embeddings") -> dict:
        """
        Convert embeddings JSON to CSV and import to Cloud SQL
        
        Args:
            embeddings_file_name: Name of JSON file (e.g., "contract_abc_embeddings.json")
            folder: Folder in temps bucket - "embeddings" for base contracts or "kb" for amendments
        
        Returns:
            dict with success status and details
        """
        try:
            bucket_name = settings.gcs_embeddings_bucket
            file_path = f"{folder}/{embeddings_file_name}"
            
            logger.info(f"Syncing to SQL: gs://{bucket_name}/{file_path}")
            
            # 1. Download JSON from GCS
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(file_path)
            
            if not blob.exists():
                logger.error(f"File not found: gs://{bucket_name}/{file_path}")
                return {"success": False, "error": "File not found"}
            
            json_content = blob.download_as_text()
            data = json.loads(json_content)
            
            # 2. Convert to DataFrame
            rows = []
            for item in data:
                rows.append({
                    'contract_name': item.get('contract_name', ''),
                    'chunk_id': item.get('chunk_id', ''),
                    'text': item.get('text', ''),
                    'section': item.get('section', ''),
                    'embedding': json.dumps(item.get('embedding', [])),
                    'metadata': json.dumps(item.get('metadata', {}))
                })
            
            if not rows:
                logger.warning(f"No data found in {file_path}")
                return {"success": False, "error": "No data in file"}
            
            df = pd.DataFrame(rows)
            
            # 3. Save CSV to temp-csv/ folder in GCS
            csv_filename = embeddings_file_name.replace('.json', '.csv')
            csv_path = f"temp-csv/{csv_filename}"
            csv_blob = bucket.blob(csv_path)
            csv_blob.upload_from_string(df.to_csv(index=False, header=False), 'text/csv')
            
            logger.info(f"CSV created: gs://{bucket_name}/{csv_path}")
            
            # 4. Import CSV to Cloud SQL
            import_request = {
                "importContext": {
                    "fileType": "CSV",
                    "uri": f"gs://{bucket_name}/{csv_path}",
                    "database": "contract_mining_db",
                    "csvImportOptions": {
                        "table": "embeddings",
                        "columns": ["contract_name", "chunk_id", "text", "section", "embedding", "metadata"]
                    }
                }
            }
            
            response = self.sql_service.instances().import_(
                project=settings.gcp_project_id,
                instance='contractminingai',
                body=import_request
            ).execute()
            
            logger.info(f"SQL import started: {response.get('name', 'unknown')}")
            
            return {
                "success": True,
                "rows_synced": len(rows),
                "csv_path": f"gs://{bucket_name}/{csv_path}",
                "sql_operation": response.get('name', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error syncing to SQL: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

# Global instance
embeddings_sync_service = EmbeddingsSyncService()
