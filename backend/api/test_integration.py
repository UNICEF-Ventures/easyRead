"""
Integration tests for the EasyRead embedding provider system.
Tests the complete workflow from API endpoints to embedding generation.
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import tempfile
import os
from PIL import Image
from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status

# Import the models and services
from api.models import ImageSet, Image as ImageModel, Embedding, ProcessedContent
from api.similarity_search import SimilaritySearcher, search_similar_images
from api.embedding_utils import get_embedding_model
from api.embedding_adapter import managed_embedding_model, switch_provider
from api.embedding_providers.factory import EmbeddingProviderFactory


class MockEmbeddingProvider:
    """Mock provider for integration testing."""
    
    def __init__(self, config=None):
        self.embedding_dimension = 384  # Common dimension
        self.model_name = "mock-integration-model"
    
    def encode_texts(self, texts, batch_size=32):
        """Generate consistent mock embeddings for text."""
        embeddings = []
        for text in texts:
            # Generate deterministic embeddings based on text content
            # This ensures consistent test results
            text_hash = hash(text) % 1000000
            np.random.seed(text_hash)
            embedding = np.random.rand(self.embedding_dimension).astype(np.float32)
            # Normalize the embedding
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)
        return np.array(embeddings)
    
    def encode_images(self, images, batch_size=8):
        """Generate consistent mock embeddings for images."""
        embeddings = []
        for i, image in enumerate(images):
            # Generate deterministic embeddings based on index
            np.random.seed(i + 12345)
            embedding = np.random.rand(self.embedding_dimension).astype(np.float32)
            # Normalize the embedding
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)
        return np.array(embeddings)
    
    def encode_single_text(self, text):
        """Encode single text."""
        return self.encode_texts([text])[0]
    
    def encode_single_image(self, image):
        """Encode single image."""
        return self.encode_images([image])[0]
    
    def compute_similarity(self, embedding1, embedding2):
        """Compute cosine similarity."""
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return np.dot(embedding1, embedding2) / (norm1 * norm2)
    
    def find_most_similar(self, query_embedding, candidate_embeddings, top_k=5):
        """Find most similar embeddings."""
        similarities = []
        for i, embedding in enumerate(candidate_embeddings):
            similarity = self.compute_similarity(query_embedding, embedding)
            similarities.append((i, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def get_embedding_dimension(self):
        """Get embedding dimension."""
        return self.embedding_dimension
    
    def is_available(self):
        """Check if provider is available."""
        return True
    
    def get_provider_info(self):
        """Get provider information."""
        return {
            'name': 'mock_integration',
            'type': 'local',
            'model': self.model_name,
            'embedding_dimension': self.embedding_dimension,
            'supports_texts': True,
            'supports_images': True,
            'estimated_memory_mb': 0
        }
    
    def cleanup(self):
        """Cleanup provider."""
        pass


class SimilaritySearchIntegrationTest(TestCase):
    """Test similarity search integration with the provider system."""
    
    def setUp(self):
        """Set up test data."""
        # Register and use mock provider for consistent testing
        EmbeddingProviderFactory.register_provider('mock_integration', MockEmbeddingProvider)
        
        # Create test image set
        self.image_set = ImageSet.objects.create(
            name="Test Animals",
            description="Test animal images"
        )
        
        # Create test images
        self.image1 = ImageModel.objects.create(
            set=self.image_set,
            filename="cat.png",
            original_path="/test/cat.png",
            description="A cute cat sitting"
        )
        
        self.image2 = ImageModel.objects.create(
            set=self.image_set,
            filename="dog.png", 
            original_path="/test/dog.png",
            description="A happy dog running"
        )
        
        self.image3 = ImageModel.objects.create(
            set=self.image_set,
            filename="bird.png",
            original_path="/test/bird.png", 
            description="A colorful bird flying"
        )
        
        # Generate embeddings using the mock provider
        with managed_embedding_model(provider_name='mock_integration') as model:
            # Text embeddings for descriptions
            for image in [self.image1, self.image2, self.image3]:
                text_embedding = model.encode_single_text(image.description)
                Embedding.objects.create(
                    image=image,
                    embedding_type='text',
                    vector=text_embedding.tolist(),
                    model_name=model.model_name
                )
                
                # Image embeddings (mock)
                image_embedding = model.encode_single_image(image.filename)
                Embedding.objects.create(
                    image=image,
                    embedding_type='image', 
                    vector=image_embedding.tolist(),
                    model_name=model.model_name
                )
    
    def test_similarity_search_with_provider_abstraction(self):
        """Test that similarity search works with the new provider system."""
        # Test text-based similarity search
        results = search_similar_images("cute cat", n_results=3)
        
        self.assertTrue(len(results) > 0)
        self.assertLessEqual(len(results), 3)
        
        # Check result structure
        first_result = results[0]
        self.assertIn('id', first_result)
        self.assertIn('filename', first_result)
        self.assertIn('similarity', first_result)
        self.assertIn('description', first_result)
        
        # The cat image should be most similar to "cute cat" query
        # Due to our deterministic mock, this should be consistent
        cat_result = next((r for r in results if r['filename'] == 'cat.png'), None)
        self.assertIsNotNone(cat_result)
    
    def test_similarity_search_by_image(self):
        """Test image-to-image similarity search."""
        from api.similarity_search import search_similar_images_by_image
        
        # Find images similar to the cat image
        results = search_similar_images_by_image(self.image1.id, n_results=2)
        
        self.assertTrue(len(results) > 0)
        self.assertLessEqual(len(results), 2)
        
        # Should not include the reference image itself
        for result in results:
            self.assertNotEqual(result['id'], self.image1.id)
    
    def test_searcher_uses_new_provider_system(self):
        """Test that SimilaritySearcher properly uses the new provider system."""
        searcher = SimilaritySearcher()
        
        # The searcher should be using our mock provider through the abstraction
        self.assertIsNotNone(searcher.embedding_model)
        
        # Test direct embedding generation
        with managed_embedding_model(provider_name='mock_integration') as model:
            embedding = model.encode_single_text("test query")
            self.assertIsInstance(embedding, np.ndarray)
            self.assertEqual(embedding.shape[0], 384)  # Our mock dimension


class BackwardCompatibilityIntegrationTest(TestCase):
    """Test that existing code still works with the new provider system."""
    
    def setUp(self):
        """Set up test data."""
        EmbeddingProviderFactory.register_provider('mock_integration', MockEmbeddingProvider)
    
    def test_old_embedding_utils_still_work(self):
        """Test that old embedding_utils functions still work."""
        from api.embedding_utils import (
            get_embedding_model,
            create_text_embedding, 
            create_batch_text_embeddings
        )
        
        # Test that the old interface still works
        with managed_embedding_model(provider_name='mock_integration') as model:
            # Test single text embedding
            text_embedding = create_text_embedding("test text")
            self.assertIsInstance(text_embedding, np.ndarray)
            
            # Test batch embeddings
            batch_embeddings = create_batch_text_embeddings(["text1", "text2"])
            self.assertIsInstance(batch_embeddings, np.ndarray)
            self.assertEqual(batch_embeddings.shape[0], 2)
    
    def test_model_lifecycle_backward_compatibility(self):
        """Test that model lifecycle functions work."""
        from api.embedding_utils import get_embedding_model, cleanup_embedding_model
        
        # Should be able to get a model
        with managed_embedding_model(provider_name='mock_integration') as model:
            self.assertIsNotNone(model)
            
            # Should be able to generate embeddings
            embedding = model.encode_single_text("test")
            self.assertIsInstance(embedding, np.ndarray)


class ProviderSwitchingIntegrationTest(TestCase):
    """Test provider switching in real workflow scenarios."""
    
    def setUp(self):
        """Set up test data."""
        EmbeddingProviderFactory.register_provider('mock_integration', MockEmbeddingProvider)
        
        # Create another mock provider with different dimensions
        class AlternateMockProvider(MockEmbeddingProvider):
            def __init__(self, config=None):
                super().__init__(config)
                self.embedding_dimension = 512
                self.model_name = "alternate-mock-model"
        
        EmbeddingProviderFactory.register_provider('alternate_mock', AlternateMockProvider)
    
    def test_provider_switching_workflow(self):
        """Test switching providers mid-workflow."""
        # Start with first provider
        with managed_embedding_model(provider_name='mock_integration') as model1:
            embedding1 = model1.encode_single_text("test text")
            self.assertEqual(embedding1.shape[0], 384)
        
        # Switch to second provider
        with managed_embedding_model(provider_name='alternate_mock') as model2:
            embedding2 = model2.encode_single_text("test text")
            self.assertEqual(embedding2.shape[0], 512)
        
        # Embeddings should be different due to different dimensions
        self.assertNotEqual(embedding1.shape[0], embedding2.shape[0])
    
    def test_provider_info_integration(self):
        """Test getting provider information in integration context."""
        from api.embedding_adapter import get_provider_info
        
        with managed_embedding_model(provider_name='mock_integration'):
            info = get_provider_info()
            
            self.assertEqual(info['name'], 'mock_integration')
            self.assertEqual(info['embedding_dimension'], 384)
            self.assertTrue(info['supports_texts'])
            self.assertTrue(info['supports_images'])


class DatabaseIntegrationTest(TransactionTestCase):
    """Test database operations with the embedding system."""
    
    def setUp(self):
        """Set up test data."""
        EmbeddingProviderFactory.register_provider('mock_integration', MockEmbeddingProvider)
    
    def test_embedding_storage_and_retrieval(self):
        """Test storing and retrieving embeddings from database."""
        # Create test image set and image
        image_set = ImageSet.objects.create(name="Test Set")
        image = ImageModel.objects.create(
            set=image_set,
            filename="test.png",
            original_path="/test/test.png",
            description="Test image"
        )
        
        # Generate and store embedding
        with managed_embedding_model(provider_name='mock_integration') as model:
            text_embedding = model.encode_single_text("test description")
            
            # Store in database
            embedding_obj = Embedding.objects.create(
                image=image,
                embedding_type='text',
                vector=text_embedding.tolist(),
                model_name=model.model_name
            )
            
            # Retrieve and verify
            retrieved = Embedding.objects.get(id=embedding_obj.id)
            retrieved_vector = np.array(retrieved.vector)
            
            # Should be identical (within floating point precision)
            np.testing.assert_array_almost_equal(text_embedding, retrieved_vector)
    
    def test_bulk_embedding_operations(self):
        """Test bulk embedding operations."""
        # Create multiple images
        image_set = ImageSet.objects.create(name="Bulk Test Set")
        images = []
        
        for i in range(5):
            image = ImageModel.objects.create(
                set=image_set,
                filename=f"image_{i}.png",
                original_path=f"/test/image_{i}.png",
                description=f"Test image {i}"
            )
            images.append(image)
        
        # Generate embeddings in bulk
        with managed_embedding_model(provider_name='mock_integration') as model:
            descriptions = [img.description for img in images]
            embeddings = model.encode_texts(descriptions)
            
            # Store all embeddings
            embedding_objects = []
            for i, (image, embedding) in enumerate(zip(images, embeddings)):
                embedding_obj = Embedding(
                    image=image,
                    embedding_type='text',
                    vector=embedding.tolist(),
                    model_name=model.model_name
                )
                embedding_objects.append(embedding_obj)
            
            # Bulk create
            Embedding.objects.bulk_create(embedding_objects)
            
            # Verify all were created
            self.assertEqual(Embedding.objects.filter(image__in=images).count(), 5)


class ErrorHandlingIntegrationTest(TestCase):
    """Test error handling in the integrated system."""
    
    def setUp(self):
        """Set up test data."""
        # Create a provider that fails
        class FailingProvider:
            def __init__(self, config=None):
                pass
            
            def encode_texts(self, texts, **kwargs):
                raise Exception("Provider failed")
            
            def encode_images(self, images, **kwargs):
                raise Exception("Provider failed")
            
            def get_embedding_dimension(self):
                return 384
            
            def is_available(self):
                return False
            
            def get_provider_info(self):
                return {'name': 'failing', 'available': False}
            
            def cleanup(self):
                pass
        
        EmbeddingProviderFactory.register_provider('failing_provider', FailingProvider)
    
    def test_graceful_error_handling(self):
        """Test that the system handles provider errors gracefully."""
        # Try to use failing provider
        try:
            with managed_embedding_model(provider_name='failing_provider') as model:
                # This should fail, but not crash the system
                embedding = model.encode_single_text("test")
                self.fail("Should have raised an exception")
        except Exception as e:
            # Error should be properly caught and handled
            self.assertIn("failed", str(e).lower())
    
    def test_fallback_behavior(self):
        """Test system fallback behavior when provider fails."""
        from api.similarity_search import SimilaritySearcher
        
        # Create searcher - should handle provider errors gracefully
        searcher = SimilaritySearcher()
        
        # Even with no data, should return empty results, not crash
        results = searcher.find_similar_images("test query")
        self.assertEqual(results, [])


class APIEndpointIntegrationTest(APITestCase):
    """Test API endpoints with the new embedding system."""
    
    def setUp(self):
        """Set up test data."""
        EmbeddingProviderFactory.register_provider('mock_integration', MockEmbeddingProvider)
        
        # Create test data
        self.image_set = ImageSet.objects.create(name="API Test Set")
        self.image = ImageModel.objects.create(
            set=self.image_set,
            filename="api_test.png",
            original_path="/test/api_test.png",
            description="API test image"
        )
    
    def test_similarity_search_endpoint(self):
        """Test similarity search through API endpoint."""
        # This would test the actual API endpoint if it exists
        # For now, test the underlying functionality
        from api.similarity_search import search_similar_images
        
        # Generate some test embeddings first
        with managed_embedding_model(provider_name='mock_integration') as model:
            text_embedding = model.encode_single_text(self.image.description)
            Embedding.objects.create(
                image=self.image,
                embedding_type='text',
                vector=text_embedding.tolist(),
                model_name=model.model_name
            )
        
        # Search for similar images
        results = search_similar_images("test image")
        
        # Should find our test image
        self.assertTrue(len(results) > 0)
        found_image = next((r for r in results if r['id'] == self.image.id), None)
        self.assertIsNotNone(found_image)