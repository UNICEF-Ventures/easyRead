from django.urls import path
from . import views

urlpatterns = [
    path('markdown-extraction/', views.pdf_to_markdown, name='markdown_extraction'),
    path('easy-read-generation/', views.process_page, name='easy_read_generation'),
    path('content-validation/', views.validate_completeness, name='content_validation'),
    path('sentence-revision/', views.revise_sentences, name='sentence_revision'),
    path('image-upload/', views.upload_image, name='image_upload'),
    path('batch-upload-images/', views.batch_upload_images, name='batch_upload_images'),
    path('list-images/', views.list_images, name='list_images'),
    path('find-similar-images/', views.find_similar_images, name='find_similar_images'),
    path('save-content/', views.save_processed_content, name='save_content'),
    path('saved-content/', views.list_saved_content, name='list_saved_content'),
    path('saved-content/<int:content_id>/', views.get_saved_content_detail, name='get_saved_content_detail'),
    path('saved-content/<int:content_id>/update-image/', views.update_saved_content_image, name='update_saved_content_image'),
    path('generate-image/', views.generate_image_view, name='generate_image'),
] 