"""
URL configuration for the API endpoints.
Updated to include new endpoints for the refactored embedding system.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Document processing endpoints
    path('pdf-to-markdown/', views.pdf_to_markdown, name='pdf_to_markdown'),
    path('process-page/', views.process_page, name='process_page'),
    path('validate-completeness/', views.validate_completeness, name='validate_completeness'),
    path('revise-sentences/', views.revise_sentences, name='revise_sentences'),
    
    # Image upload and management endpoints
    path('upload-image/', views.upload_image, name='upload_image'),
    path('batch-upload-images/', views.batch_upload_images, name='batch_upload_images'),
    path('generate-image/', views.generate_image_view, name='generate_image'),
    path('list-images/', views.list_images, name='list_images'),
    
    # Image similarity search endpoint
    path('find-similar-images/', views.find_similar_images, name='find_similar_images'),
    
    # Content management endpoints
    path('save-processed-content/', views.save_processed_content, name='save_processed_content'),
    path('list-saved-content/', views.list_saved_content, name='list_saved_content'),
    path('saved-content/<int:content_id>/', views.get_saved_content_detail, name='get_saved_content_detail'),
    path('update-saved-content-image/<int:content_id>/', views.update_saved_content_image, name='update_saved_content_image'),
    
    # New endpoints for the refactored system
    path('image-sets/', views.get_image_sets, name='get_image_sets'),
    path('image-sets/<str:set_name>/images/', views.get_images_in_set, name='get_images_in_set'),
    
    # Health monitoring endpoint
    path('health/', views.health_check, name='health_check'),
]