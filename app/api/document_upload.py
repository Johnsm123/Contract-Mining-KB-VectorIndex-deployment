"""Local document upload endpoint with processing"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
import os
import shutil
from pathlib import Path
from app.config.settings import settings
from app.services.local_document_processor import local_doc_processor

router = APIRouter()

@router.post("/upload-documents")
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload and process contract documents locally"""
    try:
        upload_dir = Path(settings.local_storage_path) / "uploaded_contracts"
        upload_dir.mkdir(exist_ok=True)
        
        results = []
        
        for file in files:
            if file.filename.endswith(('.pdf', '.docx', '.txt')):
                file_path = upload_dir / file.filename
                
                # Save uploaded file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # Process and vectorize
                processing_result = await local_doc_processor.process_uploaded_file(file_path)
                results.append(processing_result)
        
        return {
            "success": True,
            "results": results,
            "message": f"Processed {len(results)} documents"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list-documents")
async def list_documents():
    """List uploaded and processed documents"""
    try:
        uploaded = local_doc_processor.get_uploaded_files()
        processed = local_doc_processor.get_processed_files()
        
        return {
            "success": True,
            "uploaded_files": uploaded,
            "processed_files": processed,
            "total_uploaded": len(uploaded),
            "total_processed": len(processed)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))