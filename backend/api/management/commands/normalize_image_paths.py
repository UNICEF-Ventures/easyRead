"""
Django management command to normalize image paths in the database.
Converts all paths to relative paths that work in both Docker and non-Docker environments.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import Image
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Normalize image paths to work in both Docker and non-Docker environments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        images = Image.objects.all()
        self.stdout.write(f'Found {images.count()} images to process')
        
        updated_count = 0
        
        for image in images:
            original_path = image.original_path
            normalized_path = self.normalize_path(original_path)
            
            if original_path != normalized_path:
                self.stdout.write(f'Image {image.id}: "{original_path}" -> "{normalized_path}"')
                
                if not dry_run:
                    image.original_path = normalized_path
                    image.save(update_fields=['original_path'])
                
                updated_count += 1
            
            # Also normalize processed_path if it exists
            if image.processed_path:
                original_processed = image.processed_path
                normalized_processed = self.normalize_path(original_processed)
                
                if original_processed != normalized_processed:
                    self.stdout.write(f'Image {image.id} processed: "{original_processed}" -> "{normalized_processed}"')
                    
                    if not dry_run:
                        image.processed_path = normalized_processed
                        image.save(update_fields=['processed_path'])
                    
                    updated_count += 1
        
        action = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f'{action} {updated_count} image paths')
        )
    
    def normalize_path(self, path_str):
        """
        Normalize a path to be relative to the media directory.
        Works with both absolute and relative paths.
        Also verifies that the file actually exists and corrects the path if needed.
        """
        if not path_str:
            return path_str
        
        path = Path(path_str)
        
        # If already relative and doesn't contain problematic parts, check if it exists
        if not path.is_absolute() and 'backend' not in str(path) and 'media' not in str(path).split('/')[0]:
            # Check if file exists at this relative path
            full_path = settings.MEDIA_ROOT / path_str
            if full_path.exists():
                return path_str
            else:
                # Try to find the actual file location
                filename = path.name
                actual_path = self.find_actual_file_path(filename)
                if actual_path:
                    return actual_path
                return path_str  # Keep original if we can't find it
        
        # Handle absolute paths
        if path.is_absolute():
            # Try to find 'media' in the path and extract everything after it
            parts = path.parts
            for i, part in enumerate(parts):
                if part == 'media' and i < len(parts) - 1:
                    # Return everything after 'media/'
                    relative_parts = parts[i + 1:]
                    candidate_path = str(Path(*relative_parts))
                    
                    # Verify the file exists at this path
                    full_path = settings.MEDIA_ROOT / candidate_path
                    if full_path.exists():
                        return candidate_path
                    else:
                        # Try to find the actual location
                        filename = path.name
                        actual_path = self.find_actual_file_path(filename)
                        if actual_path:
                            return actual_path
                        return candidate_path  # Keep the candidate if we can't find better
            
            # If no 'media' directory found, try to find the file
            filename = path.name
            actual_path = self.find_actual_file_path(filename)
            if actual_path:
                return actual_path
            return f"images/{filename}"
        
        # Handle relative paths that might have 'backend/media' or similar
        path_str_clean = path_str
        
        # Remove common prefixes that shouldn't be there
        prefixes_to_remove = [
            'backend/media/',
            'media/',
            './media/',
            '../media/',
        ]
        
        for prefix in prefixes_to_remove:
            if path_str_clean.startswith(prefix):
                path_str_clean = path_str_clean[len(prefix):]
                break
        
        return path_str_clean
    
    def find_actual_file_path(self, filename):
        """
        Find the actual file path for a given filename in the media directory.
        """
        media_root = Path(settings.MEDIA_ROOT)
        
        # Search for the file in all subdirectories
        for file_path in media_root.rglob(filename):
            # Return path relative to media root
            return str(file_path.relative_to(media_root))
        
        return None