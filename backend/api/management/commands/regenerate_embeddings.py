"""
Management command to regenerate embeddings for images that don't have them.
Useful for fixing images that were uploaded when embeddings failed.
"""

import logging
from django.core.management.base import BaseCommand
from api.models import Image, Embedding
from api.embedding_adapter import get_embedding_model
from api.validators import EmbeddingValidator
from api.model_config import pad_vector_to_standard

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Regenerate embeddings for images that are missing them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--set-name',
            type=str,
            help='Only regenerate embeddings for images in a specific set'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate embeddings even if they already exist'
        )

    def handle(self, *args, **options):
        # Get embedding model
        try:
            embedding_model = get_embedding_model()
            model_metadata = embedding_model.provider.get_model_metadata()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to initialize embedding model: {e}')
            )
            return

        # Find images without embeddings
        images_query = Image.objects.all()
        
        if options['set_name']:
            images_query = images_query.filter(set__name=options['set_name'])
        
        if not options['force']:
            # Only get images without text embeddings
            images_query = images_query.exclude(
                embeddings__embedding_type='text',
                embeddings__provider_name=model_metadata['provider_name'],
                embeddings__model_name=model_metadata['model_name']
            )
        
        images_to_process = list(images_query)
        
        if not images_to_process:
            self.stdout.write(
                self.style.SUCCESS('No images need embedding regeneration')
            )
            return

        self.stdout.write(f'Found {len(images_to_process)} images to process')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
            for image in images_to_process:
                self.stdout.write(f'  Would process: {image.filename} in set {image.set.name}')
            return

        # Process images
        processed = 0
        failed = 0
        
        for image in images_to_process:
            try:
                # Use filename's first part as embedding text
                filename_without_ext = image.filename.rsplit('.', 1)[0]
                embedding_text = filename_without_ext.split('_')[0]
                
                if image.description:
                    embedding_text = image.description
                
                self.stdout.write(f'Processing {image.filename} with text: "{embedding_text}"')
                
                # Generate embedding
                text_embedding = embedding_model.encode_single_text(embedding_text)
                
                if text_embedding is not None:
                    # Validate embedding
                    validation = EmbeddingValidator.validate_embedding_vector(
                        text_embedding, model_metadata['model_name']
                    )
                    
                    if validation['valid']:
                        # Pad vector for storage
                        padded_embedding = pad_vector_to_standard(text_embedding)
                        
                        # Create or update embedding
                        embedding_obj, created = Embedding.objects.get_or_create(
                            image=image,
                            embedding_type='text',
                            provider_name=model_metadata['provider_name'],
                            model_name=model_metadata['model_name'],
                            defaults={
                                'vector': padded_embedding.tolist(),
                                'embedding_dimension': len(text_embedding)
                            }
                        )
                        
                        if not created:
                            embedding_obj.vector = padded_embedding.tolist()
                            embedding_obj.embedding_dimension = len(text_embedding)
                            embedding_obj.save()
                        
                        processed += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Generated embedding for {image.filename}')
                        )
                    else:
                        failed += 1
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ Validation failed for {image.filename}: {validation["errors"]}')
                        )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Failed to generate embedding for {image.filename}')
                    )
                    
            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error processing {image.filename}: {e}')
                )
        
        self.stdout.write('')
        self.stdout.write(f'Completed: {processed} successful, {failed} failed')
        
        if failed > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'{failed} images failed - check embedding provider configuration'
                )
            )