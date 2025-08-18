"""
Simple concurrency limiter for similarity search requests.
"""
import asyncio
import threading
from functools import wraps
import logging
import os

logger = logging.getLogger(__name__)

class ConcurrencyLimiter:
    """
    Simple semaphore-based concurrency limiter for similarity search requests.
    """
    
    def __init__(self, max_concurrent=2):
        self.max_concurrent = max_concurrent
        self._semaphore = threading.Semaphore(max_concurrent)
        self._active_requests = 0
        self._lock = threading.Lock()
    
    def __call__(self, func):
        """
        Decorator to limit concurrent executions of a function.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self._lock:
                self._active_requests += 1
                logger.info(f"Similarity search request started. Active: {self._active_requests}/{self.max_concurrent}")
            
            try:
                # Acquire semaphore (blocks if max concurrent reached)
                self._semaphore.acquire()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    self._semaphore.release()
            finally:
                with self._lock:
                    self._active_requests -= 1
                    logger.info(f"Similarity search request completed. Active: {self._active_requests}/{self.max_concurrent}")
        
        return wrapper

# Global instance - read max concurrent searches from environment
_max_concurrent = int(os.getenv('MAX_CONCURRENT_SIMILARITY_SEARCHES', '4'))
similarity_search_limiter = ConcurrencyLimiter(max_concurrent=_max_concurrent)