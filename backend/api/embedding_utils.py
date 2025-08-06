"""
MEMORY-OPTIMIZED: This module now uses only API-based embedding providers.
All local models have been removed to prevent memory issues with large batch uploads.

API-based providers supported (zero memory usage):
- AWS Bedrock: Cohere, Amazon Titan, Claude models
- OpenAI: text-embedding-3-small, text-embedding-3-large
- Cohere: embed-english-v3.0, embed-multilingual-v3.0

Configuration:
- AWS: Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME
- OpenAI: Set OPENAI_API_KEY environment variable
- Cohere: Set COHERE_API_KEY environment variable

The system automatically selects the best available provider for scalability.
"""

# Import the new adapter to maintain backward compatibility
from .embedding_adapter import (
    EmbeddingModelAdapter,
    get_embedding_model,
    cleanup_embedding_model, 
    managed_embedding_model,
    temporary_model
)

# Re-export the old class name for compatibility
EmbeddingModel = EmbeddingModelAdapter

# Legacy warning
import warnings
warnings.warn(
    "embedding_utils is deprecated. Use embedding_providers and embedding_adapter instead.",
    DeprecationWarning,
    stacklevel=2
)

# LOCAL MODEL CODE REMOVED - System now uses only API-based providers
# All local model functionality has been moved to API-based providers
# for better scalability and memory management.

# Legacy functions maintained for compatibility - redirect to new adapter
from typing import List, Union, Optional, Tuple
from pathlib import Path
import numpy as np

# Simple compatibility functions that redirect to the new system
def create_image_embedding(image_path: Union[str, Path]) -> Optional[np.ndarray]:
    """
    Create an embedding for a single image using API-based providers.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        numpy array of embedding or None if failed
    """
    model = get_embedding_model()
    return model.encode_single_image(image_path)


def create_text_embedding(text: str) -> Optional[np.ndarray]:
    """
    Create an embedding for a single text using API-based providers.
    
    Args:
        text: Text string
        
    Returns:
        numpy array of embedding or None if failed
    """
    model = get_embedding_model()
    return model.encode_single_text(text)


def create_batch_image_embeddings(image_paths: List[Union[str, Path]], 
                                batch_size: int = 32) -> np.ndarray:
    """
    Create embeddings for a batch of images using API-based providers.
    
    Args:
        image_paths: List of image paths
        batch_size: Batch size for processing
        
    Returns:
        numpy array of embeddings
    """
    model = get_embedding_model()
    return model.encode_images(image_paths, batch_size)


def create_batch_text_embeddings(texts: List[str], 
                                batch_size: int = 32) -> np.ndarray:
    """
    Create embeddings for a batch of texts using API-based providers.
    
    Args:
        texts: List of text strings
        batch_size: Batch size for processing
        
    Returns:
        numpy array of embeddings
    """
    model = get_embedding_model()
    return model.encode_texts(texts, batch_size)


# Compatibility cleanup functions (now no-ops since no local models)
def cleanup_embedding_model():
    """No-op: API-based providers don't require cleanup"""
    pass


def force_cleanup_openclip_resources():
    """No-op: No OpenCLIP resources to clean up"""
    pass