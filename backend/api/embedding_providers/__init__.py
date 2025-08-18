"""
Embedding providers package.
Provides a unified interface for various embedding providers.
"""

from .base import EmbeddingProvider, ProviderError, ProviderNotAvailableError, EmbeddingError
from .bedrock_provider import BedrockEmbeddingProvider, TitanEmbeddingProvider, CohereBedrockEmbeddingProvider
from .factory import EmbeddingProviderFactory, get_embedding_provider, list_available_providers, cleanup_global_provider

__all__ = [
    'EmbeddingProvider',
    'ProviderError', 
    'ProviderNotAvailableError',
    'EmbeddingError',
    'BedrockEmbeddingProvider',
    'TitanEmbeddingProvider', 
    'CohereBedrockEmbeddingProvider',
    'EmbeddingProviderFactory',
    'get_embedding_provider',
    'list_available_providers',
    'cleanup_global_provider'
]