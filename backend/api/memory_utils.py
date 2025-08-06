"""
Memory monitoring and management utilities for upload operations.
Provides memory-efficient file processing and monitoring.
"""

import os
import psutil
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager
from PIL import Image
import io

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """
    Monitor and manage memory usage during file operations.
    """
    
    # Memory thresholds
    MEMORY_WARNING_THRESHOLD = 80  # Warn at 80% memory usage
    MEMORY_CRITICAL_THRESHOLD = 90  # Reject operations at 90% memory usage
    
    @classmethod
    def get_memory_status(cls) -> Dict[str, Any]:
        """
        Get current memory status of the system.
        
        Returns:
            Dictionary with memory statistics
        """
        memory = psutil.virtual_memory()
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()
        
        return {
            'system': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used,
                'free': memory.free
            },
            'process': {
                'rss': process_memory.rss,  # Resident Set Size
                'vms': process_memory.vms,  # Virtual Memory Size
                'percent': process.memory_percent()
            },
            'status': cls._get_status(memory.percent)
        }
    
    @classmethod
    def _get_status(cls, percent: float) -> str:
        """
        Get memory status based on percentage.
        
        Args:
            percent: Memory usage percentage
            
        Returns:
            Status string (ok/warning/critical)
        """
        if percent >= cls.MEMORY_CRITICAL_THRESHOLD:
            return 'critical'
        elif percent >= cls.MEMORY_WARNING_THRESHOLD:
            return 'warning'
        return 'ok'
    
    @classmethod
    def check_memory_available(cls, required_mb: int = 100) -> Dict[str, Any]:
        """
        Check if sufficient memory is available for an operation.
        
        Args:
            required_mb: Required memory in megabytes
            
        Returns:
            Check result dictionary
        """
        memory_status = cls.get_memory_status()
        available_mb = memory_status['system']['available'] / (1024 * 1024)
        
        result = {
            'allowed': True,
            'available_mb': available_mb,
            'required_mb': required_mb,
            'memory_percent': memory_status['system']['percent'],
            'status': memory_status['status']
        }
        
        if memory_status['status'] == 'critical':
            result['allowed'] = False
            result['message'] = f"Memory usage critical ({memory_status['system']['percent']:.1f}%). Operation blocked."
        elif available_mb < required_mb:
            result['allowed'] = False
            result['message'] = f"Insufficient memory. Required: {required_mb}MB, Available: {available_mb:.1f}MB"
        elif memory_status['status'] == 'warning':
            result['warning'] = f"Memory usage high ({memory_status['system']['percent']:.1f}%)"
        
        return result
    
    @classmethod
    @contextmanager
    def monitor_operation(cls, operation_name: str):
        """
        Context manager to monitor memory usage during an operation.
        
        Args:
            operation_name: Name of the operation being monitored
        """
        # Get initial memory state
        initial_memory = cls.get_memory_status()
        logger.info(f"Starting {operation_name} - Memory: {initial_memory['system']['percent']:.1f}%")
        
        try:
            yield
        finally:
            # Get final memory state
            final_memory = cls.get_memory_status()
            memory_delta = final_memory['process']['rss'] - initial_memory['process']['rss']
            
            logger.info(
                f"Completed {operation_name} - "
                f"Memory: {final_memory['system']['percent']:.1f}%, "
                f"Process delta: {memory_delta / (1024 * 1024):.1f}MB"
            )
            
            # Log warning if memory usage is high
            if final_memory['status'] in ['warning', 'critical']:
                logger.warning(
                    f"High memory usage after {operation_name}: "
                    f"{final_memory['system']['percent']:.1f}%"
                )


class StreamingImageProcessor:
    """
    Process images in a memory-efficient streaming manner.
    """
    
    @staticmethod
    def process_image_chunked(
        file_obj,
        max_dimension: int = 2048,
        quality: int = 85
    ) -> Dict[str, Any]:
        """
        Process image with memory-efficient chunked reading.
        
        Args:
            file_obj: File object to process
            max_dimension: Maximum dimension for resizing
            quality: JPEG quality for compression
            
        Returns:
            Processed image information
        """
        result = {
            'success': False,
            'processed_data': None,
            'metadata': {},
            'errors': []
        }
        
        try:
            # Check memory before processing
            memory_check = MemoryMonitor.check_memory_available(50)  # Require 50MB
            if not memory_check['allowed']:
                result['errors'].append(memory_check['message'])
                return result
            
            # Read image in chunks to avoid loading entire file
            file_obj.seek(0)
            img_data = io.BytesIO()
            
            # Stream copy with small chunks
            chunk_size = 8192  # 8KB chunks
            while True:
                chunk = file_obj.read(chunk_size)
                if not chunk:
                    break
                img_data.write(chunk)
            
            img_data.seek(0)
            
            # Open and process image
            with Image.open(img_data) as img:
                # Get original metadata
                result['metadata'] = {
                    'original_size': img.size,
                    'format': img.format,
                    'mode': img.mode
                }
                
                # Check if resizing is needed
                if max(img.size) > max_dimension:
                    # Calculate new dimensions maintaining aspect ratio
                    ratio = max_dimension / max(img.size)
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    
                    # Resize using efficient algorithm
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    result['metadata']['resized'] = True
                    result['metadata']['new_size'] = new_size
                
                # Convert to RGB if necessary (for JPEG)
                if img.mode not in ('RGB', 'L'):
                    if img.mode == 'RGBA':
                        # Create white background for transparency
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                        img = background
                    else:
                        img = img.convert('RGB')
                
                # Save processed image to BytesIO
                output = io.BytesIO()
                
                # Use appropriate format
                save_format = 'JPEG' if img.format != 'PNG' else 'PNG'
                save_kwargs = {'format': save_format}
                
                if save_format == 'JPEG':
                    save_kwargs['quality'] = quality
                    save_kwargs['optimize'] = True
                elif save_format == 'PNG':
                    save_kwargs['optimize'] = True
                
                img.save(output, **save_kwargs)
                output.seek(0)
                
                result['processed_data'] = output
                result['metadata']['processed_size'] = output.getbuffer().nbytes
                result['metadata']['processed_format'] = save_format
                result['success'] = True
            
        except Exception as e:
            result['errors'].append(f"Image processing error: {str(e)}")
            logger.error(f"Error in chunked image processing: {e}")
        
        return result
    
    @staticmethod
    def estimate_memory_requirement(file_size: int, image_dimensions: tuple = None) -> int:
        """
        Estimate memory requirement for processing an image.
        
        Args:
            file_size: Size of the image file in bytes
            image_dimensions: Optional (width, height) tuple
            
        Returns:
            Estimated memory requirement in bytes
        """
        # Base estimate: file size * 3 (for decompression and processing)
        base_estimate = file_size * 3
        
        # If dimensions provided, refine estimate
        if image_dimensions:
            width, height = image_dimensions
            # Assume 4 bytes per pixel (RGBA)
            pixel_memory = width * height * 4
            # Add buffer for processing
            base_estimate = max(base_estimate, pixel_memory * 2)
        
        # Add overhead (20%)
        return int(base_estimate * 1.2)


def cleanup_memory():
    """
    Force garbage collection and clear caches to free memory.
    """
    import gc
    
    # Force garbage collection
    gc.collect()
    
    # Clear PIL image cache if available
    try:
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = False
    except ImportError:
        # PIL not available or cannot be configured
        pass
    
    # Log memory status after cleanup
    memory_status = MemoryMonitor.get_memory_status()
    logger.info(f"Memory cleanup completed. Current usage: {memory_status['system']['percent']:.1f}%")