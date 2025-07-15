"""
Comprehensive tests for the embedding provider system.
Tests all providers, factory, adapter, and configuration functionality.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import numpy as np
import tempfile
import os
from pathlib import Path
from PIL import Image
from django.test import TestCase, override_settings
from django.conf import settings

# Import the provider system
from api.embedding_providers.base import EmbeddingProvider, ProviderError, ProviderNotAvailableError
from api.embedding_providers.openclip import OpenCLIPProvider
from api.embedding_providers.openai_provider import OpenAIProvider, OpenAIVisionProvider
from api.embedding_providers.cohere_provider import CohereProvider
from api.embedding_providers.factory import (
    EmbeddingProviderFactory, 
    get_embedding_provider, 
    list_available_providers,
    auto_configure_provider
)
from api.embedding_adapter import (
    EmbeddingModelAdapter,
    get_embedding_model,
    managed_embedding_model,
    temporary_model,
    switch_provider,
    get_provider_info,
    test_provider
)


class BaseProviderTest(TestCase):
    """Test the base embedding provider abstract class."""
    
    def test_base_provider_is_abstract(self):
        """Test that base provider cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            EmbeddingProvider({})
    
    def test_provider_error_exceptions(self):
        """Test custom exception classes."""
        with self.assertRaises(ProviderError):
            raise ProviderError("Test error")
        
        with self.assertRaises(ProviderNotAvailableError):
            raise ProviderNotAvailableError("Provider not available")


class MockProvider(EmbeddingProvider):
    """Mock provider for testing base functionality."""
    
    def __init__(self, config):
        super().__init__(config)
        self.model_name = "mock-model"
        self.embedding_dimension = 512
    
    def encode_texts(self, texts, batch_size=32):
        """Mock text encoding."""
        return np.random.rand(len(texts), self.embedding_dimension).astype(np.float32)
    
    def encode_images(self, images, batch_size=8):
        """Mock image encoding.""" 
        return np.random.rand(len(images), self.embedding_dimension).astype(np.float32)
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension."""
        return self.embedding_dimension
    
    def is_available(self) -> bool:
        """Check if provider is available."""
        return True
    
    def get_provider_info(self):
        """Mock provider info."""
        return {
            'name': 'mock',
            'type': 'local',
            'model': self.model_name,
            'embedding_dimension': self.embedding_dimension,
            'supports_texts': True,
            'supports_images': True,
            'estimated_memory_mb': 100
        }


class OpenCLIPProviderTest(TestCase):
    """Test the OpenCLIP provider."""
    
    @patch('api.embedding_providers.openclip.open_clip.create_model_and_transforms')
    @patch('api.embedding_providers.openclip.open_clip.get_tokenizer')
    @patch('api.embedding_providers.openclip.torch.cuda.is_available')
    def setUp(self, mock_cuda, mock_tokenizer, mock_create_model):
        """Set up mocked OpenCLIP provider."""
        # Mock CUDA availability
        mock_cuda.return_value = False
        
        # Mock OpenCLIP components
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer_instance = MagicMock()
        
        mock_create_model.return_value = (mock_model, None, mock_preprocess)
        mock_tokenizer.return_value = mock_tokenizer_instance
        
        # Configure mock responses
        mock_model.encode_text.return_value = MagicMock()
        mock_model.encode_image.return_value = MagicMock()
        mock_model.eval.return_value = mock_model
        mock_model.parameters.return_value = []
        
        # Mock tensor operations
        mock_tensor = MagicMock()
        mock_tensor.cpu.return_value.numpy.return_value = np.random.rand(1, 512).astype(np.float32)
        mock_model.encode_text.return_value = mock_tensor
        mock_model.encode_image.return_value = mock_tensor
        
        self.mock_model = mock_model
        self.mock_preprocess = mock_preprocess
        self.mock_tokenizer = mock_tokenizer_instance
    
    def test_openclip_provider_initialization(self):
        """Test OpenCLIP provider initialization."""
        config = {'model_size': 'tiny'}
        provider = OpenCLIPProvider(config)
        
        self.assertIsNotNone(provider.model)
        self.assertIsNotNone(provider.preprocess)
        self.assertIsNotNone(provider.tokenizer)
        self.assertEqual(provider.model_name, 'ViT-B-32')
    
    def test_openclip_encode_texts(self):
        """Test text encoding with OpenCLIP."""
        config = {'model_size': 'tiny'}
        provider = OpenCLIPProvider(config)
        
        texts = ["hello world", "test text"]
        embeddings = provider.encode_texts(texts)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], len(texts))
    
    def test_openclip_encode_images(self):
        """Test image encoding with OpenCLIP."""
        config = {'model_size': 'tiny'}
        provider = OpenCLIPProvider(config)
        
        # Create temporary test images
        test_images = []
        temp_files = []
        
        for i in range(2):
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                img = Image.new('RGB', (64, 64), color=f'red')
                img.save(tmp_file.name, 'PNG')
                test_images.append(tmp_file.name)
                temp_files.append(tmp_file.name)
        
        try:
            embeddings = provider.encode_images(test_images)
            
            self.assertIsInstance(embeddings, np.ndarray)
            self.assertEqual(embeddings.shape[0], len(test_images))
        finally:
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
    
    def test_openclip_provider_info(self):
        """Test getting provider information."""
        config = {'model_size': 'tiny'}
        provider = OpenCLIPProvider(config)
        
        info = provider.get_provider_info()
        
        self.assertEqual(info['name'], 'openclip')
        self.assertEqual(info['type'], 'local')
        self.assertTrue(info['supports_texts'])
        self.assertTrue(info['supports_images'])
        self.assertIn('embedding_dimension', info)


class APIProviderTestBase:
    """Base class for API provider tests."""
    
    def create_mock_response(self, data, status_code=200):
        """Create a mock HTTP response."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None
        return mock_response


class OpenAIProviderTest(TestCase, APIProviderTestBase):
    """Test the OpenAI provider."""
    
    def test_openai_provider_initialization(self):
        """Test OpenAI provider initialization."""
        config = {
            'api_key': 'test-key',
            'model': 'text-embedding-3-small'
        }
        
        provider = OpenAIProvider(config)
        
        self.assertEqual(provider.api_key, 'test-key')
        self.assertEqual(provider.model, 'text-embedding-3-small')
    
    @patch('builtins.__import__')
    def test_openai_encode_texts(self, mock_import):
        """Test text encoding with OpenAI."""
        # Mock the openai module
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        
        def side_effect(name, *args):
            if name == 'openai':
                return mock_openai
            return __import__(name, *args)
        
        mock_import.side_effect = side_effect
        
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2, 0.3, 0.4, 0.5]),
            MagicMock(embedding=[0.2, 0.3, 0.4, 0.5, 0.6])
        ]
        mock_client.embeddings.create.return_value = mock_response
        
        config = {'api_key': 'test-key'}
        provider = OpenAIProvider(config)
        
        texts = ["hello world", "test text"]
        embeddings = provider.encode_texts(texts)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], len(texts))
        self.assertEqual(embeddings.shape[1], 5)
    
    def test_openai_provider_no_api_key(self):
        """Test OpenAI provider without API key."""
        with self.assertRaises(ProviderError):
            OpenAIProvider({})
    
    @patch('builtins.__import__')
    def test_openai_api_error_handling(self, mock_import):
        """Test OpenAI API error handling."""
        # Mock the openai module
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        
        def side_effect(name, *args):
            if name == 'openai':
                return mock_openai
            return __import__(name, *args)
        
        mock_import.side_effect = side_effect
        
        # Mock API error
        mock_client.embeddings.create.side_effect = Exception("Unauthorized")
        
        config = {'api_key': 'invalid-key'}
        provider = OpenAIProvider(config)
        
        with self.assertRaises(Exception):
            provider.encode_texts(["test"])


class CohereProviderTest(TestCase, APIProviderTestBase):
    """Test the Cohere provider."""
    
    @patch('api.embedding_providers.cohere_provider.cohere.Client')
    def test_cohere_provider_initialization(self, mock_cohere):
        """Test Cohere provider initialization."""
        config = {
            'api_key': 'test-key',
            'model': 'embed-english-v3.0'
        }
        
        # Mock the Cohere client
        mock_client = MagicMock()
        mock_cohere.return_value = mock_client
        
        provider = CohereProvider(config)
        
        self.assertEqual(provider.api_key, 'test-key')
        self.assertEqual(provider.model, 'embed-english-v3.0')
    
    @patch('api.embedding_providers.cohere_provider.cohere.Client')
    def test_cohere_encode_texts(self, mock_cohere):
        """Test text encoding with Cohere."""
        # Mock the Cohere client and response
        mock_client = MagicMock()
        mock_cohere.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.embeddings = [
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.2, 0.3, 0.4, 0.5, 0.6]
        ]
        mock_client.embed.return_value = mock_response
        
        config = {'api_key': 'test-key'}
        provider = CohereProvider(config)
        
        texts = ["hello world", "test text"]
        embeddings = provider.encode_texts(texts)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], len(texts))
        self.assertEqual(embeddings.shape[1], 5)
    
    def test_cohere_provider_no_api_key(self):
        """Test Cohere provider without API key."""
        with self.assertRaises(ProviderError):
            CohereProvider({})


class EmbeddingProviderFactoryTest(TestCase):
    """Test the embedding provider factory."""
    
    def test_factory_get_available_providers(self):
        """Test getting available providers."""
        providers = EmbeddingProviderFactory.get_available_providers()
        
        self.assertIn('openclip', providers)
        self.assertIn('openai', providers)
        self.assertIn('cohere', providers)
        self.assertIn('openai_vision', providers)
    
    def test_factory_register_provider(self):
        """Test registering a new provider."""
        EmbeddingProviderFactory.register_provider('mock', MockProvider)
        
        providers = EmbeddingProviderFactory.get_available_providers()
        self.assertIn('mock', providers)
    
    @patch('api.embedding_providers.openclip.open_clip.create_model_and_transforms')
    @patch('api.embedding_providers.openclip.open_clip.get_tokenizer')
    @patch('api.embedding_providers.openclip.torch.cuda.is_available')
    def test_factory_create_openclip_provider(self, mock_cuda, mock_tokenizer, mock_create_model):
        """Test creating OpenCLIP provider via factory."""
        # Mock setup
        mock_cuda.return_value = False
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        mock_model.parameters.return_value = []
        mock_create_model.return_value = (mock_model, None, MagicMock())
        mock_tokenizer.return_value = MagicMock()
        
        config = {'model_size': 'tiny'}
        provider = EmbeddingProviderFactory.create_provider('openclip', config)
        
        self.assertIsInstance(provider, OpenCLIPProvider)
    
    def test_factory_create_unknown_provider(self):
        """Test creating unknown provider."""
        with self.assertRaises(ProviderError):
            EmbeddingProviderFactory.create_provider('unknown', {})
    
    def test_factory_get_provider_info(self):
        """Test getting provider information."""
        info = EmbeddingProviderFactory.get_provider_info('openclip')
        
        self.assertEqual(info['name'], 'openclip')
        self.assertIn('class', info)
        self.assertTrue(info['supports_texts'])
        self.assertTrue(info['supports_images'])
    
    def test_list_available_providers(self):
        """Test listing all providers with info."""
        providers = list_available_providers()
        
        self.assertIn('openclip', providers)
        self.assertIn('openai', providers)
        self.assertIn('cohere', providers)
        
        for name, info in providers.items():
            self.assertIn('name', info)
            self.assertIn('supports_texts', info)
            self.assertIn('supports_images', info)


class EmbeddingAdapterTest(TestCase):
    """Test the embedding model adapter."""
    
    def setUp(self):
        """Set up test adapter with mock provider."""
        self.mock_provider = MockProvider({})
        self.adapter = EmbeddingModelAdapter(self.mock_provider)
    
    def test_adapter_initialization(self):
        """Test adapter initialization."""
        self.assertIsNotNone(self.adapter.provider)
        self.assertEqual(self.adapter.model_name, 'mock-model')
    
    def test_adapter_encode_texts(self):
        """Test text encoding through adapter."""
        texts = ["hello", "world"]
        embeddings = self.adapter.encode_texts(texts)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], len(texts))
        self.assertEqual(embeddings.shape[1], 512)
    
    def test_adapter_encode_images(self):
        """Test image encoding through adapter."""
        # Create test images
        test_images = []
        temp_files = []
        
        for i in range(2):
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                img = Image.new('RGB', (64, 64), color='red')
                img.save(tmp_file.name, 'PNG')
                test_images.append(tmp_file.name)
                temp_files.append(tmp_file.name)
        
        try:
            embeddings = self.adapter.encode_images(test_images)
            
            self.assertIsInstance(embeddings, np.ndarray)
            self.assertEqual(embeddings.shape[0], len(test_images))
        finally:
            # Clean up
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
    
    def test_adapter_single_encoding(self):
        """Test single text and image encoding."""
        # Test single text
        text_embedding = self.adapter.encode_single_text("test")
        self.assertIsInstance(text_embedding, np.ndarray)
        self.assertEqual(text_embedding.shape[0], 512)
        
        # Test single image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            img = Image.new('RGB', (64, 64), color='blue')
            img.save(tmp_file.name, 'PNG')
            
            try:
                image_embedding = self.adapter.encode_single_image(tmp_file.name)
                self.assertIsInstance(image_embedding, np.ndarray)
                self.assertEqual(image_embedding.shape[0], 512)
            finally:
                os.unlink(tmp_file.name)
    
    def test_adapter_similarity_computation(self):
        """Test similarity computation."""
        emb1 = np.array([1.0, 0.0, 0.0])
        emb2 = np.array([0.0, 1.0, 0.0])
        emb3 = np.array([1.0, 0.0, 0.0])
        
        # Test orthogonal vectors (similarity should be 0)
        sim1 = self.adapter.compute_similarity(emb1, emb2)
        self.assertAlmostEqual(sim1, 0.0, places=5)
        
        # Test identical vectors (similarity should be 1)
        sim2 = self.adapter.compute_similarity(emb1, emb3)
        self.assertAlmostEqual(sim2, 1.0, places=5)
    
    def test_adapter_find_most_similar(self):
        """Test finding most similar embeddings."""
        query = np.array([1.0, 0.0, 0.0])
        candidates = [
            np.array([0.9, 0.1, 0.0]),  # Very similar
            np.array([0.0, 1.0, 0.0]),  # Orthogonal
            np.array([0.5, 0.5, 0.0])   # Somewhat similar
        ]
        
        results = self.adapter.find_most_similar(query, candidates, top_k=2)
        
        self.assertEqual(len(results), 2)
        # First result should be most similar (index 0)
        self.assertEqual(results[0][0], 0)
        # Second result should be index 2
        self.assertEqual(results[1][0], 2)


class ProviderConfigurationTest(TestCase):
    """Test provider configuration and auto-selection."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-openai-key', 'COHERE_API_KEY': ''}, clear=True)
    def test_auto_configure_with_openai_key(self):
        """Test auto-configuration with OpenAI API key."""
        config = auto_configure_provider()
        
        self.assertEqual(config['provider'], 'openai')
        self.assertEqual(config['config']['api_key'], 'test-openai-key')
    
    @patch.dict(os.environ, {'COHERE_API_KEY': 'test-cohere-key', 'OPENAI_API_KEY': ''}, clear=True)
    def test_auto_configure_with_cohere_key(self):
        """Test auto-configuration with Cohere API key."""
        config = auto_configure_provider()
        
        self.assertEqual(config['provider'], 'cohere')
        self.assertEqual(config['config']['api_key'], 'test-cohere-key')
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': '', 'COHERE_API_KEY': ''}, clear=True)
    def test_auto_configure_fallback_to_openclip(self):
        """Test auto-configuration fallback to OpenCLIP."""
        config = auto_configure_provider()
        
        self.assertEqual(config['provider'], 'openclip')
        self.assertIn('model_name', config['config'])


class ContextManagerTest(TestCase):
    """Test context managers for embedding models."""
    
    def test_managed_embedding_model(self):
        """Test managed embedding model context manager."""
        with managed_embedding_model(provider_name='mock') as model:
            # Register mock provider first
            EmbeddingProviderFactory.register_provider('mock', MockProvider)
            
            # Test with registered provider
            with managed_embedding_model(provider_name='mock') as model:
                self.assertIsInstance(model, EmbeddingModelAdapter)
                
                # Test encoding
                embeddings = model.encode_single_text("test")
                self.assertIsInstance(embeddings, np.ndarray)
    
    def test_temporary_model(self):
        """Test temporary model context manager."""
        # Register mock provider
        EmbeddingProviderFactory.register_provider('mock', MockProvider)
        
        with temporary_model(provider_name='mock') as model:
            self.assertIsInstance(model, EmbeddingModelAdapter)
            
            # Test encoding
            embeddings = model.encode_single_text("test")
            self.assertIsInstance(embeddings, np.ndarray)


class ProviderSwitchingTest(TestCase):
    """Test provider switching functionality."""
    
    def test_switch_provider(self):
        """Test switching between providers."""
        # Register mock provider
        EmbeddingProviderFactory.register_provider('mock', MockProvider)
        
        # Switch to mock provider
        adapter = switch_provider('mock', {})
        
        self.assertIsInstance(adapter, EmbeddingModelAdapter)
        self.assertEqual(adapter.model_name, 'mock-model')
    
    def test_get_provider_info(self):
        """Test getting current provider info."""
        # Register and set mock provider
        EmbeddingProviderFactory.register_provider('mock', MockProvider)
        
        # This will use the mock provider
        with managed_embedding_model(provider_name='mock') as model:
            info = model.provider.get_provider_info()
            
            self.assertEqual(info['name'], 'mock')
            self.assertEqual(info['type'], 'local')
            self.assertTrue(info['supports_texts'])
            self.assertTrue(info['supports_images'])


class ProviderTestingTest(TestCase):
    """Test provider testing functionality."""
    
    def test_test_provider_success(self):
        """Test successful provider testing."""
        # Register mock provider
        EmbeddingProviderFactory.register_provider('mock', MockProvider)
        
        result = test_provider('mock', {})
        
        self.assertTrue(result['success'])
        self.assertIn('provider_info', result)
        self.assertIn('text_embedding_shape', result)
        self.assertIn('image_embedding_shape', result)
        self.assertTrue(result['supports_texts'])
        self.assertTrue(result['supports_images'])
    
    def test_test_provider_failure(self):
        """Test provider testing with invalid provider."""
        result = test_provider('nonexistent', {})
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)


class IntegrationTest(TestCase):
    """Integration tests for the complete provider system."""
    
    def test_backward_compatibility(self):
        """Test that the system maintains backward compatibility."""
        # Register mock provider
        EmbeddingProviderFactory.register_provider('mock', MockProvider)
        
        # Test old-style function calls still work
        with managed_embedding_model(provider_name='mock') as model:
            # Test single text encoding (old API)
            text_embedding = model.encode_single_text("test text")
            self.assertIsInstance(text_embedding, np.ndarray)
            
            # Test batch text encoding (old API)
            text_embeddings = model.encode_texts(["test1", "test2"])
            self.assertIsInstance(text_embeddings, np.ndarray)
            self.assertEqual(text_embeddings.shape[0], 2)
    
    def test_provider_lifecycle(self):
        """Test complete provider lifecycle."""
        # Register mock provider
        EmbeddingProviderFactory.register_provider('mock', MockProvider)
        
        # Create provider through factory
        provider = EmbeddingProviderFactory.create_provider('mock', {})
        self.assertIsInstance(provider, MockProvider)
        
        # Create adapter
        adapter = EmbeddingModelAdapter(provider)
        self.assertIsInstance(adapter, EmbeddingModelAdapter)
        
        # Test functionality
        embeddings = adapter.encode_texts(["hello", "world"])
        self.assertIsInstance(embeddings, np.ndarray)
        
        # Cleanup
        adapter.cleanup()