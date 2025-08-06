"""
Integration tests for the batch endpoint with image allocation.
Tests the full flow from API request to optimized allocation response.
"""

import json
import time
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from rest_framework import status


class TestBatchEndpointIntegration(TestCase):
    """Test integration between batch endpoint and image allocation."""
    
    def setUp(self):
        """Set up test client and common data."""
        self.client = Client()
        self.batch_url = reverse('find_similar_images_batch')
        
        # Mock similarity search results
        self.mock_search_results = [
            {
                'id': 101,
                'original_path': '/media/images/car1.jpg',
                'processed_path': None,
                'description': 'red car on street',
                'similarity': 0.92,
                'filename': 'car1.jpg',
                'set_name': 'vehicles',
                'file_format': 'jpg'
            },
            {
                'id': 102,
                'original_path': '/media/images/car2.jpg', 
                'processed_path': None,
                'description': 'blue car on road',
                'similarity': 0.78,
                'filename': 'car2.jpg',
                'set_name': 'vehicles',
                'file_format': 'jpg'
            }
        ]
    
    def test_batch_endpoint_basic_functionality(self):
        """Test basic batch endpoint functionality."""
        request_data = {
            "queries": [
                {"index": 0, "query": "red car", "n_results": 3},
                {"index": 1, "query": "blue car", "n_results": 3}
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search:
            # Mock search returns different results for each query
            mock_search.side_effect = [
                [
                    {'id': 101, 'original_path': '/media/car1.jpg', 'similarity': 0.92, 
                     'description': 'red car', 'filename': 'car1.jpg', 'set_name': 'vehicles', 'file_format': 'jpg'}
                ],
                [
                    {'id': 102, 'original_path': '/media/car2.jpg', 'similarity': 0.85,
                     'description': 'blue car', 'filename': 'car2.jpg', 'set_name': 'vehicles', 'file_format': 'jpg'}
                ]
            ]
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            response_data = response.json()
            
            # Check basic response structure
            self.assertIn('results', response_data)
            self.assertIn('optimal_allocation', response_data)
            self.assertIn('allocation_metrics', response_data)
            
            # Check results structure
            results = response_data['results']
            self.assertIn('0', results)
            self.assertIn('1', results)
            
            # Check allocation was applied
            allocation = response_data['optimal_allocation']
            self.assertIsInstance(allocation, dict)
            
            # Check metrics
            metrics = response_data['allocation_metrics']
            self.assertIn('algorithm', metrics)
            self.assertIn('processing_time_ms', metrics)
            self.assertIn('assignment_rate', metrics)
    
    def test_batch_endpoint_with_duplicate_images(self):
        """Test batch endpoint when queries return overlapping images."""
        request_data = {
            "queries": [
                {"index": 0, "query": "car", "n_results": 3},
                {"index": 1, "query": "vehicle", "n_results": 3}
            ]
        }
        
        # Mock overlapping search results
        overlapping_results = [
            {'id': 101, 'original_path': '/media/car1.jpg', 'similarity': 0.9, 
             'description': 'red car', 'filename': 'car1.jpg', 'set_name': 'vehicles', 'file_format': 'jpg'},
            {'id': 102, 'original_path': '/media/car2.jpg', 'similarity': 0.8,
             'description': 'blue car', 'filename': 'car2.jpg', 'set_name': 'vehicles', 'file_format': 'jpg'}
        ]
        
        with patch('api.views.search_similar_images') as mock_search:
            # Both queries return same images with different similarities
            mock_search.side_effect = [
                overlapping_results,
                [
                    {'id': 101, 'original_path': '/media/car1.jpg', 'similarity': 0.75,  # Lower similarity
                     'description': 'red car', 'filename': 'car1.jpg', 'set_name': 'vehicles', 'file_format': 'jpg'},
                    {'id': 103, 'original_path': '/media/truck.jpg', 'similarity': 0.7,
                     'description': 'truck', 'filename': 'truck.jpg', 'set_name': 'vehicles', 'file_format': 'jpg'}
                ]
            ]
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            response_data = response.json()
            allocation = response_data['optimal_allocation']
            
            if len(allocation) >= 2:
                # Should allocate different images to avoid duplicates
                assigned_ids = [alloc['image_id'] for alloc in allocation.values()]
                self.assertEqual(len(set(assigned_ids)), len(assigned_ids), "Duplicate images assigned")
                
                # First query should get the better match for shared image
                if '0' in allocation and '1' in allocation:
                    sentence_0_id = allocation['0']['image_id']
                    sentence_1_id = allocation['1']['image_id']
                    self.assertNotEqual(sentence_0_id, sentence_1_id)
    
    def test_batch_endpoint_single_query_no_allocation(self):
        """Test that single queries don't trigger allocation."""
        request_data = {
            "queries": [
                {"index": 0, "query": "single query", "n_results": 3}
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search:
            mock_search.return_value = [
                {'id': 101, 'original_path': '/media/test.jpg', 'similarity': 0.8,
                 'description': 'test image', 'filename': 'test.jpg', 'set_name': 'test', 'file_format': 'jpg'}
            ]
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            
            # Should have results but allocation should be empty or not present
            self.assertIn('results', response_data)
            
            # Allocation might be empty for single query
            if 'optimal_allocation' in response_data:
                allocation = response_data['optimal_allocation']
                # If present, should be minimal
                self.assertLessEqual(len(allocation), 1)
    
    def test_batch_endpoint_error_handling(self):
        """Test error handling in batch endpoint."""
        # Test malformed request
        malformed_requests = [
            {},  # Empty request
            {"queries": []},  # Empty queries
            {"queries": [{"invalid": "data"}]},  # Invalid query format
            {"queries": [{"index": "invalid", "query": "test"}]},  # Invalid index
        ]
        
        for malformed_request in malformed_requests:
            response = self.client.post(
                self.batch_url,
                data=json.dumps(malformed_request),
                content_type='application/json'
            )
            
            # Should return 400 for malformed requests
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            response_data = response.json()
            self.assertIn('error', response_data)
    
    def test_batch_endpoint_search_failure_handling(self):
        """Test handling when image search fails."""
        request_data = {
            "queries": [
                {"index": 0, "query": "test query", "n_results": 3}
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search:
            # Mock search failure
            mock_search.side_effect = Exception("Database connection failed")
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            # Should still return 200 but with error information
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            
            # Should have empty or error results
            self.assertIn('results', response_data)
    
    def test_batch_endpoint_allocation_failure_handling(self):
        """Test handling when allocation optimization fails."""
        request_data = {
            "queries": [
                {"index": 0, "query": "test query 1", "n_results": 3},
                {"index": 1, "query": "test query 2", "n_results": 3}
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search, \
             patch('api.views.optimize_image_allocation') as mock_allocation:
            
            # Mock successful search
            mock_search.return_value = [
                {'id': 101, 'original_path': '/media/test.jpg', 'similarity': 0.8,
                 'description': 'test', 'filename': 'test.jpg', 'set_name': 'test', 'file_format': 'jpg'}
            ]
            
            # Mock allocation failure
            mock_allocation.side_effect = Exception("Allocation algorithm failed")
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            # Should still return successful response
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            
            # Should have search results even if allocation failed
            self.assertIn('results', response_data)
            
            # Allocation should be absent or empty
            allocation = response_data.get('optimal_allocation', {})
            self.assertEqual(len(allocation), 0)
    
    def test_batch_endpoint_performance(self):
        """Test performance characteristics of batch endpoint."""
        # Create larger request
        request_data = {
            "queries": [
                {"index": i, "query": f"test query {i}", "n_results": 5}
                for i in range(20)  # 20 queries
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search:
            # Mock consistent results
            mock_search.return_value = [
                {'id': i, 'original_path': f'/media/img{i}.jpg', 'similarity': 0.8 - (i * 0.01),
                 'description': f'image {i}', 'filename': f'img{i}.jpg', 'set_name': 'test', 'file_format': 'jpg'}
                for i in range(10)
            ]
            
            start_time = time.time()
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            response_time = time.time() - start_time
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Should complete reasonably quickly
            self.assertLess(response_time, 5.0)  # Less than 5 seconds
            
            response_data = response.json()
            
            # Check allocation metrics if present
            if 'allocation_metrics' in response_data:
                metrics = response_data['allocation_metrics']
                processing_time = metrics.get('processing_time_ms', 0)
                
                # Allocation should be fast
                self.assertLess(processing_time, 1000)  # Less than 1 second for allocation
    
    def test_batch_endpoint_analytics_tracking(self):
        """Test that analytics are properly tracked."""
        request_data = {
            "queries": [
                {"index": 0, "query": "test analytics", "n_results": 3},
                {"index": 1, "query": "another test", "n_results": 3}
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search, \
             patch('api.views.get_or_create_session') as mock_session, \
             patch('api.views.track_event') as mock_track:
            
            # Mock successful search
            mock_search.return_value = [
                {'id': 101, 'original_path': '/media/test.jpg', 'similarity': 0.8,
                 'description': 'test', 'filename': 'test.jpg', 'set_name': 'test', 'file_format': 'jpg'}
            ]
            
            # Mock session
            mock_session.return_value = MagicMock()
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Check that analytics were called
            mock_session.assert_called_once()
            
            # Should have tracked both batch search and allocation events
            self.assertGreaterEqual(mock_track.call_count, 1)
            
            # Check the types of events tracked
            tracked_events = [call[0][1] for call in mock_track.call_args_list]
            self.assertIn('image_search_batch', tracked_events)
            
            # If allocation was applied, should track that too
            if len(request_data['queries']) > 1:
                self.assertIn('image_allocation_applied', tracked_events)


class TestBatchEndpointEdgeCases(TestCase):
    """Test edge cases and boundary conditions."""
    
    def setUp(self):
        self.client = Client()
        self.batch_url = reverse('find_similar_images_batch')
    
    def test_large_number_of_queries(self):
        """Test with large number of queries."""
        request_data = {
            "queries": [
                {"index": i, "query": f"large test {i}", "n_results": 3}
                for i in range(100)  # 100 queries
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search:
            mock_search.return_value = [
                {'id': 1, 'original_path': '/media/test.jpg', 'similarity': 0.8,
                 'description': 'test', 'filename': 'test.jpg', 'set_name': 'test', 'file_format': 'jpg'}
            ]
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            # Should handle large requests
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            self.assertIn('results', response_data)
    
    def test_high_similarity_threshold(self):
        """Test with very high similarity requirements."""
        request_data = {
            "queries": [
                {"index": 0, "query": "high similarity test", "n_results": 5},
                {"index": 1, "query": "another high similarity", "n_results": 5}
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search:
            # Return mix of high and low similarity results
            mock_search.return_value = [
                {'id': 1, 'original_path': '/media/high.jpg', 'similarity': 0.95,
                 'description': 'high sim', 'filename': 'high.jpg', 'set_name': 'test', 'file_format': 'jpg'},
                {'id': 2, 'original_path': '/media/low.jpg', 'similarity': 0.3,
                 'description': 'low sim', 'filename': 'low.jpg', 'set_name': 'test', 'file_format': 'jpg'}
            ]
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            
            # Check that allocation prioritized high similarity images
            if 'optimal_allocation' in response_data:
                allocation = response_data['optimal_allocation']
                for alloc in allocation.values():
                    # Should prefer higher similarity images
                    self.assertGreaterEqual(alloc.get('similarity', 0), 0.1)
    
    def test_unicode_and_special_characters(self):
        """Test with unicode and special characters in queries."""
        request_data = {
            "queries": [
                {"index": 0, "query": "émojis 🚗 and ñice çharacters", "n_results": 3},
                {"index": 1, "query": "ファッション style 中文", "n_results": 3}
            ]
        }
        
        with patch('api.views.search_similar_images') as mock_search:
            mock_search.return_value = [
                {'id': 1, 'original_path': '/media/unicode.jpg', 'similarity': 0.8,
                 'description': 'unicode test', 'filename': 'unicode.jpg', 'set_name': 'test', 'file_format': 'jpg'}
            ]
            
            response = self.client.post(
                self.batch_url,
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            # Should handle unicode gracefully
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            self.assertIn('results', response_data)


if __name__ == '__main__':
    import unittest
    unittest.main(verbosity=2)