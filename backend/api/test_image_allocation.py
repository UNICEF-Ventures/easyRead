"""
Comprehensive tests for image allocation optimization.
Tests all algorithms, edge cases, and performance characteristics.
"""

import unittest
import time
from unittest.mock import patch, MagicMock
from api.image_allocation import (
    ImageAllocationOptimizer, 
    optimize_image_allocation, 
    analyze_allocation_problem
)


class TestImageAllocationOptimizer(unittest.TestCase):
    """Test the ImageAllocationOptimizer class and its methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = ImageAllocationOptimizer(prevent_duplicates=True)
        
        # Sample test data
        self.simple_batch_results = {
            "0": [
                {"id": 1, "url": "car1.jpg", "similarity": 0.9, "description": "red car"},
                {"id": 2, "url": "car2.jpg", "similarity": 0.7, "description": "blue car"},
                {"id": 3, "url": "house1.jpg", "similarity": 0.3, "description": "house"}
            ],
            "1": [
                {"id": 3, "url": "house1.jpg", "similarity": 0.85, "description": "house"},
                {"id": 4, "url": "house2.jpg", "similarity": 0.8, "description": "green house"},
                {"id": 1, "url": "car1.jpg", "similarity": 0.2, "description": "red car"}
            ]
        }
        
        self.complex_batch_results = {
            "0": [{"id": i, "url": f"img{i}.jpg", "similarity": 0.9 - (i * 0.1)} for i in range(1, 6)],
            "1": [{"id": i, "url": f"img{i}.jpg", "similarity": 0.8 - (i * 0.1)} for i in range(3, 8)],
            "2": [{"id": i, "url": f"img{i}.jpg", "similarity": 0.7 - (i * 0.1)} for i in range(5, 10)],
            "3": [{"id": i, "url": f"img{i}.jpg", "similarity": 0.6 - (i * 0.1)} for i in range(7, 12)]
        }
    
    def test_simple_allocation(self):
        """Test basic allocation with simple data."""
        result = self.optimizer.optimize_allocation(self.simple_batch_results)
        
        self.assertIn("allocation", result)
        self.assertIn("metrics", result)
        
        allocation = result["allocation"]
        metrics = result["metrics"]
        
        # Should allocate both sentences
        self.assertEqual(len(allocation), 2)
        self.assertIn("0", allocation)
        self.assertIn("1", allocation)
        
        # Check allocation quality
        self.assertEqual(allocation["0"]["image_id"], 1)  # Best match for sentence 0
        self.assertEqual(allocation["1"]["image_id"], 3)  # Best available for sentence 1
        
        # Check metrics
        self.assertEqual(metrics["sentences_processed"], 2)
        self.assertEqual(metrics["sentences_assigned"], 2)
        self.assertEqual(metrics["assignment_rate"], 1.0)
        self.assertGreater(metrics["total_similarity"], 1.5)  # Should be high quality
    
    def test_duplicate_prevention(self):
        """Test that duplicate prevention works correctly."""
        result = self.optimizer.optimize_allocation(self.simple_batch_results)
        allocation = result["allocation"]
        
        # Extract assigned image IDs
        assigned_ids = set()
        for sentence_allocation in allocation.values():
            assigned_ids.add(sentence_allocation["image_id"])
        
        # Should have no duplicate assignments
        self.assertEqual(len(assigned_ids), len(allocation))
    
    def test_no_duplicate_prevention(self):
        """Test allocation without duplicate prevention."""
        optimizer = ImageAllocationOptimizer(prevent_duplicates=False)
        result = optimizer.optimize_allocation(self.simple_batch_results)
        allocation = result["allocation"]
        
        # Should still allocate optimally, but duplicates allowed
        self.assertEqual(len(allocation), 2)
        
        # Both sentences should get their best matches
        self.assertEqual(allocation["0"]["image_id"], 1)  # Best for sentence 0
        self.assertEqual(allocation["1"]["image_id"], 3)  # Best for sentence 1
    
    def test_complex_allocation(self):
        """Test allocation with more complex overlapping data."""
        result = self.optimizer.optimize_allocation(self.complex_batch_results)
        allocation = result["allocation"]
        metrics = result["metrics"]
        
        # Should allocate all 4 sentences
        self.assertEqual(len(allocation), 4)
        self.assertEqual(metrics["sentences_assigned"], 4)
        self.assertEqual(metrics["assignment_rate"], 1.0)
        
        # Check for duplicate prevention
        assigned_ids = [alloc["image_id"] for alloc in allocation.values()]
        self.assertEqual(len(set(assigned_ids)), len(assigned_ids))
        
        # Quality should be reasonable
        self.assertGreater(metrics["average_similarity"], 0.3)
    
    def test_empty_input(self):
        """Test handling of empty input."""
        result = self.optimizer.optimize_allocation({})
        
        self.assertEqual(result["allocation"], {})
        self.assertEqual(result["metrics"]["sentences_processed"], 0)
        self.assertEqual(result["metrics"]["sentences_assigned"], 0)
    
    def test_no_valid_images(self):
        """Test handling when no images meet similarity threshold."""
        low_similarity_results = {
            "0": [{"id": 1, "url": "img1.jpg", "similarity": 0.05}],
            "1": [{"id": 2, "url": "img2.jpg", "similarity": 0.03}]
        }
        
        result = self.optimizer.optimize_allocation(low_similarity_results)
        allocation = result["allocation"]
        
        # Should still attempt allocation with available images
        self.assertLessEqual(len(allocation), 2)
    
    def test_similarity_threshold_filtering(self):
        """Test that similarity threshold filtering works."""
        options = {"similarity_threshold": 0.5}
        result = self.optimizer.optimize_allocation(self.simple_batch_results, options)
        
        # Only high-similarity images should be considered
        allocation = result["allocation"]
        
        for sentence_allocation in allocation.values():
            self.assertGreaterEqual(sentence_allocation["similarity"], 0.5)
    
    def test_uniqueness_bonus(self):
        """Test that uniqueness bonus affects allocation."""
        # Create data where uniqueness should matter
        batch_results = {
            "0": [
                {"id": 1, "url": "common.jpg", "similarity": 0.7},
                {"id": 2, "url": "unique1.jpg", "similarity": 0.69}
            ],
            "1": [
                {"id": 1, "url": "common.jpg", "similarity": 0.7},
                {"id": 3, "url": "unique2.jpg", "similarity": 0.69}
            ]
        }
        
        options = {"uniqueness_bonus": 0.1}
        result = self.optimizer.optimize_allocation(batch_results, options)
        allocation = result["allocation"]
        
        # Should prefer unique images due to bonus
        assigned_ids = [alloc["image_id"] for alloc in allocation.values()]
        self.assertNotEqual(assigned_ids[0], assigned_ids[1])  # Should be different
    
    def test_local_search_optimization(self):
        """Test local search optimization improvement."""
        options = {"enable_local_search": True, "local_search_iterations": 3}
        result = self.optimizer.optimize_allocation(self.complex_batch_results, options)
        
        metrics = result["metrics"]
        
        # Should complete successfully
        self.assertGreater(metrics["sentences_assigned"], 0)
        self.assertIn("algorithm", metrics)
    
    def test_large_scale_allocation(self):
        """Test allocation with large number of sentences."""
        # Generate large test data
        large_batch_results = {}
        for i in range(50):  # 50 sentences
            large_batch_results[str(i)] = [
                {"id": j, "url": f"img{j}.jpg", "similarity": 0.9 - (j * 0.05)} 
                for j in range(i, min(i + 10, 100))  # 10 images per sentence
            ]
        
        start_time = time.time()
        result = self.optimizer.optimize_allocation(large_batch_results)
        processing_time = time.time() - start_time
        
        allocation = result["allocation"]
        metrics = result["metrics"]
        
        # Should handle large scale efficiently
        self.assertLess(processing_time, 1.0)  # Should complete in <1 second
        self.assertGreater(len(allocation), 40)  # Should allocate most sentences
        self.assertGreater(metrics["assignment_rate"], 0.8)  # High assignment rate
    
    def test_error_handling(self):
        """Test error handling with malformed input."""
        malformed_inputs = [
            None,
            {"0": None},
            {"0": [{"invalid": "data"}]},
            {"invalid_index": [{"id": 1, "url": "test.jpg", "similarity": 0.8}]}
        ]
        
        for malformed_input in malformed_inputs:
            result = self.optimizer.optimize_allocation(malformed_input)
            
            # Should not crash and return valid structure
            self.assertIn("allocation", result)
            self.assertIn("metrics", result)
            self.assertIsInstance(result["allocation"], dict)
            self.assertIsInstance(result["metrics"], dict)


class TestConvenienceFunctions(unittest.TestCase):
    """Test the convenience functions and utilities."""
    
    def test_optimize_image_allocation_function(self):
        """Test the convenience function."""
        batch_results = {
            "0": [{"id": 1, "url": "test1.jpg", "similarity": 0.8}],
            "1": [{"id": 2, "url": "test2.jpg", "similarity": 0.7}]
        }
        
        result = optimize_image_allocation(batch_results, prevent_duplicates=True)
        
        self.assertIn("allocation", result)
        self.assertIn("metrics", result)
        self.assertEqual(len(result["allocation"]), 2)
    
    def test_analyze_allocation_problem(self):
        """Test the problem analysis function."""
        batch_results = {
            "0": [
                {"id": 1, "url": "img1.jpg", "similarity": 0.9},
                {"id": 2, "url": "img2.jpg", "similarity": 0.7}
            ],
            "1": [
                {"id": 1, "url": "img1.jpg", "similarity": 0.6},
                {"id": 3, "url": "img3.jpg", "similarity": 0.8}
            ]
        }
        
        analysis = analyze_allocation_problem(batch_results)
        
        # Check analysis results
        self.assertEqual(analysis["sentences_count"], 2)
        self.assertEqual(analysis["total_image_options"], 4)
        self.assertEqual(analysis["unique_images"], 3)
        self.assertAlmostEqual(analysis["avg_images_per_sentence"], 2.0)
        self.assertGreater(analysis["avg_similarity"], 0.7)
        self.assertIn("complexity", analysis)
        self.assertIn("sparsity", analysis)


class TestPerformanceAndScalability(unittest.TestCase):
    """Test performance characteristics and scalability."""
    
    def setUp(self):
        self.optimizer = ImageAllocationOptimizer(prevent_duplicates=True)
    
    def test_small_document_performance(self):
        """Test performance with small documents (1-5 sentences)."""
        batch_results = {
            str(i): [
                {"id": j, "url": f"img{j}.jpg", "similarity": 0.9 - (j * 0.1)} 
                for j in range(1, 6)
            ] 
            for i in range(3)  # 3 sentences
        }
        
        start_time = time.time()
        result = self.optimizer.optimize_allocation(batch_results)
        processing_time = time.time() - start_time
        
        # Should be very fast
        self.assertLess(processing_time, 0.1)  # <100ms
        self.assertEqual(result["metrics"]["sentences_assigned"], 3)
    
    def test_medium_document_performance(self):
        """Test performance with medium documents (10-30 sentences)."""
        batch_results = {
            str(i): [
                {"id": j, "url": f"img{j}.jpg", "similarity": 0.8 - (j * 0.05)} 
                for j in range(i, i + 15)  # 15 images per sentence
            ] 
            for i in range(20)  # 20 sentences
        }
        
        start_time = time.time()
        result = self.optimizer.optimize_allocation(batch_results)
        processing_time = time.time() - start_time
        
        # Should still be reasonably fast
        self.assertLess(processing_time, 0.5)  # <500ms
        self.assertGreaterEqual(result["metrics"]["sentences_assigned"], 15)  # Most assigned
    
    def test_large_document_performance(self):
        """Test performance with large documents (50+ sentences)."""
        batch_results = {
            str(i): [
                {"id": j, "url": f"img{j}.jpg", "similarity": 0.7 - (j * 0.02)} 
                for j in range(i, i + 20)  # 20 images per sentence  
            ] 
            for i in range(100)  # 100 sentences
        }
        
        start_time = time.time()
        result = self.optimizer.optimize_allocation(batch_results)
        processing_time = time.time() - start_time
        
        # Should handle large documents efficiently
        self.assertLess(processing_time, 2.0)  # <2 seconds
        self.assertGreater(result["metrics"]["assignment_rate"], 0.7)  # Good assignment rate
    
    def test_memory_usage_stability(self):
        """Test that memory usage remains stable across multiple allocations."""
        import gc
        import sys
        
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Run multiple allocations
        for _ in range(10):
            batch_results = {
                str(i): [
                    {"id": j, "url": f"img{j}.jpg", "similarity": 0.8 - (j * 0.1)} 
                    for j in range(10)
                ] 
                for i in range(20)
            }
            
            self.optimizer.optimize_allocation(batch_results)
        
        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage should not grow significantly
        object_growth = final_objects - initial_objects
        self.assertLess(object_growth, 1000)  # Allow some growth but not excessive


class TestIntegrationScenarios(unittest.TestCase):
    """Test real-world integration scenarios."""
    
    def setUp(self):
        self.optimizer = ImageAllocationOptimizer(prevent_duplicates=True)
    
    def test_realistic_document_scenario(self):
        """Test with realistic document-like data."""
        # Simulate a real document with mixed similarity patterns
        realistic_batch = {
            "0": [  # "A red car driving down the street"
                {"id": 101, "url": "red_car_street.jpg", "similarity": 0.92, "description": "red car on street"},
                {"id": 102, "url": "blue_car_road.jpg", "similarity": 0.78, "description": "blue car on road"},
                {"id": 103, "url": "truck_highway.jpg", "similarity": 0.45, "description": "truck on highway"}
            ],
            "1": [  # "The house has a green door"
                {"id": 201, "url": "house_green_door.jpg", "similarity": 0.89, "description": "house with green door"},
                {"id": 202, "url": "house_red_door.jpg", "similarity": 0.72, "description": "house with red door"},
                {"id": 101, "url": "red_car_street.jpg", "similarity": 0.23, "description": "red car on street"}
            ],
            "2": [  # "A cat sleeping on the sofa"
                {"id": 301, "url": "cat_sofa_sleeping.jpg", "similarity": 0.95, "description": "cat sleeping on sofa"},
                {"id": 302, "url": "dog_couch.jpg", "similarity": 0.54, "description": "dog on couch"},
                {"id": 201, "url": "house_green_door.jpg", "similarity": 0.18, "description": "house with green door"}
            ]
        }
        
        result = self.optimizer.optimize_allocation(realistic_batch)
        allocation = result["allocation"]
        metrics = result["metrics"]
        
        # Should achieve high-quality allocation
        self.assertEqual(len(allocation), 3)
        self.assertEqual(metrics["assignment_rate"], 1.0)
        self.assertGreater(metrics["average_similarity"], 0.8)
        
        # Check optimal assignments
        self.assertEqual(allocation["0"]["image_id"], 101)  # Best car match
        self.assertEqual(allocation["1"]["image_id"], 201)  # Best house match  
        self.assertEqual(allocation["2"]["image_id"], 301)  # Best cat match
    
    def test_sparse_similarity_scenario(self):
        """Test scenario with sparse, low similarities."""
        sparse_batch = {
            "0": [
                {"id": 1, "url": "img1.jpg", "similarity": 0.35},
                {"id": 2, "url": "img2.jpg", "similarity": 0.28}
            ],
            "1": [
                {"id": 3, "url": "img3.jpg", "similarity": 0.31},
                {"id": 1, "url": "img1.jpg", "similarity": 0.22}
            ],
            "2": [
                {"id": 4, "url": "img4.jpg", "similarity": 0.29},
                {"id": 2, "url": "img2.jpg", "similarity": 0.25}
            ]
        }
        
        result = self.optimizer.optimize_allocation(sparse_batch)
        allocation = result["allocation"]
        
        # Should still make reasonable assignments
        self.assertGreater(len(allocation), 0)
        
        # All assignments should use different images (duplicate prevention)
        assigned_ids = [alloc["image_id"] for alloc in allocation.values()]
        self.assertEqual(len(set(assigned_ids)), len(assigned_ids))
    
    def test_high_overlap_scenario(self):
        """Test scenario where many sentences share the same images."""
        high_overlap_batch = {
            str(i): [
                {"id": 1, "url": "popular_img.jpg", "similarity": 0.8 - (i * 0.05)},
                {"id": 2, "url": "common_img.jpg", "similarity": 0.7 - (i * 0.05)},
                {"id": i + 10, "url": f"unique_img_{i}.jpg", "similarity": 0.6}
            ]
            for i in range(8)  # 8 sentences, all wanting the same top images
        }
        
        result = self.optimizer.optimize_allocation(high_overlap_batch)
        allocation = result["allocation"]
        metrics = result["metrics"]
        
        # Should handle high overlap gracefully
        self.assertGreater(len(allocation), 6)  # Most sentences assigned
        self.assertGreater(metrics["assignment_rate"], 0.75)
        
        # Should distribute the popular images optimally
        assigned_ids = [alloc["image_id"] for alloc in allocation.values()]
        self.assertEqual(len(set(assigned_ids)), len(assigned_ids))  # No duplicates


if __name__ == '__main__':
    # Set up test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestImageAllocationOptimizer))
    suite.addTests(loader.loadTestsFromTestCase(TestConvenienceFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceAndScalability))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"TESTS RUN: {result.testsRun}")
    print(f"FAILURES: {len(result.failures)}")
    print(f"ERRORS: {len(result.errors)}")
    print(f"SUCCESS RATE: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")