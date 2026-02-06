"""
Vector store wrapper using ChromaDB.
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import numpy as np
from pathlib import Path
import hashlib


class VectorStore:
    """ChromaDB wrapper for document storage and retrieval."""
    
    def __init__(self, persist_directory: str = "./data/chroma_db"):
        """Initialize ChromaDB client."""
        Path(persist_directory).parent.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.Client(
            Settings(
                persist_directory=persist_directory,
                anonymized_telemetry=False
            )
        )
        
        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_documents(
        self,
        documents: List[str],
        embeddings: np.ndarray,
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> None:
        """Add documents with their embeddings to the store."""
        if ids is None:
            # Generate IDs from content hash
            ids = [
                hashlib.md5(doc.encode()).hexdigest()[:16]
                for doc in documents
            ]
        
        # Convert embeddings to list for Chroma
        embeddings_list = embeddings.tolist() if isinstance(embeddings, np.ndarray) else embeddings
        
        self.collection.add(
            documents=documents,
            embeddings=embeddings_list,
            metadatas=metadatas,
            ids=ids
        )
    
    def query(
        self,
        query_embedding: np.ndarray,
        n_results: int = 10,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Query the vector store for similar documents."""
        # Convert to list if numpy array
        query_list = query_embedding.tolist() if isinstance(query_embedding, np.ndarray) else query_embedding
        
        results = self.collection.query(
            query_embeddings=[query_list],
            n_results=n_results,
            where=where
        )
        
        return results
    
    def delete_all(self) -> None:
        """Delete all documents from the collection."""
        self.client.delete_collection("documents")
        self.collection = self.client.create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
    
    def count(self) -> int:
        """Get total number of documents."""
        return self.collection.count()
    
    def peek(self, limit: int = 5) -> Dict[str, Any]:
        """Peek at documents in the collection."""
        return self.collection.peek(limit=limit)
