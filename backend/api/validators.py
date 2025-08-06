"""
Content validation utilities for the EasyRead embedding system.
Provides validation for images, embeddings, and content integrity.
"""

import logging
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from PIL import Image, UnidentifiedImageError
# import magic  # Temporarily disabled to avoid libmagic dependency
import hashlib
from django.core.exceptions import ValidationError
from django.conf import settings

logger = logging.getLogger(__name__)


class ImageValidator:
    """
    Comprehensive image validation utilities.
    """
    
    # Supported image formats and their magic bytes
    SUPPORTED_FORMATS = {
        'PNG': {
            'extensions': ['.png'],
            'mime_types': ['image/png'],
            'magic_bytes': [b'\x89PNG\r\n\x1a\n']
        },
        'JPEG': {
            'extensions': ['.jpg', '.jpeg'],
            'mime_types': ['image/jpeg'],
            'magic_bytes': [b'\xff\xd8\xff']
        },
        'SVG': {
            'extensions': ['.svg'],
            'mime_types': ['image/svg+xml', 'text/xml'],
            'magic_bytes': [b'<svg', b'<?xml']
        },
        'WEBP': {
            'extensions': ['.webp'],
            'mime_types': ['image/webp'],
            'magic_bytes': [b'RIFF', b'WEBP']
        }
    }
    
    # Image constraints
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MIN_DIMENSIONS = (1, 1)
    MAX_DIMENSIONS = (8192, 8192)
    
    @classmethod
    def validate_file_format(cls, file_path: Path) -> Dict[str, Any]:
        """
        Validate image file format using multiple methods.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'valid': False,
            'format': None,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check file extension
            extension = file_path.suffix.lower()
            format_by_extension = None
            
            for fmt, info in cls.SUPPORTED_FORMATS.items():
                if extension in info['extensions']:
                    format_by_extension = fmt
                    break
            
            if not format_by_extension:
                result['errors'].append(f"Unsupported file extension: {extension}")
                return result
            
            # Check file exists and is readable
            if not file_path.exists():
                result['errors'].append(f"File does not exist: {file_path}")
                return result
            
            if not file_path.is_file():
                result['errors'].append(f"Path is not a file: {file_path}")
                return result
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > cls.MAX_FILE_SIZE:
                result['errors'].append(f"File too large: {file_size} bytes (max: {cls.MAX_FILE_SIZE})")
                return result
            
            if file_size == 0:
                result['errors'].append("File is empty")
                return result
            
            # Check magic bytes
            with open(file_path, 'rb') as f:
                file_header = f.read(16)
            
            magic_match = False
            for magic_bytes in cls.SUPPORTED_FORMATS[format_by_extension]['magic_bytes']:
                if file_header.startswith(magic_bytes):
                    magic_match = True
                    break
            
            if not magic_match:
                result['warnings'].append(f"Magic bytes don't match expected format for {format_by_extension}")
            
            # Validate with PIL (for raster images)
            if format_by_extension in ['PNG', 'JPEG', 'WEBP']:
                try:
                    with Image.open(file_path) as img:
                        img.verify()
                        
                    # Reopen to get dimensions (verify() closes the image)
                    with Image.open(file_path) as img:
                        width, height = img.size
                        
                        if width < cls.MIN_DIMENSIONS[0] or height < cls.MIN_DIMENSIONS[1]:
                            result['errors'].append(f"Image too small: {width}x{height} (min: {cls.MIN_DIMENSIONS})")
                            return result
                        
                        if width > cls.MAX_DIMENSIONS[0] or height > cls.MAX_DIMENSIONS[1]:
                            result['warnings'].append(f"Image very large: {width}x{height} (max recommended: {cls.MAX_DIMENSIONS})")
                        
                        result['dimensions'] = (width, height)
                        result['mode'] = img.mode
                        result['pil_format'] = img.format
                        
                except UnidentifiedImageError:
                    result['errors'].append("PIL cannot identify image format")
                    return result
                except Exception as e:
                    result['errors'].append(f"PIL validation failed: {e}")
                    return result
            
            # Validate SVG
            elif format_by_extension == 'SVG':
                try:
                    content = file_path.read_text(encoding='utf-8')
                    if '<svg' not in content.lower():
                        result['errors'].append("SVG file does not contain <svg> tag")
                        return result
                    
                    # Basic SVG structure validation
                    if not content.strip().endswith('>'):
                        result['warnings'].append("SVG file may be malformed (doesn't end with >)")
                        
                except UnicodeDecodeError:
                    result['errors'].append("SVG file contains invalid UTF-8")
                    return result
                except Exception as e:
                    result['errors'].append(f"SVG validation failed: {e}")
                    return result
            
            # If we get here, validation passed
            result['valid'] = True
            result['format'] = format_by_extension
            result['file_size'] = file_size
            
        except Exception as e:
            result['errors'].append(f"Unexpected validation error: {e}")
        
        return result
    
    @classmethod
    def calculate_file_hash(cls, file_path: Path, algorithm: str = 'sha256') -> str:
        """
        Calculate hash of file for duplicate detection.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use
            
        Returns:
            Hexadecimal hash string
        """
        hash_func = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    @classmethod
    def validate_and_get_info(cls, file_path: Path) -> Dict[str, Any]:
        """
        Comprehensive validation and information extraction.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Complete validation and metadata dictionary
        """
        result = cls.validate_file_format(file_path)
        
        if result['valid']:
            try:
                # Add file hash for duplicate detection
                result['file_hash'] = cls.calculate_file_hash(file_path)
                
                # Add timestamp info
                stat = file_path.stat()
                result['modified_time'] = stat.st_mtime
                result['created_time'] = stat.st_ctime
                
            except Exception as e:
                result['warnings'].append(f"Failed to get additional metadata: {e}")
        
        return result


class EmbeddingValidator:
    """
    Validation utilities for embedding vectors.
    """
    
    # Expected embedding dimensions for API-based models only
    EXPECTED_DIMENSIONS = {
        'cohere.embed-multilingual-v3': 1024,  # Cohere multilingual model
        'cohere.embed-english-v3': 1024,      # Cohere English model  
        'amazon.titan-embed-text-v1': 1536,   # Amazon Titan v1
        'amazon.titan-embed-text-v2:0': 1024, # Amazon Titan v2
        'text-embedding-3-small': 1536,       # OpenAI small
        'text-embedding-3-large': 3072,       # OpenAI large
        # Padded dimensions (after padding to standard size)
        'padded': 2000,  # Standard padded dimension for multi-model compatibility
    }
    
    @classmethod
    def validate_embedding_vector(cls, vector: np.ndarray, model_name: str = 'cohere.embed-multilingual-v3', is_padded: bool = False) -> Dict[str, Any]:
        """
        Validate an embedding vector.
        
        Args:
            vector: Embedding vector as numpy array
            model_name: Name of the model that generated the embedding
            is_padded: Whether the vector is padded to standard dimension
            
        Returns:
            Validation results dictionary
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'dimension': None,
            'original_dimension': None,
            'is_padded': is_padded,
            'norm': None,
            'has_nan': False,
            'has_inf': False
        }
        
        try:
            # Check if it's a numpy array
            if not isinstance(vector, np.ndarray):
                result['errors'].append(f"Vector must be numpy array, got {type(vector)}")
                return result
            
            # Check dimensions
            if vector.ndim != 1:
                result['errors'].append(f"Vector must be 1-dimensional, got {vector.ndim} dimensions")
                return result
            
            dimension = len(vector)
            result['dimension'] = dimension
            
            # Check expected dimensions
            if is_padded:
                # If padded, must be 2000
                if dimension != 2000:
                    result['errors'].append(f"Padded vector must be 2000 dimensions, got {dimension}")
                    return result
                # Try to detect original dimension from non-zero values
                non_zero_indices = np.where(vector != 0)[0]
                if len(non_zero_indices) > 0:
                    result['original_dimension'] = int(non_zero_indices[-1] + 1)
            else:
                # Not padded - check against expected dimensions
                if model_name in cls.EXPECTED_DIMENSIONS:
                    expected_dim = cls.EXPECTED_DIMENSIONS[model_name]
                    if dimension != expected_dim:
                        result['warnings'].append(f"Expected {expected_dim} dimensions for {model_name}, got {dimension}")
                else:
                    # For unknown models, allow common dimensions
                    common_dims = [512, 768, 1024, 1536, 2048, 3072]
                    if dimension not in common_dims:
                        result['warnings'].append(f"Unknown model {model_name}, unusual dimension {dimension}")
            
            # Check for NaN values
            if np.isnan(vector).any():
                result['has_nan'] = True
                result['errors'].append("Vector contains NaN values")
                return result
            
            # Check for infinite values
            if np.isinf(vector).any():
                result['has_inf'] = True
                result['errors'].append("Vector contains infinite values")
                return result
            
            # Calculate vector norm
            norm = np.linalg.norm(vector)
            result['norm'] = float(norm)
            
            # Check if vector is zero
            if norm == 0:
                result['errors'].append("Vector has zero norm")
                return result
            
            # Check for very small or very large norms (may indicate issues)
            if norm < 1e-6:
                result['warnings'].append(f"Vector has very small norm: {norm}")
            elif norm > 1e6:
                result['warnings'].append(f"Vector has very large norm: {norm}")
            
            # If we get here, validation passed
            result['valid'] = True
            
        except Exception as e:
            result['errors'].append(f"Unexpected validation error: {e}")
        
        return result
    
    @classmethod
    def validate_embedding_similarity(cls, vector1: np.ndarray, vector2: np.ndarray) -> Dict[str, Any]:
        """
        Validate similarity calculation between two embeddings.
        
        Args:
            vector1: First embedding vector
            vector2: Second embedding vector
            
        Returns:
            Similarity validation results
        """
        result = {
            'valid': False,
            'similarity': None,
            'errors': []
        }
        
        try:
            # Validate both vectors
            val1 = cls.validate_embedding_vector(vector1)
            val2 = cls.validate_embedding_vector(vector2)
            
            if not val1['valid']:
                result['errors'].extend([f"Vector 1: {err}" for err in val1['errors']])
            
            if not val2['valid']:
                result['errors'].extend([f"Vector 2: {err}" for err in val2['errors']])
            
            if not (val1['valid'] and val2['valid']):
                return result
            
            # Check dimensions match
            if len(vector1) != len(vector2):
                result['errors'].append(f"Vector dimensions don't match: {len(vector1)} vs {len(vector2)}")
                return result
            
            # Calculate cosine similarity
            norm1 = np.linalg.norm(vector1)
            norm2 = np.linalg.norm(vector2)
            
            if norm1 == 0 or norm2 == 0:
                result['errors'].append("Cannot calculate similarity with zero-norm vectors")
                return result
            
            similarity = np.dot(vector1, vector2) / (norm1 * norm2)
            result['similarity'] = float(similarity)
            result['valid'] = True
            
        except Exception as e:
            result['errors'].append(f"Similarity calculation error: {e}")
        
        return result


class ContentValidator:
    """
    General content validation utilities.
    """
    
    @staticmethod
    def validate_image_set_name(name: str) -> Dict[str, Any]:
        """
        Validate image set name.
        
        Args:
            name: Image set name to validate
            
        Returns:
            Validation results
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': []
        }
        
        # Check length
        if len(name) < 1:
            result['errors'].append("Image set name cannot be empty")
            return result
        
        if len(name) > 255:
            result['errors'].append("Image set name too long (max 255 characters)")
            return result
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', '<', '>', ':', '"', '|', '?', '*']
        for char in invalid_chars:
            if char in name:
                result['errors'].append(f"Image set name contains invalid character: {char}")
                return result
        
        # Check for reserved names
        reserved_names = ['con', 'prn', 'aux', 'nul'] + [f'com{i}' for i in range(1, 10)] + [f'lpt{i}' for i in range(1, 10)]
        if name.lower() in reserved_names:
            result['errors'].append(f"Image set name is reserved: {name}")
            return result
        
        # Warnings for potentially problematic names
        if name.startswith('.'):
            result['warnings'].append("Image set name starts with dot")
        
        if name.endswith(' '):
            result['warnings'].append("Image set name ends with space")
        
        result['valid'] = True
        return result
    
    @staticmethod
    def validate_filename(filename: str) -> Dict[str, Any]:
        """
        Validate image filename.
        
        Args:
            filename: Filename to validate
            
        Returns:
            Validation results
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': []
        }
        
        # Check length
        if len(filename) < 1:
            result['errors'].append("Filename cannot be empty")
            return result
        
        if len(filename) > 255:
            result['errors'].append("Filename too long (max 255 characters)")
            return result
        
        # Check for path separators
        if '/' in filename or '\\' in filename:
            result['errors'].append("Filename cannot contain path separators")
            return result
        
        # Check for invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in invalid_chars:
            if char in filename:
                result['errors'].append(f"Filename contains invalid character: {char}")
                return result
        
        # Check extension
        if '.' not in filename:
            result['warnings'].append("Filename has no extension")
        else:
            extension = filename.split('.')[-1].lower()
            valid_extensions = []
            for fmt_info in ImageValidator.SUPPORTED_FORMATS.values():
                valid_extensions.extend([ext[1:] for ext in fmt_info['extensions']])  # Remove leading dot
            
            if extension not in valid_extensions:
                result['warnings'].append(f"Unexpected file extension: {extension}")
        
        result['valid'] = True
        return result


def validate_uploaded_image(file_path: Path, set_name: str = 'General') -> Dict[str, Any]:
    """
    Comprehensive validation for uploaded images.
    
    Args:
        file_path: Path to the uploaded image
        set_name: Name of the target image set
        
    Returns:
        Complete validation results
    """
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'image_info': None,
        'set_validation': None,
        'filename_validation': None
    }
    
    try:
        # Validate image file
        image_validation = ImageValidator.validate_and_get_info(file_path)
        result['image_info'] = image_validation
        
        if not image_validation['valid']:
            result['errors'].extend(image_validation['errors'])
        
        result['warnings'].extend(image_validation.get('warnings', []))
        
        # Validate set name
        set_validation = ContentValidator.validate_image_set_name(set_name)
        result['set_validation'] = set_validation
        
        if not set_validation['valid']:
            result['errors'].extend([f"Set name: {err}" for err in set_validation['errors']])
        
        result['warnings'].extend([f"Set name: {warn}" for warn in set_validation.get('warnings', [])])
        
        # Validate filename
        filename_validation = ContentValidator.validate_filename(file_path.name)
        result['filename_validation'] = filename_validation
        
        if not filename_validation['valid']:
            result['errors'].extend([f"Filename: {err}" for err in filename_validation['errors']])
        
        result['warnings'].extend([f"Filename: {warn}" for warn in filename_validation.get('warnings', [])])
        
        # Overall validation
        result['valid'] = (
            image_validation['valid'] and 
            set_validation['valid'] and 
            filename_validation['valid']
        )
        
    except Exception as e:
        result['errors'].append(f"Validation error: {e}")
    
    return result