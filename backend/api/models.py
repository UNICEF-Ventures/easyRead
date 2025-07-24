from django.db import models
from django.utils import timezone
import uuid
from pgvector.django import VectorField

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
    # Vector field for pgvector - efficient similarity search
    vector = VectorField(dimensions=1024)  # 1024 dimensions for Cohere multilingual embeddings
    
    # Enhanced model tracking fields
    provider_name = models.CharField(max_length=100, default='openclip')  # e.g., 'openclip', 'openai', 'cohere'
    model_name = models.CharField(max_length=100, default='openclip-vit-b-32')  # e.g., 'ViT-B-32', 'text-embedding-3-small'
    embedding_dimension = models.IntegerField(default=1024)  # Store actual dimension for filtering, default to Cohere multilingual size
    
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


# Analytics Models for Session Tracking

class UserSession(models.Model):
    """
    Tracks user sessions for analytics purposes.
    Since there's no user authentication, sessions are identified by IP + user agent.
    """
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    # Analytics summary fields
    pdf_uploaded = models.BooleanField(default=False)
    pdf_size_bytes = models.BigIntegerField(null=True, blank=True)
    input_content_size = models.IntegerField(null=True, blank=True)  # Characters after PDF conversion or pasted content
    sentences_generated = models.IntegerField(default=0)
    exported_result = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['ip_address', 'started_at']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"Session {self.session_id} - {self.ip_address} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"


class SessionEvent(models.Model):
    """
    Tracks individual events within a user session.
    """
    EVENT_TYPES = [
        ('pdf_upload', 'PDF Upload'),
        ('content_input', 'Content Input'),
        ('page_process', 'Page Processing'),
        ('content_validate', 'Content Validation'),
        ('sentence_revise', 'Sentence Revision'),
        ('image_search', 'Image Search'),
        ('image_select', 'Image Selection'),
        ('image_change', 'Image Change'),
        ('content_save', 'Content Save'),
        ('content_export', 'Content Export'),
        ('image_upload', 'Image Upload'),
        ('image_generate', 'Image Generation'),
    ]
    
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Flexible data field for event-specific information
    event_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session', 'event_type']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.session.session_id} - {self.event_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class ImageSetSelection(models.Model):
    """
    Tracks which image sets were selected during a session.
    """
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='image_set_selections')
    image_set = models.ForeignKey(ImageSet, on_delete=models.CASCADE)
    selected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['session', 'image_set']
        ordering = ['selected_at']
    
    def __str__(self):
        return f"{self.session.session_id} - {self.image_set.name}"


class ImageSelectionChange(models.Model):
    """
    Tracks changes made to image selections, including ranking positions.
    """
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='image_changes')
    sentence_index = models.IntegerField()  # Which sentence this change is for
    old_image = models.ForeignKey(Image, on_delete=models.SET_NULL, null=True, blank=True, related_name='old_selections')
    new_image = models.ForeignKey(Image, on_delete=models.SET_NULL, null=True, blank=True, related_name='new_selections')
    old_ranking = models.IntegerField(null=True, blank=True)  # Previous ranking position
    new_ranking = models.IntegerField(null=True, blank=True)  # New ranking position
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['session', 'sentence_index']),
            models.Index(fields=['changed_at']),
        ]
    
    def __str__(self):
        return f"{self.session.session_id} - Sentence {self.sentence_index} - {self.changed_at.strftime('%Y-%m-%d %H:%M:%S')}"
