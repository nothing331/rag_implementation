"""
Configuration module for the RAG application.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "CloudSync RAG"
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "development"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # External Services
    groq_api_key: str
    
    # Vector Store
    vector_store_path: str = "./data/chroma_db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Document Processing
    chunk_size: int = 500
    chunk_overlap: int = 50
    max_retrieval_chunks: int = 10
    validation_threshold: float = 0.6
    
    # Agent Models
    planner_model: str = "llama-3.1-70b-versatile"
    validator_model: str = "llama-3.1-70b-versatile"
    synthesizer_model: str = "llama-3.1-70b-versatile"
    
    # Agent Temperatures
    planner_temperature: float = 0.1
    validator_temperature: float = 0.0
    synthesizer_temperature: float = 0.3
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
