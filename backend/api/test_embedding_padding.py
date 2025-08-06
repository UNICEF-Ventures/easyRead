#!/usr/bin/env python3
"""
Test script to validate embedding padding and dimension handling fixes.
This script tests the key issues that were identified and fixed.
"""

import os
import sys
import django
import numpy as np
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easyread_backend.settings')
django.setup()

from api.models import Embedding, Image, ImageSet
from api.model_config import pad_vector_to_standard, unpad_vector, STANDARD_VECTOR_DIMENSION
from api.validators import EmbeddingValidator
from api.similarity_search import SimilaritySearcher
from api.embedding_adapter import get_embedding_model

logger = logging.getLogger(__name__)

class EmbeddingPaddingTester:
    """Test class for embedding padding functionality."""
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {test_name}: {message}")
        
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
        
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def test_padding_functions(self):
        """Test padding and unpadding functions."""
        print("\n=== Testing Padding Functions ===")
        
        # Test 1: Basic padding
        try:
            original_vector = np.random.rand(1024).astype(np.float32)
            padded_vector = pad_vector_to_standard(original_vector)
            
            self.log_test(
                "Basic padding",
                len(padded_vector) == STANDARD_VECTOR_DIMENSION,
                f"Padded from {len(original_vector)} to {len(padded_vector)}"
            )
        except Exception as e:
            self.log_test("Basic padding", False, f"Exception: {e}")
        
        # Test 2: Unpadding
        try:
            unpadded_vector = unpad_vector(padded_vector, len(original_vector))
            vectors_match = np.allclose(original_vector, unpadded_vector)
            
            self.log_test(
                "Unpadding preserves data",
                vectors_match,
                f"Original and unpadded vectors {'match' if vectors_match else 'differ'}"
            )
        except Exception as e:
            self.log_test("Unpadding preserves data", False, f"Exception: {e}")
        
        # Test 3: Padding already large vector
        try:
            large_vector = np.random.rand(5000).astype(np.float32)
            padded_large = pad_vector_to_standard(large_vector)
            
            self.log_test(
                "Padding large vector",
                len(padded_large) == STANDARD_VECTOR_DIMENSION,
                f"Large vector {len(large_vector)} -> {len(padded_large)} (truncated)"
            )
        except Exception as e:
            self.log_test("Padding large vector", False, f"Exception: {e}")
    
    def test_validator(self):
        """Test embedding validator with padded vectors."""
        print("\n=== Testing Embedding Validator ===")
        
        # Test 1: Validate unpadded vector
        try:
            test_vector = np.random.rand(1024).astype(np.float32)
            validation = EmbeddingValidator.validate_embedding_vector(
                test_vector, 'openclip-vit-b-32', is_padded=False
            )
            
            self.log_test(
                "Validate unpadded vector",
                validation['valid'],
                f"Validation: {validation['errors'] if not validation['valid'] else 'OK'}"
            )
        except Exception as e:
            self.log_test("Validate unpadded vector", False, f"Exception: {e}")
        
        # Test 2: Validate padded vector
        try:
            padded_vector = pad_vector_to_standard(test_vector)
            validation = EmbeddingValidator.validate_embedding_vector(
                padded_vector, 'openclip-vit-b-32', is_padded=True
            )
            
            self.log_test(
                "Validate padded vector",
                validation['valid'],
                f"Validation: {validation['errors'] if not validation['valid'] else 'OK'}"
            )
            
            if validation['valid'] and 'original_dimension' in validation:
                self.log_test(
                    "Detect original dimension",
                    validation['original_dimension'] == len(test_vector),
                    f"Detected {validation['original_dimension']} vs actual {len(test_vector)}"
                )
        except Exception as e:
            self.log_test("Validate padded vector", False, f"Exception: {e}")
    
    def test_database_compatibility(self):
        """Test database field compatibility."""
        print("\n=== Testing Database Compatibility ===")
        
        try:
            # Check if we can create an embedding with 2000-dim vector
            from django.db import connection
            
            # Check vector field configuration
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT column_name, data_type, character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'api_embedding' AND column_name = 'vector'
                """)
                result = cursor.fetchone()
                
                if result:
                    self.log_test(
                        "Database vector field exists",
                        True,
                        f"Field type: {result[1]}"
                    )
                else:
                    self.log_test(
                        "Database vector field exists",
                        False,
                        "Vector field not found in database"
                    )
        except Exception as e:
            self.log_test("Database vector field exists", False, f"Exception: {e}")
    
    def test_similarity_search_dimensions(self):
        """Test similarity search handles dimensions correctly."""
        print("\n=== Testing Similarity Search Dimensions ===")
        
        try:
            # Create a searcher instance
            searcher = SimilaritySearcher()
            
            # Test dimension validation
            test_vector1 = np.random.rand(1024).astype(np.float32)
            test_vector2 = np.random.rand(512).astype(np.float32)
            
            # Test cosine similarity with different dimensions
            similarity = searcher._calculate_cosine_similarity(
                test_vector1, test_vector2, 
                original_dim1=1024, original_dim2=512
            )
            
            self.log_test(
                "Handle dimension mismatch",
                similarity == 0.0,  # Should return 0 for incompatible dimensions
                f"Similarity between 1024D and 512D vectors: {similarity}"
            )
            
            # Test with compatible dimensions
            test_vector3 = np.random.rand(1024).astype(np.float32)
            similarity_compatible = searcher._calculate_cosine_similarity(
                test_vector1, test_vector3,
                original_dim1=1024, original_dim2=1024
            )
            
            self.log_test(
                "Compatible dimensions work",
                0.0 <= similarity_compatible <= 1.0,
                f"Similarity between compatible 1024D vectors: {similarity_compatible}"
            )
            
        except Exception as e:
            self.log_test("Similarity search dimensions", False, f"Exception: {e}")
    
    def test_embedding_storage_retrieval(self):
        """Test that embeddings can be stored and retrieved with correct padding."""
        print("\n=== Testing Embedding Storage/Retrieval ===")
        
        try:
            # Create test data if it doesn't exist
            image_set, _ = ImageSet.objects.get_or_create(
                name="test_padding",
                defaults={"description": "Test set for padding validation"}
            )
            
            image_obj, _ = Image.objects.get_or_create(
                set=image_set,
                filename="test_padding.png",
                defaults={
                    'original_path': '/test/path.png',
                    'processed_path': '/test/path.png',
                    'description': 'Test image for padding',
                    'file_format': 'PNG',
                    'file_size': 1000,
                    'width': 100,
                    'height': 100
                }
            )
            
            # Create test embedding with padding
            original_vector = np.random.rand(1024).astype(np.float32)
            padded_vector = pad_vector_to_standard(original_vector)
            
            # Store embedding
            embedding_obj, created = Embedding.objects.get_or_create(
                image=image_obj,
                embedding_type='text',
                provider_name='test',
                model_name='test-model',
                defaults={
                    'vector': padded_vector.tolist(),
                    'embedding_dimension': len(original_vector)
                }
            )
            
            self.log_test(
                "Store padded embedding",
                True,
                f"Created embedding with {len(padded_vector)}D vector, original {len(original_vector)}D"
            )
            
            # Retrieve and validate
            retrieved_vector = np.array(embedding_obj.vector)
            stored_dim = embedding_obj.embedding_dimension
            
            self.log_test(
                "Retrieve padded embedding",
                len(retrieved_vector) == 2000 and stored_dim == 1024,
                f"Retrieved {len(retrieved_vector)}D vector, stored dim {stored_dim}"
            )
            
            # Test unpadding
            unpadded_retrieved = unpad_vector(retrieved_vector, stored_dim)
            vectors_match = np.allclose(original_vector, unpadded_retrieved, rtol=1e-6)
            
            self.log_test(
                "Round-trip preserves data",
                vectors_match,
                f"Original and retrieved vectors {'match' if vectors_match else 'differ'}"
            )
            
        except Exception as e:
            self.log_test("Embedding storage/retrieval", False, f"Exception: {e}")
    
    def run_all_tests(self):
        """Run all tests."""
        print("Starting Embedding Padding Tests...")
        print("=" * 50)
        
        self.test_padding_functions()
        self.test_validator()
        self.test_database_compatibility()
        self.test_similarity_search_dimensions()
        self.test_embedding_storage_retrieval()
        
        print("\n" + "=" * 50)
        print(f"Test Results: {self.passed} passed, {self.failed} failed")
        
        if self.failed == 0:
            print("🎉 All tests passed! Embedding padding is working correctly.")
        else:
            print("⚠️  Some tests failed. Please review the issues above.")
        
        return self.failed == 0

def main():
    """Main test runner."""
    tester = EmbeddingPaddingTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()