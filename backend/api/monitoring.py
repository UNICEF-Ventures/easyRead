"""
Enhanced error handling and monitoring for the EasyRead embedding system.
Provides structured logging, performance metrics, and error tracking.
"""

import logging
import time
import traceback
from functools import wraps
from typing import Optional, Dict, Any, List
from django.conf import settings
from pathlib import Path
import json

# Configure structured logging
def setup_embeddings_logger():
    """
    Set up a dedicated logger for embedding operations with structured output.
    """
    logger = logging.getLogger('easyread.embeddings')
    
    if not logger.handlers:
        # Create file handler for embedding logs
        log_file = Path(settings.BASE_DIR) / 'logs' / 'embeddings.log'
        log_file.parent.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Structured JSON formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
    
    return logger

# Global logger instance
embeddings_logger = setup_embeddings_logger()


class EmbeddingMetrics:
    """
    Class to track and report embedding system metrics.
    """
    
    def __init__(self):
        self.metrics = {
            'embedding_generation': {
                'total_requests': 0,
                'successful': 0,
                'failed': 0,
                'total_time': 0.0,
                'avg_time': 0.0
            },
            'similarity_search': {
                'total_requests': 0,
                'successful': 0,
                'failed': 0,
                'total_time': 0.0,
                'avg_time': 0.0
            },
            'image_processing': {
                'total_images': 0,
                'svg_conversions': 0,
                'validation_failures': 0,
                'processing_time': 0.0
            },
            'errors': []
        }
    
    def record_embedding_generation(self, success: bool, duration: float, 
                                  embedding_type: str, error: Optional[str] = None):
        """Record metrics for embedding generation."""
        metrics = self.metrics['embedding_generation']
        metrics['total_requests'] += 1
        metrics['total_time'] += duration
        
        if success:
            metrics['successful'] += 1
        else:
            metrics['failed'] += 1
            if error:
                self.metrics['errors'].append({
                    'type': 'embedding_generation',
                    'embedding_type': embedding_type,
                    'error': error,
                    'timestamp': time.time()
                })
        
        metrics['avg_time'] = metrics['total_time'] / metrics['total_requests']
    
    def record_similarity_search(self, success: bool, duration: float, 
                               result_count: int, error: Optional[str] = None):
        """Record metrics for similarity search operations."""
        metrics = self.metrics['similarity_search']
        metrics['total_requests'] += 1
        metrics['total_time'] += duration
        
        if success:
            metrics['successful'] += 1
        else:
            metrics['failed'] += 1
            if error:
                self.metrics['errors'].append({
                    'type': 'similarity_search',
                    'error': error,
                    'timestamp': time.time()
                })
        
        metrics['avg_time'] = metrics['total_time'] / metrics['total_requests']
    
    def record_image_processing(self, svg_conversion: bool, validation_success: bool, 
                              processing_time: float):
        """Record metrics for image processing operations."""
        metrics = self.metrics['image_processing']
        metrics['total_images'] += 1
        metrics['processing_time'] += processing_time
        
        if svg_conversion:
            metrics['svg_conversions'] += 1
        
        if not validation_success:
            metrics['validation_failures'] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            'embedding_generation': {
                **self.metrics['embedding_generation'],
                'success_rate': self._calculate_success_rate('embedding_generation')
            },
            'similarity_search': {
                **self.metrics['similarity_search'],
                'success_rate': self._calculate_success_rate('similarity_search')
            },
            'image_processing': self.metrics['image_processing'],
            'recent_errors': self.metrics['errors'][-10:],  # Last 10 errors
            'total_errors': len(self.metrics['errors'])
        }
    
    def _calculate_success_rate(self, operation_type: str) -> float:
        """Calculate success rate for an operation type."""
        metrics = self.metrics[operation_type]
        total = metrics['total_requests']
        if total == 0:
            return 0.0
        return (metrics['successful'] / total) * 100.0


# Global metrics instance
embedding_metrics = EmbeddingMetrics()


def monitor_embedding_operation(operation_type: str):
    """
    Decorator to monitor embedding operations and collect metrics.
    
    Args:
        operation_type: Type of operation ('generation', 'search', 'processing')
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_msg = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                success = True
                
                # Log successful operation
                embeddings_logger.info(
                    f"Successful {operation_type}",
                    extra={
                        'operation': operation_type,
                        'duration': time.time() - start_time,
                        'success': True,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    }
                )
                
            except Exception as e:
                error_msg = str(e)
                success = False
                
                # Log error with full traceback
                embeddings_logger.error(
                    f"Failed {operation_type}: {error_msg}",
                    extra={
                        'operation': operation_type,
                        'duration': time.time() - start_time,
                        'success': False,
                        'error': error_msg,
                        'traceback': traceback.format_exc(),
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    }
                )
                
                # Re-raise the exception
                raise
            
            finally:
                duration = time.time() - start_time
                
                # Record metrics based on operation type
                if operation_type == 'embedding_generation':
                    embedding_type = kwargs.get('embedding_type', 'unknown')
                    embedding_metrics.record_embedding_generation(
                        success, duration, embedding_type, error_msg
                    )
                elif operation_type == 'similarity_search':
                    result_count = len(result) if result and isinstance(result, list) else 0
                    embedding_metrics.record_similarity_search(
                        success, duration, result_count, error_msg
                    )
                elif operation_type == 'image_processing':
                    svg_conversion = kwargs.get('svg_conversion', False)
                    validation_success = success  # If no exception, validation succeeded
                    embedding_metrics.record_image_processing(
                        svg_conversion, validation_success, duration
                    )
            
            return result
        return wrapper
    return decorator


class EmbeddingHealthCheck:
    """
    Health check utilities for the embedding system.
    """
    
    @staticmethod
    def check_model_availability() -> Dict[str, Any]:
        """Check if the embedding model is available and working."""
        try:
            from api.embedding_adapter import get_embedding_model
            
            model = get_embedding_model()
            
            # Test with a simple text
            test_embedding = model.encode_single_text("test")
            
            return {
                'status': 'healthy',
                'model_loaded': True,
                'test_embedding_generated': test_embedding is not None,
                'embedding_dimension': len(test_embedding) if test_embedding is not None else None
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'model_loaded': False,
                'error': str(e)
            }
    
    @staticmethod
    def check_database_connectivity() -> Dict[str, Any]:
        """Check database connectivity and basic operations."""
        try:
            from api.models import ImageSet, Image, Embedding
            from django.db import connection
            
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_connected = cursor.fetchone()[0] == 1
            
            # Test model queries
            image_sets_count = ImageSet.objects.count()
            images_count = Image.objects.count()
            embeddings_count = Embedding.objects.count()
            
            return {
                'status': 'healthy',
                'database_connected': db_connected,
                'image_sets_count': image_sets_count,
                'images_count': images_count,
                'embeddings_count': embeddings_count
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'database_connected': False,
                'error': str(e)
            }
    
    @staticmethod
    def check_storage_accessibility() -> Dict[str, Any]:
        """Check if media storage is accessible."""
        try:
            from django.conf import settings
            from pathlib import Path
            
            media_root = Path(settings.MEDIA_ROOT)
            images_dir = media_root / 'images'
            
            # Check if directories exist and are writable
            media_exists = media_root.exists()
            media_writable = media_root.is_dir() and os.access(media_root, os.W_OK) if media_exists else False
            
            images_exists = images_dir.exists()
            images_writable = images_dir.is_dir() and os.access(images_dir, os.W_OK) if images_exists else False
            
            return {
                'status': 'healthy' if media_writable and images_writable else 'degraded',
                'media_root_exists': media_exists,
                'media_root_writable': media_writable,
                'images_dir_exists': images_exists,
                'images_dir_writable': images_writable,
                'media_root_path': str(media_root)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    @classmethod
    def full_health_check(cls) -> Dict[str, Any]:
        """Perform a comprehensive health check."""
        return {
            'timestamp': time.time(),
            'model': cls.check_model_availability(),
            'database': cls.check_database_connectivity(),
            'storage': cls.check_storage_accessibility(),
            'metrics': embedding_metrics.get_summary()
        }


def log_structured_error(logger: logging.Logger, error: Exception, 
                        context: Dict[str, Any], operation: str):
    """
    Log an error with structured context information.
    
    Args:
        logger: Logger instance to use
        error: The exception that occurred
        context: Additional context information
        operation: Description of the operation that failed
    """
    error_data = {
        'operation': operation,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'context': context,
        'timestamp': time.time()
    }
    
    logger.error(
        f"Operation failed: {operation}",
        extra=error_data
    )


# Import os for storage check
import os