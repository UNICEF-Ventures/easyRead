from django.db import models

# Create your models here.

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
    
    def __str__(self):
        return f"{self.set.name}/{self.filename}"


class Embedding(models.Model):
    """
    Stores embeddings for both images and text descriptions.
    Now supports multiple embedding models per image/type combination.
    Uses PostgreSQL vector field for efficient similarity search.
    """
    EMBEDDING_TYPES = [
        ('image', 'Image Embedding'),
        ('text', 'Text Embedding'),
    ]
    
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='embeddings')
    embedding_type = models.CharField(max_length=10, choices=EMBEDDING_TYPES)
    # Vector field for pgvector - will be updated once pgvector is properly configured
    vector = models.JSONField()  # Temporary storage, will be replaced with vector field
    
    # Enhanced model tracking fields
    provider_name = models.CharField(max_length=100, default='openclip')  # e.g., 'openclip', 'openai', 'cohere'
    model_name = models.CharField(max_length=100, default='openclip-vit-b-32')  # e.g., 'ViT-B-32', 'text-embedding-3-small'
    embedding_dimension = models.IntegerField(default=1280)  # Store actual dimension for filtering, default to SentenceTransformer size
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Allow multiple embeddings per image/type, but unique per provider/model combination
        unique_together = ['image', 'embedding_type', 'provider_name', 'model_name']
        ordering = ['image', 'embedding_type', 'provider_name', 'model_name']
        
        # Add indexes for efficient querying
        indexes = [
            models.Index(fields=['provider_name', 'model_name', 'embedding_type']),
            models.Index(fields=['image', 'embedding_type', 'provider_name']),
            models.Index(fields=['embedding_dimension']),
        ]
    
    def __str__(self):
        return f"{self.image} - {self.embedding_type} embedding ({self.provider_name}:{self.model_name})"


class ProcessedContent(models.Model):
    title = models.CharField(max_length=255, blank=True, default='')
    original_markdown = models.TextField()
    # Store the list of dicts including sentence, keyword, and SELECTED image path
    easy_read_json = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Avoid loading large JSON in admin list view if possible
        title_str = f' - "{self.title}"' if self.title else ''
        return f"Processed Content (ID: {self.id}){title_str} - Created at {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ImageMetadata(models.Model):
    description = models.CharField(max_length=500, blank=True)
    image = models.ImageField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_generated = models.BooleanField(default=False)

    def __str__(self):
        source = "Generated" if self.is_generated else "Uploaded"
        desc = self.description[:50] + '...' if len(self.description) > 50 else self.description
        return f'{source} Image (ID: {self.id}) - "{desc}" - Created: {self.uploaded_at.strftime("%Y-%m-%d %H:%M")}'
