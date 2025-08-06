"""
Management command for bulk uploading thousands of images without rate limiting.
Ideal for initial setup or large-scale image library imports.
"""

import os
import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from api.upload_handlers import handle_image_upload
from api.validators import validate_uploaded_image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Bulk upload images from a directory structure, bypassing rate limits'

    def add_arguments(self, parser):
        parser.add_argument(
            'directory',
            type=str,
            help='Path to directory containing images to upload'
        )
        parser.add_argument(
            '--set-name',
            type=str,
            default='BulkUpload',
            help='Default image set name (default: BulkUpload)'
        )
        parser.add_argument(
            '--use-folder-names',
            action='store_true',
            help='Create image sets based on folder names (like folder upload)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be uploaded without actually doing it'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip files that already exist in the database'
        )

    def handle(self, *args, **options):
        directory = Path(options['directory'])
        
        if not directory.exists():
            self.stdout.write(
                self.style.ERROR(f'Directory does not exist: {directory}')
            )
            return
        
        if not directory.is_dir():
            self.stdout.write(
                self.style.ERROR(f'Path is not a directory: {directory}')
            )
            return

        # Find all image files
        image_extensions = {'.png', '.jpg', '.jpeg', '.svg', '.webp'}
        image_files = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if Path(file).suffix.lower() in image_extensions:
                    full_path = Path(root) / file
                    image_files.append(full_path)

        if not image_files:
            self.stdout.write(
                self.style.WARNING(f'No image files found in {directory}')
            )
            return

        self.stdout.write(f'Found {len(image_files)} image files')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No files will be uploaded'))
            
            # Group by folder if using folder names
            if options['use_folder_names']:
                folders = {}
                for file_path in image_files:
                    # Get folder name relative to base directory
                    relative_path = file_path.relative_to(directory)
                    folder_name = relative_path.parts[0] if len(relative_path.parts) > 1 else options['set_name']
                    
                    if folder_name not in folders:
                        folders[folder_name] = []
                    folders[folder_name].append(file_path.name)
                
                for folder_name, files in folders.items():
                    self.stdout.write(f'  Set "{folder_name}": {len(files)} images')
            else:
                self.stdout.write(f'  Would upload to set "{options["set_name"]}"')
                
            return

        # Perform actual upload
        uploaded = 0
        failed = 0
        skipped = 0
        
        for file_path in image_files:
            try:
                # Determine set name
                if options['use_folder_names']:
                    relative_path = file_path.relative_to(directory)
                    if len(relative_path.parts) > 1:
                        set_name = relative_path.parts[0]
                    else:
                        set_name = options['set_name']
                else:
                    set_name = options['set_name']
                
                # Generate description from filename
                description = file_path.stem.replace('_', ' ').replace('-', ' ')
                
                # Check if already exists (if skip_existing is True)
                if options['skip_existing']:
                    from api.models import Image
                    if Image.objects.filter(filename=file_path.name, set__name=set_name).exists():
                        skipped += 1
                        self.stdout.write(f'  Skipped: {file_path.name} (already exists)')
                        continue
                
                self.stdout.write(f'Uploading: {file_path.name} to set "{set_name}"')
                
                # Create a fake file object for the upload handler
                class FakeUploadedFile:
                    def __init__(self, path):
                        self.path = Path(path)
                        self.name = self.path.name
                        self.size = self.path.stat().st_size
                    
                    def chunks(self):
                        with open(self.path, 'rb') as f:
                            while True:
                                chunk = f.read(8192)
                                if not chunk:
                                    break
                                yield chunk
                    
                    def read(self):
                        with open(self.path, 'rb') as f:
                            return f.read()
                
                fake_file = FakeUploadedFile(file_path)
                
                # Upload the image (bypasses rate limiting since no request object)
                result = handle_image_upload(fake_file, description, set_name)
                
                if result.get('success'):
                    uploaded += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Uploaded: {file_path.name}')
                    )
                else:
                    failed += 1
                    errors = result.get('errors', result.get('error', 'Unknown error'))
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Failed: {file_path.name} - {errors}')
                    )
                    
            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error: {file_path.name} - {e}')
                )

        self.stdout.write('')
        self.stdout.write(f'Upload complete:')
        self.stdout.write(f'  ✓ Uploaded: {uploaded}')
        self.stdout.write(f'  ✗ Failed: {failed}')
        if skipped > 0:
            self.stdout.write(f'  ⊙ Skipped: {skipped}')
        
        if failed > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'{failed} uploads failed - check logs for details'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All uploads completed successfully!')
            )