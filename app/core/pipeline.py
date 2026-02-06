"""
Main orchestration pipeline for the RAG system.
"""
from typing import List, Dict, Any
import time
from dataclasses import dataclass
from app.config import get_settings
from app.agents.planner import QueryPlanner, SubQuery
from app.agents.retriever import RetrieverAgent, RetrievedChunk
from app.agents.validator import ValidatorAgent, ValidatedChunk
from app.agents.synthesizer import SynthesizerAgent
from app.core.vector_store import VectorStore
from app.core.embeddings import EmbeddingGenerator
from app.models import Source, QueryMetadata


@dataclass
class RAGResult:
    """Result from the RAG pipeline."""
    answer: str
    sources: List[Source]
    metadata: QueryMetadata


class RAGPipeline:
    """Main pipeline orchestrating all agents."""
    
    def __init__(self):
        """Initialize the pipeline with all agents."""
        settings = get_settings()
        
        # Initialize core components
        self.vector_store = VectorStore(settings.vector_store_path)
        self.embedding_gen = EmbeddingGenerator(settings.embedding_model)
        
        # Initialize agents
        self.planner = QueryPlanner()
        self.retriever = RetrieverAgent(self.vector_store, self.embedding_gen)
        self.validator = ValidatorAgent()
        self.synthesizer = SynthesizerAgent()
        
        self.settings = settings
    
    async def process(self, query: str, max_sources: int = 5) -> RAGResult:
        """
        Process a query through the complete RAG pipeline.
        
        Args:
            query: User's natural language query
            max_sources: Maximum number of sources to include
            
        Returns:
            RAGResult containing answer, sources, and metadata
        """
        start_time = time.time()
        
        # Step 1: Plan - Decompose query into sub-queries
        sub_queries = self.planner.plan(query)
        
        # Step 2: Retrieve - Search vector store in parallel
        chunks = self.retriever.retrieve_parallel(sub_queries, top_k=5)
        
        # Step 3: Validate - Check chunk relevance
        validated, missing_topics, needs_reretrieval = self.validator.validate_batch(
            chunks, sub_queries, query
        )
        
        # Step 3b: Re-retrieve if needed (one retry with expanded queries)
        if needs_reretrieval:
            expanded_queries = self._expand_queries(sub_queries)
            additional_chunks = self.retriever.retrieve_parallel(expanded_queries, top_k=3)
            validated.extend([
                ValidatedChunk(chunk=chunk, confidence=chunk.relevance_score, reasoning="Retry retrieval")
                for chunk in additional_chunks
            ])
            # Re-sort and deduplicate
            validated = self._deduplicate_validated(validated)
        
        # Step 4: Synthesize - Generate response
        answer = await self.synthesizer.synthesize(query, validated[:max_sources])
        
        # Calculate metadata
        processing_time = int((time.time() - start_time) * 1000)
        
        # Convert to Source objects
        sources = [
            Source(
                document=vc.chunk.document,
                section=vc.chunk.section,
                relevance_score=vc.confidence,
                content_preview=vc.chunk.content[:200] + "..." if len(vc.chunk.content) > 200 else vc.chunk.content
            )
            for vc in validated[:max_sources]
        ]
        
        metadata = QueryMetadata(
            processing_time_ms=processing_time,
            tokens_used=self._estimate_tokens(query, answer, validated),
            confidence=self._calculate_confidence(validated),
            sub_queries=[sq.text for sq in sub_queries],
            model_used=self.settings.synthesizer_model
        )
        
        return RAGResult(
            answer=answer,
            sources=sources,
            metadata=metadata
        )
    
    def _expand_queries(self, sub_queries: List[SubQuery]) -> List[SubQuery]:
        """Expand queries with synonyms for better retrieval."""
        expanded = []
        for sq in sub_queries:
            expanded.append(sq)
            # Add variations with different phrasing
            expanded.append(SubQuery(
                text=f"guide for {sq.text}",
                priority=sq.priority + 1
            ))
        return expanded
    
    def _deduplicate_validated(self, validated: List[ValidatedChunk]) -> List[ValidatedChunk]:
        """Remove duplicate chunks."""
        seen_ids = set()
        unique = []
        for vc in validated:
            if vc.chunk.chunk_id not in seen_ids:
                seen_ids.add(vc.chunk.chunk_id)
                unique.append(vc)
        return unique
    
    def _estimate_tokens(self, query: str, answer: str, validated: List[ValidatedChunk]) -> int:
        """Estimate total token usage."""
        # Rough estimate: 1 token ≈ 4 characters
        query_tokens = len(query) // 4
        answer_tokens = len(answer) // 4
        context_tokens = sum(len(vc.chunk.content) for vc in validated) // 4
        return query_tokens + answer_tokens + context_tokens + 100  # Add overhead
    
    def _calculate_confidence(self, validated: List[ValidatedChunk]) -> float:
        """Calculate overall confidence score."""
        if not validated:
            return 0.0
        # Average confidence of top 3 chunks
        top_confidences = [vc.confidence for vc in validated[:3]]
        return sum(top_confidences) / len(top_confidences)
