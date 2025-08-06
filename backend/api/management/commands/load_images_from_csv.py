"""
Django management command to load images from CSV file.
Creates ImageSet, Image, and Embedding records based on CSV data.
"""

import csv
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings
from api.models import ImageSet, Image, Embedding
from api.embedding_adapter import get_embedding_model
from api.image_utils import get_image_converter
from api.model_config import pad_vector_to_standard
from api.validators import EmbeddingValidator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load images from CSV file and create embeddings'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing image data'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=32,
            help='Batch size for embedding generation (default: 32)'
        )
        parser.add_argument(
            '--media-root',
            type=str,
            default=None,
            help='Media root directory for copying images (default: Django MEDIA_ROOT)'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip images that already exist in the database'
        )
        parser.add_argument(
            '--create-general-set',
            action='store_true',
            help='Create a "General" set for images without a set'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        batch_size = options['batch_size']
        media_root = options['media_root'] or settings.MEDIA_ROOT
        skip_existing = options['skip_existing']
        create_general_set = options['create_general_set']

        # Validate CSV file exists
        if not Path(csv_file).exists():
            raise CommandError(f'CSV file not found: {csv_file}')

        # Initialize utilities
        embedding_model = get_embedding_model()
        image_converter = get_image_converter()
        
        # Get model metadata for consistent naming
        provider_name = getattr(embedding_model, 'provider_name', 'openclip')
        model_name = getattr(embedding_model, 'model_name', 'ViT-B-32')

        # Create General set if requested
        if create_general_set:
            general_set, created = ImageSet.objects.get_or_create(
                name='General',
                defaults={'description': 'General images without specific category'}
            )
            if created:
                self.stdout.write(f'Created General image set')

        # Track statistics
        stats = {
            'total_rows': 0,
            'processed_images': 0,
            'skipped_images': 0,
            'failed_images': 0,
            'created_sets': 0,
            'created_embeddings': 0
        }

        try:
            # Read and process CSV file
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                # Validate CSV columns
                required_columns = ['set_name', 'image_path', 'image_description']
                if not all(col in reader.fieldnames for col in required_columns):
                    raise CommandError(f'CSV must contain columns: {required_columns}')

                # Process images in batches
                batch_data = []
                for row in reader:
                    stats['total_rows'] += 1
                    batch_data.append(row)
                    
                    if len(batch_data) >= batch_size:
                        self._process_batch(batch_data, stats, media_root, skip_existing, 
                                         embedding_model, image_converter, 
                                         provider_name, model_name)
                        batch_data = []

                # Process remaining images
                if batch_data:
                    self._process_batch(batch_data, stats, media_root, skip_existing, 
                                     embedding_model, image_converter,
                                     provider_name, model_name)

        except Exception as e:
            raise CommandError(f'Error processing CSV file: {e}')

        # Print statistics
        self.stdout.write(
            self.style.SUCCESS(
                f'Processing complete!\n'
                f'Total rows: {stats["total_rows"]}\n'
                f'Processed images: {stats["processed_images"]}\n'
                f'Skipped images: {stats["skipped_images"]}\n'
                f'Failed images: {stats["failed_images"]}\n'
                f'Created sets: {stats["created_sets"]}\n'
                f'Created embeddings: {stats["created_embeddings"]}'
            )
        )

    def _process_batch(self, batch_data: list, stats: dict, media_root: str, 
                      skip_existing: bool, embedding_model, image_converter, 
                      provider_name: str, model_name: str) -> None:
        """Process a batch of image data."""
        
        for row in batch_data:
            try:
                set_name = row['set_name'].strip()
                image_path = Path(row['image_path'].strip())
                image_description = row['image_description'].strip()

                # Use 'General' set if no set name provided
                if not set_name:
                    set_name = 'General'

                # Check if image file exists
                if not image_path.exists():
                    self.stdout.write(
                        self.style.WARNING(f'Image file not found: {image_path}')
                    )
                    stats['failed_images'] += 1
                    continue

                # Validate image
                if not image_converter.validate_image(image_path):
                    self.stdout.write(
                        self.style.WARNING(f'Invalid image file: {image_path}')
                    )
                    stats['failed_images'] += 1
                    continue

                # Create or get image set
                image_set, created = ImageSet.objects.get_or_create(
                    name=set_name,
                    defaults={'description': f'Images for {set_name} set'}
                )
                if created:
                    stats['created_sets'] += 1
                    self.stdout.write(f'Created image set: {set_name}')

                # Check if image already exists
                filename = image_path.name
                if skip_existing and Image.objects.filter(set=image_set, filename=filename).exists():
                    self.stdout.write(f'Skipping existing image: {set_name}/{filename}')
                    stats['skipped_images'] += 1
                    continue

                # Process image for embedding (convert SVG to PNG if needed)
                processed_image_path = image_converter.process_image_for_embedding(image_path)
                if not processed_image_path:
                    self.stdout.write(
                        self.style.WARNING(f'Failed to process image: {image_path}')
                    )
                    stats['failed_images'] += 1
                    continue

                # Copy image to media directory
                media_image_path = image_converter.copy_image_to_media(
                    processed_image_path, media_root
                )
                if not media_image_path:
                    self.stdout.write(
                        self.style.WARNING(f'Failed to copy image to media: {image_path}')
                    )
                    stats['failed_images'] += 1
                    continue

                # Get image metadata
                image_info = image_converter.get_image_info(processed_image_path)
                if not image_info:
                    self.stdout.write(
                        self.style.WARNING(f'Failed to get image info: {image_path}')
                    )
                    stats['failed_images'] += 1
                    continue

                # Create or update Image record
                with transaction.atomic():
                    image_obj, created = Image.objects.get_or_create(
                        set=image_set,
                        filename=filename,
                        defaults={
                            'original_path': str(image_path),
                            'processed_path': str(processed_image_path),
                            'description': image_description,
                            'file_format': image_info.get('file_format', 'PNG'),
                            'file_size': image_info.get('file_size'),
                            'width': image_info.get('width'),
                            'height': image_info.get('height'),
                        }
                    )

                    if not created:
                        # Update existing image
                        image_obj.description = image_description
                        image_obj.processed_path = str(processed_image_path)
                        image_obj.file_format = image_info.get('file_format', 'PNG')
                        image_obj.file_size = image_info.get('file_size')
                        image_obj.width = image_info.get('width')
                        image_obj.height = image_info.get('height')
                        image_obj.save()

                    # Skip image embedding for now - using text-only embeddings
                    # image_embedding = embedding_model.encode_single_image(processed_image_path)
                    # if image_embedding is not None:
                    #     embedding_obj, created = Embedding.objects.get_or_create(
                    #         image=image_obj,
                    #         embedding_type='image',
                    #         provider_name=provider_name,
                    #         model_name=model_name,
                    #         defaults={
                    #             'vector': image_embedding.tolist(),
                    #             'embedding_dimension': len(image_embedding)
                    #         }
                    #     )
                    #     if created:
                    #         stats['created_embeddings'] += 1

                    # Create text embedding if description exists
                    if image_description:
                        text_embedding = embedding_model.encode_single_text(image_description)
                        if text_embedding is not None:
                            # Validate embedding before storage
                            validation = EmbeddingValidator.validate_embedding_vector(text_embedding, model_name)
                            
                            if validation['valid']:
                                # Pad vector to standard dimension for multi-model compatibility
                                padded_text_embedding = pad_vector_to_standard(text_embedding)
                                
                                embedding_obj, created = Embedding.objects.get_or_create(
                                    image=image_obj,
                                    embedding_type='text',
                                    provider_name=provider_name,
                                    model_name=model_name,
                                    defaults={
                                        'vector': padded_text_embedding.tolist(),  # Store padded vector
                                        'embedding_dimension': len(text_embedding)  # Store original dimension
                                    }
                                )
                                
                                if not created:
                                    # Update existing embedding
                                    embedding_obj.vector = padded_text_embedding.tolist()
                                    embedding_obj.embedding_dimension = len(text_embedding)
                                    embedding_obj.save()
                                
                                if created:
                                    stats['created_embeddings'] += 1
                            else:
                                self.stdout.write(
                                    self.style.WARNING(f'Invalid embedding for {filename}: {validation["errors"]}')
                                )
                        else:
                            self.stdout.write(
                                self.style.WARNING(f'Failed to generate text embedding for {filename}')
                            )

                    stats['processed_images'] += 1
                    self.stdout.write(f'Processed: {set_name}/{filename}')

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing image {row.get("image_path", "unknown")}: {e}')
                )
                stats['failed_images'] += 1
                continue