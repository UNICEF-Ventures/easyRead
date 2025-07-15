"""
Base abstraction for embedding providers.
Provides a unified interface for both local and API-based embedding models.
"""

from abc import ABC, abstractmethod
from typing import List, Union, Optional, Dict, Any, Tuple
from pathlib import Path
import numpy as np
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    This class defines the interface that all embedding providers must implement,
    whether they are local models (like OpenCLIP) or API-based services (like OpenAI).
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the embedding provider.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config or {}
        self.provider_name = self.__class__.__name__
        
    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about this provider.
        
        Returns:
            Dictionary containing provider metadata including:
            - name: Provider name (e.g., 'openclip', 'openai')
            - model: Specific model (e.g., 'ViT-B-32', 'text-embedding-3-small')
            - embedding_dimension: Integer dimension
            - other metadata
        """
        pass
    
    @property
    def provider_identifier(self) -> str:
        """
        Get unique identifier for this provider configuration.
        
        Returns:
            String identifier in format 'provider:model'
        """
        info = self.get_provider_info()
        provider_name = info.get('name', 'unknown')
        model_name = info.get('model', 'default')
        return f"{provider_name}:{model_name}"
    
    def get_model_metadata(self) -> Dict[str, Any]:
        """
        Get standardized model metadata for database storage.
        
        Returns:
            Dictionary with provider_name, model_name, and embedding_dimension
        """
        info = self.get_provider_info()
        return {
            'provider_name': info.get('name', 'unknown'),
            'model_name': info.get('model', 'default'),
            'embedding_dimension': self.get_embedding_dimension()
        }
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available and ready to use.
        
        Returns:
            True if provider is available, False otherwise
        """
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this provider.
        
        Returns:
            Embedding dimension
        """
        pass
    
    @abstractmethod
    def encode_texts(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Encode a list of texts into embeddings.
        
        Args:
            texts: List of text strings to encode
            **kwargs: Provider-specific arguments
            
        Returns:
            numpy array of embeddings with shape (num_texts, embedding_dim)
        """
        pass
    
    @abstractmethod
    def encode_images(self, images: List[Union[str, Path, Image.Image]], **kwargs) -> np.ndarray:
        """
        Encode a list of images into embeddings.
        
        Args:
            images: List of image paths or PIL Image objects
            **kwargs: Provider-specific arguments
            
        Returns:
            numpy array of embeddings with shape (num_images, embedding_dim)
        """
        pass
    
    def encode_single_text(self, text: str, **kwargs) -> Optional[np.ndarray]:
        """
        Encode a single text into embedding.
        
        Args:
            text: Text string to encode
            **kwargs: Provider-specific arguments
            
        Returns:
            numpy array of embedding or None if encoding failed
        """
        try:
            embeddings = self.encode_texts([text], **kwargs)
            return embeddings[0] if len(embeddings) > 0 else None
        except Exception as e:
            logger.error(f"Error encoding single text with {self.provider_name}: {e}")
            return None
    
    def encode_single_image(self, image: Union[str, Path, Image.Image], **kwargs) -> Optional[np.ndarray]:
        """
        Encode a single image into embedding.
        
        Args:
            image: Image path or PIL Image object
            **kwargs: Provider-specific arguments
            
        Returns:
            numpy array of embedding or None if encoding failed
        """
        try:
            embeddings = self.encode_images([image], **kwargs)
            return embeddings[0] if len(embeddings) > 0 else None
        except Exception as e:
            logger.error(f"Error encoding single image with {self.provider_name}: {e}")
            return None
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Cosine similarity score
        """
        # Normalize embeddings
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Compute cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        return float(similarity)
    
    def find_most_similar(self, query_embedding: np.ndarray, 
                         candidate_embeddings: List[np.ndarray], 
                         top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Find most similar embeddings to a query embedding.
        
        Args:
            query_embedding: Query embedding to compare against
            candidate_embeddings: List of candidate embeddings
            top_k: Number of top results to return
            
        Returns:
            List of tuples (index, similarity_score) sorted by similarity
        """
        similarities = []
        
        for i, candidate in enumerate(candidate_embeddings):
            similarity = self.compute_similarity(query_embedding, candidate)
            similarities.append((i, similarity))
        
        # Sort by similarity score in descending order
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def cleanup(self):
        """
        Clean up resources used by this provider.
        Default implementation does nothing, override in subclasses if needed.
        """
        pass
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


class ProviderError(Exception):
    """Base exception for provider-related errors."""
    pass


class ProviderNotAvailableError(ProviderError):
    """Raised when a provider is not available."""
    pass


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is misconfigured."""
    pass


class EmbeddingError(ProviderError):
    """Raised when embedding generation fails."""
    pass