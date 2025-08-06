"""
Performance optimizations and caching for the EasyRead embedding system.
Provides caching mechanisms and performance improvements.
"""

import logging
import time
import hashlib
from typing import Any, Optional, Dict, List, Tuple
from functools import wraps, lru_cache
from django.core.cache import cache
from django.conf import settings
import numpy as np
import pickle

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Caching system for embeddings and similarity search results.
    """
    
    # Cache timeouts (in seconds)
    EMBEDDING_CACHE_TIMEOUT = 24 * 60 * 60  # 24 hours
    SIMILARITY_CACHE_TIMEOUT = 60 * 60      # 1 hour
    MODEL_CACHE_TIMEOUT = 7 * 24 * 60 * 60  # 7 days
    
    # Cache key prefixes
    IMAGE_EMBEDDING_PREFIX = "embed_img"
    TEXT_EMBEDDING_PREFIX = "embed_txt"
    SIMILARITY_PREFIX = "similarity"
    MODEL_PREFIX = "model"
    
    @classmethod
    def _generate_cache_key(cls, prefix: str, identifier: str) -> str:
        """
        Generate a cache key with prefix and hashed identifier.
        
        Args:
            prefix: Cache key prefix
            identifier: Unique identifier for the item
            
        Returns:
            Cache key string
        """
        # Hash the identifier to ensure consistent key length
        hash_obj = hashlib.md5(identifier.encode('utf-8'))
        return f"{prefix}:{hash_obj.hexdigest()}"
    
    @classmethod
    def cache_image_embedding(cls, image_path: str, model_name: str, embedding: np.ndarray) -> bool:
        """
        Cache an image embedding.
        
        Args:
            image_path: Path to the image file
            model_name: Name of the embedding model
            embedding: Embedding vector
            
        Returns:
            True if cached successfully
        """
        try:
            identifier = f"{image_path}:{model_name}"
            cache_key = cls._generate_cache_key(cls.IMAGE_EMBEDDING_PREFIX, identifier)
            
            # Serialize the numpy array
            serialized_embedding = pickle.dumps(embedding)
            
            cache.set(cache_key, serialized_embedding, cls.EMBEDDING_CACHE_TIMEOUT)
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache image embedding: {e}")
            return False
    
    @classmethod
    def get_image_embedding(cls, image_path: str, model_name: str) -> Optional[np.ndarray]:
        """
        Retrieve cached image embedding.
        
        Args:
            image_path: Path to the image file
            model_name: Name of the embedding model
            
        Returns:
            Cached embedding or None if not found
        """
        try:
            identifier = f"{image_path}:{model_name}"
            cache_key = cls._generate_cache_key(cls.IMAGE_EMBEDDING_PREFIX, identifier)
            
            serialized_embedding = cache.get(cache_key)
            if serialized_embedding is not None:
                return pickle.loads(serialized_embedding)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached image embedding: {e}")
            return None
    
    @classmethod
    def cache_text_embedding(cls, text: str, model_name: str, embedding: np.ndarray) -> bool:
        """
        Cache a text embedding.
        
        Args:
            text: Input text
            model_name: Name of the embedding model
            embedding: Embedding vector
            
        Returns:
            True if cached successfully
        """
        try:
            identifier = f"{text}:{model_name}"
            cache_key = cls._generate_cache_key(cls.TEXT_EMBEDDING_PREFIX, identifier)
            
            # Serialize the numpy array
            serialized_embedding = pickle.dumps(embedding)
            
            cache.set(cache_key, serialized_embedding, cls.EMBEDDING_CACHE_TIMEOUT)
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache text embedding: {e}")
            return False
    
    @classmethod
    def get_text_embedding(cls, text: str, model_name: str) -> Optional[np.ndarray]:
        """
        Retrieve cached text embedding.
        
        Args:
            text: Input text
            model_name: Name of the embedding model
            
        Returns:
            Cached embedding or None if not found
        """
        try:
            identifier = f"{text}:{model_name}"
            cache_key = cls._generate_cache_key(cls.TEXT_EMBEDDING_PREFIX, identifier)
            
            serialized_embedding = cache.get(cache_key)
            if serialized_embedding is not None:
                return pickle.loads(serialized_embedding)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached text embedding: {e}")
            return None
    
    @classmethod
    def cache_similarity_results(cls, query_hash: str, results: List[Dict]) -> bool:
        """
        Cache similarity search results.
        
        Args:
            query_hash: Hash of the search query parameters
            results: Search results to cache
            
        Returns:
            True if cached successfully
        """
        try:
            cache_key = cls._generate_cache_key(cls.SIMILARITY_PREFIX, query_hash)
            cache.set(cache_key, results, cls.SIMILARITY_CACHE_TIMEOUT)
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache similarity results: {e}")
            return False
    
    @classmethod
    def get_similarity_results(cls, query_hash: str) -> Optional[List[Dict]]:
        """
        Retrieve cached similarity search results.
        
        Args:
            query_hash: Hash of the search query parameters
            
        Returns:
            Cached results or None if not found
        """
        try:
            cache_key = cls._generate_cache_key(cls.SIMILARITY_PREFIX, query_hash)
            return cache.get(cache_key)
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached similarity results: {e}")
            return None
    
    @classmethod
    def generate_similarity_query_hash(cls, query_text: str, n_results: int, 
                                     image_set: Optional[str] = None,
                                     exclude_ids: Optional[List[int]] = None) -> str:
        """
        Generate a hash for similarity query parameters.
        
        Args:
            query_text: Search query text
            n_results: Number of results requested
            image_set: Optional image set filter
            exclude_ids: Optional list of IDs to exclude
            
        Returns:
            Hash string for the query
        """
        # Create a deterministic string from query parameters
        exclude_str = ",".join(map(str, sorted(exclude_ids))) if exclude_ids else ""
        query_string = f"{query_text}:{n_results}:{image_set or ''}:{exclude_str}"
        
        return hashlib.md5(query_string.encode('utf-8')).hexdigest()
    
    @classmethod
    def clear_cache(cls, prefix: Optional[str] = None) -> bool:
        """
        Clear cached items by prefix.
        
        Args:
            prefix: Cache prefix to clear (if None, clears all embedding caches)
            
        Returns:
            True if successful
        """
        try:
            if prefix:
                # Note: Django's cache framework doesn't have a direct way to clear by prefix
                # This is a simplified implementation
                logger.warning("Cache clearing by prefix not fully implemented")
                return False
            else:
                # Clear all cache
                cache.clear()
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False


def cache_embedding(embedding_type: str = 'both'):
    """
    Decorator to cache embedding generation results.
    
    Args:
        embedding_type: Type of embedding to cache ('image', 'text', or 'both')
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract relevant parameters for caching
            if 'image_path' in kwargs or (len(args) > 0 and hasattr(args[0], 'encode_single_image')):
                # This is likely an image embedding call
                if embedding_type in ['image', 'both']:
                    # Try to get from cache first
                    if len(args) > 1:  # args[0] is self, args[1] is image_path
                        image_path = str(args[1])
                        model_name = getattr(args[0], 'model_name', 'default-api-model')
                        
                        cached_result = EmbeddingCache.get_image_embedding(image_path, model_name)
                        if cached_result is not None:
                            logger.debug(f"Cache hit for image embedding: {image_path}")
                            return cached_result
            
            elif 'text' in kwargs or (len(args) > 1 and isinstance(args[1], str)):
                # This is likely a text embedding call
                if embedding_type in ['text', 'both']:
                    # Try to get from cache first
                    if len(args) > 1:  # args[0] is self, args[1] is text
                        text = str(args[1])
                        model_name = getattr(args[0], 'model_name', 'default-api-model')
                        
                        cached_result = EmbeddingCache.get_text_embedding(text, model_name)
                        if cached_result is not None:
                            logger.debug(f"Cache hit for text embedding: {text[:50]}...")
                            return cached_result
            
            # Cache miss - call the original function
            result = func(*args, **kwargs)
            
            # Cache the result if it's valid
            if result is not None and isinstance(result, np.ndarray):
                try:
                    if 'image_path' in kwargs or (len(args) > 1 and not isinstance(args[1], str)):
                        # Cache image embedding
                        if embedding_type in ['image', 'both'] and len(args) > 1:
                            image_path = str(args[1])
                            model_name = getattr(args[0], 'model_name', 'default-api-model')
                            EmbeddingCache.cache_image_embedding(image_path, model_name, result)
                    
                    elif len(args) > 1 and isinstance(args[1], str):
                        # Cache text embedding
                        if embedding_type in ['text', 'both']:
                            text = str(args[1])
                            model_name = getattr(args[0], 'model_name', 'default-api-model')
                            EmbeddingCache.cache_text_embedding(text, model_name, result)
                            
                except Exception as e:
                    logger.error(f"Failed to cache embedding result: {e}")
            
            return result
        return wrapper
    return decorator


def cache_similarity_search(func):
    """
    Decorator to cache similarity search results.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Extract search parameters
            query_text = kwargs.get('query_text') or (args[1] if len(args) > 1 else None)
            n_results = kwargs.get('n_results', 10)
            image_set = kwargs.get('image_set')
            exclude_ids = kwargs.get('exclude_image_ids')
            
            if query_text:
                # Generate cache key
                query_hash = EmbeddingCache.generate_similarity_query_hash(
                    query_text, n_results, image_set, exclude_ids
                )
                
                # Try to get cached results
                cached_results = EmbeddingCache.get_similarity_results(query_hash)
                if cached_results is not None:
                    logger.debug(f"Cache hit for similarity search: {query_text[:50]}...")
                    return cached_results
                
                # Cache miss - call the original function
                results = func(*args, **kwargs)
                
                # Cache the results
                if results:
                    EmbeddingCache.cache_similarity_results(query_hash, results)
                
                return results
            
        except Exception as e:
            logger.error(f"Error in similarity search caching: {e}")
        
        # Fallback to original function
        return func(*args, **kwargs)
    
    return wrapper


class BatchProcessor:
    """
    Utilities for batch processing of embeddings and operations.
    """
    
    @staticmethod
    def optimize_batch_size(total_items: int, memory_limit_mb: int = 1024) -> int:
        """
        Calculate optimal batch size based on available memory and item count.
        
        Args:
            total_items: Total number of items to process
            memory_limit_mb: Memory limit in megabytes
            
        Returns:
            Optimal batch size
        """
        # Rough estimation: each embedding takes ~4KB (1024 floats * 4 bytes)
        embedding_size_mb = 4 / 1024  # ~0.004 MB per embedding
        
        # Conservative estimate accounting for model overhead
        max_batch_by_memory = int(memory_limit_mb / (embedding_size_mb * 10))  # 10x safety factor
        
        # Don't exceed total items or use excessively large batches
        optimal_batch = min(max_batch_by_memory, total_items, 100)
        
        # Ensure minimum batch size of 1
        return max(1, optimal_batch)
    
    @staticmethod
    def process_in_batches(items: List[Any], batch_size: int, 
                          processor_func, progress_callback=None) -> List[Any]:
        """
        Process items in batches with optional progress tracking.
        
        Args:
            items: List of items to process
            batch_size: Size of each batch
            processor_func: Function to process each batch
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of processed results
        """
        results = []
        total_batches = (len(items) + batch_size - 1) // batch_size
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_number = i // batch_size + 1
            
            try:
                start_time = time.time()
                batch_results = processor_func(batch)
                process_time = time.time() - start_time
                
                results.extend(batch_results)
                
                # Progress reporting
                if progress_callback:
                    progress_callback(batch_number, total_batches, process_time)
                else:
                    logger.info(f"Processed batch {batch_number}/{total_batches} "
                              f"({len(batch)} items) in {process_time:.2f}s")
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_number}: {e}")
                # Continue with next batch
                continue
        
        return results


# Connection pooling configuration
class DatabaseOptimizer:
    """
    Database optimization utilities.
    """
    
    @staticmethod
    def get_recommended_db_settings() -> Dict[str, Any]:
        """
        Get recommended database settings for optimal performance.
        
        Returns:
            Dictionary of recommended settings
        """
        return {
            'CONN_MAX_AGE': 600,  # 10 minutes
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {
                'MAX_CONNS': 20,
                'MIN_CONNS': 5,
                'sslmode': 'prefer',
                # PostgreSQL-specific optimizations
                'statement_timeout': 300000,  # 5 minutes
                'idle_in_transaction_session_timeout': 60000,  # 1 minute
            }
        }
    
    @staticmethod
    def optimize_query_performance():
        """
        Apply database query optimizations.
        """
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Set PostgreSQL optimization parameters
            optimization_queries = [
                "SET shared_preload_libraries = 'pg_stat_statements';",
                "SET effective_cache_size = '1GB';",
                "SET maintenance_work_mem = '256MB';",
                "SET checkpoint_completion_target = 0.9;",
                "SET wal_buffers = '16MB';",
                "SET default_statistics_target = 100;",
            ]
            
            for query in optimization_queries:
                try:
                    cursor.execute(query)
                except Exception as e:
                    logger.warning(f"Failed to apply optimization: {query} - {e}")


# Performance monitoring utilities
class PerformanceMonitor:
    """
    Monitor and report performance metrics.
    """
    
    @staticmethod
    def time_function(func):
        """
        Decorator to time function execution.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            
            execution_time = end_time - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            
            return result
        return wrapper
    
    @staticmethod
    def profile_memory_usage():
        """
        Profile memory usage (requires psutil).
        """
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            return {
                'rss': memory_info.rss / 1024 / 1024,  # MB
                'vms': memory_info.vms / 1024 / 1024,  # MB
                'percent': process.memory_percent()
            }
        except ImportError:
            logger.warning("psutil not available, cannot profile memory usage")
            return None