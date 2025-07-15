"""
OpenAI API embedding provider.
Provides embeddings using OpenAI's embedding API.
"""

import numpy as np
from PIL import Image
import logging
import time
from typing import List, Union, Optional, Dict, Any
from pathlib import Path
import base64
import io

from .base import EmbeddingProvider, ProviderError, ProviderNotAvailableError, EmbeddingError

logger = logging.getLogger(__name__)


class OpenAIProvider(EmbeddingProvider):
    """
    OpenAI API embedding provider.
    
    Provides text embeddings using OpenAI's API. Note: OpenAI's embedding API 
    currently only supports text, not images.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize OpenAI provider.
        
        Args:
            config: Configuration dictionary with keys:
                - api_key: OpenAI API key (required)
                - model: Model name (default: text-embedding-3-small)
                - batch_size: Batch size for API calls (default: 100)
                - rate_limit_delay: Delay between API calls in seconds (default: 0.1)
                - max_retries: Maximum number of retries for failed requests (default: 3)
        """
        super().__init__(config)
        
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ProviderNotAvailableError("OpenAI API key not provided")
        
        self.model = config.get('model', 'text-embedding-3-small')
        self.batch_size = config.get('batch_size', 100)
        self.rate_limit_delay = config.get('rate_limit_delay', 0.1)
        self.max_retries = config.get('max_retries', 3)
        
        # Model dimensions mapping
        self.model_dimensions = {
            'text-embedding-3-small': 1536,
            'text-embedding-3-large': 3072,
            'text-embedding-ada-002': 1536,
        }
        
        # Check if OpenAI library is available
        try:
            import openai
            self.openai = openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ProviderNotAvailableError("OpenAI library not installed. Install with: pip install openai")
        
        # Test API key validity
        self._test_api_key()
    
    def _test_api_key(self):
        """Test if the API key is valid."""
        try:
            # Make a simple API call to test the key
            response = self.client.embeddings.create(
                model=self.model,
                input=["test"],
                encoding_format="float"
            )
            logger.info(f"OpenAI API key validated successfully with model {self.model}")
        except Exception as e:
            raise ProviderNotAvailableError(f"Invalid OpenAI API key or model: {e}")
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this provider."""
        return {
            'name': 'openai',  # Standardized lowercase name
            'model': self.model,  # Key field for provider identification
            'type': 'api',
            'embedding_dimension': self.get_embedding_dimension(),
            'supports_images': False,  # OpenAI embeddings don't support images
            'supports_texts': True,
            'batch_size': self.batch_size,
            'rate_limit_delay': self.rate_limit_delay,
            'cost_per_1k_tokens': self._get_cost_estimate(),
            'api_endpoint': 'https://api.openai.com/v1/embeddings'
        }
    
    def _get_cost_estimate(self) -> float:
        """Get cost estimate per 1K tokens."""
        # Approximate costs as of 2024 (check OpenAI pricing for current rates)
        cost_mapping = {
            'text-embedding-3-small': 0.00002,
            'text-embedding-3-large': 0.00013,
            'text-embedding-ada-002': 0.0001,
        }
        return cost_mapping.get(self.model, 0.0001)
    
    def is_available(self) -> bool:
        """Check if this provider is available."""
        return hasattr(self, 'client') and self.client is not None
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self.model_dimensions.get(self.model, 1536)
    
    def encode_texts(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Encode a list of texts into embeddings using OpenAI API.
        
        Args:
            texts: List of text strings to encode
            **kwargs: Additional arguments:
                - batch_size: Override default batch size
                
        Returns:
            numpy array of embeddings with shape (num_texts, embedding_dim)
        """
        if not self.is_available():
            raise ProviderNotAvailableError("OpenAI client not initialized")
        
        if not texts:
            return np.array([])
        
        batch_size = kwargs.get('batch_size', self.batch_size)
        all_embeddings = []
        
        # Process texts in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # Filter out empty texts
            batch_texts = [text for text in batch_texts if text.strip()]
            if not batch_texts:
                continue
            
            # Make API call with retries
            embeddings = self._call_api_with_retries(batch_texts)
            if embeddings is not None:
                all_embeddings.extend(embeddings)
            
            # Rate limiting
            if self.rate_limit_delay > 0:
                time.sleep(self.rate_limit_delay)
        
        if all_embeddings:
            return np.array(all_embeddings)
        else:
            raise EmbeddingError("Failed to encode any texts with OpenAI API")
    
    def _call_api_with_retries(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Make API call with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                    encoding_format="float"
                )
                
                # Extract embeddings from response
                embeddings = []
                for data in response.data:
                    embeddings.append(data.embedding)
                
                return embeddings
                
            except Exception as e:
                logger.error(f"OpenAI API call failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                # Check if it's a rate limit error
                if "rate_limit" in str(e).lower():
                    wait_time = (2 ** attempt) * self.rate_limit_delay
                    logger.info(f"Rate limited, waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
                elif attempt == self.max_retries - 1:
                    # Last attempt failed
                    logger.error(f"All retry attempts failed for OpenAI API call")
                    return None
                else:
                    # Wait before retry
                    time.sleep(1.0)
        
        return None
    
    def encode_images(self, images: List[Union[str, Path, Image.Image]], **kwargs) -> np.ndarray:
        """
        OpenAI's embedding API doesn't support images.
        
        Args:
            images: List of image paths or PIL Image objects
            **kwargs: Additional arguments
            
        Raises:
            ProviderError: Always, as OpenAI embeddings don't support images
        """
        raise ProviderError("OpenAI embedding API does not support image embeddings. Use OpenCLIP or other multimodal providers.")
    
    def encode_single_image(self, image: Union[str, Path, Image.Image], **kwargs) -> Optional[np.ndarray]:
        """OpenAI doesn't support image embeddings."""
        raise ProviderError("OpenAI embedding API does not support image embeddings. Use OpenCLIP or other multimodal providers.")
    
    def cleanup(self):
        """Clean up resources (nothing to cleanup for API provider)."""
        pass


class OpenAIVisionProvider(EmbeddingProvider):
    """
    OpenAI Vision provider using GPT-4 Vision to create text descriptions 
    that can then be embedded using the text embedding API.
    
    This is a workaround for OpenAI's lack of direct image embedding support.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize OpenAI Vision provider.
        
        Args:
            config: Configuration dictionary with keys:
                - api_key: OpenAI API key (required)
                - vision_model: Vision model name (default: gpt-4-vision-preview)
                - embedding_model: Embedding model name (default: text-embedding-3-small)
                - description_prompt: Prompt for image description (optional)
        """
        super().__init__(config)
        
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ProviderNotAvailableError("OpenAI API key not provided")
        
        self.vision_model = config.get('vision_model', 'gpt-4-vision-preview')
        self.embedding_model = config.get('embedding_model', 'text-embedding-3-small')
        self.description_prompt = config.get('description_prompt', 
            "Describe this image in detail, focusing on the main objects, actions, and visual elements that would be useful for image search and retrieval.")
        
        # Initialize OpenAI client
        try:
            import openai
            self.openai = openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ProviderNotAvailableError("OpenAI library not installed")
        
        # Initialize text embedding provider
        self.text_provider = OpenAIProvider({
            'api_key': self.api_key,
            'model': self.embedding_model,
            'batch_size': config.get('batch_size', 50),
            'rate_limit_delay': config.get('rate_limit_delay', 0.2)
        })
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this provider."""
        return {
            'name': 'openai_vision',  # Standardized lowercase name
            'model': f"{self.vision_model}+{self.embedding_model}",  # Combined model identifier
            'type': 'api',
            'vision_model': self.vision_model,
            'embedding_model': self.embedding_model,
            'embedding_dimension': self.text_provider.get_embedding_dimension(),
            'supports_images': True,
            'supports_texts': True,
            'description_prompt': self.description_prompt[:100] + '...' if len(self.description_prompt) > 100 else self.description_prompt
        }
    
    def is_available(self) -> bool:
        """Check if this provider is available."""
        return hasattr(self, 'client') and self.client is not None and self.text_provider.is_available()
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self.text_provider.get_embedding_dimension()
    
    def encode_texts(self, texts: List[str], **kwargs) -> np.ndarray:
        """Encode texts using the text embedding provider."""
        return self.text_provider.encode_texts(texts, **kwargs)
    
    def encode_images(self, images: List[Union[str, Path, Image.Image]], **kwargs) -> np.ndarray:
        """
        Encode images by first converting them to text descriptions, then embedding the descriptions.
        
        Args:
            images: List of image paths or PIL Image objects
            **kwargs: Additional arguments
            
        Returns:
            numpy array of embeddings with shape (num_images, embedding_dim)
        """
        if not images:
            return np.array([])
        
        # Convert images to text descriptions
        descriptions = []
        for image in images:
            try:
                description = self._describe_image(image)
                descriptions.append(description)
            except Exception as e:
                logger.error(f"Failed to describe image {image}: {e}")
                descriptions.append("Unknown image content")
        
        # Embed the descriptions
        return self.text_provider.encode_texts(descriptions, **kwargs)
    
    def _describe_image(self, image: Union[str, Path, Image.Image]) -> str:
        """Generate a text description of an image using GPT-4 Vision."""
        try:
            # Convert image to base64
            if isinstance(image, (str, Path)):
                with open(image, 'rb') as image_file:
                    image_data = image_file.read()
            else:
                # PIL Image
                buffer = io.BytesIO()
                image.save(buffer, format='PNG')
                image_data = buffer.getvalue()
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Make API call
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.description_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error describing image with GPT-4 Vision: {e}")
            return "Image description not available"
    
    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'text_provider'):
            self.text_provider.cleanup()