"""
Unit tests for the EasyRead embedding system.
Tests the new models, embedding utilities, and API endpoints.
"""

from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
import numpy as np
import tempfile
import os
from pathlib import Path

from api.models import ImageSet, Image, Embedding
from api.embedding_utils import EmbeddingModel, get_embedding_model
from api.similarity_search import SimilaritySearcher
from api.image_utils import ImageConverter
from api.monitoring import EmbeddingMetrics, EmbeddingHealthCheck


class ImageSetModelTest(TestCase):
    """Test the ImageSet model."""
    
    def test_create_image_set(self):
        """Test creating an image set."""
        image_set = ImageSet.objects.create(
            name="Test Set",
            description="A test image set"
        )
        
        self.assertEqual(image_set.name, "Test Set")
        self.assertEqual(image_set.description, "A test image set")
        self.assertIsNotNone(image_set.created_at)
    
    def test_image_set_string_representation(self):
        """Test the string representation of ImageSet."""
        image_set = ImageSet.objects.create(name="Animals")
        self.assertEqual(str(image_set), "Animals")
    
    def test_image_set_unique_name(self):
        """Test that image set names must be unique."""
        ImageSet.objects.create(name="Unique Set")
        
        with self.assertRaises(Exception):  # IntegrityError
            ImageSet.objects.create(name="Unique Set")


class ImageModelTest(TestCase):
    """Test the Image model."""
    
    def setUp(self):
        """Set up test data."""
        self.image_set = ImageSet.objects.create(name="Test Set")
    
    def test_create_image(self):
        """Test creating an image."""
        image = Image.objects.create(
            set=self.image_set,
            filename="test.png",
            original_path="/path/to/test.png",
            description="Test image",
            file_format="PNG",
            file_size=1024,
            width=100,
            height=100
        )
        
        self.assertEqual(image.filename, "test.png")
        self.assertEqual(image.set, self.image_set)
        self.assertEqual(image.file_format, "PNG")
    
    def test_image_string_representation(self):
        """Test the string representation of Image."""
        image = Image.objects.create(
            set=self.image_set,
            filename="test.png",
            original_path="/path/to/test.png"
        )
        self.assertEqual(str(image), "Test Set/test.png")
    
    def test_unique_filename_per_set(self):
        """Test that filenames must be unique within a set."""
        Image.objects.create(
            set=self.image_set,
            filename="duplicate.png",
            original_path="/path/to/duplicate1.png"
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            Image.objects.create(
                set=self.image_set,
                filename="duplicate.png",
                original_path="/path/to/duplicate2.png"
            )


class EmbeddingModelTest(TestCase):
    """Test the Embedding model."""
    
    def setUp(self):
        """Set up test data."""
        self.image_set = ImageSet.objects.create(name="Test Set")
        self.image = Image.objects.create(
            set=self.image_set,
            filename="test.png",
            original_path="/path/to/test.png"
        )
    
    def test_create_embedding(self):
        """Test creating an embedding."""
        test_vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        embedding = Embedding.objects.create(
            image=self.image,
            embedding_type="image",
            vector=test_vector,
            model_name="test-model"
        )
        
        self.assertEqual(embedding.image, self.image)
        self.assertEqual(embedding.embedding_type, "image")
        self.assertEqual(embedding.vector, test_vector)
        self.assertEqual(embedding.model_name, "test-model")
    
    def test_unique_embedding_per_type_per_image(self):
        """Test that each image can have only one embedding per type."""
        test_vector = [0.1, 0.2, 0.3]
        
        Embedding.objects.create(
            image=self.image,
            embedding_type="image",
            vector=test_vector
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            Embedding.objects.create(
                image=self.image,
                embedding_type="image",
                vector=test_vector
            )


class EmbeddingUtilsTest(TestCase):
    """Test the embedding utilities."""
    
    @patch('api.embedding_utils.open_clip.create_model_and_transforms')
    @patch('api.embedding_utils.open_clip.get_tokenizer')
    def setUp(self, mock_tokenizer, mock_create_model):
        """Set up mocked embedding model."""
        # Mock the OpenCLIP components
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer_instance = MagicMock()
        
        mock_create_model.return_value = (mock_model, None, mock_preprocess)
        mock_tokenizer.return_value = mock_tokenizer_instance
        
        # Configure the mock model to return consistent embeddings
        mock_model.encode_image.return_value = MagicMock()
        mock_model.encode_text.return_value = MagicMock()
        
        self.embedding_model = EmbeddingModel()
    
    def test_embedding_model_initialization(self):
        """Test that the embedding model initializes correctly."""
        self.assertIsNotNone(self.embedding_model.model)
        self.assertIsNotNone(self.embedding_model.preprocess)
        self.assertIsNotNone(self.embedding_model.tokenizer)
    
    @patch('api.embedding_utils.Image.open')
    def test_encode_single_text(self, mock_image_open):
        """Test encoding a single text."""
        # Mock the model output
        mock_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        self.embedding_model.model.encode_text.return_value = MagicMock()
        self.embedding_model.model.encode_text.return_value.cpu.return_value.numpy.return_value = mock_embedding
        
        result = self.embedding_model.encode_single_text("test text")
        
        self.assertIsNotNone(result)
        np.testing.assert_array_equal(result, mock_embedding)


class ImageConverterTest(TestCase):
    """Test the image conversion utilities."""
    
    def setUp(self):
        """Set up image converter."""
        self.converter = ImageConverter()
    
    def test_validate_image_png(self):
        """Test validating a PNG image."""
        # Create a temporary PNG file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            # Create a simple 1x1 PNG
            from PIL import Image
            img = Image.new('RGB', (1, 1), color='red')
            img.save(tmp_file.name, 'PNG')
            tmp_file_path = tmp_file.name
        
        try:
            result = self.converter.validate_image(tmp_file_path)
            self.assertTrue(result)
        finally:
            os.unlink(tmp_file_path)
    
    def test_get_image_info(self):
        """Test getting image information."""
        # Create a temporary image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            from PIL import Image
            img = Image.new('RGB', (100, 200), color='blue')
            img.save(tmp_file.name, 'PNG')
            tmp_file_path = tmp_file.name
        
        try:
            info = self.converter.get_image_info(tmp_file_path)
            
            self.assertIsNotNone(info)
            self.assertEqual(info['file_format'], 'PNG')
            self.assertEqual(info['width'], 100)
            self.assertEqual(info['height'], 200)
            self.assertGreater(info['file_size'], 0)
        finally:
            os.unlink(tmp_file_path)


class SimilaritySearchTest(TestCase):
    """Test the similarity search functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create test image set and images
        self.image_set = ImageSet.objects.create(name="Test Set")
        self.image1 = Image.objects.create(
            set=self.image_set,
            filename="image1.png",
            original_path="/path/to/image1.png",
            description="A red car"
        )
        self.image2 = Image.objects.create(
            set=self.image_set,
            filename="image2.png",
            original_path="/path/to/image2.png",
            description="A blue car"
        )
        
        # Create test embeddings
        Embedding.objects.create(
            image=self.image1,
            embedding_type="text",
            vector=[0.1, 0.9, 0.1, 0.1, 0.1]  # Should be similar to "red"
        )
        Embedding.objects.create(
            image=self.image2,
            embedding_type="text",
            vector=[0.1, 0.1, 0.9, 0.1, 0.1]  # Should be similar to "blue"
        )
    
    @patch('api.similarity_search.get_embedding_model')
    def test_find_similar_images(self, mock_get_model):
        """Test finding similar images."""
        # Mock the embedding model
        mock_model = MagicMock()
        mock_model.encode_single_text.return_value = np.array([0.1, 0.8, 0.1, 0.1, 0.1])  # Similar to red
        mock_get_model.return_value = mock_model
        
        searcher = SimilaritySearcher()
        results = searcher.find_similar_images("red vehicle", n_results=2)
        
        self.assertEqual(len(results), 2)
        # The first result should be the red car (image1) due to higher similarity
        self.assertEqual(results[0]['id'], self.image1.id)


class EmbeddingMetricsTest(TestCase):
    """Test the monitoring and metrics functionality."""
    
    def test_embedding_metrics_initialization(self):
        """Test that metrics initialize correctly."""
        metrics = EmbeddingMetrics()
        
        self.assertEqual(metrics.metrics['embedding_generation']['total_requests'], 0)
        self.assertEqual(metrics.metrics['similarity_search']['total_requests'], 0)
        self.assertEqual(len(metrics.metrics['errors']), 0)
    
    def test_record_embedding_generation_success(self):
        """Test recording successful embedding generation."""
        metrics = EmbeddingMetrics()
        metrics.record_embedding_generation(True, 1.5, "text")
        
        gen_metrics = metrics.metrics['embedding_generation']
        self.assertEqual(gen_metrics['total_requests'], 1)
        self.assertEqual(gen_metrics['successful'], 1)
        self.assertEqual(gen_metrics['failed'], 0)
        self.assertEqual(gen_metrics['total_time'], 1.5)
        self.assertEqual(gen_metrics['avg_time'], 1.5)
    
    def test_record_embedding_generation_failure(self):
        """Test recording failed embedding generation."""
        metrics = EmbeddingMetrics()
        metrics.record_embedding_generation(False, 0.5, "text", "Test error")
        
        gen_metrics = metrics.metrics['embedding_generation']
        self.assertEqual(gen_metrics['total_requests'], 1)
        self.assertEqual(gen_metrics['successful'], 0)
        self.assertEqual(gen_metrics['failed'], 1)
        self.assertEqual(len(metrics.metrics['errors']), 1)
        self.assertEqual(metrics.metrics['errors'][0]['error'], "Test error")


class APIEndpointsTest(APITestCase):
    """Test the API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.image_set = ImageSet.objects.create(name="Test Set")
    
    def test_get_image_sets(self):
        """Test the image sets endpoint."""
        response = self.client.get('/api/image-sets/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('image_sets', response.data)
        self.assertEqual(len(response.data['image_sets']), 1)
        self.assertEqual(response.data['image_sets'][0]['name'], 'Test Set')
    
    def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        response = self.client.get('/api/health/')
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        self.assertIn('status', response.data)
        self.assertIn('components', response.data)
    
    @patch('api.views.handle_image_upload')
    def test_upload_image_success(self, mock_handle_upload):
        """Test successful image upload."""
        # Mock successful upload
        mock_handle_upload.return_value = {
            'success': True,
            'image_id': 1,
            'image_path': 'images/test.png',
            'filename': 'test.png',
            'set_name': 'General',
            'description': 'Test image',
            'embeddings_created': 2,
            'file_format': 'PNG'
        }
        
        # Create a test image file
        image_content = b'fake image content'
        uploaded_file = SimpleUploadedFile("test.png", image_content, content_type="image/png")
        
        response = self.client.post('/api/upload-image/', {
            'image': uploaded_file,
            'description': 'Test image',
            'set_name': 'General'
        }, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('image_id', response.data)
        self.assertEqual(response.data['embeddings_created'], 2)
    
    def test_upload_image_no_file(self):
        """Test upload endpoint with no file."""
        response = self.client.post('/api/upload-image/', {
            'description': 'Test image'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class EmbeddingHealthCheckTest(TestCase):
    """Test the health check functionality."""
    
    @patch('api.monitoring.get_embedding_model')
    def test_check_model_availability_success(self, mock_get_model):
        """Test successful model availability check."""
        # Mock successful model
        mock_model = MagicMock()
        mock_model.encode_single_text.return_value = np.array([0.1, 0.2, 0.3])
        mock_get_model.return_value = mock_model
        
        result = EmbeddingHealthCheck.check_model_availability()
        
        self.assertEqual(result['status'], 'healthy')
        self.assertTrue(result['model_loaded'])
        self.assertTrue(result['test_embedding_generated'])
        self.assertEqual(result['embedding_dimension'], 3)
    
    @patch('api.monitoring.get_embedding_model')
    def test_check_model_availability_failure(self, mock_get_model):
        """Test failed model availability check."""
        mock_get_model.side_effect = Exception("Model loading failed")
        
        result = EmbeddingHealthCheck.check_model_availability()
        
        self.assertEqual(result['status'], 'unhealthy')
        self.assertFalse(result['model_loaded'])
        self.assertIn('error', result)
    
    def test_check_database_connectivity(self):
        """Test database connectivity check."""
        result = EmbeddingHealthCheck.check_database_connectivity()
        
        self.assertEqual(result['status'], 'healthy')
        self.assertTrue(result['database_connected'])
        self.assertIn('image_sets_count', result)
        self.assertIn('images_count', result)
        self.assertIn('embeddings_count', result)