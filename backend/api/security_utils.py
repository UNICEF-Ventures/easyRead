"""
Security utilities for file upload handling.
Provides secure filename sanitization, file validation, and rate limiting.
"""

import os
import re
import hashlib
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import boto3
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

MEDIA_STORE = os.getenv('MEDIA_STORE', 'server')

class FileSecurityValidator:
    """
    Comprehensive file security validation.
    """
    
    # Maximum file sizes by type
    MAX_FILE_SIZES = {
        'image': 5 * 1024 * 1024,  # 5MB for images
        'document': 10 * 1024 * 1024,  # 10MB for documents
        'default': 5 * 1024 * 1024  # 5MB default
    }
    
    # Magic bytes for file type verification
    FILE_SIGNATURES = {
        'png': {
            'magic': b'\x89PNG\r\n\x1a\n',
            'offset': 0,
            'extensions': ['.png']
        },
        'jpeg': {
            'magic': b'\xff\xd8\xff',
            'offset': 0,
            'extensions': ['.jpg', '.jpeg']
        },
        'gif': {
            'magic': b'GIF87a',
            'magic_alt': b'GIF89a',
            'offset': 0,
            'extensions': ['.gif']
        },
        'webp': {
            'magic': b'RIFF',
            'magic2': b'WEBP',
            'offset': 0,
            'offset2': 8,
            'extensions': ['.webp']
        },
        'svg': {
            'magic_patterns': [b'<svg', b'<?xml'],
            'offset': 0,
            'extensions': ['.svg'],
            'text_file': True
        }
    }
    
    @classmethod
    def sanitize_filename(cls, filename: str, max_length: int = 255) -> str:
        """
        Sanitize filename to prevent path traversal and other attacks.
        
        Args:
            filename: Original filename
            max_length: Maximum allowed length
            
        Returns:
            Sanitized filename
        """
        # Remove any path components
        filename = os.path.basename(filename)
        
        # Remove null bytes
        filename = filename.replace('\x00', '')
        
        # Replace path separators
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Remove dangerous characters for Windows/Unix
        dangerous_chars = '<>:"|?*'
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Remove control characters
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # Prevent directory traversal patterns
        patterns_to_remove = ['..', './', '.\\', '~']
        for pattern in patterns_to_remove:
            filename = filename.replace(pattern, '_')
        
        # Handle hidden files (starting with dot)
        if filename.startswith('.'):
            filename = '_' + filename[1:]
        
        # Remove trailing spaces and dots (Windows issue)
        filename = filename.rstrip(' .')
        
        # Ensure filename has content
        if not filename or filename == '_':
            filename = f'file_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}'
        
        # Limit filename length
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            # Keep extension if possible
            if len(ext) < max_length:
                name = name[:max_length - len(ext)]
                filename = name + ext
            else:
                filename = filename[:max_length]
        
        # Ensure proper extension
        if '.' not in filename:
            filename += '.unknown'
        
        return filename
    
    @classmethod
    def validate_file_content(cls, file_obj, allowed_types: List[str] = None) -> Dict[str, Any]:
        """
        Validate file content using magic bytes.
        
        Args:
            file_obj: File object to validate
            allowed_types: List of allowed file types
            
        Returns:
            Validation result dictionary
        """
        result = {
            'valid': False,
            'detected_type': None,
            'errors': [],
            'warnings': []
        }
        
        if allowed_types is None:
            allowed_types = ['png', 'jpeg', 'gif', 'webp', 'svg']
        
        try:
            # Read file header (first 512 bytes should be enough)
            file_obj.seek(0)
            header = file_obj.read(512)
            file_obj.seek(0)  # Reset position
            
            detected_type = None
            
            # Check each file signature
            for file_type, signature in cls.FILE_SIGNATURES.items():
                if file_type not in allowed_types:
                    continue
                
                # Handle SVG (text-based)
                if signature.get('text_file'):
                    try:
                        file_obj.seek(0)
                        text_header = file_obj.read(1024).decode('utf-8', errors='ignore').lower()
                        file_obj.seek(0)

                        for pattern in signature.get('magic_patterns', []):
                            if pattern.decode('utf-8').lower() in text_header:
                                detected_type = file_type
                                break
                    except Exception as e:
                        logger.debug(f"Could not read file signature for {file_type}: {e}")
                        pass
                
                # Handle WebP (dual magic bytes)
                elif 'magic2' in signature:
                    if (header[signature['offset']:signature['offset'] + len(signature['magic'])] == signature['magic'] and
                        header[signature['offset2']:signature['offset2'] + len(signature['magic2'])] == signature['magic2']):
                        detected_type = file_type
                        break
                
                # Handle GIF (alternative magic bytes)
                elif 'magic_alt' in signature:
                    magic_match = (
                        header[signature['offset']:signature['offset'] + len(signature['magic'])] == signature['magic'] or
                        header[signature['offset']:signature['offset'] + len(signature['magic_alt'])] == signature['magic_alt']
                    )
                    if magic_match:
                        detected_type = file_type
                        break
                
                # Standard magic byte check
                elif 'magic' in signature:
                    if header[signature['offset']:signature['offset'] + len(signature['magic'])] == signature['magic']:
                        detected_type = file_type
                        break
            
            if detected_type:
                result['valid'] = True
                result['detected_type'] = detected_type
                
                # Verify extension matches detected type
                filename = getattr(file_obj, 'name', 'unknown')
                ext = os.path.splitext(filename)[1].lower()
                expected_exts = cls.FILE_SIGNATURES[detected_type]['extensions']
                
                if ext not in expected_exts:
                    result['warnings'].append(
                        f"File extension '{ext}' doesn't match detected type '{detected_type}' "
                        f"(expected one of {expected_exts})"
                    )
            else:
                result['errors'].append(f"File type not recognized or not allowed. Allowed types: {allowed_types}")
            
        except Exception as e:
            result['errors'].append(f"Error validating file content: {str(e)}")
        
        return result
    
    @classmethod
    def check_file_size(cls, file_obj, file_type: str = 'default') -> Dict[str, Any]:
        """
        Check if file size is within acceptable limits.
        
        Args:
            file_obj: File object to check
            file_type: Type of file for size limit lookup
            
        Returns:
            Validation result
        """
        result = {
            'valid': False,
            'size': 0,
            'errors': []
        }
        
        try:
            # Get file size
            if hasattr(file_obj, 'size'):
                file_size = file_obj.size
            else:
                file_obj.seek(0, 2)  # Seek to end
                file_size = file_obj.tell()
                file_obj.seek(0)  # Reset
            
            result['size'] = file_size
            
            # Get max size for file type
            max_size = cls.MAX_FILE_SIZES.get(file_type, cls.MAX_FILE_SIZES['default'])
            
            if file_size > max_size:
                result['errors'].append(
                    f"File size ({file_size:,} bytes) exceeds maximum allowed size ({max_size:,} bytes)"
                )
            elif file_size == 0:
                result['errors'].append("File is empty")
            else:
                result['valid'] = True
            
        except Exception as e:
            result['errors'].append(f"Error checking file size: {str(e)}")
        
        return result


class RateLimiter:
    """
    Rate limiting for upload endpoints.
    """
    
    @staticmethod
    def check_rate_limit(
        identifier: str,
        action: str = 'upload',
        max_requests: int = 10,
        window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Check if an action is rate limited.
        
        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            action: Action being rate limited
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            Rate limit check result
        """
        cache_key = f"rate_limit:{action}:{identifier}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= max_requests:
            return {
                'allowed': False,
                'current_count': current_count,
                'max_requests': max_requests,
                'retry_after': window_seconds,
                'message': f"Rate limit exceeded. Maximum {max_requests} {action}s per {window_seconds} seconds."
            }
        
        # Increment counter
        cache.set(cache_key, current_count + 1, window_seconds)
        
        return {
            'allowed': True,
            'current_count': current_count + 1,
            'max_requests': max_requests,
            'remaining': max_requests - (current_count + 1)
        }

from pathlib import Path

def get_image_mime_type(ext: str) -> str | None:
    """
    Return the MIME type for a given image filename based on its extension.
    Supports popular image formats. Returns None if unknown.
    """
    
    mapping = {
        # Raster formats
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "jpe":  "image/jpeg",
        "png":  "image/png",
        "gif":  "image/gif",
        "bmp":  "image/bmp",
        "dib":  "image/bmp",
        "webp": "image/webp",
        "tif":  "image/tiff",
        "tiff": "image/tiff",
        "ico":  "image/x-icon",
        "cur":  "image/x-icon",

        # Vector / other common image-ish formats
        "svg":  "image/svg+xml",
        "svgz": "image/svg+xml",

        # Modern / mobile photo formats
        "avif": "image/avif",
        "heic": "image/heic",
        "heif": "image/heif",

        # Some camera RAW formats (not strictly "web images" but often used)
        "cr2":  "image/x-canon-cr2",
        "cr3":  "image/x-canon-cr3",
        "nef":  "image/x-nikon-nef",
        "arw":  "image/x-sony-arw",
        "raf":  "image/x-fuji-raf",
        "dng":  "image/x-adobe-dng",
    }

    return mapping.get(ext)


class AtomicFileHandler:
    """
    Handle file operations atomically to prevent race conditions.
    """

    @staticmethod
    def save_file_to_server(file_obj, safe_filename:str, foldername:str, validate: bool = True) -> Dict[str, Any]:
        """
        Save file atomically using temporary file and rename.
        
        Args:
            file_obj: File object to save
            target_path: Target path for the file
            validate: Whether to validate file before saving
            
        Returns:
            Operation result
        """
        # Get safe upload path
        target_path = get_safe_upload_path(safe_filename, 'images', foldername)
        
        result = {
            'success': False,
            'path': None,
            'errors': []
        }
        
        temp_file = None
        try:
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create temporary file in the same directory (for atomic rename)
            with tempfile.NamedTemporaryFile(
                mode='wb',
                dir=target_path.parent,
                delete=False,
                prefix='.tmp_',
                suffix=target_path.suffix
            ) as temp_file:
                # Write file content in chunks
                for chunk in file_obj.chunks() if hasattr(file_obj, 'chunks') else [file_obj.read()]:
                    temp_file.write(chunk)
                temp_path = Path(temp_file.name)
            
            # Validate if requested
            if validate:
                from api.validators import ImageValidator
                validation = ImageValidator.validate_file_format(temp_path)
                if not validation['valid']:
                    result['errors'].extend(validation['errors'])
                    # Clean up temp file
                    temp_path.unlink(missing_ok=True)
                    return result
            
            # Check if target already exists
            if target_path.exists():
                # Generate unique name
                counter = 1
                base_path = target_path.parent / target_path.stem
                while target_path.exists():
                    target_path = base_path.parent / f"{base_path.name}_{counter}{target_path.suffix}"
                    counter += 1
            
            # Atomic rename
            temp_path.replace(target_path)
            
            result['success'] = True
            result['path'] = target_path
            result['path'] = target_path.name

            
        except Exception as e:
            result['errors'].append(f"Failed to save file atomically: {str(e)}")
            # Clean up temp file if it exists
            if temp_file and Path(temp_file.name).exists():
                try:
                    Path(temp_file.name).unlink()
                except Exception as e:
                    logger.debug(f"Failed to clean up temporary file: {e}")
                    pass
        
        return result
    
    @staticmethod
    def save_file_to_s3(file_obj, safe_filename:str, foldername:str, validate: bool = True) -> Dict[str, Any]:
        """
        Save file atomically using temporary file and rename.
        
        Args:
            file_obj: File object to save
            target_path: Target path for the file
            validate: Whether to validate file before saving
            
        Returns:
            Operation result
        """
        result = {
            'success': False,
            'path': None,
            'errors': []
        }
        
        try:
            region_name = os.getenv("S3_BUCKET_REGION")
            bucket = os.getenv("S3_BUCKET_NAME")

            ext = safe_filename.lower().split(".")[1]  # e.g. "jpg"
            filename_only = safe_filename.lower().split(".")[0]
            contentType = get_image_mime_type(ext)
            counter = 0
            key_escaped = quote_plus(safe_filename)
            full_name = foldername + "/" + key_escaped

            client = boto3.client(service_name='s3', region_name="eu-north-1")
                        
            # check if file with same name already exists
            def s3_key_exists(bucket: str, key: str) -> bool:
                """
                Return True if an object with this key exists in the given bucket, else False.
                """
                try:
                    client.head_object(Bucket=bucket, Key=key)
                    return True
                except ClientError as e:
                    # Not found
                    if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                        return False
                    # Some other error (permissions, etc.) – re-raise
                    print("exception", str(e))
                    raise
            while(s3_key_exists(bucket, full_name)):
                counter += 1
                tmp_filename = f"{filename_only}_{counter}.{ext}"
                key_escaped = quote_plus(tmp_filename)
                full_name = foldername + "/" + key_escaped

            filename = safe_filename
            if counter > 0:
                filename = f"{filename_only}_{counter}.{ext}"

            filename = quote_plus(filename)
            filename = foldername + "/" + filename

            client.upload_fileobj(file_obj, bucket, filename, ExtraArgs={"ContentType": contentType})

            # Region-aware HTTPS URL (virtual-hosted–style)

            if region_name == "us-east-1":
                base_url = f"https://{bucket}.s3.amazonaws.com"
            else:
                base_url = f"https://{bucket}.s3.{region_name}.amazonaws.com"

            # URL-encode the key for safety (spaces, etc.)
            url = f"{base_url}/{filename}"    
            result['success'] = True
            result['path'] = url
            result['name'] = key_escaped
            
        except Exception as e:
            result['errors'].append(f"Failed to save file atomically: {str(e)}")            
        
        return result
    
    @staticmethod
    def save_file_atomically(file_obj, safe_filename:str, foldername: str, validate: bool = True) -> Dict[str, Any]:
        """
        Save file atomically using temporary file and rename.
        
        Args:
            file_obj: File object to save
            target_path: Target path for the file
            validate: Whether to validate file before saving
            
        Returns:
            Operation result
        """
        try:
            if MEDIA_STORE == 'server':
                return AtomicFileHandler.save_file_to_server(file_obj, safe_filename, foldername, validate)
            elif MEDIA_STORE == 'S3':
                return AtomicFileHandler.save_file_to_s3(file_obj, safe_filename, foldername, validate)
            else:
                raise Exception('Invalid media storage selected.')
        except Exception as e:
            logger.debug(f"Failed to upload file: {e}")
            raise e
            

class SecurityLogger:
    """
    Security-focused logging for upload operations.
    """
    
    @staticmethod
    def log_upload_attempt(
        request,
        filename: str,
        result: str,
        details: Dict[str, Any] = None
    ):
        """
        Log upload attempt for security monitoring.
        
        Args:
            request: Django request object
            filename: Name of uploaded file
            result: Result of upload (success/failure/blocked)
            details: Additional details to log
        """
        from api.analytics import get_client_ip, get_user_agent
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event': 'file_upload',
            'result': result,
            'filename': filename,
            'ip_address': get_client_ip(request),
            'user_agent': get_user_agent(request),
            'session_id': request.session.session_key if hasattr(request.session, 'session_key') else None,
            'details': details or {}
        }
        
        if result == 'blocked':
            logger.warning(f"SECURITY: Upload blocked - {log_entry}")
        elif result == 'failure':
            logger.error(f"Upload failed - {log_entry}")
        else:
            logger.info(f"Upload successful - {log_entry}")
        
        # Store in cache for rate limit analysis
        cache_key = f"upload_log:{datetime.now().strftime('%Y%m%d')}:{get_client_ip(request)}"
        logs = cache.get(cache_key, [])
        logs.append(log_entry)
        cache.set(cache_key, logs, 86400)  # Keep for 24 hours


def get_safe_upload_path(filename: str, upload_type: str = 'images') -> Path:
    """
    Get a safe upload path for a file.
    
    Args:
        filename: Original filename
        upload_type: Type of upload (images, documents, etc.)
        
    Returns:
        Safe Path object for file storage
    """
    # Sanitize the filename
    safe_filename = FileSecurityValidator.sanitize_filename(filename)
    
    # Create date-based subdirectory for organization
    date_path = datetime.now().strftime('%Y/%m/%d')
    
    # Build full path
    upload_path = settings.MEDIA_ROOT / upload_type / date_path / safe_filename
    
    return upload_path


def validate_upload_request(request, file_obj, upload_type: str = 'image') -> Dict[str, Any]:
    """
    Comprehensive validation for upload requests.
    
    Args:
        request: Django request object
        file_obj: File object to upload
        upload_type: Type of upload
        
    Returns:
        Validation result with details
    """
    from api.analytics import get_client_ip
    
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'details': {}
    }
    
    # Check rate limiting (skip for localhost/development)
    ip_address = get_client_ip(request)
    
    # Initialize rate_check with default allowed state
    rate_check = {'allowed': True, 'message': 'Rate limiting skipped for development'}
    
    # Skip rate limiting for localhost/development environments
    if ip_address not in ['127.0.0.1', 'localhost', '::1'] and not ip_address.startswith('192.168.'):
        rate_check = RateLimiter.check_rate_limit(
            identifier=ip_address,
            action='upload',
            max_requests=1000,  # 1000 uploads per minute (for large image sets with thousands of images)
            window_seconds=60
        )
        
        if not rate_check['allowed']:
            result['errors'].append(rate_check['message'])
            result['details']['rate_limit'] = rate_check
            return result
    
    # Check file size
    size_check = FileSecurityValidator.check_file_size(file_obj, upload_type)
    if not size_check['valid']:
        result['errors'].extend(size_check['errors'])
        result['details']['size_check'] = size_check
        return result
    
    # Validate file content
    content_check = FileSecurityValidator.validate_file_content(file_obj)
    if not content_check['valid']:
        result['errors'].extend(content_check['errors'])
        result['details']['content_check'] = content_check
        return result
    
    result['warnings'].extend(content_check.get('warnings', []))
    
    # If we get here, validation passed
    result['valid'] = True
    result['details'].update({
        'rate_limit': rate_check,
        'size_check': size_check,
        'content_check': content_check
    })
    
    return result