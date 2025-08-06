"""
Updated image upload handlers for the new embedding system.
Uses the new ImageSet, Image, and Embedding models.
Enhanced with comprehensive security validations.
"""

import os
import uuid
import logging
from pathlib import Path
from django.conf import settings
from django.db import transaction
from api.models import ImageSet, Image, Embedding
from api.embedding_adapter import get_embedding_model
from api.validators import validate_uploaded_image, ImageValidator, ContentValidator
from api.monitoring import monitor_embedding_operation
from api.model_config import pad_vector_to_standard, STANDARD_VECTOR_DIMENSION
from api.security_utils import (
    FileSecurityValidator,
    AtomicFileHandler,
    SecurityLogger,
    get_safe_upload_path,
    validate_upload_request
)

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
        # Validate set name first
        set_validation = ContentValidator.validate_image_set_name(set_name)
        if not set_validation['valid']:
            return {
                "success": False,
                "errors": set_validation['errors'],
                "filename": getattr(image_file, 'name', 'unknown')
            }
        
        # Get or create image set
        image_set, created = ImageSet.objects.get_or_create(
            name=set_name,
            defaults={'description': f'Images for {set_name} set'}
        )
        if created:
            logger.info(f"Created new image set: {set_name}")
        
        # Sanitize filename to prevent path traversal
        safe_filename = FileSecurityValidator.sanitize_filename(image_file.name)
        
        # Get safe upload path with date-based organization
        image_save_path = get_safe_upload_path(safe_filename, 'images')
        
        # Save file atomically to prevent race conditions
        save_result = AtomicFileHandler.save_file_atomically(
            image_file,
            image_save_path,
            validate=True
        )
        
        if not save_result['success']:
            return {
                "success": False,
                "errors": save_result['errors'],
                "filename": safe_filename
            }
        
        # Update path if it was changed (due to existing file)
        image_save_path = save_result['path']
        safe_filename = image_save_path.name
        
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
        
        # FIRST: Generate embeddings before creating database records
        # This ensures we only store images that have successful embeddings
        
        embedding_model = get_embedding_model()
        model_metadata = embedding_model.provider.get_model_metadata()
        
        # Import EmbeddingValidator at the beginning
        from api.validators import EmbeddingValidator
        
        # Ensure we have a description for embedding generation
        # Use only the first part of filename before underscore as fallback
        if description:
            embedding_text = description
        else:
            # Extract label from filename: only the part before the first underscore
            filename_without_ext = os.path.splitext(safe_filename)[0]
            embedding_text = filename_without_ext.split('_')[0]
        
        # Generate and validate embedding BEFORE creating database records
        text_embedding = None
        padded_text_embedding = None
        
        try:
            if not embedding_text:
                raise ValueError("No text available for embedding generation")
                
            text_embedding = embedding_model.encode_single_text(embedding_text)
            if text_embedding is None:
                raise ValueError("Embedding model returned None")
                
            # Validate text embedding
            validation = EmbeddingValidator.validate_embedding_vector(text_embedding, model_metadata['model_name'])
            if not validation['valid']:
                raise ValueError(f"Embedding validation failed: {validation['errors']}")
                
            # Pad vector to standard dimension for multi-model compatibility
            padded_text_embedding = pad_vector_to_standard(text_embedding)
            
            logger.info(f"Successfully generated embedding for {safe_filename}")
            
        except Exception as e:
            # Embedding generation failed - clean up files and return error
            logger.error(f"Failed to generate embedding for {safe_filename}: {e}")
            
            # Clean up the uploaded files
            try:
                if image_save_path.exists():
                    image_save_path.unlink()
                    logger.info(f"Cleaned up original file: {image_save_path}")
                if processed_image_path != image_save_path and processed_image_path.exists():
                    processed_image_path.unlink() 
                    logger.info(f"Cleaned up processed file: {processed_image_path}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up files for {safe_filename}: {cleanup_error}")
            
            return {
                "success": False,
                "error": f"Failed to generate embeddings for image: {str(e)}",
                "filename": safe_filename,
                "message": "Image upload failed - embeddings are required for all images"
            }
        
        # SECOND: Create database records only if embeddings succeeded
        try:
            with transaction.atomic():
                # Create Image record
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
                
                # Create the embedding record
                embedding_obj, embedding_created = Embedding.objects.get_or_create(
                    image=image_obj,
                    embedding_type='text',
                    provider_name=model_metadata['provider_name'],
                    model_name=model_metadata['model_name'],
                    defaults={
                        'vector': padded_text_embedding.tolist(),
                        'embedding_dimension': len(text_embedding)
                    }
                )
                
                if embedding_created:
                    logger.info(f"Created image and embedding records for {safe_filename}")
                else:
                    # Update existing embedding
                    embedding_obj.vector = padded_text_embedding.tolist()
                    embedding_obj.embedding_dimension = len(text_embedding)
                    embedding_obj.save()
                    logger.info(f"Updated image and embedding records for {safe_filename}")
                    
        except Exception as e:
            # Database creation failed - clean up files and return error
            logger.error(f"Failed to create database records for {safe_filename}: {e}")
            
            # Clean up the uploaded files
            try:
                if image_save_path.exists():
                    image_save_path.unlink()
                if processed_image_path != image_save_path and processed_image_path.exists():
                    processed_image_path.unlink()
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up files after database failure for {safe_filename}: {cleanup_error}")
            
            return {
                "success": False,
                "error": f"Failed to create database records: {str(e)}",
                "filename": safe_filename,
                "message": "Image upload failed - database error"
            }
        
        # Build success response - embeddings are guaranteed to exist at this point
        relative_path = os.path.relpath(processed_image_path, settings.MEDIA_ROOT)
        
        return {
            "success": True,
            "message": "Image uploaded successfully with embeddings",
            "image_id": image_obj.id,
            "image_path": str(relative_path),
            "filename": safe_filename,
            "set_name": set_name,
            "description": description,
            "embeddings_created": 1,  # Always 1 since we require embeddings
            "has_embeddings": True,   # Always True since we require embeddings
            "search_ready": True,     # Always True since we require embeddings
            "file_format": image_info.get('file_format', 'PNG'),
            "file_size": image_info.get('file_size'),
            "width": image_info.get('width'),
            "height": image_info.get('height'),
            "embedding_info": {
                "provider": model_metadata['provider_name'],
                "model": model_metadata['model_name'],
                "dimension": len(text_embedding)
            }
        }
        
    except Exception as e:
        logger.error(f"Unexpected error during image upload: {e}")
        
        # Clean up any files that might have been created
        try:
            if 'image_save_path' in locals() and image_save_path.exists():
                image_save_path.unlink()
                logger.info(f"Cleaned up file after unexpected error: {image_save_path}")
            if 'processed_image_path' in locals() and processed_image_path != image_save_path and processed_image_path.exists():
                processed_image_path.unlink()
                logger.info(f"Cleaned up processed file after unexpected error: {processed_image_path}")
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up files after unexpected error: {cleanup_error}")
        
        return {
            "success": False,
            "error": f"Unexpected error during image upload: {str(e)}",
            "filename": getattr(image_file, 'name', 'unknown'),
            "message": "Image upload failed - embeddings are required for all images"
        }


def handle_batch_image_upload(image_files, description: str = '', set_name: str = 'General', request=None):
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
    
    for image_file in image_files:
        # Comprehensive validation for each file
        if request:
            validation = validate_upload_request(request, image_file, 'image')
            if not validation['valid']:
                results.append({
                    "success": False,
                    "filename": image_file.name,
                    "errors": validation['errors'],
                    "warnings": validation.get('warnings', [])
                })
                # Log blocked upload
                SecurityLogger.log_upload_attempt(
                    request, image_file.name, 'blocked',
                    {'reason': validation['errors']}
                )
                continue
        else:
            # Fallback to basic content validation if no request object
            content_check = FileSecurityValidator.validate_file_content(image_file)
            if not content_check['valid']:
                results.append({
                    "success": False,
                    "filename": image_file.name,
                    "errors": content_check['errors']
                })
                continue
        
        # Handle individual upload
        result = handle_image_upload(image_file, description, set_name)
        results.append(result)
        
        if result.get("success"):
            successful_uploads += 1
            if request:
                SecurityLogger.log_upload_attempt(
                    request, image_file.name, 'success',
                    {'set_name': set_name, 'image_id': result.get('image_id')}
                )
        else:
            if request:
                SecurityLogger.log_upload_attempt(
                    request, image_file.name, 'failure',
                    {'errors': result.get('errors', result.get('error'))}
                )
    
    return {
        "message": f"Processed {len(results)} images: {successful_uploads} succeeded, {len(results) - successful_uploads} failed",
        "results": results,
        "successful_uploads": successful_uploads,
        "total_uploads": len(results),
        "description": description,
        "set_name": set_name
    }


def handle_folder_upload(folder_data, request=None):
    """
    Handle folder structure upload with automatic set creation based on folder names.
    
    Args:
        folder_data: Dictionary with folder structure from frontend:
        {
            'folder_name/image1.jpg': file_object,
            'folder_name/image2.png': file_object,
            'folder_name/subfolder/image3.jpg': file_object
        }
        
    Returns:
        Dictionary with folder upload results
    """
    results = {}
    total_uploads = 0
    total_successful = 0
    
    # Group files by their folder structure
    folders_to_files = {}
    for file_path, file_obj in folder_data.items():
        # For folder uploads, we need to preserve the path structure for set names
        # but still sanitize individual components to prevent directory traversal
        path_parts = file_path.split('/')
        safe_parts = []
        for part in path_parts:
            if part and not part.startswith('..') and part not in ['.', '']:
                # Sanitize individual path component but don't use basename
                safe_part = part.replace('\x00', '').replace('\\', '').strip()
                if safe_part:
                    safe_parts.append(safe_part)
        
        safe_path = '/'.join(safe_parts) if safe_parts else file_obj.name
        
        # Extract folder name from path (use first level as set name)
        folder_name = None
        if '/' in safe_path:
            folder_name = safe_path.split('/')[0]
        
        # If no folder detected from path, try to extract from filename patterns
        if not folder_name:
            # Try to detect folder name from file naming patterns
            filename_base = file_obj.name
            if filename_base:
                # Remove extension
                name_without_ext = filename_base.rsplit('.', 1)[0]
                
                # Try common folder/prefix patterns:
                # Pattern 1: "FolderName_filename" or "FolderName-filename"
                if '_' in name_without_ext or '-' in name_without_ext:
                    # Split on underscore or hyphen and take first part
                    delimiter = '_' if '_' in name_without_ext else '-'
                    potential_folder = name_without_ext.split(delimiter)[0].strip()
                    if len(potential_folder) > 1 and potential_folder.isalnum():
                        folder_name = potential_folder
                
                # Pattern 2: If no clear pattern, use filename without number suffix
                if not folder_name:
                    # Remove trailing numbers: "MyImages123" -> "MyImages"
                    import re
                    match = re.match(r'^([a-zA-Z]+)', name_without_ext)
                    if match and len(match.group(1)) > 2:
                        folder_name = match.group(1)
        
        # Final fallback - use a descriptive default based on upload time
        if not folder_name:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            folder_name = f"Uploaded_{timestamp}"
        
        logger.info(f"Extracted folder name: '{folder_name}' from path: '{safe_path}'")
        
        # Sanitize folder name for use as set name
        validation_result = ContentValidator.validate_image_set_name(folder_name)
        
        if not validation_result['valid']:
            logger.warning(f"Folder name '{folder_name}' validation failed: {validation_result['errors']}")
            # Use timestamp fallback instead of Generic 'General'
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            folder_name = f"Invalid_Name_{timestamp}"
            logger.info(f"Using fallback folder name: '{folder_name}'")
        else:
            folder_name = validation_result.get('sanitized', folder_name)  # Use sanitized version if available
            logger.info(f"Using validated folder name: '{folder_name}'")
        
        if folder_name not in folders_to_files:
            folders_to_files[folder_name] = []
        folders_to_files[folder_name].append((safe_path, file_obj))
    
    # Process each folder as a separate set
    for folder_name, files in folders_to_files.items():
        logger.info(f"Processing folder '{folder_name}' with {len(files)} files")
        
        set_results = []
        successful_in_set = 0
        
        for file_path, file_obj in files:
            # Validate file before processing
            if request:
                validation = validate_upload_request(request, file_obj, 'image')
                if not validation['valid']:
                    set_results.append({
                        "success": False,
                        "filename": file_obj.name,
                        "errors": validation['errors']
                    })
                    total_uploads += 1
                    SecurityLogger.log_upload_attempt(
                        request, file_obj.name, 'blocked',
                        {'reason': validation['errors'], 'folder': folder_name}
                    )
                    continue
            
            # Generate description from filename
            filename = file_path.split('/')[-1]  # Get just the filename
            description = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ')
            
            # Upload the image to the folder-named set
            result = handle_image_upload(file_obj, description, folder_name)
            set_results.append(result)
            total_uploads += 1
            
            if result.get("success"):
                successful_in_set += 1
                total_successful += 1
                logger.info(f"✅ File {file_obj.name} uploaded successfully. Total successful: {total_successful}")
                if request:
                    SecurityLogger.log_upload_attempt(
                        request, file_obj.name, 'success',
                        {'folder': folder_name, 'image_id': result.get('image_id')}
                    )
            else:
                logger.error(f"❌ File {file_obj.name} failed to upload: {result.get('errors', result.get('error'))}")
                if request:
                    SecurityLogger.log_upload_attempt(
                        request, file_obj.name, 'failure',
                        {'errors': result.get('errors', result.get('error')), 'folder': folder_name}
                    )
        
        # Store results for this folder/set
        results[folder_name] = {
            "set_name": folder_name,
            "results": set_results,
            "successful_uploads": successful_in_set,
            "total_files": len(files)
        }
    
    logger.info(f"📊 Final folder upload summary: {total_successful}/{total_uploads} successful, {len(folders_to_files)} sets created")
    
    return {
        "message": f"Processed {len(folders_to_files)} folder(s): {total_successful}/{total_uploads} images uploaded successfully",
        "folders": results,
        "total_successful": total_successful,
        "total_uploads": total_uploads,
        "sets_created": len(folders_to_files)
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
        # Get all images with their sets and embeddings
        all_images = Image.objects.select_related('set').prefetch_related('embeddings').order_by('-created_at')
        
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
                
                # Check if image has embeddings
                text_embeddings = image.embeddings.filter(embedding_type='text')
                has_embeddings = text_embeddings.exists()
                
                # Get embedding provider info if available
                embedding_info = None
                if has_embeddings:
                    latest_embedding = text_embeddings.first()
                    embedding_info = {
                        "provider": latest_embedding.provider_name,
                        "model": latest_embedding.model_name,
                        "dimension": latest_embedding.embedding_dimension
                    }
                
                images_by_set[set_name].append({
                    "id": image.id,
                    "filename": image.filename,
                    "image_url": image_url,
                    "description": image.description,
                    "file_format": image.file_format,
                    "file_size": image.file_size,
                    "width": image.width,
                    "height": image.height,
                    "created_at": image.created_at.isoformat() if image.created_at else None,
                    "has_embeddings": has_embeddings,
                    "embedding_info": embedding_info,
                    "search_ready": has_embeddings  # Indicates if image will work in similarity search
                })
                
            except Exception as e:
                logger.error(f"Error formatting image {image.id}: {e}")
                continue
        
        # Calculate embedding statistics
        total_images = all_images.count()
        images_with_embeddings = sum(
            1 for images in images_by_set.values() 
            for image in images 
            if image.get('has_embeddings', False)
        )
        images_without_embeddings = total_images - images_with_embeddings
        
        return {
            "images_by_set": images_by_set,
            "total_images": total_images,
            "total_sets": len(images_by_set),
            "embedding_stats": {
                "total_images": total_images,
                "with_embeddings": images_with_embeddings,
                "without_embeddings": images_without_embeddings,
                "embedding_coverage_percent": round((images_with_embeddings / total_images * 100), 1) if total_images > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting image list: {e}")
        return {
            "images_by_set": {},
            "total_images": 0,
            "total_sets": 0,
            "error": str(e)
        }