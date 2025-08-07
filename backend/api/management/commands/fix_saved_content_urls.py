"""
Django management command to convert absolute image URLs in saved ProcessedContent to relative paths.
Makes saved content portable across environments.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import ProcessedContent, Image
import re
import json
from urllib.parse import urlparse
from pathlib import Path


class Command(BaseCommand):
    help = 'Convert absolute image URLs in saved ProcessedContent to relative paths for portability'

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
        
        contents = ProcessedContent.objects.all()
        self.stdout.write(f'Found {contents.count()} saved content items to process')
        
        updated_count = 0
        
        for content in contents:
            if not content.easy_read_json:
                continue
                
            content_updated = False
            
            for item in content.easy_read_json:
                if item.get('selected_image_path'):
                    original_url = item['selected_image_path']
                    relative_path = self.convert_to_relative_path(original_url)
                    
                    if original_url != relative_path:
                        self.stdout.write(f'Content "{content.title[:50]}...":')
                        self.stdout.write(f'  OLD: {original_url}')
                        self.stdout.write(f'  NEW: {relative_path}')
                        
                        if not dry_run:
                            item['selected_image_path'] = relative_path
                        
                        content_updated = True
            
            if content_updated and not dry_run:
                content.save()
                updated_count += 1
        
        action = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f'{action} {updated_count} saved content items')
        )
    
    def convert_to_relative_path(self, url):
        """
        Convert an absolute URL to a relative path.
        
        This extracts just the path portion and looks up the correct
        relative path from the Image model if possible.
        """
        if not url:
            return url
            
        # If it's already a relative path, keep it
        if not url.startswith('http'):
            return url
            
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # Extract the filename from the path
            filename = Path(path).name
            
            # Try to find the actual image in the database and get correct relative path
            try:
                image = Image.objects.filter(filename=filename).first()
                if image:
                    # Return just the relative path from the model
                    return image.get_url()  # This returns /media/images/...
            except Exception as e:
                self.stdout.write(f"Warning: Could not find image {filename} in database: {e}")
            
            # Fallback: clean the path manually
            # Remove any leading domain/protocol info and just keep the path
            if path.startswith('/media/'):
                # Fix common path issues
                if '/2025/08/07/' in path:
                    path = path.replace('/2025/08/07/', '/2025/08/06/')
                return path
            
            # If path doesn't start with /media/, try to extract it
            if '/media/' in path:
                media_index = path.find('/media/')
                corrected_path = path[media_index:]
                if '/2025/08/07/' in corrected_path:
                    corrected_path = corrected_path.replace('/2025/08/07/', '/2025/08/06/')
                return corrected_path
            
            # Last resort: construct a reasonable path from filename
            return f"/media/images/{filename}"
            
        except Exception as e:
            self.stdout.write(f"Error converting URL {url}: {e}")
            return url