"""
Middleware for monitoring memory usage and cleaning up resources.
"""

import logging
import gc
import psutil
import os
from django.conf import settings
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class MemoryMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor memory usage and periodically clean up resources.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.request_count = 0
        self.cleanup_interval = getattr(settings, 'MEMORY_CLEANUP_INTERVAL', 50)  # Clean up every 50 requests
        self.memory_warning_threshold = getattr(settings, 'MEMORY_WARNING_MB', 1000)  # Warn if over 1GB
        super().__init__(get_response)
    
    def process_request(self, request):
        """Log memory usage before processing request."""
        self.request_count += 1
        
        # Log memory usage periodically
        if self.request_count % 10 == 0:
            self.log_memory_usage(f"Before request {self.request_count}")
        
        return None
    
    def process_response(self, request, response):
        """Clean up resources after processing request."""
        # Periodic cleanup
        if self.request_count % self.cleanup_interval == 0:
            self.cleanup_resources()
        
        # Log memory usage periodically
        if self.request_count % 10 == 0:
            self.log_memory_usage(f"After request {self.request_count}")
        
        return response
    
    def log_memory_usage(self, label):
        """Log current memory usage."""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            rss_mb = memory_info.rss / 1024 / 1024
            
            if rss_mb > self.memory_warning_threshold:
                logger.warning(f"High memory usage ({label}): {rss_mb:.1f} MB")
            else:
                logger.info(f"Memory usage ({label}): {rss_mb:.1f} MB")
                
        except Exception as e:
            logger.error(f"Error getting memory info: {e}")
    
    def cleanup_resources(self):
        """Clean up resources to prevent memory leaks."""
        try:
            logger.info(f"Running periodic cleanup after {self.request_count} requests")
            
            # Force garbage collection
            gc.collect()
            
            # Clear PyTorch cache if available
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            
            # Clean up multiprocessing resources
            try:
                import multiprocessing
                multiprocessing.util._cleanup_tests()
            except (AttributeError, ImportError):
                pass
            
            logger.info("Periodic cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during periodic cleanup: {e}")


class ResourceCleanupMiddleware(MiddlewareMixin):
    """
    Middleware to ensure proper cleanup of ML resources for specific endpoints.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Endpoints that use ML models heavily
        self.ml_endpoints = [
            '/api/find-similar-images/',
            '/api/find-similar-images-batch/',
            '/api/process-page/',
            '/api/generate-image/',
        ]
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """Clean up ML resources after ML-heavy endpoints."""
        # Check if this was an ML endpoint
        if any(request.path.startswith(endpoint) for endpoint in self.ml_endpoints):
            try:
                # Force garbage collection after ML operations
                gc.collect()
                
                # Clear PyTorch cache if available
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass
                
                # Clean up multiprocessing resources after ML operations
                try:
                    import multiprocessing
                    multiprocessing.util._cleanup_tests()
                except (AttributeError, ImportError):
                    pass
                
                # Removed aggressive cleanup for find-similar-images endpoint
                # This was causing "OpenCLIP model not loaded" errors during concurrent requests
                # as it would clean up the model while other requests were still processing
                
                logger.debug(f"Cleaned up resources after ML endpoint: {request.path}")
                
            except Exception as e:
                logger.error(f"Error cleaning up after ML endpoint {request.path}: {e}")
        
        return response