"""
Retriever Agent - Handles vector search operations.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np
from app.core.vector_store import VectorStore
from app.core.embeddings import EmbeddingGenerator
from app.agents.planner import SubQuery


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata."""
    content: str
    document: str
    section: str
    relevance_score: float
    chunk_id: str
    

class RetrieverAgent:
    """Agent that retrieves relevant documents from the vector store."""
    
    def __init__(self, vector_store: Optional[VectorStore] = None, embedding_gen: Optional[EmbeddingGenerator] = None):
        """Initialize with vector store and embedding generator."""
        self.vector_store = vector_store if vector_store is not None else VectorStore()
        self.embedding_gen = embedding_gen if embedding_gen is not None else EmbeddingGenerator()
    
    def retrieve_parallel(
        self,
        sub_queries: List[SubQuery],
        top_k: int = 5
    ) -> List[RetrievedChunk]:
        """
        Execute parallel retrieval for all sub-queries.
        
        Args:
            sub_queries: List of sub-queries from planner
            top_k: Number of chunks to retrieve per query
            
        Returns:
            List of unique RetrievedChunk objects
        """
        all_chunks = []
        seen_ids = set()
        
        for sub_query in sub_queries:
            # Generate embedding for this sub-query
            query_embedding = self.embedding_gen.embed_single(sub_query.text)
            
            # Query vector store
            results = self.vector_store.query(
                query_embedding=query_embedding,
                n_results=top_k
            )
            
            # Process results
            if results and results.get('documents') and len(results['documents']) > 0:
                documents = results['documents'][0]
                metadatas = results.get('metadatas', [{}])[0] if results.get('metadatas') else [{}] * len(documents)
                ids = results.get('ids', [[]])[0] if results.get('ids') else [''] * len(documents)
                distances = results.get('distances', [[]])[0] if results.get('distances') else [0] * len(documents)
                
                for idx, (doc, metadata, doc_id, distance) in enumerate(zip(documents, metadatas, ids, distances)):
                    # Skip duplicates
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    
                    # Convert cosine distance to similarity score (lower distance = higher similarity)
                    # Chroma uses cosine distance where 0 = identical, 2 = opposite
                    similarity = 1 - (distance / 2) if distance is not None else 0.5
                    
                    chunk = RetrievedChunk(
                        content=doc,
                        document=metadata.get('document', 'unknown'),
                        section=metadata.get('section', 'unknown'),
                        relevance_score=max(0.0, min(1.0, similarity)),
                        chunk_id=doc_id
                    )
                    all_chunks.append(chunk)
        
        # Sort by relevance score (descending)
        all_chunks.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return all_chunks
    
    def retrieve_single(self, query: str, top_k: int = 5) -> List[RetrievedChunk]:
        """Convenience method for single query retrieval."""
        return self.retrieve_parallel([SubQuery(text=query, priority=1)], top_k=top_k)
