"""
Validator Agent - Validates retrieved chunks for relevance.
"""
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import json
import groq
from app.config import get_settings
from app.agents.retriever import RetrievedChunk
from app.agents.planner import SubQuery


@dataclass
class ValidatedChunk:
    """A validated chunk with confidence score."""
    chunk: RetrievedChunk
    confidence: float
    reasoning: str


class ValidatorAgent:
    """Agent that validates retrieved chunks against queries."""
    
    def __init__(self, min_confidence: float = 0.0):
        """Initialize with Groq client and threshold."""
        settings = get_settings()
        self.client = groq.Groq(api_key=settings.groq_api_key)
        self.model = settings.validator_model
        self.temperature = settings.validator_temperature
        self.min_confidence = min_confidence if min_confidence > 0 else settings.validation_threshold
    
    def validate_batch(
        self,
        chunks: List[RetrievedChunk],
        sub_queries: List[SubQuery],
        original_query: str
    ) -> Tuple[List[ValidatedChunk], List[str], bool]:
        """
        Validate a batch of retrieved chunks.
        
        Args:
            chunks: Retrieved chunks from retriever
            sub_queries: Original sub-queries
            original_query: The user's original query
            
        Returns:
            Tuple of (validated_chunks, missing_topics, needs_reretrieval)
        """
        if not chunks:
            return [], [sq.text for sq in sub_queries], True
        
        validated = []
        missing_topics = []
        
        # Validate each chunk
        for chunk in chunks:
            confidence, reasoning = self._validate_single(chunk, original_query)
            
            # Medium strictness: keep if confidence >= threshold
            if confidence >= self.min_confidence:
                validated.append(ValidatedChunk(
                    chunk=chunk,
                    confidence=confidence,
                    reasoning=reasoning
                ))
        
        # Sort by confidence
        validated.sort(key=lambda x: x.confidence, reverse=True)
        
        # Check coverage - which sub-queries aren't well covered
        covered_topics = set()
        for vc in validated[:5]:  # Check top 5
            for sq in sub_queries:
                if self._topic_coverage(vc.chunk, sq.text):
                    covered_topics.add(sq.text)
        
        for sq in sub_queries:
            if sq.text not in covered_topics:
                missing_topics.append(sq.text)
        
        # Decide if re-retrieval is needed
        # Medium strictness: need re-retrieval if < 3 valid chunks or missing high-priority topics
        high_priority_missing = any(
            sq.text in missing_topics and sq.priority == 1
            for sq in sub_queries
        )
        needs_reretrieval = len(validated) < 3 or high_priority_missing
        
        return validated, missing_topics, needs_reretrieval
    
    def _validate_single(self, chunk: RetrievedChunk, query: str) -> Tuple[float, str]:
        """Validate a single chunk using LLM."""
        # For prototype, use simple heuristic
        # In production, use LLM-based validation
        
        # Simple keyword-based validation for speed
        query_words = set(query.lower().split())
        chunk_words = set(chunk.content.lower().split())
        
        overlap = len(query_words.intersection(chunk_words))
        coverage = overlap / len(query_words) if query_words else 0
        
        # Adjust by original relevance score
        confidence = (coverage * 0.5) + (chunk.relevance_score * 0.5)
        
        if confidence > 0.8:
            reasoning = "High semantic relevance and keyword overlap"
        elif confidence > 0.6:
            reasoning = "Moderate relevance, likely useful"
        elif confidence > 0.4:
            reasoning = "Low relevance, may be tangential"
        else:
            reasoning = "Poor relevance, likely not useful"
        
        return confidence, reasoning
    
    def _topic_coverage(self, chunk: RetrievedChunk, sub_query: str) -> bool:
        """Check if a chunk covers a specific sub-query topic."""
        # Simple word overlap check
        query_words = set(sub_query.lower().split())
        chunk_words = set(chunk.content.lower().split())
        
        overlap = len(query_words.intersection(chunk_words))
        coverage_ratio = overlap / len(query_words) if query_words else 0
        
        return coverage_ratio > 0.3  # At least 30% word overlap
