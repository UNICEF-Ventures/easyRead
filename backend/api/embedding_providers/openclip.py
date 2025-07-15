"""
OpenCLIP local embedding provider.
Wraps the existing OpenCLIP implementation in the provider abstraction.
"""

import torch
import open_clip
import numpy as np
from PIL import Image
import logging
from typing import List, Union, Optional, Dict, Any
from pathlib import Path

from .base import EmbeddingProvider, ProviderError, ProviderNotAvailableError, EmbeddingError
from ..model_config import ModelConfig, get_model_for_environment
from ..monitoring import monitor_embedding_operation
from ..performance import cache_embedding

logger = logging.getLogger(__name__)


class OpenCLIPProvider(EmbeddingProvider):
    """
    Local OpenCLIP embedding provider.
    
    Provides embeddings using locally-hosted OpenCLIP models with various size options.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize OpenCLIP provider.
        
        Args:
            config: Configuration dictionary with keys:
                - model_name: OpenCLIP model name (optional)
                - pretrained: Pretrained weights (optional)
                - model_size: Model size ('tiny', 'small', 'medium', 'large') (optional)
                - device: Device to use ('auto', 'cpu', 'cuda') (optional)
                - batch_size_images: Batch size for image encoding (optional)
                - batch_size_texts: Batch size for text encoding (optional)
        """
        super().__init__(config)
        
        # Get model configuration
        model_name = config.get('model_name')
        pretrained = config.get('pretrained')
        model_size = config.get('model_size')
        
        if model_name is None or pretrained is None:
            if model_size:
                model_name, pretrained = ModelConfig.get_model_config(model_size)
            else:
                model_name, pretrained = get_model_for_environment()
        
        self.model_name = model_name
        self.pretrained = pretrained
        self.model_size = model_size or 'auto'
        
        # Device configuration
        device_config = config.get('device', 'auto')
        if device_config == 'auto':
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device_config)
        
        # Batch sizes
        self.batch_size_images = config.get('batch_size_images', 8)
        self.batch_size_texts = config.get('batch_size_texts', 16)
        
        # Model components
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self._embedding_dimension = None
        
        # Load model on initialization
        self._load_model()
    
    def _load_model(self):
        """Load the OpenCLIP model and components."""
        try:
            # Log memory usage before loading
            import psutil
            import os
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024
            logger.info(f"Memory before model loading: {memory_before:.1f} MB")
            
            # Load model and preprocessing
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name, 
                pretrained=self.pretrained,
                device=self.device
            )
            
            # Load tokenizer
            self.tokenizer = open_clip.get_tokenizer(self.model_name)
            
            # Set model to evaluation mode and disable gradients
            self.model.eval()
            for param in self.model.parameters():
                param.requires_grad = False
            
            # Get embedding dimension
            with torch.no_grad():
                sample_text = self.tokenizer(["sample"]).to(self.device)
                sample_embedding = self.model.encode_text(sample_text)
                self._embedding_dimension = sample_embedding.shape[1]
                del sample_text, sample_embedding
            
            # Log memory usage after loading
            memory_after = process.memory_info().rss / 1024 / 1024
            memory_used = memory_after - memory_before
            logger.info(f"Loaded OpenCLIP model {self.model_name} with {self.pretrained} weights on {self.device}")
            logger.info(f"Memory after model loading: {memory_after:.1f} MB (used: {memory_used:.1f} MB)")
            
        except Exception as e:
            logger.error(f"Failed to load OpenCLIP model {self.model_name}: {e}")
            # Try fallback to tiny model
            if self.model_name != "ViT-B-32":
                logger.info("Falling back to ViT-B-32 model")
                try:
                    self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                        "ViT-B-32", 
                        pretrained="openai",
                        device=self.device
                    )
                    self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
                    self.model_name = "ViT-B-32"
                    self.pretrained = "openai"
                    
                    # Set model properties
                    self.model.eval()
                    for param in self.model.parameters():
                        param.requires_grad = False
                    
                    # Get embedding dimension
                    with torch.no_grad():
                        sample_text = self.tokenizer(["sample"]).to(self.device)
                        sample_embedding = self.model.encode_text(sample_text)
                        self._embedding_dimension = sample_embedding.shape[1]
                        del sample_text, sample_embedding
                        
                except Exception as fallback_error:
                    raise ProviderNotAvailableError(f"Failed to load OpenCLIP model: {fallback_error}")
            else:
                raise ProviderNotAvailableError(f"Failed to load OpenCLIP model: {e}")
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this provider."""
        memory_estimate = ModelConfig.get_memory_estimate(self.model_size) if self.model_size != 'auto' else 'auto'
        
        return {
            'name': 'openclip',  # Standardized lowercase name
            'model': self.model_name,  # Key field for provider identification
            'type': 'local',
            'model_name': self.model_name,  # Keep for backward compatibility
            'pretrained': self.pretrained,
            'model_size': self.model_size,
            'device': str(self.device),
            'embedding_dimension': self._embedding_dimension,
            'estimated_memory_mb': memory_estimate,
            'supports_images': True,
            'supports_texts': True,
            'batch_size_images': self.batch_size_images,
            'batch_size_texts': self.batch_size_texts
        }
    
    def is_available(self) -> bool:
        """Check if this provider is available."""
        return (self.model is not None and 
                self.preprocess is not None and 
                self.tokenizer is not None)
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        if not self.is_available():
            raise ProviderNotAvailableError("OpenCLIP model not loaded")
        return self._embedding_dimension
    
    @monitor_embedding_operation('embedding_generation')
    def encode_texts(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Encode a list of texts into embeddings.
        
        Args:
            texts: List of text strings to encode
            **kwargs: Additional arguments:
                - batch_size: Override default batch size
                
        Returns:
            numpy array of embeddings with shape (num_texts, embedding_dim)
        """
        if not self.is_available():
            raise ProviderNotAvailableError("OpenCLIP model not loaded")
        
        if not texts:
            return np.array([])
        
        batch_size = kwargs.get('batch_size', self.batch_size_texts)
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
                logger.error(f"Error processing text batch {i//batch_size}: {e}")
                # Clean up on error
                if 'tokens' in locals():
                    del tokens
                continue
        
        if all_embeddings:
            return np.vstack(all_embeddings)
        else:
            raise EmbeddingError("Failed to encode any texts")
    
    @monitor_embedding_operation('embedding_generation')
    def encode_images(self, images: List[Union[str, Path, Image.Image]], **kwargs) -> np.ndarray:
        """
        Encode a list of images into embeddings.
        
        Args:
            images: List of image paths or PIL Image objects
            **kwargs: Additional arguments:
                - batch_size: Override default batch size
                
        Returns:
            numpy array of embeddings with shape (num_images, embedding_dim)
        """
        if not self.is_available():
            raise ProviderNotAvailableError("OpenCLIP model not loaded")
        
        if not images:
            return np.array([])
        
        batch_size = kwargs.get('batch_size', self.batch_size_images)
        all_embeddings = []
        
        # Process images in batches with memory optimization
        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]
            batch_tensors = []
            
            try:
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
                        
                        # Clean up PIL image to save memory
                        del pil_img
                        
                    except Exception as e:
                        logger.error(f"Error processing image {img}: {e}")
                        continue
                
                if not batch_tensors:
                    continue
                
                # Combine batch tensors
                batch_tensor = torch.cat(batch_tensors, dim=0).to(self.device)
                
                # Clean up individual tensors to save memory
                for tensor in batch_tensors:
                    del tensor
                del batch_tensors
                
                # Generate embeddings
                with torch.no_grad():
                    embeddings = self.model.encode_image(batch_tensor)
                    embeddings = embeddings.cpu().numpy()
                    all_embeddings.append(embeddings)
                
                # Clean up batch tensor immediately
                del batch_tensor
                del embeddings
                
                # Force garbage collection every few batches
                if i % (batch_size * 4) == 0:
                    import gc
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        
            except Exception as e:
                logger.error(f"Error processing image batch {i//batch_size}: {e}")
                # Clean up on error
                if 'batch_tensor' in locals():
                    del batch_tensor
                if 'batch_tensors' in locals():
                    del batch_tensors
                continue
        
        if all_embeddings:
            return np.vstack(all_embeddings)
        else:
            raise EmbeddingError("Failed to encode any images")
    
    @cache_embedding('text')
    def encode_single_text(self, text: str, **kwargs) -> Optional[np.ndarray]:
        """Encode a single text with caching."""
        return super().encode_single_text(text, **kwargs)
    
    @cache_embedding('image')
    def encode_single_image(self, image: Union[str, Path, Image.Image], **kwargs) -> Optional[np.ndarray]:
        """Encode a single image with caching."""
        return super().encode_single_image(image, **kwargs)
    
    def cleanup(self):
        """Clean up model resources and free memory."""
        try:
            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Delete model components
            if hasattr(self, 'model') and self.model is not None:
                del self.model
                self.model = None
            if hasattr(self, 'preprocess') and self.preprocess is not None:
                del self.preprocess
                self.preprocess = None
            if hasattr(self, 'tokenizer') and self.tokenizer is not None:
                del self.tokenizer
                self.tokenizer = None
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Additional cleanup for potential multiprocessing resources
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
            
            logger.info(f"Cleaned up OpenCLIP provider {self.model_name}")
            
            # Log memory usage after cleanup
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                memory_after_cleanup = process.memory_info().rss / 1024 / 1024
                logger.info(f"Memory after cleanup: {memory_after_cleanup:.1f} MB")
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Error during OpenCLIP provider cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup when object is garbage collected."""
        self.cleanup()