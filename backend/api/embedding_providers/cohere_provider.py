"""
Cohere API embedding provider.
Provides embeddings using Cohere's embedding API.
"""

import numpy as np
from PIL import Image
import logging
import time
from typing import List, Union, Optional, Dict, Any
from pathlib import Path

from .base import EmbeddingProvider, ProviderError, ProviderNotAvailableError, EmbeddingError

logger = logging.getLogger(__name__)


class CohereProvider(EmbeddingProvider):
    """
    Cohere API embedding provider.
    
    Provides text embeddings using Cohere's API. Note: Cohere's embedding API
    currently only supports text, not images.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Cohere provider.
        
        Args:
            config: Configuration dictionary with keys:
                - api_key: Cohere API key (required)
                - model: Model name (default: embed-english-v3.0)
                - input_type: Input type for embeddings (default: search_document)
                - batch_size: Batch size for API calls (default: 96)
                - rate_limit_delay: Delay between API calls in seconds (default: 0.1)
                - max_retries: Maximum number of retries for failed requests (default: 3)
        """
        super().__init__(config)
        
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ProviderNotAvailableError("Cohere API key not provided")
        
        self.model = config.get('model', 'embed-english-v3.0')
        self.input_type = config.get('input_type', 'search_document')
        self.batch_size = config.get('batch_size', 96)  # Cohere's max batch size
        self.rate_limit_delay = config.get('rate_limit_delay', 0.1)
        self.max_retries = config.get('max_retries', 3)
        
        # Model dimensions mapping
        self.model_dimensions = {
            'embed-english-v3.0': 1024,
            'embed-multilingual-v3.0': 1024,
            'embed-english-light-v3.0': 384,
            'embed-multilingual-light-v3.0': 384,
            'embed-english-v2.0': 4096,
            'embed-english-light-v2.0': 1024,
        }
        
        # Check if Cohere library is available
        try:
            import cohere
            self.cohere = cohere
            self.client = cohere.Client(api_key=self.api_key)
        except ImportError:
            raise ProviderNotAvailableError("Cohere library not installed. Install with: pip install cohere")
        
        # Test API key validity
        self._test_api_key()
    
    def _test_api_key(self):
        """Test if the API key is valid."""
        try:
            # Make a simple API call to test the key
            response = self.client.embed(
                model=self.model,
                texts=["test"],
                input_type=self.input_type
            )
            logger.info(f"Cohere API key validated successfully with model {self.model}")
        except Exception as e:
            raise ProviderNotAvailableError(f"Invalid Cohere API key or model: {e}")
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this provider."""
        return {
            'name': 'cohere',  # Standardized lowercase name
            'model': self.model,  # Key field for provider identification
            'type': 'api',
            'input_type': self.input_type,
            'embedding_dimension': self.get_embedding_dimension(),
            'supports_images': False,  # Cohere embeddings don't support images
            'supports_texts': True,
            'batch_size': self.batch_size,
            'rate_limit_delay': self.rate_limit_delay,
            'cost_estimate': self._get_cost_estimate(),
            'api_endpoint': 'https://api.cohere.ai/v1/embed'
        }
    
    def _get_cost_estimate(self) -> str:
        """Get cost estimate information."""
        # Cohere pricing varies by model and usage tier
        return "Check Cohere pricing for current rates"
    
    def is_available(self) -> bool:
        """Check if this provider is available."""
        return hasattr(self, 'client') and self.client is not None
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self.model_dimensions.get(self.model, 1024)
    
    def encode_texts(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Encode a list of texts into embeddings using Cohere API.
        
        Args:
            texts: List of text strings to encode
            **kwargs: Additional arguments:
                - batch_size: Override default batch size
                - input_type: Override default input type
                
        Returns:
            numpy array of embeddings with shape (num_texts, embedding_dim)
        """
        if not self.is_available():
            raise ProviderNotAvailableError("Cohere client not initialized")
        
        if not texts:
            return np.array([])
        
        batch_size = kwargs.get('batch_size', self.batch_size)
        input_type = kwargs.get('input_type', self.input_type)
        all_embeddings = []
        
        # Process texts in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # Filter out empty texts
            batch_texts = [text for text in batch_texts if text.strip()]
            if not batch_texts:
                continue
            
            # Make API call with retries
            embeddings = self._call_api_with_retries(batch_texts, input_type)
            if embeddings is not None:
                all_embeddings.extend(embeddings)
            
            # Rate limiting
            if self.rate_limit_delay > 0:
                time.sleep(self.rate_limit_delay)
        
        if all_embeddings:
            return np.array(all_embeddings)
        else:
            raise EmbeddingError("Failed to encode any texts with Cohere API")
    
    def _call_api_with_retries(self, texts: List[str], input_type: str) -> Optional[List[List[float]]]:
        """Make API call with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.embed(
                    model=self.model,
                    texts=texts,
                    input_type=input_type
                )
                
                # Extract embeddings from response
                embeddings = []
                for embedding in response.embeddings:
                    embeddings.append(embedding)
                
                return embeddings
                
            except Exception as e:
                logger.error(f"Cohere API call failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                # Check if it's a rate limit error
                if "rate" in str(e).lower() or "429" in str(e):
                    wait_time = (2 ** attempt) * self.rate_limit_delay
                    logger.info(f"Rate limited, waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
                elif attempt == self.max_retries - 1:
                    # Last attempt failed
                    logger.error(f"All retry attempts failed for Cohere API call")
                    return None
                else:
                    # Wait before retry
                    time.sleep(1.0)
        
        return None
    
    def encode_images(self, images: List[Union[str, Path, Image.Image]], **kwargs) -> np.ndarray:
        """
        Cohere's embedding API doesn't support images.
        
        Args:
            images: List of image paths or PIL Image objects
            **kwargs: Additional arguments
            
        Raises:
            ProviderError: Always, as Cohere embeddings don't support images
        """
        raise ProviderError("Cohere embedding API does not support image embeddings. Use OpenCLIP or other multimodal providers.")
    
    def encode_single_image(self, image: Union[str, Path, Image.Image], **kwargs) -> Optional[np.ndarray]:
        """Cohere doesn't support image embeddings."""
        raise ProviderError("Cohere embedding API does not support image embeddings. Use OpenCLIP or other multimodal providers.")
    
    def cleanup(self):
        """Clean up resources (nothing to cleanup for API provider)."""
        pass