"""
Alternative models.py file with pgvector VectorField integration.
This file contains the updated Embedding model that uses proper pgvector fields.

USAGE:
1. Install pgvector: pip install pgvector
2. Create pgvector extension: CREATE EXTENSION vector;
3. Replace the vector field in models.py with the one from this file
4. Run migrations

This file is provided as a reference for when pgvector is properly set up.
"""

from django.db import models
from django.contrib.postgres.fields import ArrayField

# Uncomment this import when pgvector is installed
# from pgvector.django import VectorField


class ImageSet(models.Model):
    """
    Represents a set/collection of images with similar style or theme.
    Images without a specific set are grouped into 'General' set.
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Image(models.Model):
    """
    Represents an image with its metadata and set association.
    Replaces ImageMetadata with enhanced functionality.
    """
    set = models.ForeignKey(ImageSet, on_delete=models.CASCADE, related_name='images')
    filename = models.CharField(max_length=255)
    original_path = models.CharField(max_length=500)  # Original file path
    processed_path = models.CharField(max_length=500, blank=True)  # PNG path if converted from SVG
    description = models.TextField(blank=True)
    file_format = models.CharField(max_length=10, choices=[('PNG', 'PNG'), ('SVG', 'SVG')])
    file_size = models.IntegerField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['set', 'filename']  # Unique images per set
        ordering = ['set__name', 'filename']
        indexes = [
            models.Index(fields=['set', 'filename']),
            models.Index(fields=['file_format']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.set.name}/{self.filename}"


class EmbeddingWithPgVector(models.Model):
    """
    Stores embeddings for both images and text descriptions using pgvector.
    This is the updated version that should replace the Embedding model.
    
    IMPORTANT: Requires pgvector extension and Python package.
    """
    EMBEDDING_TYPES = [
        ('image', 'Image Embedding'),
        ('text', 'Text Embedding'),
    ]
    
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='embeddings')
    embedding_type = models.CharField(max_length=10, choices=EMBEDDING_TYPES)
    
    # Use pgvector VectorField instead of JSONField
    # Uncomment this when pgvector is installed:
    # vector = VectorField(dimensions=1024)  # Adjust dimensions based on OpenCLIP model
    
    # Temporary fallback (remove when pgvector is ready):
    vector = models.JSONField()
    
    model_name = models.CharField(max_length=100, default='openclip-vit-b-32')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['image', 'embedding_type']  # One embedding per type per image
        ordering = ['image', 'embedding_type']
        indexes = [
            models.Index(fields=['image', 'embedding_type']),
            models.Index(fields=['embedding_type']),
            models.Index(fields=['model_name']),
            # Vector index will be created via SQL in migration
        ]
    
    def __str__(self):
        return f"{self.image} - {self.embedding_type} embedding"


# Example of how to update the similarity search with pgvector
class PgVectorSimilaritySearch:
    """
    Example similarity search using pgvector operations.
    This shows how to optimize searches once pgvector is properly integrated.
    """
    
    @staticmethod
    def find_similar_embeddings_sql(query_embedding, embedding_type='text', limit=10, image_set=None):
        """
        Example SQL query for efficient similarity search with pgvector.
        
        Args:
            query_embedding: The query embedding vector
            embedding_type: Type of embeddings to search ('image' or 'text')
            limit: Number of results to return
            image_set: Optional image set name to filter by
            
        Returns:
            Raw SQL query string for pgvector similarity search
        """
        base_query = """
        SELECT 
            e.id,
            i.id as image_id,
            i.filename,
            i.description,
            s.name as set_name,
            (e.vector <=> %s) as distance
        FROM api_embedding e
        JOIN api_image i ON e.image_id = i.id
        JOIN api_imageset s ON i.set_id = s.id
        WHERE e.embedding_type = %s
        """
        
        params = [query_embedding, embedding_type]
        
        if image_set:
            base_query += " AND s.name = %s"
            params.append(image_set)
        
        base_query += """
        ORDER BY e.vector <=> %s
        LIMIT %s
        """
        params.extend([query_embedding, limit])
        
        return base_query, params
    
    @staticmethod 
    def create_vector_index_sql():
        """
        SQL commands to create optimal vector indexes for pgvector.
        
        Returns:
            List of SQL commands to create indexes
        """
        return [
            # IVFFlat index for cosine similarity (good for most use cases)
            """
            CREATE INDEX embedding_vector_cosine_idx 
            ON api_embedding 
            USING ivfflat (vector vector_cosine_ops) 
            WITH (lists = 100);
            """,
            
            # HNSW index for L2 distance (if needed)
            """
            CREATE INDEX embedding_vector_l2_idx 
            ON api_embedding 
            USING hnsw (vector vector_l2_ops) 
            WITH (m = 16, ef_construction = 64);
            """,
            
            # Composite index for filtered searches
            """
            CREATE INDEX embedding_type_vector_idx 
            ON api_embedding (embedding_type) 
            INCLUDE (vector);
            """
        ]


# Configuration constants for pgvector
PGVECTOR_CONFIG = {
    # OpenCLIP ViT-bigG-14 embedding dimensions
    'EMBEDDING_DIMENSIONS': 1024,  # Update this based on actual model output
    
    # IVFFlat index parameters
    'IVFFLAT_LISTS': 100,  # Number of cluster centers
    
    # HNSW index parameters  
    'HNSW_M': 16,  # Number of bi-directional links for each node
    'HNSW_EF_CONSTRUCTION': 64,  # Size of dynamic candidate list
    
    # Search parameters
    'DEFAULT_SIMILARITY_LIMIT': 50,
    'MAX_SIMILARITY_LIMIT': 1000,
}