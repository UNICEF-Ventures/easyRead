"""
Embedding providers package.
Provides a unified interface for various embedding providers.
"""

from .base import EmbeddingProvider, ProviderError, ProviderNotAvailableError, EmbeddingError
from .openclip import OpenCLIPProvider
from .openai_provider import OpenAIProvider, OpenAIVisionProvider
from .cohere_provider import CohereProvider
from .factory import EmbeddingProviderFactory, get_embedding_provider, list_available_providers, cleanup_global_provider

__all__ = [
    'EmbeddingProvider',
    'ProviderError', 
    'ProviderNotAvailableError',
    'EmbeddingError',
    'OpenCLIPProvider',
    'OpenAIProvider',
    'OpenAIVisionProvider', 
    'CohereProvider',
    'EmbeddingProviderFactory',
    'get_embedding_provider',
    'list_available_providers',
    'cleanup_global_provider'
]