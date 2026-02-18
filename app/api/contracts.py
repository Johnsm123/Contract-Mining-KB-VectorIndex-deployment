from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
import uuid
import logging
from datetime import datetime
from pathlib import Path
import shutil
import asyncio

from app.services.local_document_processor import local_doc_processor
from app.config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_contract(
    file: UploadFile = File(...),
    contract_id: str = Form(...),
    name: str = Form(...),
    year: int = Form(...),
    user_id: str = Form(...),
    payer_id: Optional[str] = Form(None),
    hospital_id: Optional[str] = Form(None)
):
    """Upload single contract locally with processing"""
    try:
        # Validate file type
        if not file.filename.endswith(('.docx', '.pdf', '.txt')):
            raise HTTPException(status_code=400, detail="Only DOCX, PDF, and TXT files are supported")
        
        # Save to local storage
        upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
        upload_dir.mkdir(exist_ok=True)
        
        # Create unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{contract_id}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = upload_dir / unique_filename
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process and vectorize
        processing_result = await local_doc_processor.process_uploaded_file(file_path)
        
        logger.info(f"✅ Uploaded contract: {contract_id}")
        
        return {
            "success": True,
            "contract_id": contract_id,
            "name": name,
            "year": year,
            "user_id": user_id,
            "payer_id": payer_id,
            "hospital_id": hospital_id,
            "filename": unique_filename,
            "local_path": str(file_path),
            "file_size": file_path.stat().st_size,
            "processing_result": processing_result,
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-batch")
async def upload_contracts_batch(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...),
    year: Optional[int] = Form(2024),
    payer_id: Optional[str] = Form(None),
    hospital_id: Optional[str] = Form(None)
):
    """Upload multiple contracts at once (25-50 documents)"""
    try:
        upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
        upload_dir.mkdir(exist_ok=True)
        
        results = []
        failed_uploads = []
        
        logger.info(f"🚀 Starting batch upload of {len(files)} files")
        
        # Process each file
        for i, file in enumerate(files, 1):
            try:
                # Validate file type
                if not file.filename.endswith(('.docx', '.pdf', '.txt')):
                    failed_uploads.append({
                        "filename": file.filename,
                        "error": "Unsupported file type. Only DOCX, PDF, and TXT files are supported"
                    })
                    continue
                
                # Generate contract_id from filename
                contract_id = Path(file.filename).stem
                
                # Create unique filename
                file_extension = Path(file.filename).suffix
                unique_filename = f"{contract_id}_{uuid.uuid4().hex[:8]}{file_extension}"
                file_path = upload_dir / unique_filename
                
                # Save uploaded file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # Process and vectorize in background for faster batch processing
                processing_task = asyncio.create_task(
                    local_doc_processor.process_uploaded_file(file_path)
                )
                
                results.append({
                    "success": True,
                    "contract_id": contract_id,
                    "original_filename": file.filename,
                    "unique_filename": unique_filename,
                    "user_id": user_id,
                    "year": year,
                    "payer_id": payer_id,
                    "hospital_id": hospital_id,
                    "local_path": str(file_path),
                    "file_size": file_path.stat().st_size,
                    "status": "processing",
                    "processing_task": processing_task
                })
                
                logger.info(f"📄 [{i}/{len(files)}] Uploaded: {file.filename}")
                
            except Exception as e:
                logger.error(f"❌ Failed to upload {file.filename}: {e}")
                failed_uploads.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        # Wait for all processing tasks to complete
        logger.info("⏳ Waiting for document processing to complete...")
        for result in results:
            if "processing_task" in result:
                try:
                    processing_result = await result["processing_task"]
                    result["processing_result"] = processing_result
                    result["status"] = "completed"
                    del result["processing_task"]  # Remove task from response
                except Exception as e:
                    result["status"] = "failed"
                    result["processing_error"] = str(e)
                    del result["processing_task"]
        
        logger.info(f"✅ Batch upload completed: {len(results)} successful, {len(failed_uploads)} failed")
        
        return {
            "success": True,
            "total_files": len(files),
            "successful_uploads": len(results),
            "failed_uploads": len(failed_uploads),
            "results": results,
            "failures": failed_uploads,
            "message": f"Processed {len(results)} documents successfully"
        }
        
    except Exception as e:
        logger.error(f"Batch upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{contract_id}")
async def get_contract(contract_id: str, user_id: str):
    """Get contract details from local storage"""
    try:
        upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
        
        # Find contract file by contract_id prefix
        contract_files = list(upload_dir.glob(f"{contract_id}_*"))
        
        if not contract_files:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        contract_file = contract_files[0]
        
        return {
            "success": True,
            "contract": {
                "contract_id": contract_id,
                "filename": contract_file.name,
                "file_size": contract_file.stat().st_size,
                "created_at": datetime.fromtimestamp(contract_file.stat().st_ctime).isoformat(),
                "local_path": str(contract_file)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get contract failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_contracts(user_id: str, year: Optional[int] = None):
    """List all contracts from local storage"""
    try:
        upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
        
        if not upload_dir.exists():
            return {
                "success": True,
                "contracts": [],
                "count": 0
            }
        
        contracts = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                contracts.append({
                    "filename": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "created_at": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                    "local_path": str(file_path)
                })
        
        # Sort by creation time (newest first)
        contracts.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "success": True,
            "contracts": contracts,
            "count": len(contracts)
        }
        
    except Exception as e:
        logger.error(f"List contracts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background processing is handled by local_doc_processor

@router.delete("/{contract_id}")
async def delete_contract(contract_id: str, user_id: str):
    """Delete contract from local storage"""
    try:
        upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
        embeddings_dir = Path(settings.local_storage_path) / "embeddings"
        
        # Find and delete contract file
        contract_files = list(upload_dir.glob(f"{contract_id}_*"))
        
        if not contract_files:
            raise HTTPException(status_code=404, detail="Contract not found")
        
        deleted_files = []
        for contract_file in contract_files:
            contract_file.unlink()
            deleted_files.append(contract_file.name)
            
            # Delete corresponding embeddings
            embedding_file = embeddings_dir / f"{contract_file.stem}_embeddings.json"
            if embedding_file.exists():
                embedding_file.unlink()
                deleted_files.append(embedding_file.name)
        
        return {
            "success": True, 
            "message": "Contract deleted",
            "deleted_files": deleted_files
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete contract failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
