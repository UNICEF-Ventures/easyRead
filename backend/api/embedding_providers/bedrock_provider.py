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

# Import boto3 for direct AWS Bedrock access
try:
    import boto3
    import json
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not available, AWS Bedrock provider will be disabled")


class BedrockEmbeddingProvider(EmbeddingProvider):
    """
    AWS Bedrock embedding provider using boto3 directly.
    
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
        
        if not BOTO3_AVAILABLE:
            raise ProviderNotAvailableError("boto3 package is required for AWS Bedrock provider")
        
        self.model_name = model_name
        
        if self.model_name not in self.MODEL_CONFIGS:
            available_models = ', '.join(self.MODEL_CONFIGS.keys())
            raise ProviderError(f"Unsupported model: {model_name}. Available models: {available_models}")
        
        self.model_config = self.MODEL_CONFIGS[self.model_name]
        
        # AWS credentials for boto3 client
        self.aws_access_key_id = (config or {}).get('aws_access_key_id') or os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = (config or {}).get('aws_secret_access_key') or os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_region = (config or {}).get('aws_region') or os.environ.get('AWS_REGION_NAME', 'us-east-1')
        
        # Initialize boto3 client
        if all([self.aws_access_key_id, self.aws_secret_access_key]):
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )
        else:
            # Try to use default credentials
            try:
                self.bedrock_client = boto3.client('bedrock-runtime', region_name=self.aws_region)
            except Exception as e:
                raise ProviderNotAvailableError(f"AWS credentials not found and default credentials failed: {e}")
    
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
        if not BOTO3_AVAILABLE:
            return False
        
        return hasattr(self, 'bedrock_client') and self.bedrock_client is not None
    
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
            
            embeddings = []
            
            # Process texts individually (Bedrock doesn't support batch for all models)
            for text in filtered_texts:
                # Prepare the request body based on model type
                if self.model_name.startswith('amazon.titan'):
                    body = json.dumps({"inputText": text})
                elif self.model_name.startswith('cohere.embed'):
                    body = json.dumps({
                        "texts": [text],
                        "input_type": "search_document"
                    })
                else:
                    raise EmbeddingError(f"Unsupported model: {self.model_name}")
                
                # Call AWS Bedrock directly
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_name,
                    body=body,
                    contentType='application/json',
                    accept='application/json'
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                
                if self.model_name.startswith('amazon.titan'):
                    embedding_vector = response_body['embedding']
                elif self.model_name.startswith('cohere.embed'):
                    embedding_vector = response_body['embeddings'][0]
                else:
                    raise EmbeddingError(f"Unknown response format for model: {self.model_name}")
                
                embeddings.append(embedding_vector)
            
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