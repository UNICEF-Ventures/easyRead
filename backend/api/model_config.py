"""
Model configuration for EasyRead embedding models.
Provides centralized configuration for different model sizes and memory usage.
"""

import logging
import numpy as np
from typing import Dict, Tuple, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Standard vector dimension for multi-model support  
# Limited to 2000 due to pgvector 0.8.0 index constraints
STANDARD_VECTOR_DIMENSION = 2000


def pad_vector_to_standard(vector: np.ndarray, target_dim: int = STANDARD_VECTOR_DIMENSION) -> np.ndarray:
    """
    Pad vector with zeros to reach standard dimension for multi-model compatibility.
    
    Args:
        vector: Input vector as numpy array
        target_dim: Target dimension (default: STANDARD_VECTOR_DIMENSION)
        
    Returns:
        Padded vector of length target_dim
    """
    if len(vector) >= target_dim:
        logger.warning(f"Vector dimension {len(vector)} >= target {target_dim}, truncating")
        return vector[:target_dim]
    
    padded = np.zeros(target_dim, dtype=np.float32)
    padded[:len(vector)] = vector
    return padded


def unpad_vector(vector: np.ndarray, original_dim: int) -> np.ndarray:
    """
    Extract original vector from padded vector.
    
    Args:
        vector: Padded vector
        original_dim: Original vector dimension
        
    Returns:
        Original vector without padding
    """
    return vector[:original_dim]


class ModelConfig:
    """Configuration class for embedding models."""
    
    # Model configurations: (model_name, pretrained, approx_memory_mb, description)
    MODELS = {
        'tiny': ('ViT-B-32', 'openai', 400, 'Fastest, lowest memory usage'),
        'small': ('ViT-B-16', 'openai', 800, 'Good balance of speed and quality'),
        'medium': ('ViT-L-14', 'openai', 3000, 'High quality, moderate memory usage'),
        'large': ('ViT-bigG-14', 'laion2b_s39b_b160k', 12000, 'Highest quality, very high memory usage'),
    }
    
    # Default model based on environment
    DEFAULT_MODEL = getattr(settings, 'EMBEDDING_MODEL_SIZE', 'tiny')
    
    @classmethod
    def get_model_config(cls, size: str = None) -> Tuple[str, str]:
        """
        Get model configuration for specified size.
        
        Args:
            size: Model size ('tiny', 'small', 'medium', 'large') or None for default
            
        Returns:
            Tuple of (model_name, pretrained)
        """
        if size is None:
            size = cls.DEFAULT_MODEL
            
        if size not in cls.MODELS:
            logger.warning(f"Unknown model size '{size}', using 'tiny'")
            size = 'tiny'
            
        model_name, pretrained, memory_mb, description = cls.MODELS[size]
        logger.info(f"Using {size} model: {model_name} ({description}, ~{memory_mb}MB)")
        
        return model_name, pretrained
    
    @classmethod
    def get_memory_estimate(cls, size: str = None) -> int:
        """
        Get memory estimate for specified model size.
        
        Args:
            size: Model size or None for default
            
        Returns:
            Estimated memory usage in MB
        """
        if size is None:
            size = cls.DEFAULT_MODEL
            
        if size not in cls.MODELS:
            size = 'tiny'
            
        return cls.MODELS[size][2]
    
    @classmethod
    def list_available_models(cls) -> Dict[str, Dict[str, any]]:
        """
        List all available model configurations.
        
        Returns:
            Dictionary of model configurations
        """
        result = {}
        for size, (model_name, pretrained, memory_mb, description) in cls.MODELS.items():
            result[size] = {
                'model_name': model_name,
                'pretrained': pretrained,
                'memory_mb': memory_mb,
                'description': description,
                'is_default': size == cls.DEFAULT_MODEL
            }
        return result
    
    @classmethod
    def recommend_model_for_memory(cls, available_memory_mb: int) -> str:
        """
        Recommend best model size for available memory.
        
        Args:
            available_memory_mb: Available memory in MB
            
        Returns:
            Recommended model size
        """
        # Sort models by memory usage
        sorted_models = sorted(cls.MODELS.items(), key=lambda x: x[1][2])
        
        # Find largest model that fits in memory (with 20% buffer)
        memory_limit = available_memory_mb * 0.8
        
        recommended = 'tiny'  # Default fallback
        for size, (_, _, memory_mb, _) in sorted_models:
            if memory_mb <= memory_limit:
                recommended = size
            else:
                break
        
        logger.info(f"Recommended model for {available_memory_mb}MB: {recommended}")
        return recommended


def get_default_model_config() -> Tuple[str, str]:
    """
    Get the default model configuration.
    
    Returns:
        Tuple of (model_name, pretrained)
    """
    return ModelConfig.get_model_config()


def get_model_for_environment() -> Tuple[str, str]:
    """
    Get model configuration optimized for current environment.
    For consistency with stored embeddings, defaults to 'medium' model (ViT-L-14).
    
    Returns:
        Tuple of (model_name, pretrained)
    """
    # Use configured model size from environment variable or default to tiny
    # This respects EMBEDDING_MODEL_SIZE environment variable and Django settings
    return ModelConfig.get_model_config()