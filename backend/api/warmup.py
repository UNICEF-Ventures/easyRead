"""
Model warmup utilities to improve performance.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def warmup_embedding_model(num_warmup_calls: int = 3) -> bool:
    """
    Warmup the embedding model to improve performance.
    
    Args:
        num_warmup_calls: Number of warmup calls to make
        
    Returns:
        True if warmup was successful, False otherwise
    """
    try:
        from .embedding_adapter import get_embedding_model
        
        logger.info("Starting embedding model warmup...")
        start_time = time.time()
        
        # Get the model instance
        model = get_embedding_model()
        
        # Perform warmup calls
        for i in range(num_warmup_calls):
            embedding = model.encode_single_text(f'warmup test {i}')
            if embedding is None:
                logger.warning(f"Warmup call {i} failed")
                return False
        
        end_time = time.time()
        logger.info(f"Embedding model warmup completed in {(end_time - start_time) * 1000:.2f}ms")
        
        # Test performance after warmup
        perf_start = time.time()
        test_embedding = model.encode_single_text('performance test')
        perf_end = time.time()
        
        if test_embedding is not None:
            logger.info(f"Post-warmup encoding performance: {(perf_end - perf_start) * 1000:.2f}ms")
            return True
        else:
            logger.error("Post-warmup performance test failed")
            return False
            
    except Exception as e:
        logger.error(f"Error during embedding model warmup: {e}")
        return False


def warmup_similarity_search() -> bool:
    """
    Warmup the similarity search to improve performance.
    
    Returns:
        True if warmup was successful, False otherwise
    """
    try:
        from .similarity_search import search_similar_images
        
        logger.info("Starting similarity search warmup...")
        start_time = time.time()
        
        # Perform a test search
        results = search_similar_images('warmup test', n_results=3)
        
        end_time = time.time()
        logger.info(f"Similarity search warmup completed in {(end_time - start_time) * 1000:.2f}ms")
        logger.info(f"Found {len(results)} results during warmup")
        
        return len(results) >= 0  # Success if we get any results (including empty)
        
    except Exception as e:
        logger.error(f"Error during similarity search warmup: {e}")
        return False


def warmup_all_models() -> bool:
    """
    Warmup all models and components.
    
    Returns:
        True if all warmups were successful, False otherwise
    """
    logger.info("Starting complete system warmup...")
    
    embedding_success = warmup_embedding_model()
    search_success = warmup_similarity_search()
    
    success = embedding_success and search_success
    
    if success:
        logger.info("All models warmed up successfully")
    else:
        logger.warning("Some models failed to warm up properly")
    
    return success