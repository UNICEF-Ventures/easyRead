"""
Management command to clean up orphaned images (images without embeddings).
This helps maintain data consistency by removing images that don't have embeddings.
"""

import os
import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import Image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up images that don\'t have any embeddings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Actually perform the cleanup (required for non-dry-run)'
        )

    def handle(self, *args, **options):
        # Find images without embeddings
        orphaned_images = Image.objects.filter(embeddings__isnull=True).distinct()
        
        if not orphaned_images.exists():
            self.stdout.write(
                self.style.SUCCESS('No orphaned images found - all images have embeddings!')
            )
            return

        self.stdout.write(f'Found {orphaned_images.count()} images without embeddings')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
            
            for image in orphaned_images:
                self.stdout.write(f'  Would delete: {image.filename} from set {image.set.name}')
                self.stdout.write(f'    File: {image.original_path}')
                if image.processed_path != image.original_path:
                    self.stdout.write(f'    Processed: {image.processed_path}')
            
            self.stdout.write('')
            self.stdout.write(f'Total: {orphaned_images.count()} images would be removed')
            self.stdout.write('Run with --force to actually perform cleanup')
            return

        if not options['force']:
            self.stdout.write(
                self.style.ERROR('Must specify --force to actually perform cleanup')
            )
            return

        # Perform actual cleanup
        deleted_files = 0
        deleted_records = 0
        errors = 0
        
        for image in orphaned_images:
            try:
                # Delete physical files
                files_to_delete = []
                if image.original_path:
                    files_to_delete.append(Path(image.original_path))
                if image.processed_path and image.processed_path != image.original_path:
                    files_to_delete.append(Path(image.processed_path))
                
                for file_path in files_to_delete:
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            deleted_files += 1
                            self.stdout.write(f'  ✓ Deleted file: {file_path}')
                        except Exception as e:
                            self.stdout.write(f'  ✗ Failed to delete file {file_path}: {e}')
                            errors += 1
                    else:
                        self.stdout.write(f'  ⊙ File not found: {file_path}')
                
                # Delete database record
                image_filename = image.filename
                image_set = image.set.name
                image.delete()
                deleted_records += 1
                self.stdout.write(f'  ✓ Deleted record: {image_filename} from {image_set}')
                
            except Exception as e:
                errors += 1
                self.stdout.write(f'  ✗ Error deleting {image.filename}: {e}')
        
        self.stdout.write('')
        self.stdout.write(f'Cleanup completed:')
        self.stdout.write(f'  ✓ Deleted files: {deleted_files}')
        self.stdout.write(f'  ✓ Deleted records: {deleted_records}') 
        if errors > 0:
            self.stdout.write(f'  ✗ Errors: {errors}')
            self.stdout.write(
                self.style.WARNING(f'{errors} errors occurred - check logs for details')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All orphaned images cleaned up successfully!')
            )