from django.contrib import admin
from .models import ProcessedContent, ImageSet, Image, Embedding

# Register your models here.

@admin.register(ProcessedContent)
class ProcessedContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'original_markdown')
    readonly_fields = ('created_at',)


# New models for refactored system
@admin.register(ImageSet)
class ImageSetAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'image_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    
    def image_count(self, obj):
        return obj.images.count()
    image_count.short_description = 'Number of Images'

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'set', 'file_format', 'file_size', 'has_embeddings', 'created_at')
    list_filter = ('file_format', 'set', 'created_at')
    search_fields = ('filename', 'description', 'set__name')
    readonly_fields = ('created_at',)
    raw_id_fields = ('set',)
    
    def has_embeddings(self, obj):
        return obj.embeddings.exists()
    has_embeddings.boolean = True
    has_embeddings.short_description = 'Has Embeddings'

@admin.register(Embedding)
class EmbeddingAdmin(admin.ModelAdmin):
    list_display = ('id', 'image', 'embedding_type', 'model_name', 'created_at')
    list_filter = ('embedding_type', 'model_name', 'created_at')
    search_fields = ('image__filename', 'image__set__name')
    readonly_fields = ('created_at', 'vector')
    raw_id_fields = ('image',)
