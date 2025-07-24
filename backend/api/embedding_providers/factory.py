"""
Factory for creating embedding providers based on configuration.
"""

import logging
from typing import Dict, Any, Optional, List, Type
from django.conf import settings

from .base import EmbeddingProvider, ProviderError, ProviderNotAvailableError
from .openclip import OpenCLIPProvider
from .openai_provider import OpenAIProvider, OpenAIVisionProvider
from .cohere_provider import CohereProvider
from .bedrock_provider import BedrockEmbeddingProvider, TitanEmbeddingProvider, CohereBedrockEmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingProviderFactory:
    """Factory for creating embedding providers."""
    
    # Registry of available providers
    _providers: Dict[str, Type[EmbeddingProvider]] = {
        'openclip': OpenCLIPProvider,
        'openai': OpenAIProvider,
        'openai_vision': OpenAIVisionProvider,
        'cohere': CohereProvider,
        'bedrock': BedrockEmbeddingProvider,
        'titan': TitanEmbeddingProvider,
        'cohere_bedrock': CohereBedrockEmbeddingProvider,
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[EmbeddingProvider]):
        """
        Register a new provider.
        
        Args:
            name: Provider name
            provider_class: Provider class
        """
        cls._providers[name] = provider_class
        logger.info(f"Registered embedding provider: {name}")
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available provider names.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())
    
    @classmethod
    def create_provider(cls, provider_name: str, config: Dict[str, Any] = None) -> EmbeddingProvider:
        """
        Create an embedding provider instance.
        
        Args:
            provider_name: Name of the provider to create
            config: Provider-specific configuration
            
        Returns:
            EmbeddingProvider instance
            
        Raises:
            ProviderError: If provider is not available or creation fails
        """
        if provider_name not in cls._providers:
            available = ', '.join(cls._providers.keys())
            raise ProviderError(f"Unknown provider '{provider_name}'. Available: {available}")
        
        provider_class = cls._providers[provider_name]
        
        try:
            # Handle special cases for provider initialization
            if provider_name == 'cohere_bedrock':
                # Default to multilingual for Cohere Bedrock
                language = (config or {}).get('language', 'multilingual')
                provider = provider_class(language=language, config=config)
            elif provider_name == 'titan':
                # Default to v1 for Titan
                version = (config or {}).get('version', 'v1')
                provider = provider_class(version=version, config=config)
            else:
                provider = provider_class(config or {})
            
            logger.info(f"Created embedding provider: {provider_name}")
            return provider
        except Exception as e:
            logger.error(f"Failed to create provider '{provider_name}': {e}")
            raise ProviderError(f"Failed to create provider '{provider_name}': {e}")
    
    @classmethod
    def create_from_settings(cls) -> EmbeddingProvider:
        """
        Create provider from Django settings.
        
        Returns:
            EmbeddingProvider instance
        """
        config = getattr(settings, 'EMBEDDING_PROVIDER_CONFIG', {})
        provider_name = config.get('provider', 'openclip')
        provider_config = config.get('config', {})
        
        return cls.create_provider(provider_name, provider_config)
    
    @classmethod
    def get_provider_info(cls, provider_name: str) -> Dict[str, Any]:
        """
        Get information about a provider without creating it.
        
        Args:
            provider_name: Provider name
            
        Returns:
            Provider information dictionary
        """
        if provider_name not in cls._providers:
            raise ProviderError(f"Unknown provider '{provider_name}'")
        
        provider_class = cls._providers[provider_name]
        
        # Return basic info that can be determined from the class
        info = {
            'name': provider_name,
            'class': provider_class.__name__,
            'module': provider_class.__module__,
            'supports_images': hasattr(provider_class, 'encode_images'),
            'supports_texts': hasattr(provider_class, 'encode_texts'),
        }
        
        # Try to get more detailed info if possible
        try:
            # Some providers might have static info methods
            if hasattr(provider_class, 'get_static_info'):
                info.update(provider_class.get_static_info())
        except Exception:
            pass
        
        return info


# Global provider instance for singleton pattern
_global_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider(provider_name: str = None, config: Dict[str, Any] = None, 
                          force_new: bool = False) -> EmbeddingProvider:
    """
    Get an embedding provider instance.
    
    Args:
        provider_name: Provider name (optional, will use settings if not provided)
        config: Provider configuration (optional)
        force_new: Force creation of new provider instance
        
    Returns:
        EmbeddingProvider instance
    """
    global _global_provider
    
    # If force_new or no global provider exists, create new one
    if force_new or _global_provider is None:
        if provider_name:
            _global_provider = EmbeddingProviderFactory.create_provider(provider_name, config)
        else:
            _global_provider = EmbeddingProviderFactory.create_from_settings()
    
    # Check if the provider is available, if not, recreate it
    if not _global_provider.is_available():
        logger.warning("Global provider is not available, recreating...")
        try:
            _global_provider.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up unavailable provider: {e}")
        
        if provider_name:
            _global_provider = EmbeddingProviderFactory.create_provider(provider_name, config)
        else:
            _global_provider = EmbeddingProviderFactory.create_from_settings()
    
    return _global_provider


def list_available_providers() -> Dict[str, Dict[str, Any]]:
    """
    List all available providers with their information.
    
    Returns:
        Dictionary mapping provider names to their information
    """
    result = {}
    
    for provider_name in EmbeddingProviderFactory.get_available_providers():
        try:
            info = EmbeddingProviderFactory.get_provider_info(provider_name)
            result[provider_name] = info
        except Exception as e:
            result[provider_name] = {
                'name': provider_name,
                'error': str(e),
                'available': False
            }
    
    return result


def cleanup_global_provider():
    """Clean up the global provider instance."""
    global _global_provider
    
    if _global_provider is not None:
        try:
            _global_provider.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up global provider: {e}")
        finally:
            _global_provider = None


# Provider configuration helpers
def get_default_openclip_config() -> Dict[str, Any]:
    """Get default OpenCLIP configuration."""
    from ..model_config import get_model_for_environment
    
    model_name, pretrained = get_model_for_environment()
    
    return {
        'provider': 'openclip',
        'config': {
            'model_name': model_name,
            'pretrained': pretrained,
            'device': 'auto',
            'batch_size_images': 8,
            'batch_size_texts': 16
        }
    }


def get_openai_config(api_key: str, model: str = 'text-embedding-3-small') -> Dict[str, Any]:
    """
    Get OpenAI configuration.
    
    Args:
        api_key: OpenAI API key
        model: Model name
        
    Returns:
        Configuration dictionary
    """
    return {
        'provider': 'openai',
        'config': {
            'api_key': api_key,
            'model': model,
            'batch_size': 100,
            'rate_limit_delay': 0.1,
            'max_retries': 3
        }
    }


def get_cohere_config(api_key: str, model: str = 'embed-english-v3.0') -> Dict[str, Any]:
    """
    Get Cohere configuration.
    
    Args:
        api_key: Cohere API key
        model: Model name
        
    Returns:
        Configuration dictionary
    """
    return {
        'provider': 'cohere',
        'config': {
            'api_key': api_key,
            'model': model,
            'input_type': 'search_document',
            'batch_size': 96,
            'rate_limit_delay': 0.1,
            'max_retries': 3
        }
    }


def get_bedrock_config(model: str = 'amazon.titan-embed-text-v1', aws_region: str = 'us-east-1') -> Dict[str, Any]:
    """
    Get AWS Bedrock configuration.
    
    Args:
        model: Bedrock model name
        aws_region: AWS region
        
    Returns:
        Configuration dictionary
    """
    return {
        'provider': 'bedrock',
        'config': {
            'model_name': model,
            'aws_region': aws_region,
            'batch_size': 25,  # Bedrock has batch limits
            'rate_limit_delay': 0.1,
            'max_retries': 3
        }
    }


def get_titan_config(version: str = 'v1', aws_region: str = 'us-east-1') -> Dict[str, Any]:
    """
    Get Amazon Titan configuration.
    
    Args:
        version: 'v1' or 'v2'
        aws_region: AWS region
        
    Returns:
        Configuration dictionary
    """
    return {
        'provider': 'titan',
        'config': {
            'version': version,
            'aws_region': aws_region,
            'batch_size': 25,
            'rate_limit_delay': 0.1,
            'max_retries': 3
        }
    }


def get_cohere_bedrock_config(language: str = 'multilingual', aws_region: str = 'us-east-1') -> Dict[str, Any]:
    """
    Get Cohere Bedrock configuration.
    
    Args:
        language: 'english' or 'multilingual'
        aws_region: AWS region
        
    Returns:
        Configuration dictionary
    """
    return {
        'provider': 'cohere_bedrock',
        'config': {
            'language': language,
            'aws_region': aws_region,
            'batch_size': 25,  # Bedrock has batch limits
            'rate_limit_delay': 0.1,
            'max_retries': 3
        }
    }


def auto_configure_provider() -> Dict[str, Any]:
    """
    Auto-configure provider based on available API keys and system resources.
    
    Returns:
        Configuration dictionary for the best available provider
    """
    import os
    
    # Check for API keys in environment
    openai_key = os.getenv('OPENAI_API_KEY')
    cohere_key = os.getenv('COHERE_API_KEY')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    # If we have AWS credentials, prefer AWS Bedrock for cost and performance
    if aws_access_key and aws_secret_key:
        logger.info("Found AWS credentials, using Cohere Multilingual embedding provider via Bedrock")
        return get_cohere_bedrock_config()
    
    # If we have API keys, prefer API-based providers for zero memory usage
    if openai_key:
        logger.info("Found OpenAI API key, using OpenAI provider")
        return get_openai_config(openai_key)
    
    if cohere_key:
        logger.info("Found Cohere API key, using Cohere provider")
        return get_cohere_config(cohere_key)
    
    # Fall back to local OpenCLIP
    logger.info("No API keys found, using local OpenCLIP provider")
    return get_default_openclip_config()