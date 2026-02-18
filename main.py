from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import os

from app.config.settings import settings
from app.api import contracts, search, chat, amendments, document_upload, document_modifications, insertion_suggestions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("=" * 60)
    logger.info("CONTRACT MINING ASSISTANT - PURE GCP ARCHITECTURE")
    logger.info("=" * 60)
    logger.info(f"Project: {settings.gcp_project_id}")
    logger.info(f"Region: {settings.gcp_region}")
    logger.info(f"Embeddings Bucket: {settings.gcs_embeddings_bucket}")
    logger.info("✅ Application started successfully")
    
    yield
    
    logger.info("Shutting down...")

app = FastAPI(
    title="Contract Mining Assistant API",
    description="AI-powered contract analysis with pure GCP architecture",
    version="3.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(contracts.router, prefix="/api/contracts", tags=["Contracts"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(amendments.router, prefix="/api/amendments", tags=["Amendments"])
app.include_router(document_upload.router, prefix="/api/documents", tags=["Documents"])
app.include_router(document_modifications.router, prefix="/api/modify", tags=["Modifications"])
app.include_router(insertion_suggestions.router, prefix="/api/insertion", tags=["Insertion Suggestions"])

# Serve frontend
@app.get("/frontend")
async def serve_frontend():
    """Serve the frontend HTML file"""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    else:
        return {"error": "Frontend file not found"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Contract Mining Assistant API",
        "version": "3.0.0",
        "architecture": "Pure GCP",
        "status": "running",
        "features": {
            "storage": "Google Cloud Storage",
            "embeddings": "Vertex AI text-embedding-004",
            "llm": "Gemini 1.5 Pro/Flash",
            "knowledge_base": "GCS Vector Storage",
            "document_ai": "Document AI OCR"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "platform": "GCP",
        "storage": "ready"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",            
        host="0.0.0.0",
        port=settings.api_port,
        log_level="info",
        reload=True            
    )
