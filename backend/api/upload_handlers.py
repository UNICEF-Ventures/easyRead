"""
Updated image upload handlers for the new embedding system.
Uses the new ImageSet, Image, and Embedding models.
"""

import os
import uuid
import logging
from pathlib import Path
from django.conf import settings
from django.db import transaction
from api.models import ImageSet, Image, Embedding
from api.embedding_adapter import get_embedding_model
# from api.image_utils import get_image_converter
from api.validators import validate_uploaded_image
from api.monitoring import monitor_embedding_operation
from api.model_config import pad_vector_to_standard, STANDARD_VECTOR_DIMENSION

logger = logging.getLogger(__name__)


@monitor_embedding_operation('image_processing')
def handle_image_upload(image_file, description: str = '', set_name: str = 'General', is_generated: bool = False):
    """
    Handle image upload with the new database schema.
    
    Args:
        image_file: Django uploaded file object
        description: Image description
        set_name: Name of the image set
        is_generated: Whether this is a generated image
        
    Returns:
        Dictionary with upload results
    """
    try:
        # Get or create image set
        image_set, created = ImageSet.objects.get_or_create(
            name=set_name,
            defaults={'description': f'Images for {set_name} set'}
        )
        if created:
            logger.info(f"Created new image set: {set_name}")
        
        # Generate safe filename
        safe_filename = image_file.name.replace(" ", "_")
        image_save_path = settings.MEDIA_ROOT / "images" / safe_filename
        
        # Check if file already exists
        if image_save_path.exists():
            # Generate unique name with UUID
            name, ext = os.path.splitext(safe_filename)
            safe_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            image_save_path = settings.MEDIA_ROOT / "images" / safe_filename
        
        # Ensure directory exists
        image_save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the image file
        with open(image_save_path, 'wb+') as destination:
            for chunk in image_file.chunks():
                destination.write(chunk)
        
        logger.info(f"Image saved to: {image_save_path}")
        
        # Validate the uploaded image
        validation_result = validate_uploaded_image(image_save_path, set_name)
        
        if not validation_result['valid']:
            # Log validation errors
            logger.warning(f"Image validation failed for {safe_filename}: {validation_result['errors']}")
            # Continue processing but log the issues
        
        if validation_result.get('warnings'):
            logger.info(f"Image validation warnings for {safe_filename}: {validation_result['warnings']}")
        
        # Skip SVG processing for now to avoid cairo dependency
        processed_image_path = image_save_path
        
        # Get basic image metadata using PIL
        try:
            from PIL import Image as PILImage
            with PILImage.open(image_save_path) as img:
                image_info = {
                    'filename': safe_filename,
                    'file_format': img.format,
                    'width': img.width,
                    'height': img.height,
                    'file_size': image_save_path.stat().st_size,
                    'path': str(image_save_path)
                }
        except Exception as e:
            logger.warning(f"Failed to get image info: {image_save_path}, error: {e}")
            image_info = {
                'filename': safe_filename,
                'file_format': 'PNG' if safe_filename.lower().endswith('.png') else 'JPEG',
                'file_size': None,
                'width': None,
                'height': None
            }
        
        # Create Image record
        with transaction.atomic():
            image_obj, created = Image.objects.get_or_create(
                set=image_set,
                filename=safe_filename,
                defaults={
                    'original_path': str(image_save_path),
                    'processed_path': str(processed_image_path),
                    'description': description,
                    'file_format': image_info.get('file_format', 'PNG'),
                    'file_size': image_info.get('file_size'),
                    'width': image_info.get('width'),
                    'height': image_info.get('height'),
                }
            )
            
            if not created:
                logger.info(f"Image already exists, updating: {safe_filename}")
                # Update existing image
                image_obj.description = description
                image_obj.processed_path = str(processed_image_path)
                image_obj.file_format = image_info.get('file_format', 'PNG')
                image_obj.file_size = image_info.get('file_size')
                image_obj.width = image_info.get('width')
                image_obj.height = image_info.get('height')
                image_obj.save()
            
            # Generate embeddings
            embedding_model = get_embedding_model()
            embeddings_created = 0
            
            # Get model metadata for consistent storage
            model_metadata = embedding_model.provider.get_model_metadata()
            
            # Create image embedding
            try:
                image_embedding = embedding_model.encode_single_image(processed_image_path)
                if image_embedding is not None:
                    # Validate embedding before storing
                    from api.validators import EmbeddingValidator
                    validation = EmbeddingValidator.validate_embedding_vector(image_embedding, model_metadata['model_name'])
                    
                    if validation['valid']:
                        # Pad vector to standard dimension for multi-model compatibility
                        padded_image_embedding = pad_vector_to_standard(image_embedding)
                        
                        embedding_obj, created = Embedding.objects.get_or_create(
                            image=image_obj,
                            embedding_type='image',
                            provider_name=model_metadata['provider_name'],
                            model_name=model_metadata['model_name'],
                            defaults={
                                'vector': padded_image_embedding.tolist(),
                                'embedding_dimension': len(image_embedding)  # Store original dimension
                            }
                        )
                        if created:
                            embeddings_created += 1
                            logger.info(f"Created image embedding for {safe_filename}")
                        else:
                            # Update existing embedding with padded vector
                            padded_image_embedding = pad_vector_to_standard(image_embedding)
                            embedding_obj.vector = padded_image_embedding.tolist()
                            embedding_obj.embedding_dimension = len(image_embedding)  # Update original dimension
                            embedding_obj.save()
                            logger.info(f"Updated image embedding for {safe_filename}")
                    else:
                        logger.error(f"Image embedding validation failed for {safe_filename}: {validation['errors']}")
                else:
                    logger.warning(f"Failed to generate image embedding for {safe_filename}")
            except Exception as e:
                logger.error(f"Error generating image embedding for {safe_filename}: {e}")
            
            # Create text embedding if description exists
            if description:
                try:
                    text_embedding = embedding_model.encode_single_text(description)
                    if text_embedding is not None:
                        # Validate text embedding
                        validation = EmbeddingValidator.validate_embedding_vector(text_embedding, model_metadata['model_name'])
                        
                        if validation['valid']:
                            # Pad vector to standard dimension for multi-model compatibility
                            padded_text_embedding = pad_vector_to_standard(text_embedding)
                            
                            embedding_obj, created = Embedding.objects.get_or_create(
                                image=image_obj,
                                embedding_type='text',
                                provider_name=model_metadata['provider_name'],
                                model_name=model_metadata['model_name'],
                                defaults={
                                    'vector': padded_text_embedding.tolist(),
                                    'embedding_dimension': len(text_embedding)  # Store original dimension
                                }
                            )
                            if created:
                                embeddings_created += 1
                                logger.info(f"Created text embedding for {safe_filename}")
                            else:
                                # Update existing embedding with padded vector
                                padded_text_embedding = pad_vector_to_standard(text_embedding)
                                embedding_obj.vector = padded_text_embedding.tolist()
                                embedding_obj.embedding_dimension = len(text_embedding)  # Update original dimension
                                embedding_obj.save()
                                logger.info(f"Updated text embedding for {safe_filename}")
                        else:
                            logger.error(f"Text embedding validation failed for {safe_filename}: {validation['errors']}")
                    else:
                        logger.warning(f"Failed to generate text embedding for {safe_filename}")
                except Exception as e:
                    logger.error(f"Error generating text embedding for {safe_filename}: {e}")
        
        # Build response
        relative_path = os.path.relpath(processed_image_path, settings.MEDIA_ROOT)
        return {
            "success": True,
            "message": "Image uploaded successfully",
            "image_id": image_obj.id,
            "image_path": str(relative_path),
            "filename": safe_filename,
            "set_name": set_name,
            "description": description,
            "embeddings_created": embeddings_created,
            "file_format": image_info.get('file_format', 'PNG'),
            "file_size": image_info.get('file_size'),
            "width": image_info.get('width'),
            "height": image_info.get('height')
        }
        
    except Exception as e:
        logger.error(f"Error handling image upload: {e}")
        return {
            "success": False,
            "error": str(e),
            "filename": getattr(image_file, 'name', 'unknown')
        }


def handle_batch_image_upload(image_files, description: str = '', set_name: str = 'General'):
    """
    Handle batch image upload with the new database schema.
    
    Args:
        image_files: List of Django uploaded file objects
        description: Shared description for all images
        set_name: Name of the image set
        
    Returns:
        Dictionary with batch upload results
    """
    results = []
    successful_uploads = 0
    
    # Validate file types
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp', '.svg']
    
    for image_file in image_files:
        # Basic file type check
        file_ext = os.path.splitext(image_file.name)[1].lower()
        if file_ext not in allowed_extensions:
            results.append({
                "success": False,
                "filename": image_file.name,
                "error": f"Invalid file type '{file_ext}'. Allowed types: {allowed_extensions}"
            })
            continue
        
        # Handle individual upload
        result = handle_image_upload(image_file, description, set_name)
        results.append(result)
        
        if result.get("success"):
            successful_uploads += 1
    
    return {
        "message": f"Processed {len(results)} images: {successful_uploads} succeeded, {len(results) - successful_uploads} failed",
        "results": results,
        "successful_uploads": successful_uploads,
        "total_uploads": len(results),
        "description": description,
        "set_name": set_name
    }


def get_image_list_formatted(request):
    """
    Get formatted list of all images for API response.
    
    Args:
        request: Django request object for building URLs
        
    Returns:
        Dictionary with formatted image lists
    """
    try:
        # Get all images with their sets
        all_images = Image.objects.select_related('set').order_by('-created_at')
        
        # Group by set
        images_by_set = {}
        for image in all_images:
            set_name = image.set.name
            if set_name not in images_by_set:
                images_by_set[set_name] = []
            
            # Build image URL
            try:
                if image.processed_path:
                    image_path = Path(image.processed_path)
                else:
                    image_path = Path(image.original_path)
                
                if image_path.is_absolute():
                    try:
                        relative_path = image_path.relative_to(settings.MEDIA_ROOT)
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + str(relative_path))
                    except ValueError:
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + 'images/' + image_path.name)
                else:
                    image_url = request.build_absolute_uri(settings.MEDIA_URL + str(image_path))
                
                images_by_set[set_name].append({
                    "id": image.id,
                    "filename": image.filename,
                    "image_url": image_url,
                    "description": image.description,
                    "file_format": image.file_format,
                    "file_size": image.file_size,
                    "width": image.width,
                    "height": image.height,
                    "created_at": image.created_at.isoformat() if image.created_at else None
                })
                
            except Exception as e:
                logger.error(f"Error formatting image {image.id}: {e}")
                continue
        
        return {
            "images_by_set": images_by_set,
            "total_images": all_images.count(),
            "total_sets": len(images_by_set)
        }
        
    except Exception as e:
        logger.error(f"Error getting image list: {e}")
        return {
            "images_by_set": {},
            "total_images": 0,
            "total_sets": 0,
            "error": str(e)
        }