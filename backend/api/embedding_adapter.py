"""
Compatibility adapter for the new embedding provider system.
Provides backward compatibility with existing code while using the new abstraction.
"""

import numpy as np
from typing import List, Union, Optional, Dict, Any
from pathlib import Path
from PIL import Image
from contextlib import contextmanager
import logging

from .embedding_providers import (
    EmbeddingProvider, 
    get_embedding_provider, 
    cleanup_global_provider
)

logger = logging.getLogger(__name__)


class EmbeddingModelAdapter:
    """
    Adapter class that provides the same interface as the old EmbeddingModel
    but uses the new provider system underneath.
    """
    
    def __init__(self, provider: EmbeddingProvider = None):
        """
        Initialize the adapter.
        
        Args:
            provider: Embedding provider to use (optional, will get default if not provided)
        """
        self.provider = provider or get_embedding_provider()
        self.model_name = getattr(self.provider, 'model_name', self.provider.__class__.__name__)
        self.device = getattr(self.provider, 'device', 'auto')
    
    def encode_images(self, images: List[Union[str, Path, Image.Image]], batch_size: int = 8) -> np.ndarray:
        """
        Encode a list of images into embeddings.
        
        Args:
            images: List of image paths or PIL Image objects
            batch_size: Batch size for processing
            
        Returns:
            numpy array of embeddings with shape (num_images, embedding_dim)
        """
        return self.provider.encode_images(images, batch_size=batch_size)
    
    def encode_texts(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        """
        Encode a list of texts into embeddings.
        
        Args:
            texts: List of text strings
            batch_size: Batch size for processing
            
        Returns:
            numpy array of embeddings with shape (num_texts, embedding_dim)
        """
        return self.provider.encode_texts(texts, batch_size=batch_size)
    
    def encode_single_image(self, image: Union[str, Path, Image.Image]) -> Optional[np.ndarray]:
        """
        Encode a single image into embedding.
        
        Args:
            image: Image path or PIL Image object
            
        Returns:
            numpy array of embedding or None if processing failed
        """
        return self.provider.encode_single_image(image)
    
    def encode_single_text(self, text: str) -> Optional[np.ndarray]:
        """
        Encode a single text into embedding.
        
        Args:
            text: Text string
            
        Returns:
            numpy array of embedding or None if processing failed
        """
        return self.provider.encode_single_text(text)
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Cosine similarity score
        """
        return self.provider.compute_similarity(embedding1, embedding2)
    
    def find_most_similar(self, query_embedding: np.ndarray, 
                         candidate_embeddings: List[np.ndarray], 
                         top_k: int = 5) -> List[tuple]:
        """
        Find most similar embeddings to a query embedding.
        
        Args:
            query_embedding: Query embedding to compare against
            candidate_embeddings: List of candidate embeddings
            top_k: Number of top results to return
            
        Returns:
            List of tuples (index, similarity_score) sorted by similarity
        """
        return self.provider.find_most_similar(query_embedding, candidate_embeddings, top_k)
    
    def cleanup(self):
        """Clean up resources used by this adapter."""
        if self.provider:
            self.provider.cleanup()
    
    def __del__(self):
        """Destructor to ensure cleanup when object is garbage collected."""
        self.cleanup()


# Backward compatibility functions

# Global adapter instance for caching
_global_adapter = None

def get_embedding_model(model_name: str = None, model_size: str = None, 
                       force_reload: bool = False) -> EmbeddingModelAdapter:
    """
    Get an embedding model adapter (backward compatibility).
    
    Args:
        model_name: Model name (for OpenCLIP compatibility)
        model_size: Model size (for OpenCLIP compatibility)
        force_reload: Force reload of the model
        
    Returns:
        EmbeddingModelAdapter instance
    """
    global _global_adapter
    
    # If no specific parameters and not forcing reload, use cached adapter
    if not model_name and not model_size and not force_reload and _global_adapter is not None:
        return _global_adapter
    
    provider_config = None
    
    # Handle OpenCLIP-specific parameters
    if model_name or model_size:
        provider_config = {
            'provider': 'openclip',
            'config': {}
        }
        
        if model_name:
            provider_config['config']['model_name'] = model_name
        if model_size:
            provider_config['config']['model_size'] = model_size
    
    if provider_config:
        from .embedding_providers.factory import EmbeddingProviderFactory
        provider = EmbeddingProviderFactory.create_provider(
            provider_config['provider'], 
            provider_config['config']
        )
    else:
        provider = get_embedding_provider(force_new=force_reload)
    
    adapter = EmbeddingModelAdapter(provider)
    
    # Cache the adapter if it's the default configuration
    if not model_name and not model_size:
        _global_adapter = adapter
    
    return adapter


def cleanup_embedding_model():
    """
    Clean up the global embedding model instance (backward compatibility).
    """
    global _global_adapter
    if _global_adapter is not None:
        _global_adapter.cleanup()
        _global_adapter = None
    cleanup_global_provider()


@contextmanager
def managed_embedding_model(model_name: str = None, model_size: str = None, 
                          auto_unload: bool = True, provider_name: str = None,
                          provider_config: Dict[str, Any] = None):
    """
    Context manager for safe embedding model usage with automatic cleanup.
    
    Args:
        model_name: Optional specific model to use (OpenCLIP)
        model_size: Optional model size (OpenCLIP)
        auto_unload: Whether to unload the model after use (saves memory)
        provider_name: Provider to use ('openclip', 'openai', 'cohere')
        provider_config: Provider-specific configuration
    
    Usage:
        with managed_embedding_model(provider_name='openai') as model:
            embeddings = model.encode_texts(['hello', 'world'])
    """
    adapter = None
    try:
        if provider_name:
            from .embedding_providers.factory import EmbeddingProviderFactory
            provider = EmbeddingProviderFactory.create_provider(provider_name, provider_config or {})
            adapter = EmbeddingModelAdapter(provider)
        else:
            adapter = get_embedding_model(model_name, model_size, force_reload=True)
        
        yield adapter
        
    finally:
        if adapter is not None:
            if auto_unload:
                adapter.cleanup()
                logger.info("Model auto-unloaded to save memory")


@contextmanager
def temporary_model(model_name: str = None, model_size: str = None, 
                   provider_name: str = None, provider_config: Dict[str, Any] = None):
    """
    Context manager for temporary model usage that always unloads after use.
    
    Args:
        model_name: Model to temporarily load (OpenCLIP)
        model_size: Model size to temporarily load (OpenCLIP)
        provider_name: Provider to use ('openclip', 'openai', 'cohere')
        provider_config: Provider-specific configuration
    
    Usage:
        with temporary_model(provider_name='openai') as model:
            embeddings = model.encode_texts(['hello', 'world'])
        # Model is automatically unloaded here
    """
    with managed_embedding_model(
        model_name=model_name, 
        model_size=model_size, 
        auto_unload=True,
        provider_name=provider_name,
        provider_config=provider_config
    ) as model:
        yield model


# Additional helper functions for the new system

def switch_provider(provider_name: str, config: Dict[str, Any] = None) -> EmbeddingModelAdapter:
    """
    Switch to a different embedding provider.
    
    Args:
        provider_name: Name of the provider to switch to
        config: Provider-specific configuration
        
    Returns:
        EmbeddingModelAdapter instance with new provider
    """
    from .embedding_providers.factory import EmbeddingProviderFactory
    
    # Clean up current global provider
    cleanup_global_provider()
    
    # Create new provider
    provider = EmbeddingProviderFactory.create_provider(provider_name, config or {})
    
    return EmbeddingModelAdapter(provider)


def get_provider_info() -> Dict[str, Any]:
    """
    Get information about the current provider.
    
    Returns:
        Provider information dictionary
    """
    try:
        provider = get_embedding_provider()
        return provider.get_provider_info()
    except Exception as e:
        return {'error': str(e), 'available': False}


def test_provider(provider_name: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Test a provider configuration.
    
    Args:
        provider_name: Provider name to test
        config: Provider configuration
        
    Returns:
        Test results dictionary
    """
    try:
        with temporary_model(provider_name=provider_name, provider_config=config) as model:
            # Test text encoding
            text_result = model.encode_single_text("test")
            
            # Test image encoding if supported
            image_result = None
            try:
                # Create a simple test image
                from PIL import Image
                test_image = Image.new('RGB', (100, 100), color='red')
                image_result = model.encode_single_image(test_image)
            except Exception:
                pass
            
            provider_info = model.provider.get_provider_info()
            
            return {
                'success': True,
                'provider_info': provider_info,
                'text_embedding_shape': text_result.shape if text_result is not None else None,
                'image_embedding_shape': image_result.shape if image_result is not None else None,
                'supports_texts': text_result is not None,
                'supports_images': image_result is not None
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }