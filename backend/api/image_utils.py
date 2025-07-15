"""
Image utilities for EasyRead project.
Handles SVG to PNG conversion and image processing.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Union
from PIL import Image, ImageDraw
import io
# Import SVG conversion libraries
# Note: SVG conversion is temporarily disabled due to Cairo dependency issues
# and renderPM backend configuration problems. Most images in the dataset are PNG.
HAS_SVGLIB = False
# try:
#     from svglib.svglib import svg2rlg
#     from reportlab.graphics import renderPM
#     HAS_SVGLIB = True
# except ImportError:
#     HAS_SVGLIB = False

try:
    from wand.image import Image as WandImage
    HAS_WAND = True
except ImportError:
    HAS_WAND = False

logger = logging.getLogger(__name__)


class ImageConverter:
    """
    Utility class for image conversion and processing.
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the image converter.
        
        Args:
            output_dir: Directory to save converted images (default: creates 'converted' subdirectory)
        """
        self.output_dir = output_dir or Path("converted")
        self.output_dir.mkdir(exist_ok=True)
    
    def svg_to_png(self, svg_path: Union[str, Path], 
                   png_path: Optional[Union[str, Path]] = None,
                   width: Optional[int] = None, 
                   height: Optional[int] = None) -> Optional[Path]:
        """
        Convert SVG file to PNG.
        
        Args:
            svg_path: Path to the SVG file
            png_path: Output PNG path (optional, auto-generated if not provided)
            width: Output width in pixels (optional)
            height: Output height in pixels (optional)
            
        Returns:
            Path to the converted PNG file or None if conversion failed
        """
        try:
            svg_path = Path(svg_path)
            
            if not svg_path.exists():
                logger.error(f"SVG file not found: {svg_path}")
                return None
            
            # Generate output path if not provided
            if png_path is None:
                png_path = self.output_dir / f"{svg_path.stem}.png"
            else:
                png_path = Path(png_path)
            
            # Ensure output directory exists
            png_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert SVG to PNG using available libraries
            if HAS_SVGLIB:
                # Use svglib + reportlab with fallback to PDF conversion
                try:
                    # Read and render SVG to ReportLab drawing
                    drawing = svg2rlg(str(svg_path))
                    
                    # If width/height specified, scale the drawing
                    if width or height:
                        original_width = drawing.width
                        original_height = drawing.height
                        
                        if width and height:
                            scale_x = width / original_width
                            scale_y = height / original_height
                        elif width:
                            scale_x = scale_y = width / original_width
                        else:  # height only
                            scale_x = scale_y = height / original_height
                        
                        drawing.scale(scale_x, scale_y)
                    
                    # Try to render to PNG, fallback to PDF then convert
                    try:
                        renderPM.drawToFile(drawing, str(png_path), fmt='PNG')
                    except Exception as pm_error:
                        logger.warning(f"renderPM failed: {pm_error}, trying PDF conversion fallback")
                        # Fallback: render to PDF then convert to PNG
                        from reportlab.graphics import renderPDF
                        pdf_path = png_path.with_suffix('.pdf')
                        renderPDF.drawToFile(drawing, str(pdf_path))
                        
                        # Convert PDF to PNG using PIL (this would need additional libraries)
                        # For now, just log and return None
                        logger.error("PDF to PNG conversion not implemented")
                        return None
                        
                except Exception as e:
                    logger.error(f"SVG conversion with svglib failed: {e}")
                    return None
                    
            elif HAS_WAND:
                # Use Wand/ImageMagick if available
                with WandImage(filename=str(svg_path)) as img:
                    if width or height:
                        img.resize(width or img.width, height or img.height)
                    img.format = 'png'
                    img.save(filename=str(png_path))
            else:
                # Fallback: Skip SVG conversion and log a warning
                logger.warning(f"SVG conversion temporarily disabled due to dependency issues. "
                             f"Skipping conversion of {svg_path}. Consider converting SVG files to PNG manually.")
                return None
            
            logger.info(f"Successfully converted {svg_path} to {png_path}")
            return png_path
            
        except Exception as e:
            logger.error(f"Error converting SVG to PNG: {e}")
            return None
    
    def get_image_info(self, image_path: Union[str, Path]) -> Optional[dict]:
        """
        Get information about an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with image information or None if failed
        """
        try:
            image_path = Path(image_path)
            
            if not image_path.exists():
                logger.error(f"Image file not found: {image_path}")
                return None
            
            # Get file stats
            file_stats = image_path.stat()
            file_size = file_stats.st_size
            
            # Determine format from extension
            extension = image_path.suffix.lower()
            if extension == '.svg':
                file_format = 'SVG'
                # For SVG, we can't easily get dimensions without rendering
                width, height = None, None
            elif extension in ['.png', '.jpg', '.jpeg']:
                file_format = 'PNG' if extension == '.png' else 'JPEG'
                try:
                    with Image.open(image_path) as img:
                        width, height = img.size
                except Exception:
                    width, height = None, None
            else:
                file_format = extension[1:].upper()
                width, height = None, None
            
            return {
                'filename': image_path.name,
                'file_format': file_format,
                'file_size': file_size,
                'width': width,
                'height': height,
                'path': str(image_path)
            }
            
        except Exception as e:
            logger.error(f"Error getting image info: {e}")
            return None
    
    def validate_image(self, image_path: Union[str, Path]) -> bool:
        """
        Validate if an image file is valid and can be processed.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            True if image is valid, False otherwise
        """
        try:
            image_path = Path(image_path)
            
            if not image_path.exists():
                return False
            
            # Check file extension
            extension = image_path.suffix.lower()
            if extension == '.svg':
                # For SVG, try to read the file
                try:
                    with open(image_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        return '<svg' in content.lower()
                except Exception:
                    return False
            elif extension in ['.png', '.jpg', '.jpeg']:
                # For raster images, try to open with PIL
                try:
                    with Image.open(image_path) as img:
                        img.verify()
                        return True
                except Exception:
                    return False
            else:
                # Unknown format
                return False
                
        except Exception as e:
            logger.error(f"Error validating image: {e}")
            return False
    
    def process_image_for_embedding(self, image_path: Union[str, Path], 
                                  output_dir: Optional[Path] = None) -> Optional[Path]:
        """
        Process an image file for embedding generation.
        Converts SVG to PNG if needed, validates the image.
        
        Args:
            image_path: Path to the image file
            output_dir: Directory to save processed images (optional)
            
        Returns:
            Path to the processed image (PNG) or None if processing failed
        """
        try:
            image_path = Path(image_path)
            
            if not self.validate_image(image_path):
                logger.error(f"Invalid image file: {image_path}")
                return None
            
            # If it's already PNG or JPEG, return as-is
            if image_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                return image_path
            
            # If it's SVG, convert to PNG
            if image_path.suffix.lower() == '.svg':
                output_dir = output_dir or self.output_dir
                png_path = output_dir / f"{image_path.stem}.png"
                return self.svg_to_png(image_path, png_path)
            
            # Unsupported format
            logger.error(f"Unsupported image format: {image_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error processing image for embedding: {e}")
            return None
    
    def copy_image_to_media(self, image_path: Union[str, Path], 
                           media_root: Union[str, Path],
                           preserve_structure: bool = True) -> Optional[Path]:
        """
        Copy an image to the media directory for frontend access.
        
        Args:
            image_path: Path to the source image
            media_root: Path to the media root directory
            preserve_structure: Whether to preserve directory structure
            
        Returns:
            Path to the copied image or None if failed
        """
        try:
            import shutil
            
            image_path = Path(image_path)
            media_root = Path(media_root)
            
            if not image_path.exists():
                logger.error(f"Source image not found: {image_path}")
                return None
            
            # Create media directory if it doesn't exist
            media_root.mkdir(parents=True, exist_ok=True)
            
            if preserve_structure:
                # Try to preserve some directory structure
                # For example, if image is in clipart_images/animals/cat.png,
                # copy to media/images/animals/cat.png
                relative_path = image_path.name  # Just use filename for now
                dest_path = media_root / "images" / relative_path
            else:
                # Just copy to media/images/
                dest_path = media_root / "images" / image_path.name
            
            # Create destination directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(image_path, dest_path)
            
            logger.info(f"Copied image from {image_path} to {dest_path}")
            return dest_path
            
        except Exception as e:
            logger.error(f"Error copying image to media: {e}")
            return None


# Global converter instance
_converter_instance = None


def get_image_converter() -> ImageConverter:
    """
    Get the global image converter instance.
    
    Returns:
        ImageConverter instance
    """
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = ImageConverter()
    return _converter_instance


def convert_svg_to_png(svg_path: Union[str, Path], 
                      png_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """
    Convert SVG file to PNG.
    
    Args:
        svg_path: Path to the SVG file
        png_path: Output PNG path (optional)
        
    Returns:
        Path to the converted PNG file or None if conversion failed
    """
    converter = get_image_converter()
    return converter.svg_to_png(svg_path, png_path)


def validate_image_file(image_path: Union[str, Path]) -> bool:
    """
    Validate if an image file is valid and can be processed.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        True if image is valid, False otherwise
    """
    converter = get_image_converter()
    return converter.validate_image(image_path)


def process_image_for_embedding(image_path: Union[str, Path]) -> Optional[Path]:
    """
    Process an image file for embedding generation.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Path to the processed image (PNG) or None if processing failed
    """
    converter = get_image_converter()
    return converter.process_image_for_embedding(image_path)


def get_image_metadata(image_path: Union[str, Path]) -> Optional[dict]:
    """
    Get metadata for an image file.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Dictionary with image metadata or None if failed
    """
    converter = get_image_converter()
    return converter.get_image_info(image_path)