"""
Embedding generation utilities.
"""
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np


class EmbeddingGenerator:
    """Handles text embedding generation."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Initialize with a sentence transformer model."""
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Embedding dimension: {self.dimension}")
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts."""
        if not texts:
            return np.array([])
        
        # Encode texts in batches for efficiency
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100
        )
        
        return embeddings
    
    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        return self.embed([text])[0]
