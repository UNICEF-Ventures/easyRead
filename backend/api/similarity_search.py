"""
Image similarity search functionality for the new embedding system.
Uses PostgreSQL database with new models instead of ChromaDB.
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from django.db import connection
from django.db.models import Q
from pgvector.django import CosineDistance, L2Distance
from api.models import ImageSet, Image, Embedding
from api.embedding_adapter import get_embedding_model
from api.monitoring import monitor_embedding_operation, log_structured_error
from api.performance import cache_similarity_search
from api.concurrency_limiter import similarity_search_limiter
from api.model_config import pad_vector_to_standard, unpad_vector

logger = logging.getLogger(__name__)


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
            # Generate text embedding for the query
            query_embedding = self.embedding_model.encode_single_text(query_text)
            if query_embedding is None:
                logger.error(f"Failed to generate embedding for query: {query_text}")
                return []
            
            # Determine which model to use for filtering - must match the query model
            search_provider = provider_name or self.model_metadata['provider_name']
            search_model = model_name or self.model_metadata['model_name']
            
            # Get the query embedding dimension
            query_dim = len(query_embedding)
            
            # Build the base query for text embeddings - ONLY from the same model AND same dimension
            embeddings_query = Embedding.objects.filter(
                embedding_type='text',
                provider_name=search_provider,
                model_name=search_model,
                embedding_dimension=query_dim
            )
            
            logger.info(f"Searching for embeddings with provider={search_provider}, model={search_model}, dimension={query_dim}")
            
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
                logger.info(f"No text embeddings found for query: {query_text}")
                return []
            
            # Use pgvector for efficient similarity search instead of manual calculation
            # Convert query embedding to the format expected by pgvector
            query_vector = list(query_embedding)
            
            # Get embeddings with their cosine distances using pgvector
            similar_embeddings = (embeddings_query
                                .annotate(distance=CosineDistance('vector', query_vector))
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
            
            # Get the reference embedding vector
            query_embedding = list(reference_embedding.vector)
            query_dim = len(query_embedding)
            
            # Build the base query for image embeddings with model filtering and same dimension
            embeddings_query = Embedding.objects.filter(
                embedding_type='image',
                provider_name=search_provider,
                model_name=search_model,
                embedding_dimension=query_dim
            )
            
            logger.info(f"Searching for image embeddings with provider={search_provider}, model={search_model}, dimension={query_dim}")
            
            # Filter by image set(s) if specified
            if image_sets:
                embeddings_query = embeddings_query.filter(image__set__name__in=image_sets)
            elif image_set:
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
    
    def _calculate_cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0 to 1)
        """
        try:
            # Check if embeddings have compatible dimensions
            if embedding1.shape != embedding2.shape:
                logger.warning(f"Dimension mismatch: {embedding1.shape} vs {embedding2.shape}")
                
                # Try to handle dimension mismatch by padding or truncating
                max_dim = max(len(embedding1), len(embedding2))
                min_dim = min(len(embedding1), len(embedding2))
                
                # If one is significantly larger than the other, it might be padded
                if max_dim > min_dim:
                    if len(embedding1) > len(embedding2):
                        # Truncate embedding1 to match embedding2's dimension
                        embedding1 = embedding1[:len(embedding2)]
                    else:
                        # Truncate embedding2 to match embedding1's dimension
                        embedding2 = embedding2[:len(embedding1)]
                    
                    logger.info(f"Truncated embeddings to dimension {min_dim}")
                else:
                    # Dimensions are the same, this shouldn't happen but handle it
                    logger.error(f"Unexpected dimension mismatch: {embedding1.shape} vs {embedding2.shape}")
                    return 0.0
            
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