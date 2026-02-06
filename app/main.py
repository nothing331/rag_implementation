"""
FastAPI application for the RAG API.
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import asyncio
from typing import AsyncGenerator

from app.config import get_settings
from app.models import (
    QueryRequest, QueryResponse, QueryMetadata,
    IngestRequest, IngestResponse, HealthStatus, Source
)
from app.core.pipeline import RAGPipeline
from app.core.vector_store import VectorStore
from app.core.embeddings import EmbeddingGenerator
from app.core.document_loader import load_documents, Document
from app.utils.logger import get_logger, setup_logging
import time
import hashlib

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Global pipeline instance
pipeline: RAGPipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    global pipeline
    
    # Startup
    logger.info("Starting up RAG API")
    settings = get_settings()
    
    try:
        # Initialize pipeline
        pipeline = RAGPipeline()
        logger.info("RAG pipeline initialized")
        
        # Ingest documents if vector store is empty
        if pipeline.vector_store.count() == 0:
            logger.info("Vector store empty, ingesting documents")
            await ingest_documents_internal()
        
        logger.info("Startup complete", vector_store_count=pipeline.vector_store.count())
        
    except Exception as e:
        logger.error("Startup failed", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down RAG API")


# Create FastAPI app
app = FastAPI(
    title="CloudSync RAG API",
    description="Agentic RAG system for technical documentation",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def ingest_documents_internal() -> IngestResponse:
    """Internal function to ingest documents."""
    start_time = time.time()
    
    try:
        # Load documents
        documents = load_documents("docs")
        logger.info(f"Loaded {len(documents)} documents")
        
        if not documents:
            return IngestResponse(
                status="no_documents",
                documents_processed=0,
                chunks_created=0,
                processing_time_ms=0,
                errors=["No documents found in docs/ directory"]
            )
        
        # Clear existing
        pipeline.vector_store.delete_all()
        
        # Process documents
        all_chunks = []
        all_embeddings = []
        all_metadatas = []
        
        for doc in documents:
            # Simple chunking by paragraphs
            paragraphs = doc.content.split('\n\n')
            
            for i, para in enumerate(paragraphs):
                if len(para.strip()) < 50:  # Skip short paragraphs
                    continue
                
                all_chunks.append(para)
                all_metadatas.append({
                    "document": doc.path,
                    "section": doc.metadata.get("title", "unknown"),
                    "paragraph": i
                })
                
        # Remove duplicates based on content
        seen_content = set()
        unique_chunks = []
        unique_metadatas = []
        
        for chunk, metadata in zip(all_chunks, all_metadatas):
            content_hash = hashlib.md5(chunk.strip().encode()).hexdigest()
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_chunks.append(chunk)
                unique_metadatas.append(metadata)
        
        all_chunks = unique_chunks
        all_metadatas = unique_metadatas
        
        # Generate embeddings in batches
        logger.info(f"Generating embeddings for {len(all_chunks)} chunks")
        embeddings = pipeline.embedding_gen.embed(all_chunks)
        
        # Add to vector store
        pipeline.vector_store.add_documents(
            documents=all_chunks,
            embeddings=embeddings,
            metadatas=all_metadatas
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Document ingestion complete",
            documents_processed=len(documents),
            chunks_created=len(all_chunks)
        )
        
        return IngestResponse(
            status="success",
            documents_processed=len(documents),
            chunks_created=len(all_chunks),
            processing_time_ms=processing_time,
            errors=[]
        )
        
    except Exception as e:
        logger.error("Document ingestion failed", error=str(e))
        return IngestResponse(
            status="error",
            documents_processed=0,
            chunks_created=0,
            processing_time_ms=int((time.time() - start_time) * 1000),
            errors=[str(e)]
        )


@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    
    dependencies = {
        "vector_store": {
            "status": "connected",
            "document_count": pipeline.vector_store.count() if pipeline else 0
        },
        "llm_service": {
            "status": "available",
            "provider": "groq",
            "model": settings.synthesizer_model
        }
    }
    
    return HealthStatus(
        status="healthy",
        dependencies=dependencies
    )


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Main query endpoint."""
    logger.info("Processing query", query=request.query, session_id=request.session_id)
    
    try:
        result = await pipeline.process(request.query, max_sources=request.max_sources)
        
        return QueryResponse(
            answer=result.answer,
            sources=result.sources,
            metadata=result.metadata
        )
        
    except Exception as e:
        logger.error("Query processing failed", error=str(e), query=request.query)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """Document ingestion endpoint."""
    logger.info("Starting document ingestion", force=request.force)
    
    if request.force:
        pipeline.vector_store.delete_all()
    
    result = await ingest_documents_internal()
    return result


@app.post("/api/v1/query/stream")
async def query_stream(request: QueryRequest):
    """Streaming query endpoint for real-time responses."""
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # First send the answer
            result = await pipeline.process(request.query, max_sources=request.max_sources)
            
            # Stream answer word by word
            words = result.answer.split()
            for word in words:
                yield f'data: {{"token": "{word} "}}\n\n'
                await asyncio.sleep(0.01)  # Small delay for streaming effect
            
            # Send sources
            sources_data = [{
                "document": s.document,
                "section": s.section,
                "relevance_score": s.relevance_score,
                "content_preview": s.content_preview
            } for s in result.sources]
            yield f'data: {{"sources": {sources_data}}}\n\n'
            
            # Send metadata
            metadata = {
                "processing_time_ms": result.metadata.processing_time_ms,
                "tokens_used": result.metadata.tokens_used,
                "confidence": result.metadata.confidence,
                "model_used": result.metadata.model_used
            }
            yield f'data: {{"metadata": {metadata}}}\n\n'
            
            # Send done event
            yield 'data: {"done": true}\n\n'
            
        except Exception as e:
            yield f'data: {{"error": "{str(e)}"}}\n\n'
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
