"""
Optimized image upload handlers for large batch uploads (1000+ images).
Implements chunked processing, bulk database operations, and memory cleanup.
"""

import os
import gc
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from django.conf import settings
from django.db import transaction, connection
from api.models import ImageSet, Image, Embedding
from api.embedding_adapter import get_embedding_model
from api.validators import validate_uploaded_image, ImageValidator, ContentValidator, EmbeddingValidator
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

class BatchUploadProgress:
    """Class to track and report batch upload progress"""
    
    def __init__(self, session_id: str, total_images: int):
        self.session_id = session_id
        self.total_images = total_images
        self.processed = 0
        self.successful = 0
        self.failed = 0
        self.current_batch = 0
        self.status = "starting"
        
    def update_progress(self, processed: int, successful: int, failed: int, batch: int, status: str = "processing"):
        """Update progress counters"""
        self.processed = processed
        self.successful = successful
        self.failed = failed
        self.current_batch = batch
        self.status = status
        
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress as dictionary"""
        return {
            "session_id": self.session_id,
            "total_images": self.total_images,
            "processed": self.processed,
            "successful": self.successful,
            "failed": self.failed,
            "current_batch": self.current_batch,
            "status": self.status,
            "percentage": round((self.processed / self.total_images * 100), 1) if self.total_images > 0 else 0
        }

# Global progress tracker
_progress_tracker: Dict[str, BatchUploadProgress] = {}

def get_upload_progress(session_id: str) -> Optional[Dict[str, Any]]:
    """Get progress for a specific upload session"""
    global _progress_tracker
    if session_id in _progress_tracker:
        return _progress_tracker[session_id].get_progress()
    return None

def cleanup_progress_tracker(session_id: str):
    """Clean up progress tracker for completed upload"""
    global _progress_tracker
    if session_id in _progress_tracker:
        del _progress_tracker[session_id]

@monitor_embedding_operation('optimized_batch_upload')
def handle_optimized_batch_upload(
    image_files: List,
    description: str = '',
    set_name: str = 'General',
    batch_size: int = 50,
    request=None,
    session_id: str = None
) -> Dict[str, Any]:
    """
    Handle optimized batch image upload with chunked processing, bulk operations, and memory cleanup.
    
    Args:
        image_files: List of Django uploaded file objects
        description: Shared description for all images
        set_name: Name of the image set
        batch_size: Number of images to process per batch (default: 50)
        request: Django request object for validation
        session_id: Unique session ID for progress tracking
        
    Returns:
        Dictionary with batch upload results
    """
    global _progress_tracker
    
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
    
    # Initialize progress tracker
    progress = BatchUploadProgress(session_id, len(image_files))
    _progress_tracker[session_id] = progress
    
    total_images = len(image_files)
    logger.info(f"Starting optimized batch upload: {total_images} images in batches of {batch_size}")
    
    try:
        # Validate set name first
        set_validation = ContentValidator.validate_image_set_name(set_name)
        if not set_validation['valid']:
            progress.update_progress(0, 0, total_images, 0, "failed")
            return {
                "success": False,
                "errors": set_validation['errors'],
                "session_id": session_id,
                "message": f"Invalid set name: {set_name}"
            }
        
        # Get or create image set (outside transaction for efficiency)
        image_set, created = ImageSet.objects.get_or_create(
            name=set_name,
            defaults={'description': f'Images for {set_name} set'}
        )
        if created:
            logger.info(f"Created new image set: {set_name}")
        
        # Get embedding model once for the entire batch
        embedding_model = get_embedding_model()
        model_metadata = embedding_model.provider.get_model_metadata()
        
        # Process images in chunks
        all_results = []
        total_successful = 0
        total_failed = 0
        
        # Split images into batches
        for batch_num in range(0, total_images, batch_size):
            batch_files = image_files[batch_num:batch_num + batch_size]
            current_batch_num = (batch_num // batch_size) + 1
            
            logger.info(f"Processing batch {current_batch_num}: {len(batch_files)} images")
            progress.update_progress(batch_num, total_successful, total_failed, current_batch_num, "processing")
            
            # Process batch with bulk operations
            batch_results = _process_image_batch(
                batch_files, image_set, embedding_model, model_metadata,
                description, batch_num, request
            )
            
            all_results.extend(batch_results['results'])
            total_successful += batch_results['successful']
            total_failed += batch_results['failed']
            
            # Update progress
            processed = batch_num + len(batch_files)
            progress.update_progress(processed, total_successful, total_failed, current_batch_num, "processing")
            
            # Memory cleanup between batches
            _cleanup_batch_memory()
            
            logger.info(f"Batch {current_batch_num} completed: {batch_results['successful']} successful, {batch_results['failed']} failed")
        
        # Final progress update
        progress.update_progress(total_images, total_successful, total_failed, current_batch_num, "completed")
        
        logger.info(f"Optimized batch upload completed: {total_successful}/{total_images} successful")
        
        return {
            "success": True,
            "message": f"Processed {total_images} images: {total_successful} succeeded, {total_failed} failed",
            "results": all_results,
            "successful_uploads": total_successful,
            "total_successful": total_successful,     # Frontend expects this field name
            "total_uploads": total_images,
            "failed_uploads": total_failed,
            "sets_created": 1,                        # Always 1 for batch upload to single set
            "description": description,
            "set_name": set_name,
            "session_id": session_id,
            "batches_processed": current_batch_num,
            "embedding_info": {
                "provider": model_metadata['provider_name'],
                "model": model_metadata['model_name']
            }
        }
        
    except Exception as e:
        logger.error(f"Error during optimized batch upload: {e}")
        progress.update_progress(progress.processed, total_successful, total_failed, progress.current_batch, "failed")
        
        return {
            "success": False,
            "error": f"Batch upload failed: {str(e)}",
            "message": "Large batch upload failed - see logs for details",
            "session_id": session_id,
            "processed_before_error": progress.processed,
            "successful_before_error": total_successful
        }

def _process_image_batch(
    batch_files: List,
    image_set: ImageSet,
    embedding_model,
    model_metadata: Dict[str, str],
    description: str,
    batch_offset: int,
    request
) -> Dict[str, Any]:
    """
    Process a single batch of images with bulk database operations.
    """
    batch_results = []
    successful_count = 0
    failed_count = 0
    
    # Lists for bulk operations
    images_to_create = []
    embeddings_to_create = []
    processed_files = []
    
    # Phase 1: File processing and validation
    for i, image_file in enumerate(batch_files):
        try:
            # Validate file before processing
            if request:
                validation = validate_upload_request(request, image_file, 'image')
                if not validation['valid']:
                    batch_results.append({
                        "success": False,
                        "filename": image_file.name,
                        "errors": validation['errors']
                    })
                    failed_count += 1
                    continue
            
            # Process file (save and validate)
            file_result = _process_single_file(image_file, image_set, description)
            if not file_result['success']:
                batch_results.append(file_result)
                failed_count += 1
                continue
                
            processed_files.append((i, image_file, file_result))
            
        except Exception as e:
            logger.error(f"Error processing file {image_file.name}: {e}")
            batch_results.append({
                "success": False,
                "filename": image_file.name,
                "error": str(e)
            })
            failed_count += 1
    
    # Phase 2: Bulk embedding generation
    if processed_files:
        embedding_results = _generate_batch_embeddings(processed_files, embedding_model, model_metadata)
        
        # Phase 3: Prepare bulk database operations
        for (i, image_file, file_result), embedding_result in zip(processed_files, embedding_results):
            if embedding_result['success']:
                # Generate individual description from filename if shared description is empty
                if description and description.strip():
                    image_description = description
                else:
                    # Extract semantic label from filename: only the part before the first underscore/number
                    filename_without_ext = os.path.splitext(file_result['filename'])[0]
                    # Extract the semantic word (same logic as regular upload handler)
                    image_description = filename_without_ext.split('_')[0]
                
                # Prepare Image object for bulk creation
                image_obj = Image(
                    set=image_set,
                    filename=file_result['filename'],
                    original_path=file_result['image_path'],
                    processed_path=file_result['image_path'],
                    description=image_description,
                    file_format=file_result.get('file_format', 'PNG'),
                    file_size=file_result.get('file_size'),
                    width=file_result.get('width'),
                    height=file_result.get('height')
                )
                images_to_create.append((image_obj, embedding_result['embedding'], embedding_result['dimension']))
                
                batch_results.append({
                    "success": True,
                    "filename": file_result['filename'],
                    "message": "Image processed successfully"
                })
                
            else:
                # Clean up file if embedding failed
                try:
                    if Path(file_result['image_path']).exists():
                        Path(file_result['image_path']).unlink()
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file {file_result['filename']}: {cleanup_error}")
                
                batch_results.append({
                    "success": False,
                    "filename": file_result['filename'],
                    "error": embedding_result.get('error', 'Embedding generation failed')
                })
                failed_count += 1
    
    # Phase 4: Bulk database operations
    if images_to_create:
        successful_db, created_images = _bulk_create_images_and_embeddings(images_to_create, model_metadata)
        successful_count = successful_db
        failed_count += len(images_to_create) - successful_db
        
        # Update successful results with image IDs
        successful_results = [r for r in batch_results if r.get('success')]
        for i, result in enumerate(successful_results):
            if i < len(created_images):
                result['image_id'] = created_images[i].id
    
    return {
        "results": batch_results,
        "successful": successful_count,
        "failed": failed_count
    }

def _process_single_file(image_file, image_set: ImageSet, description: str) -> Dict[str, Any]:
    """Process a single file (save and validate)"""
    try:
        # Sanitize filename
        safe_filename = FileSecurityValidator.sanitize_filename(image_file.name)
        
        # Get safe upload path
        image_save_path = get_safe_upload_path(safe_filename, 'images')
        
        # Save file atomically
        save_result = AtomicFileHandler.save_file_atomically(
            image_file, image_save_path, validate=True
        )
        
        if not save_result['success']:
            return {
                "success": False,
                "errors": save_result['errors'],
                "filename": safe_filename
            }
        
        image_save_path = save_result['path']
        safe_filename = image_save_path.name
        
        # Get image metadata
        image_info = _get_image_metadata(image_save_path, safe_filename)
        
        return {
            "success": True,
            "filename": safe_filename,
            "image_path": str(image_save_path),
            "file_format": image_info.get('file_format', 'PNG'),
            "file_size": image_info.get('file_size'),
            "width": image_info.get('width'),
            "height": image_info.get('height')
        }
        
    except Exception as e:
        logger.error(f"Error processing file {image_file.name}: {e}")
        return {
            "success": False,
            "filename": getattr(image_file, 'name', 'unknown'),
            "error": str(e)
        }

def _get_image_metadata(image_path: Path, filename: str) -> Dict[str, Any]:
    """Get image metadata using PIL"""
    try:
        from PIL import Image as PILImage
        with PILImage.open(image_path) as img:
            return {
                'filename': filename,
                'file_format': img.format,
                'width': img.width,
                'height': img.height,
                'file_size': image_path.stat().st_size
            }
    except Exception as e:
        logger.warning(f"Failed to get image info: {image_path}, error: {e}")
        return {
            'filename': filename,
            'file_format': 'PNG' if filename.lower().endswith('.png') else 'JPEG',
            'file_size': None,
            'width': None,
            'height': None
        }

def _generate_batch_embeddings(processed_files: List[Tuple], embedding_model, model_metadata: Dict[str, str]) -> List[Dict[str, Any]]:
    """Generate embeddings for a batch of files"""
    results = []
    texts_for_embedding = []
    
    # Prepare texts for batch embedding
    for i, image_file, file_result in processed_files:
        # Generate embedding text
        if file_result.get('description'):
            embedding_text = file_result['description']
        else:
            # Extract label from filename
            filename_without_ext = os.path.splitext(file_result['filename'])[0]
            embedding_text = filename_without_ext.split('_')[0]
        
        texts_for_embedding.append(embedding_text)
    
    try:
        # Batch embedding generation
        embeddings = embedding_model.encode_texts(texts_for_embedding, batch_size=len(texts_for_embedding))
        
        # Validate and pad embeddings
        for i, (embedding_text, embedding) in enumerate(zip(texts_for_embedding, embeddings)):
            try:
                # Validate embedding
                validation = EmbeddingValidator.validate_embedding_vector(embedding, model_metadata['model_name'])
                if not validation['valid']:
                    raise ValueError(f"Embedding validation failed: {validation['errors']}")
                
                # Pad vector to standard dimension
                padded_embedding = pad_vector_to_standard(embedding)
                
                results.append({
                    "success": True,
                    "embedding": padded_embedding,
                    "dimension": len(embedding),
                    "text": embedding_text
                })
                
            except Exception as e:
                logger.error(f"Error validating embedding for text '{embedding_text}': {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "text": embedding_text
                })
    
    except Exception as e:
        logger.error(f"Error in batch embedding generation: {e}")
        # Return failed results for all files
        for embedding_text in texts_for_embedding:
            results.append({
                "success": False,
                "error": str(e),
                "text": embedding_text
            })
    
    return results

def _bulk_create_images_and_embeddings(images_data: List[Tuple], model_metadata: Dict[str, str]) -> Tuple[int, List]:
    """Bulk create Image and Embedding records in database"""
    successful_count = 0
    created_images = []
    
    try:
        with transaction.atomic():
            # Prepare Image objects for bulk creation
            image_objects = [img_obj for img_obj, _, _ in images_data]
            
            # Bulk create images
            created_images = Image.objects.bulk_create(image_objects)
            logger.info(f"Bulk created {len(created_images)} Image records")
            
            # Prepare Embedding objects for bulk creation
            embedding_objects = []
            for i, (_, embedding, dimension) in enumerate(images_data):
                if i < len(created_images):
                    embedding_obj = Embedding(
                        image=created_images[i],
                        embedding_type='text',
                        provider_name=model_metadata['provider_name'],
                        model_name=model_metadata['model_name'],
                        vector=embedding.tolist(),
                        embedding_dimension=dimension
                    )
                    embedding_objects.append(embedding_obj)
            
            # Bulk create embeddings
            created_embeddings = Embedding.objects.bulk_create(embedding_objects)
            logger.info(f"Bulk created {len(created_embeddings)} Embedding records")
            
            successful_count = len(created_images)
            
    except Exception as e:
        logger.error(f"Error in bulk database operations: {e}")
        created_images = []  # Reset on failure
        # Clean up files on database failure
        for img_obj, _, _ in images_data:
            try:
                if Path(img_obj.original_path).exists():
                    Path(img_obj.original_path).unlink()
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up file {img_obj.filename}: {cleanup_error}")
    
    return successful_count, created_images

def _cleanup_batch_memory():
    """Clean up memory between batches"""
    try:
        # Force garbage collection
        gc.collect()
        
        # Log memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            logger.debug(f"Memory after batch cleanup: {memory_mb:.1f} MB")
        except ImportError:
            logger.debug("Memory monitoring not available (psutil not installed)")
            
        # Close any idle database connections
        connection.close()
        
    except Exception as e:
        logger.error(f"Error during batch memory cleanup: {e}")