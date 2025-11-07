"""
URL configuration for the API endpoints.
Updated to include new endpoints for the refactored embedding system.
"""

from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    # Document processing endpoints
    path('pdf-to-markdown/', views.pdf_to_markdown, name='pdf_to_markdown'),
    path('process-page/', views.process_page, name='process_page'),
    path('validate-completeness/', views.validate_completeness, name='validate_completeness'),
    path('revise-sentences/', views.revise_sentences, name='revise_sentences'),
    
    # Image upload and management endpoints
    path('upload-image/', views.upload_image, name='upload_image'),
    path('batch-upload-images/', views.batch_upload_images, name='batch_upload_images'),
    path('optimized-batch-upload/', views.optimized_batch_upload, name='optimized_batch_upload'),
    path('upload-folder/', views.upload_folder, name='upload_folder'),
    path('upload-progress/<str:session_id>/', views.get_upload_progress, name='get_upload_progress'),
    path('list-images/', views.list_images, name='list_images'),
    
    # Image similarity search endpoints
    path('find-similar-images/', views.find_similar_images, name='find_similar_images'),
    path('find-similar-images-batch/', views.find_similar_images_batch, name='find_similar_images_batch'),
    
    # Content management endpoints
    path('save-processed-content/', views.save_processed_content, name='save_processed_content'),
    path('list-saved-content/', views.list_saved_content, name='list_saved_content'),
    path('saved-content/<int:content_id>/', views.get_saved_content_detail, name='get_saved_content_detail'),
    path('saved-content/by-token/<uuid:public_id>/', views.get_saved_content_detail_by_token, name='get_saved_content_detail_by_token'),
    path('update-saved-content-image/<int:content_id>/', views.update_saved_content_image, name='update_saved_content_image'),
    path('update-saved-content-image/by-token/<uuid:public_id>/', views.update_saved_content_image_by_token, name='update_saved_content_image_by_token'),
    path('bulk-update-saved-content-images/<int:content_id>/', views.bulk_update_saved_content_images, name='bulk_update_saved_content_images'),
    path('update-saved-content/<int:content_id>/', views.update_saved_content_full, name='update_saved_content_full'),
    
    # New endpoints for the refactored system
    path('image-sets/', views.get_image_sets, name='get_image_sets'),
    path('image-sets/<str:set_name>/images/', views.get_images_in_set, name='get_images_in_set'),
    
    # Export endpoints
    path('export/docx/', views.export_current_content_docx, name='export_current_content_docx'),
    path('export/docx/<int:content_id>/', views.export_content_docx, name='export_saved_content_docx'),
    
    # Health monitoring endpoint
    path('health/', views.health_check, name='health_check'),
    
    # Admin authentication endpoints
    path('admin/login/', admin_views.admin_login_view, name='admin_login'),
    path('admin/dashboard/', admin_views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/logout/', admin_views.admin_logout_view, name='admin_logout'),
    path('admin/check-auth/', admin_views.check_auth_status, name='check_auth_status'),
    path('admin/api/login/', admin_views.admin_api_login, name='admin_api_login'),
    path('admin/api/logout/', admin_views.admin_api_logout, name='admin_api_logout'),
    path('admin/api/analytics/', admin_views.analytics_api, name='admin_analytics_api'),
]