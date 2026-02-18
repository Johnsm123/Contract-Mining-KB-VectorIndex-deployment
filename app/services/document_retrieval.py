"""Service to fetch and process documents from GCS bucket"""
import logging
from typing import List, Dict, Optional
from google.cloud import storage
from docx import Document
import io
import PyPDF2
from app.config.gcp_clients import get_storage_client
from app.config.settings import settings

logger = logging.getLogger(__name__)

class DocumentRetrievalService:
    """Fetch and process documents from GCS bucket"""
    
    def __init__(self):
        self.contracts_bucket = settings.gcs_contracts_bucket
    
    async def search_documents(self, query: str, max_docs: int = 5) -> List[Dict]:
        """Search and retrieve relevant documents from GCS bucket or use sample data"""
        try:
            storage_client = get_storage_client()
            if not storage_client:
                logger.info("Using sample contract data for demonstration")
                return self._get_sample_contract_data(query)
            
            # Rest of GCS code...
            bucket = storage_client.bucket(self.contracts_bucket)
            blobs = list(bucket.list_blobs())
            
            logger.info(f"Found {len(blobs)} documents in bucket {self.contracts_bucket}")
            
            documents = []
            for blob in blobs[:max_docs]:
                try:
                    content = blob.download_as_bytes()
                    text_content = self._extract_text(content, blob.name)
                    
                    if text_content:
                        chunks = self._split_text(text_content, blob.name)
                        documents.extend(chunks)
                        
                except Exception as e:
                    logger.error(f"Error processing {blob.name}: {e}")
                    continue
            
            return documents
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return self._get_sample_contract_data(query)
    
    def _get_sample_contract_data(self, query: str) -> List[Dict]:
        """Return sample contract data for demonstration"""
        sample_contracts = [
            {
                "contract_name": "Medical Service Agreement - 2024",
                "text": "This Medical Service Agreement is between Healthcare Provider Inc. and Medical Center. The agreement covers telemedicine services, consultation fees of $150 per session, and confidentiality requirements under HIPAA. The contract term is 12 months with automatic renewal.",
                "section": "main_terms",
                "page_number": "1",
                "source": "sample_data"
            },
            {
                "contract_name": "Pharmaceutical Supply Contract",
                "text": "Supply agreement for pharmaceutical products including vaccines, medications, and medical supplies. Payment terms are Net 30 days. Quality standards must meet FDA requirements. Delivery schedule is monthly with emergency provisions.",
                "section": "supply_terms",
                "page_number": "1",
                "source": "sample_data"
            },
            {
                "contract_name": "Equipment Lease Agreement",
                "text": "Medical equipment lease for MRI machines, X-ray equipment, and diagnostic tools. Lease term is 36 months with maintenance included. Monthly payment is $5,000 with option to purchase at end of term.",
                "section": "lease_terms",
                "page_number": "1",
                "source": "sample_data"
            }
        ]
        
        # Filter based on query keywords
        relevant_contracts = []
        query_lower = query.lower()
        
        for contract in sample_contracts:
            if any(keyword in contract["text"].lower() for keyword in query_lower.split()):
                relevant_contracts.append(contract)
        
        # If no specific matches, return all for general queries
        return relevant_contracts if relevant_contracts else sample_contracts
    
    def _extract_text(self, content: bytes, filename: str) -> Optional[str]:
        """Extract text from document based on file type"""
        try:
            if filename.lower().endswith('.docx'):
                doc = Document(io.BytesIO(content))
                return "\\n".join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])
            
            elif filename.lower().endswith('.pdf'):
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\\n"
                return text
            
            elif filename.lower().endswith('.txt'):
                return content.decode('utf-8')
            
            else:
                logger.warning(f"Unsupported file type: {filename}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting text from {filename}: {e}")
            return None
    
    def _split_text(self, text: str, filename: str, chunk_size: int = 1000) -> List[Dict]:
        """Split text into chunks for better context management"""
        chunks = []
        words = text.split()
        
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            
            chunks.append({
                "contract_name": filename,
                "text": chunk_text,
                "section": f"chunk_{i//chunk_size + 1}",
                "page_number": f"{i//chunk_size + 1}",
                "source": "gcs_bucket"
            })
        
        return chunks

# Global instance
document_retrieval = DocumentRetrievalService()