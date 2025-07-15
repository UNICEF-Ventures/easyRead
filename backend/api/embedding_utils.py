"""
Embedding utilities for EasyRead project using OpenCLIP models.
Handles both image and text embeddings with batching support.

DEPRECATED: This module is kept for backward compatibility.
New code should use the embedding_providers package and embedding_adapter.

To migrate to the new system:
1. Replace 'from api.embedding_utils import EmbeddingModel' 
   with 'from api.embedding_adapter import EmbeddingModelAdapter as EmbeddingModel'
2. Use provider-specific configurations in settings.py
3. Use the new management commands for provider testing

For API-based providers (zero memory usage):
- OpenAI: Set OPENAI_API_KEY environment variable
- Cohere: Set COHERE_API_KEY environment variable

The system will automatically choose the best available provider.
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

"""
LEGACY CODE BELOW - KEPT FOR REFERENCE BUT NOT USED
The actual implementation now uses the provider abstraction.
"""

import torch
import open_clip
import numpy as np
from PIL import Image
import logging
from typing import List, Union, Optional, Tuple
from pathlib import Path
import io
from contextlib import contextmanager
from api.monitoring import monitor_embedding_operation, log_structured_error
from api.performance import cache_embedding
from api.model_config import ModelConfig, get_model_for_environment

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    OpenCLIP embedding model for generating image and text embeddings.
    Uses the openclip-vit-bigG-14 model as specified in the refactor requirements.
    """
    
    def __init__(self, model_name: str = None, pretrained: str = None, model_size: str = None):
        """
        Initialize the OpenCLIP model.
        
        Args:
            model_name: OpenCLIP model name (optional, will use config if not provided)
            pretrained: Pretrained weights name (optional, will use config if not provided)
            model_size: Model size ('tiny', 'small', 'medium', 'large') for automatic config
        
        Model Memory Usage Guide:
        - tiny (ViT-B-32): ~400MB (RECOMMENDED for most use cases)
        - small (ViT-B-16): ~800MB (better quality, more memory)
        - medium (ViT-L-14): ~3GB (high quality, high memory)
        - large (ViT-bigG-14): ~12GB (exceptional quality, very high memory)
        """
        
        # Get model configuration
        if model_name is None or pretrained is None:
            if model_size:
                config_model_name, config_pretrained = ModelConfig.get_model_config(model_size)
            else:
                config_model_name, config_pretrained = get_model_for_environment()
            
            model_name = model_name or config_model_name
            pretrained = pretrained or config_pretrained
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Log memory usage before loading
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024
        logger.info(f"Memory before model loading: {memory_before:.1f} MB")
        
        # Load model and preprocessing with memory optimization
        try:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                model_name, 
                pretrained=pretrained,
                device=self.device
            )
            
            # Load tokenizer
            self.tokenizer = open_clip.get_tokenizer(model_name)
            
            # Set model to evaluation mode to save memory
            self.model.eval()
            
            # Disable gradients to save memory
            for param in self.model.parameters():
                param.requires_grad = False
            
            # Log memory usage after loading
            memory_after = process.memory_info().rss / 1024 / 1024
            memory_used = memory_after - memory_before
            logger.info(f"Loaded OpenCLIP model {model_name} with {pretrained} weights on {self.device}")
            logger.info(f"Memory after model loading: {memory_after:.1f} MB (used: {memory_used:.1f} MB)")
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            logger.info("Falling back to smaller model ViT-B-32")
            # Fallback to smaller model
            if model_name != "ViT-B-32":
                self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                    "ViT-B-32", 
                    pretrained="openai",
                    device=self.device
                )
                self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
                self.model_name = "ViT-B-32"
                self.pretrained = "openai"
            else:
                raise e
    
    def cleanup(self):
        """Clean up model resources and free memory."""
        try:
            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Delete model components
            if hasattr(self, 'model'):
                del self.model
            if hasattr(self, 'preprocess'):
                del self.preprocess
            if hasattr(self, 'tokenizer'):
                del self.tokenizer
            
            # Force garbage collection to help with resource cleanup
            import gc
            gc.collect()
            
            # Additional cleanup for potential multiprocessing resources
            import multiprocessing
            try:
                # Clean up any remaining multiprocessing resources
                multiprocessing.util._cleanup_tests()
                
                # Clean up any remaining semaphores
                import multiprocessing.synchronize
                if hasattr(multiprocessing.synchronize, '_semaphore_tracker'):
                    try:
                        multiprocessing.synchronize._semaphore_tracker._cleanup()
                    except (AttributeError, OSError):
                        pass
                        
            except (AttributeError, ImportError):
                # Method may not exist in all Python versions
                pass
            
            logger.info(f"Cleaned up OpenCLIP model {self.model_name}")
        except Exception as e:
            logger.error(f"Error during model cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup when object is garbage collected."""
        self.cleanup()
    
    @monitor_embedding_operation('embedding_generation')
    def encode_images(self, images: List[Union[str, Path, Image.Image]], batch_size: int = 8) -> np.ndarray:
        """
        Encode a list of images into embeddings.
        
        Args:
            images: List of image paths or PIL Image objects
            batch_size: Batch size for processing (default: 32)
            
        Returns:
            numpy array of embeddings with shape (num_images, embedding_dim)
        """
        all_embeddings = []
        
        # Process images in batches
        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]
            batch_tensors = []
            
            for img in batch_images:
                try:
                    # Load image if it's a path
                    if isinstance(img, (str, Path)):
                        pil_img = Image.open(img).convert('RGB')
                    else:
                        pil_img = img.convert('RGB')
                    
                    # Preprocess image
                    tensor = self.preprocess(pil_img).unsqueeze(0)
                    batch_tensors.append(tensor)
                    
                except Exception as e:
                    logger.error(f"Error processing image {img}: {e}")
                    # Skip corrupted images
                    continue
            
            if not batch_tensors:
                continue
            
            # Combine batch tensors
            batch_tensor = torch.cat(batch_tensors, dim=0).to(self.device)
            
            # Generate embeddings
            with torch.no_grad():
                embeddings = self.model.encode_image(batch_tensor)
                embeddings = embeddings.cpu().numpy()
                all_embeddings.append(embeddings)
        
        if all_embeddings:
            return np.vstack(all_embeddings)
        else:
            return np.array([])
    
    @monitor_embedding_operation('embedding_generation')
    def encode_texts(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        """
        Encode a list of texts into embeddings.
        
        Args:
            texts: List of text strings
            batch_size: Batch size for processing (default: 32)
            
        Returns:
            numpy array of embeddings with shape (num_texts, embedding_dim)
        """
        all_embeddings = []
        
        # Process texts in batches with memory optimization
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            try:
                # Tokenize batch
                tokens = self.tokenizer(batch_texts).to(self.device)
                
                # Generate embeddings
                with torch.no_grad():
                    embeddings = self.model.encode_text(tokens)
                    embeddings = embeddings.cpu().numpy()
                    all_embeddings.append(embeddings)
                
                # Clean up tokens and embeddings immediately
                del tokens
                del embeddings
                
                # Force garbage collection every few batches
                if i % (batch_size * 4) == 0:
                    import gc
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    
            except Exception as e:
                logger.error(f"Error processing text batch: {e}")
                # Clean up on error
                if 'tokens' in locals():
                    del tokens
                continue
        
        if all_embeddings:
            return np.vstack(all_embeddings)
        else:
            return np.array([])
    
    @cache_embedding('image')
    def encode_single_image(self, image: Union[str, Path, Image.Image]) -> Optional[np.ndarray]:
        """
        Encode a single image into embedding.
        
        Args:
            image: Image path or PIL Image object
            
        Returns:
            numpy array of embedding or None if processing failed
        """
        try:
            embeddings = self.encode_images([image], batch_size=1)
            return embeddings[0] if len(embeddings) > 0 else None
        except Exception as e:
            logger.error(f"Error encoding single image: {e}")
            return None
    
    @cache_embedding('text')
    def encode_single_text(self, text: str) -> Optional[np.ndarray]:
        """
        Encode a single text into embedding.
        
        Args:
            text: Text string
            
        Returns:
            numpy array of embedding or None if processing failed
        """
        try:
            embeddings = self.encode_texts([text], batch_size=1)
            return embeddings[0] if len(embeddings) > 0 else None
        except Exception as e:
            logger.error(f"Error encoding single text: {e}")
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
        
        return np.dot(embedding1, embedding2) / (norm1 * norm2)
    
    def find_similar_embeddings(self, query_embedding: np.ndarray, 
                              embeddings: List[np.ndarray], 
                              top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Find the most similar embeddings to a query embedding.
        
        Args:
            query_embedding: Query embedding
            embeddings: List of embeddings to search
            top_k: Number of top results to return
            
        Returns:
            List of (index, similarity_score) tuples sorted by similarity
        """
        similarities = []
        
        for i, embedding in enumerate(embeddings):
            similarity = self.compute_similarity(query_embedding, embedding)
            similarities.append((i, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]


# Global model instance (singleton pattern)
_model_instance = None


def get_embedding_model(model_name: str = None, model_size: str = None, force_reload: bool = False) -> EmbeddingModel:
    """
    Get the global embedding model instance (singleton pattern).
    
    Args:
        model_name: Optional model name to use (if different from current)
        model_size: Optional model size ('tiny', 'small', 'medium', 'large')
        force_reload: Force reload of the model
    
    Returns:
        EmbeddingModel instance
    """
    global _model_instance
    
    # Check if we need to reload with a different model
    if (_model_instance is None or 
        force_reload or 
        (model_name and hasattr(_model_instance, 'model_name') and _model_instance.model_name != model_name)):
        
        # Clean up existing instance
        if _model_instance is not None:
            _model_instance.cleanup()
            _model_instance = None
        
        # Create new instance with specified model
        if model_size:
            # Use model size configuration
            _model_instance = EmbeddingModel(model_size=model_size)
        elif model_name:
            # Use specific model name
            _model_instance = EmbeddingModel(model_name=model_name)
        else:
            # Use environment-optimized model
            _model_instance = EmbeddingModel()
    
    return _model_instance


def cleanup_embedding_model():
    """
    Clean up the global embedding model instance and free memory.
    """
    global _model_instance
    if _model_instance is not None:
        _model_instance.cleanup()
        _model_instance = None
        
        # Force garbage collection after cleanup
        import gc
        gc.collect()
        
        # Additional cleanup for multiprocessing resources
        try:
            import multiprocessing
            # Clean up any remaining multiprocessing resources
            multiprocessing.util._cleanup_tests()
            
            # Clean up any remaining semaphores
            import multiprocessing.synchronize
            if hasattr(multiprocessing.synchronize, '_semaphore_tracker'):
                try:
                    multiprocessing.synchronize._semaphore_tracker._cleanup()
                except (AttributeError, OSError):
                    pass
                    
        except (AttributeError, ImportError):
            pass
        
        # Additional OpenCLIP-specific cleanup
        force_cleanup_openclip_resources()
        
        # Log memory usage after cleanup
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            memory_after_cleanup = process.memory_info().rss / 1024 / 1024
            logger.info(f"Global embedding model cleaned up. Memory: {memory_after_cleanup:.1f} MB")
        except Exception:
            logger.info("Global embedding model cleaned up")


@contextmanager
def managed_embedding_model(model_name: str = None, model_size: str = None, auto_unload: bool = True):
    """
    Context manager for safe embedding model usage with automatic cleanup.
    
    Args:
        model_name: Optional specific model to use
        model_size: Optional model size ('tiny', 'small', 'medium', 'large')
        auto_unload: Whether to unload the model after use (saves memory)
    
    Usage:
        # For memory-efficient usage (auto-unloads after use)
        with managed_embedding_model(auto_unload=True) as model:
            embeddings = model.encode_texts(['hello', 'world'])
        
        # For persistent usage (keeps model loaded)
        with managed_embedding_model(auto_unload=False) as model:
            embeddings = model.encode_texts(['hello', 'world'])
    """
    model = None
    try:
        model = get_embedding_model(model_name, model_size)
        yield model
    finally:
        if model is not None:
            # Force garbage collection after each use
            import gc
            gc.collect()
            
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Auto-unload model if requested (saves memory)
            if auto_unload:
                cleanup_embedding_model()
                logger.info("Model auto-unloaded to save memory")
                
            # Clean up any potential multiprocessing resources
            try:
                import multiprocessing
                multiprocessing.util._cleanup_tests()
                
                # Clean up any remaining semaphores
                import multiprocessing.synchronize
                if hasattr(multiprocessing.synchronize, '_semaphore_tracker'):
                    try:
                        multiprocessing.synchronize._semaphore_tracker._cleanup()
                    except (AttributeError, OSError):
                        pass
                        
            except (AttributeError, ImportError):
                pass


@contextmanager
def temporary_model(model_name: str = None, model_size: str = None):
    """
    Context manager for temporary model usage that always unloads after use.
    
    Args:
        model_name: Model to temporarily load (optional)
        model_size: Model size to temporarily load (optional)
    
    Usage:
        with temporary_model("ViT-L-14") as model:
            high_quality_embeddings = model.encode_texts(['hello', 'world'])
        # Model is automatically unloaded here
    """
    original_model = None
    global _model_instance
    
    # Save reference to current model
    if _model_instance is not None:
        original_model = _model_instance
        original_model_name = getattr(original_model, 'model_name', None)
    
    temp_model = None
    try:
        # Load temporary model
        temp_model = get_embedding_model(model_name, model_size, force_reload=True)
        yield temp_model
    finally:
        # Clean up temporary model
        if temp_model is not None:
            cleanup_embedding_model()
        
        # Restore original model if it was different
        if (original_model is not None and 
            hasattr(original_model, 'model_name') and 
            original_model.model_name != model_name):
            _model_instance = original_model
        
        # Force cleanup
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def force_cleanup_openclip_resources():
    """
    Force cleanup of OpenCLIP-related resources that may cause semaphore leaks.
    This function should be called periodically or when shutting down.
    """
    try:
        # Clean up torch multiprocessing resources
        import torch.multiprocessing as mp
        if hasattr(mp, '_prctl_pr_set_pdeathsig'):
            # Clean up any remaining processes
            try:
                mp._prctl_pr_set_pdeathsig()
            except (AttributeError, OSError):
                pass
        
        # Clean up OpenCLIP-specific resources
        import open_clip
        # Force cleanup of any cached models
        if hasattr(open_clip, '_CACHE'):
            open_clip._CACHE.clear()
        
        # Clean up multiprocessing resources
        import multiprocessing
        
        # Clean up semaphore tracker
        import multiprocessing.synchronize
        if hasattr(multiprocessing.synchronize, '_semaphore_tracker'):
            try:
                tracker = multiprocessing.synchronize._semaphore_tracker
                if hasattr(tracker, '_cleanup'):
                    tracker._cleanup()
                if hasattr(tracker, '_stop'):
                    tracker._stop()
            except (AttributeError, OSError):
                pass
        
        # Clean up resource tracker
        import multiprocessing.resource_tracker
        if hasattr(multiprocessing.resource_tracker, '_resource_tracker'):
            try:
                tracker = multiprocessing.resource_tracker._resource_tracker
                if hasattr(tracker, '_cleanup'):
                    tracker._cleanup()
                if hasattr(tracker, '_stop'):
                    tracker._stop()
            except (AttributeError, OSError):
                pass
        
        # Force garbage collection
        import gc
        gc.collect()
        
        logger.info("Forced cleanup of OpenCLIP resources completed")
        
    except Exception as e:
        logger.error(f"Error during forced OpenCLIP cleanup: {e}")
        logger.info("Global embedding model instance cleaned up")
    else:
        logger.info("No embedding model instance to clean up")


def create_image_embedding(image_path: Union[str, Path]) -> Optional[np.ndarray]:
    """
    Create an embedding for a single image.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        numpy array of embedding or None if failed
    """
    model = get_embedding_model()
    return model.encode_single_image(image_path)


def create_text_embedding(text: str) -> Optional[np.ndarray]:
    """
    Create an embedding for a single text.
    
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
    Create embeddings for a batch of images.
    
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
    Create embeddings for a batch of texts.
    
    Args:
        texts: List of text strings
        batch_size: Batch size for processing
        
    Returns:
        numpy array of embeddings
    """
    model = get_embedding_model()
    return model.encode_texts(texts, batch_size)