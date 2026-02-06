"""
Pydantic models for API requests and responses.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class Source(BaseModel):
    """A source document citation."""
    document: str = Field(..., description="Document path/name")
    section: str = Field(..., description="Section or context")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score 0-1")
    content_preview: str = Field(..., description="Brief excerpt from document")


class QueryMetadata(BaseModel):
    """Metadata about query processing."""
    model_config = ConfigDict(protected_namespaces=())
    
    processing_time_ms: int = Field(..., description="Total processing time in milliseconds")
    tokens_used: int = Field(..., description="Total LLM tokens consumed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    sub_queries: List[str] = Field(default_factory=list, description="Decomposed sub-queries")
    model_used: str = Field(..., description="LLM model used for synthesis")


class QueryRequest(BaseModel):
    """Request body for query endpoint."""
    query: str = Field(..., min_length=1, description="User query string")
    session_id: Optional[str] = Field(None, description="Optional session ID for tracking")
    max_sources: int = Field(default=5, ge=1, le=10, description="Maximum number of sources")


class QueryResponse(BaseModel):
    """Response from query endpoint."""
    answer: str = Field(..., description="Generated answer with citations")
    sources: List[Source] = Field(default_factory=list, description="List of cited sources")
    metadata: QueryMetadata = Field(..., description="Processing metadata")


class IngestRequest(BaseModel):
    """Request body for document ingestion."""
    force: bool = Field(default=False, description="Force re-ingestion even if unchanged")
    paths: Optional[List[str]] = Field(None, description="Specific directories to ingest")


class IngestResponse(BaseModel):
    """Response from document ingestion."""
    status: str = Field(..., description="Processing status")
    documents_processed: int = Field(..., description="Number of documents processed")
    chunks_created: int = Field(..., description="Number of chunks created")
    chunks_updated: int = Field(default=0, description="Number of chunks updated")
    chunks_deleted: int = Field(default=0, description="Number of chunks deleted")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class HealthStatus(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0")
    dependencies: Dict[str, Any] = Field(default_factory=dict, description="Dependency statuses")
