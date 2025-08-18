"""
Image similarity search functionality using PostgreSQL with pgvector.
"""

import logging
import numpy as np
import os
from typing import List, Dict, Optional, Tuple
from django.db import connection
from django.db.models import Q
from django.core.cache import cache
import hashlib
from pgvector.django import CosineDistance, L2Distance
from api.models import ImageSet, Image, Embedding
from api.embedding_adapter import get_embedding_model
from api.monitoring import monitor_embedding_operation, log_structured_error
from api.performance import cache_similarity_search
from api.concurrency_limiter import similarity_search_limiter
from api.model_config import pad_vector_to_standard, unpad_vector

logger = logging.getLogger(__name__)

# Cache embeddings - timeout configurable via environment
EMBEDDING_CACHE_TIMEOUT = int(os.getenv('EMBEDDING_CACHE_TIMEOUT', '3600'))


def search_similar_images_batch(query_texts: List[str], 
                                n_results: int = 10,
                                image_set: Optional[str] = None,
                                image_sets: Optional[List[str]] = None,
                                exclude_image_ids: Optional[List[int]] = None) -> Dict[int, List[Dict]]:
    """
    Batch search for similar images using multiple text queries.
    
    This function optimizes performance by:
    1. Generating embeddings for all queries in batches
    2. Performing database searches with optimized queries
    3. Caching embeddings to avoid regeneration
    
    Args:
        query_texts: List of text queries to search for
        n_results: Number of results to return per query
        image_set: Optional image set name to filter by
        image_sets: Optional list of image set names to filter by
        exclude_image_ids: Optional list of image IDs to exclude
        
    Returns:
        Dictionary mapping query index to list of similar image dictionaries
    """
    import time
    
    logger.info(f"Starting batch similarity search for {len(query_texts)} queries")
    start_time = time.time()
    
    try:
        searcher = SimilaritySearcher()
        results = {}
        
        # Separate cached and non-cached queries
        cached_queries = []
        non_cached_queries = []
        cached_results = {}
        
        for i, query_text in enumerate(query_texts):
            cached_embedding = searcher._get_cached_embedding(query_text)
            if cached_embedding is not None:
                cached_queries.append((i, query_text, cached_embedding))
            else:
                non_cached_queries.append((i, query_text))
        
        logger.info(f"Found {len(cached_queries)} cached embeddings, {len(non_cached_queries)} need generation")
        
        # Generate embeddings for non-cached queries in batch
        if non_cached_queries:
            indices, texts = zip(*non_cached_queries)
            
            # Use batch embedding generation
            try:
                embeddings = searcher.embedding_model.encode_texts(list(texts))
                
                # Cache the new embeddings
                for i, (idx, query_text) in enumerate(non_cached_queries):
                    embedding = embeddings[i]
                    searcher._cache_embedding(query_text, embedding)
                    cached_queries.append((idx, query_text, embedding))
                    
                logger.info(f"Generated {len(embeddings)} new embeddings via batch API")
                
            except Exception as e:
                logger.warning(f"Batch embedding generation failed, falling back to individual calls: {e}")
                # Fall back to individual embedding generation
                for idx, query_text in non_cached_queries:
                    try:
                        embedding = searcher.embedding_model.encode_single_text(query_text)
                        if embedding is not None:
                            searcher._cache_embedding(query_text, embedding)
                            cached_queries.append((idx, query_text, embedding))
                    except Exception as e2:
                        logger.error(f"Failed to generate embedding for query {idx}: {e2}")
                        results[idx] = []
        
        # Now perform similarity searches for all queries
        for idx, query_text, query_embedding in cached_queries:
            try:
                # Use the cached/generated embedding directly
                similar_images = searcher._perform_similarity_search(
                    query_embedding=query_embedding,
                    n_results=n_results,
                    image_set=image_set,
                    image_sets=image_sets,
                    exclude_image_ids=exclude_image_ids
                )
                results[idx] = similar_images
                
            except Exception as e:
                logger.error(f"Similarity search failed for query {idx}: {e}")
                results[idx] = []
        
        total_time = time.time() - start_time
        logger.info(f"Batch similarity search completed in {total_time:.2f}s for {len(query_texts)} queries")
        
        return results
        
    except Exception as e:
        logger.error(f"Batch similarity search failed: {e}")
        # Return empty results for all queries
        return {i: [] for i in range(len(query_texts))}


class SimilaritySearcher:
    """
    Class to handle image similarity search using the new database structure.
    """
    
    def __init__(self, embedding_model=None):
        if embedding_model is not None:
            self.embedding_model = embedding_model
        else:
            self.embedding_model = get_embedding_model()
        
        # Get model metadata for filtering
        self.model_metadata = self.embedding_model.provider.get_model_metadata()
    
    def _get_cached_embedding(self, query_text: str) -> Optional[List[float]]:
        """Get cached embedding for a text query."""
        cache_key = f"embedding:{hashlib.md5(query_text.encode()).hexdigest()}:{self.model_metadata['model_name']}"
        return cache.get(cache_key)
    
    def _cache_embedding(self, query_text: str, embedding: List[float]):
        """Cache an embedding for a text query."""
        cache_key = f"embedding:{hashlib.md5(query_text.encode()).hexdigest()}:{self.model_metadata['model_name']}"
        cache.set(cache_key, embedding, EMBEDDING_CACHE_TIMEOUT)
    
    def _perform_similarity_search(self, query_embedding: np.ndarray, 
                                   n_results: int = 10,
                                   image_set: Optional[str] = None,
                                   image_sets: Optional[List[str]] = None,
                                   exclude_image_ids: Optional[List[int]] = None,
                                   provider_name: Optional[str] = None,
                                   model_name: Optional[str] = None) -> List[Dict]:
        """
        Perform similarity search using a pre-generated embedding.
        
        Args:
            query_embedding: Pre-generated embedding vector
            n_results: Number of results to return
            image_set: Optional image set name to filter by
            image_sets: Optional list of image set names to filter by
            exclude_image_ids: Optional list of image IDs to exclude
            provider_name: Optional provider name to filter by
            model_name: Optional model name to filter by
            
        Returns:
            List of dictionaries containing image information and similarity scores
        """
        try:
            # Store original dimension before padding
            original_query_dim = len(query_embedding)
            
            # Pad the query embedding to standard dimension for pgvector comparison
            padded_query_embedding = pad_vector_to_standard(query_embedding)
            
            # Determine which model to use for filtering
            search_provider = provider_name or self.model_metadata['provider_name']
            search_model = model_name or self.model_metadata['model_name']
            
            # Build the base query for text embeddings - filter by ORIGINAL dimension stored in DB
            embeddings_query = Embedding.objects.filter(
                embedding_type='text',
                provider_name=search_provider,
                model_name=search_model,
                embedding_dimension=original_query_dim
            )
            
            # Filter by image set(s) if specified
            if image_sets:
                embeddings_query = embeddings_query.filter(image__set__name__in=image_sets)
            elif image_set:
                embeddings_query = embeddings_query.filter(image__set__name=image_set)
            
            # Exclude specific image IDs if provided
            if exclude_image_ids:
                embeddings_query = embeddings_query.exclude(image_id__in=exclude_image_ids)
            
            # Select related fields to avoid additional queries
            embeddings_query = embeddings_query.select_related('image', 'image__set')
            
            # Get all text embeddings that match the criteria
            text_embeddings = list(embeddings_query)
            
            if not text_embeddings:
                # Try fallback to any compatible dimension from the same provider/model
                fallback_query = Embedding.objects.filter(
                    embedding_type='text',
                    provider_name=search_provider,
                    model_name=search_model
                ).select_related('image', 'image__set')
                
                if image_sets:
                    fallback_query = fallback_query.filter(image__set__name__in=image_sets)
                elif image_set:
                    fallback_query = fallback_query.filter(image__set__name=image_set)
                
                if exclude_image_ids:
                    fallback_query = fallback_query.exclude(image_id__in=exclude_image_ids)
                
                text_embeddings = list(fallback_query)
                
                if not text_embeddings:
                    return []
            
            # Use pgvector for efficient similarity search
            query_vector = list(padded_query_embedding)
            
            # Validate query vector length
            if len(query_vector) != 2000:
                logger.error(f"Query vector dimension {len(query_vector)} doesn't match database field (2000)")
                return []
            
            # Get embeddings with their cosine distances
            similar_embeddings = (Embedding.objects
                                .filter(id__in=[emb.id for emb in text_embeddings])
                                .annotate(distance=CosineDistance('vector', query_vector))
                                .select_related('image', 'image__set')
                                .order_by('distance')[:n_results])
            
            similarities = []
            for embedding_obj in similar_embeddings:
                try:
                    # Convert distance to similarity score
                    similarity = max(0.0, 1.0 - embedding_obj.distance)
                    
                    # Build result dictionary
                    image_obj = embedding_obj.image
                    if image_obj:
                        similarities.append({
                            'id': image_obj.id,
                            'description': image_obj.description or '',
                            'filename': image_obj.filename or '',
                            'similarity': float(similarity),
                            'set_name': image_obj.set.name if image_obj.set else '',
                            'file_format': image_obj.file_format or ''
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing embedding result: {e}")
                    continue
            
            return similarities
            
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return []
    
    def _validate_embedding_compatibility(self, embedding_obj, query_dimension: int, provider_name: str, model_name: str) -> bool:
        """
        Validate that an embedding is compatible with the query.
        
        Args:
            embedding_obj: Embedding model instance
            query_dimension: Original query embedding dimension
            provider_name: Expected provider name
            model_name: Expected model name
            
        Returns:
            True if compatible, False otherwise
        """
        try:
            # Check provider and model match
            if embedding_obj.provider_name != provider_name or embedding_obj.model_name != model_name:
                logger.debug(f"Provider/model mismatch: {embedding_obj.provider_name}:{embedding_obj.model_name} vs {provider_name}:{model_name}")
                return False
            
            # Check dimension compatibility  
            stored_dimension = embedding_obj.embedding_dimension
            if stored_dimension != query_dimension:
                logger.debug(f"Dimension mismatch: stored {stored_dimension}D vs query {query_dimension}D")
                # Allow some flexibility for compatible dimensions
                compatible_dims = {512, 768, 1024, 1536, 2048, 3072}
                if stored_dimension not in compatible_dims or query_dimension not in compatible_dims:
                    return False
            
            # Check vector data exists and is valid
            if not hasattr(embedding_obj, 'vector') or embedding_obj.vector is None or len(embedding_obj.vector) == 0:
                logger.warning(f"Embedding {embedding_obj.id} has no vector data")
                return False
            
            # Check vector is properly padded
            vector_length = len(embedding_obj.vector) if isinstance(embedding_obj.vector, list) else len(embedding_obj.vector)
            if vector_length != 2000:
                logger.warning(f"Embedding {embedding_obj.id} vector length {vector_length} != 2000")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating embedding compatibility: {e}")
            return False
    
    @monitor_embedding_operation('similarity_search')
    @cache_similarity_search
    @similarity_search_limiter
    def find_similar_images(self, query_text: str, 
                           n_results: int = 10,
                           image_set: Optional[str] = None,
                           image_sets: Optional[List[str]] = None,
                           exclude_image_ids: Optional[List[int]] = None,
                           provider_name: Optional[str] = None,
                           model_name: Optional[str] = None) -> List[Dict]:
        """
        Find similar images based on a text query.
        
        Args:
            query_text: Text query to search for
            n_results: Number of results to return
            image_set: Optional image set name to filter by
            exclude_image_ids: Optional list of image IDs to exclude
            provider_name: Optional provider name to filter by (overrides current model)
            model_name: Optional model name to filter by (overrides current model)
            
        Returns:
            List of dictionaries containing image information and similarity scores
        """
        try:
            # Try to get cached embedding first
            query_embedding = self._get_cached_embedding(query_text)
            
            if query_embedding is None:
                # Generate text embedding for the query
                query_embedding = self.embedding_model.encode_single_text(query_text)
                if query_embedding is None:
                    logger.error(f"Failed to generate embedding for query: {query_text}")
                    return []
                
                # Cache the embedding
                self._cache_embedding(query_text, query_embedding)
            else:
                logger.debug(f"Using cached embedding for query: {query_text[:50]}...")
            
            # Store original dimension before padding
            original_query_dim = len(query_embedding)
            
            # Pad the query embedding to standard dimension for pgvector comparison
            padded_query_embedding = pad_vector_to_standard(query_embedding)
            
            # Determine which model to use for filtering - must match the query model
            search_provider = provider_name or self.model_metadata['provider_name']
            search_model = model_name or self.model_metadata['model_name']
            
            # Build the base query for text embeddings - filter by ORIGINAL dimension stored in DB
            embeddings_query = Embedding.objects.filter(
                embedding_type='text',
                provider_name=search_provider,
                model_name=search_model,
                embedding_dimension=original_query_dim  # Use original dimension, not padded
            )
            
            logger.info(f"Searching for embeddings with provider={search_provider}, model={search_model}, dimension={original_query_dim}")
            
            # Filter by image set(s) if specified
            if image_sets:
                embeddings_query = embeddings_query.filter(image__set__name__in=image_sets)
            elif image_set:
                embeddings_query = embeddings_query.filter(image__set__name=image_set)
            
            # Exclude specific image IDs if provided
            if exclude_image_ids:
                embeddings_query = embeddings_query.exclude(image_id__in=exclude_image_ids)
            
            # Select related fields to avoid additional queries
            embeddings_query = embeddings_query.select_related('image', 'image__set')
            
            # Get all text embeddings that match the criteria
            text_embeddings = list(embeddings_query)
            
            if not text_embeddings:
                logger.info(f"No text embeddings found for query: '{query_text}' with provider={search_provider}, model={search_model}, dimension={original_query_dim}")
                # Try falling back to any compatible dimension from the same provider/model
                fallback_query = Embedding.objects.filter(
                    embedding_type='text',
                    provider_name=search_provider,
                    model_name=search_model
                ).select_related('image', 'image__set')
                
                if image_sets:
                    fallback_query = fallback_query.filter(image__set__name__in=image_sets)
                elif image_set:
                    fallback_query = fallback_query.filter(image__set__name=image_set)
                
                if exclude_image_ids:
                    fallback_query = fallback_query.exclude(image_id__in=exclude_image_ids)
                
                text_embeddings = list(fallback_query)
                
                if not text_embeddings:
                    logger.warning(f"No fallback embeddings found for provider={search_provider}, model={search_model}")
                    return []
                else:
                    logger.info(f"Using fallback: found {len(text_embeddings)} embeddings from same provider/model")
            
            # Use pgvector for efficient similarity search with PADDED vectors
            # Convert padded query embedding to the format expected by pgvector
            query_vector = list(padded_query_embedding)  # Use padded vector for comparison
            
            # Validate query vector length matches database field
            if len(query_vector) != 2000:
                logger.error(f"Query vector dimension {len(query_vector)} doesn't match database field (2000)")
                return []
            
            # Re-apply the query with the actual embeddings found (for fallback case)
            if text_embeddings != list(embeddings_query):
                # We're using fallback embeddings, need to update the query
                fallback_ids = [emb.id for emb in text_embeddings]
                embeddings_query = Embedding.objects.filter(id__in=fallback_ids)
            
            # Get embeddings with their cosine distances using pgvector
            similar_embeddings = (embeddings_query
                                .annotate(distance=CosineDistance('vector', query_vector))
                                .order_by('distance')[:n_results])
            
            similarities = []
            for embedding_obj in similar_embeddings:
                try:
                    # Validate the retrieved embedding
                    if not hasattr(embedding_obj, 'vector') or embedding_obj.vector is None or len(embedding_obj.vector) == 0:
                        logger.warning(f"Embedding {embedding_obj.id} has no vector data")
                        continue
                    
                    # Check for dimension mismatch warnings
                    stored_dim = embedding_obj.embedding_dimension
                    vector_dim = len(embedding_obj.vector) if isinstance(embedding_obj.vector, list) else len(embedding_obj.vector)
                    
                    if stored_dim != original_query_dim:
                        logger.debug(f"Dimension mismatch in fallback: query {original_query_dim}D vs stored {stored_dim}D")
                    
                    # Convert distance to similarity score (1.0 - distance for cosine)
                    similarity = max(0.0, 1.0 - embedding_obj.distance)
                    
                    # Validate similarity score
                    if similarity < 0.0 or similarity > 1.0:
                        logger.warning(f"Invalid similarity score {similarity} for embedding {embedding_obj.id}")
                        similarity = max(0.0, min(1.0, similarity))
                    
                    # Build result dictionary
                    image_obj = embedding_obj.image
                    result = {
                        'id': image_obj.id,
                        'filename': image_obj.filename,
                        'set_name': image_obj.set.name,
                        'description': image_obj.description,
                        'similarity': similarity,
                        'original_path': image_obj.original_path,
                        'processed_path': image_obj.processed_path,
                        'file_format': image_obj.file_format,
                        'created_at': image_obj.created_at,
                        # Add debugging info
                        'embedding_dimension': stored_dim,
                        'query_dimension': original_query_dim,
                        'distance': embedding_obj.distance
                    }
                    similarities.append(result)
                    
                except Exception as e:
                    logger.error(f"Error processing embedding for image {embedding_obj.image.id}: {e}")
                    continue
            
            # Results are already sorted by distance (ascending), so similarities are in descending order
            return similarities
            
        except Exception as e:
            logger.error(f"Error in find_similar_images: {e}")
            return []
    
    def find_similar_images_by_image(self, image_id: int, 
                                   n_results: int = 10,
                                   image_set: Optional[str] = None,
                                   exclude_image_ids: Optional[List[int]] = None,
                                   provider_name: Optional[str] = None,
                                   model_name: Optional[str] = None) -> List[Dict]:
        """
        Find similar images based on another image's embedding.
        
        Args:
            image_id: ID of the reference image
            n_results: Number of results to return
            image_set: Optional image set name to filter by
            exclude_image_ids: Optional list of image IDs to exclude
            provider_name: Optional provider name to filter by (overrides current model)
            model_name: Optional model name to filter by (overrides current model)
            
        Returns:
            List of dictionaries containing image information and similarity scores
        """
        try:
            # Determine which model to use for filtering
            search_provider = provider_name or self.model_metadata['provider_name']
            search_model = model_name or self.model_metadata['model_name']
            
            # Get the reference image's embedding with model filtering
            reference_embedding = Embedding.objects.filter(
                image_id=image_id,
                embedding_type='image',
                provider_name=search_provider,
                model_name=search_model
            ).first()
            
            if not reference_embedding:
                logger.error(f"No image embedding found for image ID: {image_id} with model {search_provider}:{search_model}")
                return []
            
            # Get the reference embedding vector (already padded in DB)
            query_embedding = list(reference_embedding.vector)
            # Get the original dimension from the database
            original_query_dim = reference_embedding.embedding_dimension
            
            # Build the base query for image embeddings - filter by ORIGINAL dimension
            embeddings_query = Embedding.objects.filter(
                embedding_type='image',
                provider_name=search_provider,
                model_name=search_model,
                embedding_dimension=original_query_dim  # Use original dimension stored in DB
            )
            
            logger.info(f"Searching for image embeddings with provider={search_provider}, model={search_model}, dimension={original_query_dim}")
            
            # Filter by image set if specified
            if image_set:
                embeddings_query = embeddings_query.filter(image__set__name=image_set)
            
            # Exclude the reference image and any other specified IDs
            exclude_ids = [image_id]
            if exclude_image_ids:
                exclude_ids.extend(exclude_image_ids)
            embeddings_query = embeddings_query.exclude(image_id__in=exclude_ids)
            
            # Select related fields to avoid additional queries
            embeddings_query = embeddings_query.select_related('image', 'image__set')
            
            # Get all image embeddings that match the criteria
            image_embeddings = list(embeddings_query)
            
            if not image_embeddings:
                logger.info(f"No image embeddings found for comparison with image ID: {image_id} with model {search_provider}:{search_model}")
                return []
            
            # Use pgvector for efficient similarity search
            # Get embeddings with their cosine distances using pgvector
            similar_embeddings = (embeddings_query
                                .annotate(distance=CosineDistance('vector', query_embedding))
                                .order_by('distance')[:n_results])
            
            similarities = []
            for embedding_obj in similar_embeddings:
                try:
                    # Convert distance to similarity score (1.0 - distance for cosine)
                    similarity = max(0.0, 1.0 - embedding_obj.distance)
                    
                    # Build result dictionary
                    image_obj = embedding_obj.image
                    result = {
                        'id': image_obj.id,
                        'filename': image_obj.filename,
                        'set_name': image_obj.set.name,
                        'description': image_obj.description,
                        'similarity': similarity,
                        'original_path': image_obj.original_path,
                        'processed_path': image_obj.processed_path,
                        'file_format': image_obj.file_format,
                        'created_at': image_obj.created_at
                    }
                    similarities.append(result)
                    
                except Exception as e:
                    logger.error(f"Error processing embedding for image {embedding_obj.image.id}: {e}")
                    continue
            
            # Results are already sorted by distance (ascending), so similarities are in descending order
            return similarities
            
        except Exception as e:
            logger.error(f"Error in find_similar_images_by_image: {e}")
            return []
    
    def _calculate_cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray, 
                                   original_dim1: Optional[int] = None, 
                                   original_dim2: Optional[int] = None) -> float:
        """
        Calculate cosine similarity between two embeddings, handling padding correctly.
        
        Args:
            embedding1: First embedding vector (may be padded)
            embedding2: Second embedding vector (may be padded)
            original_dim1: Original dimension of first embedding before padding
            original_dim2: Original dimension of second embedding before padding
            
        Returns:
            Cosine similarity score (0 to 1)
        """
        try:
            # If we have original dimensions, unpad the vectors for fair comparison
            if original_dim1 is not None and len(embedding1) > original_dim1:
                embedding1 = unpad_vector(embedding1, original_dim1)
            if original_dim2 is not None and len(embedding2) > original_dim2:
                embedding2 = unpad_vector(embedding2, original_dim2)
            
            # Check if embeddings have compatible dimensions after unpadding
            if embedding1.shape != embedding2.shape:
                logger.warning(f"Dimension mismatch after unpadding: {embedding1.shape} vs {embedding2.shape}")
                
                # If dimensions still don't match, they're from different models - incomparable
                if original_dim1 and original_dim2 and original_dim1 != original_dim2:
                    logger.error(f"Cannot compare embeddings from different models: {original_dim1}D vs {original_dim2}D")
                    return 0.0
                
                # Fall back to truncating to smaller dimension as last resort
                min_dim = min(len(embedding1), len(embedding2))
                embedding1 = embedding1[:min_dim]
                embedding2 = embedding2[:min_dim]
                logger.warning(f"Fallback: truncated embeddings to dimension {min_dim}")
            
            # Normalize embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
            
            # Ensure the result is between 0 and 1
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def get_image_sets(self) -> List[Dict]:
        """
        Get all available image sets.
        
        Returns:
            List of image sets with their metadata
        """
        try:
            image_sets = ImageSet.objects.all().order_by('name')
            return [
                {
                    'id': img_set.id,
                    'name': img_set.name,
                    'description': img_set.description,
                    'image_count': img_set.images.count(),
                    'created_at': img_set.created_at
                }
                for img_set in image_sets
            ]
        except Exception as e:
            logger.error(f"Error getting image sets: {e}")
            return []
    
    def get_images_in_set(self, set_name: str, limit: int = 50) -> List[Dict]:
        """
        Get images in a specific set.
        
        Args:
            set_name: Name of the image set
            limit: Maximum number of images to return
            
        Returns:
            List of images in the set
        """
        try:
            images = Image.objects.filter(
                set__name=set_name
            ).select_related('set').order_by('filename')[:limit]
            
            return [
                {
                    'id': img.id,
                    'filename': img.filename,
                    'set_name': img.set.name,
                    'description': img.description,
                    'original_path': img.original_path,
                    'processed_path': img.processed_path,
                    'file_format': img.file_format,
                    'file_size': img.file_size,
                    'width': img.width,
                    'height': img.height,
                    'created_at': img.created_at
                }
                for img in images
            ]
        except Exception as e:
            logger.error(f"Error getting images in set {set_name}: {e}")
            return []


# Global searcher instance
_searcher_instance = None


def get_similarity_searcher() -> SimilaritySearcher:
    """
    Get the global similarity searcher instance.
    
    Returns:
        SimilaritySearcher instance
    """
    global _searcher_instance
    if _searcher_instance is None:
        # Use the global embedding model to avoid recreating it
        embedding_model = get_embedding_model()
        _searcher_instance = SimilaritySearcher(embedding_model)
    return _searcher_instance


def cleanup_similarity_searcher():
    """
    Clean up the global similarity searcher instance.
    """
    global _searcher_instance
    if _searcher_instance is not None:
        # The searcher will be cleaned up when the embedding model is cleaned up
        _searcher_instance = None
        logger.info("Global similarity searcher instance cleaned up")
    else:
        logger.info("No similarity searcher instance to clean up")


def search_similar_images(query_text: str, 
                         n_results: int = 10,
                         image_set: Optional[str] = None,
                         image_sets: Optional[List[str]] = None,
                         exclude_image_ids: Optional[List[int]] = None) -> List[Dict]:
    """
    Search for similar images based on text query.
    
    Args:
        query_text: Text query to search for
        n_results: Number of results to return
        image_set: Optional image set name to filter by
        image_sets: Optional list of image set names to filter by
        exclude_image_ids: Optional list of image IDs to exclude
        
    Returns:
        List of similar images with metadata
    """
    searcher = get_similarity_searcher()
    return searcher.find_similar_images(
        query_text=query_text,
        n_results=n_results,
        image_set=image_set,
        image_sets=image_sets,
        exclude_image_ids=exclude_image_ids
    )


def search_similar_images_by_image(image_id: int, 
                                  n_results: int = 10,
                                  image_set: Optional[str] = None,
                                  exclude_image_ids: Optional[List[int]] = None) -> List[Dict]:
    """
    Search for similar images based on another image.
    
    Args:
        image_id: ID of the reference image
        n_results: Number of results to return
        image_set: Optional image set name to filter by
        exclude_image_ids: Optional list of image IDs to exclude
        
    Returns:
        List of similar images with metadata
    """
    searcher = get_similarity_searcher()
    return searcher.find_similar_images_by_image(
        image_id=image_id,
        n_results=n_results,
        image_set=image_set,
        exclude_image_ids=exclude_image_ids
    )


def get_all_image_sets() -> List[Dict]:
    """
    Get all available image sets.
    
    Returns:
        List of image sets with their metadata
    """
    searcher = get_similarity_searcher()
    return searcher.get_image_sets()


def get_images_in_set(set_name: str, limit: int = 50) -> List[Dict]:
    """
    Get images in a specific set.
    
    Args:
        set_name: Name of the image set
        limit: Maximum number of images to return
        
    Returns:
        List of images in the set
    """
    searcher = get_similarity_searcher()
    return searcher.get_images_in_set(set_name, limit)