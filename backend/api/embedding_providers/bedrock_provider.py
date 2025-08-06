"""
AWS Bedrock embedding provider using LiteLLM.
Supports Amazon Titan and Cohere embedding models via AWS Bedrock.
"""

import os
import numpy as np
from typing import List, Union, Dict, Any, Optional
from pathlib import Path
from PIL import Image
import logging

from .base import EmbeddingProvider, ProviderError, ProviderNotAvailableError, EmbeddingError

logger = logging.getLogger(__name__)

# Try to import litellm for AWS Bedrock embeddings
try:
    from litellm import embedding
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning("litellm not available, AWS Bedrock provider will be disabled")


class BedrockEmbeddingProvider(EmbeddingProvider):
    """
    AWS Bedrock embedding provider using LiteLLM.
    
    Supports the following models:
    - amazon.titan-embed-text-v1 (1536 dimensions)
    - amazon.titan-embed-text-v2:0 (1024 dimensions)
    - cohere.embed-english-v3 (1024 dimensions)
    - cohere.embed-multilingual-v3 (1024 dimensions)
    """
    
    # Model configurations
    MODEL_CONFIGS = {
        'amazon.titan-embed-text-v1': {
            'name': 'bedrock-titan-v1',
            'model': 'amazon.titan-embed-text-v1',
            'dimension': 1536,
            'supports_images': False,
            'max_tokens': 8192
        },
        'amazon.titan-embed-text-v2:0': {
            'name': 'bedrock-titan-v2',
            'model': 'amazon.titan-embed-text-v2:0',
            'dimension': 1024,
            'supports_images': False,
            'max_tokens': 8192
        },
        'cohere.embed-english-v3': {
            'name': 'bedrock-cohere-english',
            'model': 'cohere.embed-english-v3',
            'dimension': 1024,
            'supports_images': False,
            'max_tokens': 512
        },
        'cohere.embed-multilingual-v3': {
            'name': 'bedrock-cohere-multilingual',
            'model': 'cohere.embed-multilingual-v3',
            'dimension': 1024,
            'supports_images': False,
            'max_tokens': 512
        }
    }
    
    def __init__(self, model_name: str = 'amazon.titan-embed-text-v1', config: Dict[str, Any] = None):
        """
        Initialize AWS Bedrock embedding provider.
        
        Args:
            model_name: Name of the Bedrock model to use
            config: Additional configuration options
        """
        super().__init__(config)
        
        if not LITELLM_AVAILABLE:
            raise ProviderNotAvailableError("litellm package is required for AWS Bedrock provider")
        
        self.model_name = model_name
        
        if self.model_name not in self.MODEL_CONFIGS:
            available_models = ', '.join(self.MODEL_CONFIGS.keys())
            raise ProviderError(f"Unsupported model: {model_name}. Available models: {available_models}")
        
        self.model_config = self.MODEL_CONFIGS[self.model_name]
        
        # AWS credentials (will be picked up by litellm from environment)
        self.aws_access_key_id = (config or {}).get('aws_access_key_id') or os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = (config or {}).get('aws_secret_access_key') or os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_region = (config or {}).get('aws_region') or os.environ.get('AWS_REGION_NAME', 'us-east-1')
        
        # Validate AWS credentials
        if not all([self.aws_access_key_id, self.aws_secret_access_key]):
            logger.warning("AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            'name': self.model_config['name'],
            'model': self.model_config['model'],
            'provider_type': 'aws_bedrock',
            'supports_text': True,
            'supports_images': self.model_config['supports_images'],
            'embedding_dimension': self.model_config['dimension'],
            'max_tokens': self.model_config['max_tokens'],
            'requires_api_key': True,
            'aws_region': self.aws_region
        }
    
    def is_available(self) -> bool:
        """Check if AWS Bedrock provider is available."""
        if not LITELLM_AVAILABLE:
            return False
        
        if not all([self.aws_access_key_id, self.aws_secret_access_key]):
            return False
        
        try:
            # Test with a simple embedding
            response = embedding(
                model=self.model_name,
                input=["test"],
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_region_name=self.aws_region
            )
            return True
        except Exception as e:
            logger.error(f"AWS Bedrock provider availability check failed: {e}")
            return False
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension."""
        return self.model_config['dimension']
    
    def encode_texts(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Encode texts using AWS Bedrock.
        
        Args:
            texts: List of text strings to encode
            **kwargs: Additional arguments
            
        Returns:
            numpy array of embeddings
        """
        if not texts:
            return np.array([])
        
        try:
            # Filter out empty texts
            filtered_texts = [text.strip() for text in texts if text.strip()]
            
            if not filtered_texts:
                return np.array([])
            
            # Call AWS Bedrock via litellm
            response = embedding(
                model=self.model_name,
                input=filtered_texts,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_region_name=self.aws_region
            )
            
            # Extract embeddings from response
            # Handle both object attributes and dictionary formats
            embeddings = []
            for item in response.data:
                if hasattr(item, 'embedding'):
                    # Object format (OpenAI-style)
                    embeddings.append(item.embedding)
                elif isinstance(item, dict) and 'embedding' in item:
                    # Dictionary format (Bedrock-style)
                    embeddings.append(item['embedding'])
                else:
                    logger.error(f"Unknown embedding format: {type(item)}")
                    raise EmbeddingError(f"Unknown embedding format: {type(item)}")
            
            return np.array(embeddings)
            
        except Exception as e:
            logger.error(f"Error encoding texts with AWS Bedrock: {e}")
            raise EmbeddingError(f"Failed to encode texts: {e}")
    
    def encode_images(self, images: List[Union[str, Path, Image.Image]], **kwargs) -> np.ndarray:
        """
        Encode images using AWS Bedrock.
        
        Note: Most AWS Bedrock text embedding models don't support images.
        This method will raise an error for unsupported models.
        
        Args:
            images: List of image paths or PIL Image objects
            **kwargs: Additional arguments
            
        Returns:
            numpy array of embeddings
        """
        if not self.model_config['supports_images']:
            raise EmbeddingError(f"Model {self.model_name} does not support image embeddings")
        
        # For future support of multimodal Bedrock models
        raise EmbeddingError("Image encoding not yet implemented for AWS Bedrock models")
    
    def cleanup(self):
        """Clean up resources."""
        # AWS Bedrock is stateless, no cleanup needed
        pass


class TitanEmbeddingProvider(BedrockEmbeddingProvider):
    """Convenience class for Amazon Titan embeddings."""
    
    def __init__(self, version: str = 'v1', config: Dict[str, Any] = None):
        """
        Initialize Titan embedding provider.
        
        Args:
            version: 'v1' or 'v2' for Titan version
            config: Additional configuration
        """
        if version == 'v1':
            model_name = 'amazon.titan-embed-text-v1'
        elif version == 'v2':
            model_name = 'amazon.titan-embed-text-v2:0'
        else:
            raise ValueError(f"Unsupported Titan version: {version}. Use 'v1' or 'v2'")
        
        super().__init__(model_name=model_name, config=config)


class CohereBedrockEmbeddingProvider(BedrockEmbeddingProvider):
    """Convenience class for Cohere embeddings via Bedrock."""
    
    def __init__(self, language: str = 'english', config: Dict[str, Any] = None):
        """
        Initialize Cohere Bedrock embedding provider.
        
        Args:
            language: 'english' or 'multilingual'
            config: Additional configuration
        """
        if language == 'english':
            model_name = 'cohere.embed-english-v3'
        elif language == 'multilingual':
            model_name = 'cohere.embed-multilingual-v3'
        else:
            raise ValueError(f"Unsupported language: {language}. Use 'english' or 'multilingual'")
        
        super().__init__(model_name=model_name, config=config)