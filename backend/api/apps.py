from django.apps import AppConfig
import atexit
import signal
import logging
import os
import threading

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    
    def ready(self):
        """Called when the app is ready. Set up cleanup handlers."""
        # Register cleanup handler for when the application shuts down
        atexit.register(self.cleanup_resources)
        
        # Register signal handlers for proper cleanup
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # For Windows compatibility
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self._signal_handler)
        
        logger.info("API app ready, cleanup handlers registered")
        
        # Temporarily disable auto-warmup in Docker to prevent startup hangs
        # Models will be loaded on-demand when first used
        logger.info("Auto-warmup disabled in Docker environment")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating cleanup...")
        self.cleanup_resources()
        # Allow normal signal handling to continue
        if signum == signal.SIGTERM:
            os._exit(0)
        elif signum == signal.SIGINT:
            os._exit(1)
    
    def cleanup_resources(self):
        """Clean up resources when the application shuts down."""
        logger.info("Cleaning up API resources...")
        try:
            # Import here to avoid circular imports
            from .embedding_utils import cleanup_embedding_model, force_cleanup_openclip_resources
            from .similarity_search import cleanup_similarity_searcher
            
            # Clean up embedding model
            cleanup_embedding_model()
            
            # Clean up similarity searcher
            cleanup_similarity_searcher()
            
            # Force cleanup of OpenCLIP resources
            force_cleanup_openclip_resources()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Clean up multiprocessing resources
            try:
                import multiprocessing
                # Clean up any remaining multiprocessing resources
                multiprocessing.util._cleanup_tests()
                
                # Clean up any active multiprocessing pools
                import multiprocessing.pool
                if hasattr(multiprocessing.pool, '_pool'):
                    multiprocessing.pool._pool = None
                    
            except (AttributeError, ImportError):
                pass
            
            # Clear PyTorch cache
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            
            logger.info("API resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during API cleanup: {e}")
