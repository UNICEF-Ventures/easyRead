"""
Management command to show embedding status across different models.
Provides insights into multi-model embedding distribution.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from api.models import Image, Embedding, ImageSet
from collections import defaultdict
import json


class Command(BaseCommand):
    help = 'Show embedding status across different models and providers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed breakdown by image set'
        )
        parser.add_argument(
            '--provider',
            type=str,
            help='Filter by specific provider name'
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Filter by specific model name'
        )
        parser.add_argument(
            '--format',
            choices=['table', 'json'],
            default='table',
            help='Output format (table or json)'
        )
        parser.add_argument(
            '--missing',
            action='store_true',
            help='Show images missing embeddings for specific models'
        )

    def handle(self, *args, **options):
        try:
            if options['missing']:
                self.show_missing_embeddings(options)
            else:
                self.show_embedding_status(options)
        except Exception as e:
            raise CommandError(f'Error: {e}')

    def show_embedding_status(self, options):
        """Show overall embedding status."""
        # Get embedding statistics grouped by provider and model
        embedding_stats = (
            Embedding.objects
            .values('provider_name', 'model_name', 'embedding_type')
            .annotate(count=Count('id'))
            .order_by('provider_name', 'model_name', 'embedding_type')
        )

        # Filter by provider/model if specified
        if options['provider']:
            embedding_stats = embedding_stats.filter(provider_name=options['provider'])
        if options['model']:
            embedding_stats = embedding_stats.filter(model_name=options['model'])

        if not embedding_stats:
            self.stdout.write(self.style.WARNING('No embeddings found'))
            return

        # Organize data
        stats_by_provider = defaultdict(lambda: defaultdict(lambda: {'image': 0, 'text': 0}))
        
        for stat in embedding_stats:
            provider = stat['provider_name']
            model = stat['model_name']
            embedding_type = stat['embedding_type']
            count = stat['count']
            
            stats_by_provider[provider][model][embedding_type] = count

        # Get total image count
        total_images = Image.objects.count()
        total_image_sets = ImageSet.objects.count()

        if options['format'] == 'json':
            self.output_json(stats_by_provider, total_images, total_image_sets)
        else:
            self.output_table(stats_by_provider, total_images, total_image_sets, options)

    def output_table(self, stats_by_provider, total_images, total_image_sets, options):
        """Output statistics in table format."""
        self.stdout.write(self.style.SUCCESS('=== Embedding Status Report ==='))
        self.stdout.write(f'Total Images: {total_images}')
        self.stdout.write(f'Total Image Sets: {total_image_sets}')
        self.stdout.write('')

        for provider_name, models in stats_by_provider.items():
            self.stdout.write(self.style.SUCCESS(f'Provider: {provider_name}'))
            self.stdout.write('-' * 80)
            
            for model_name, embedding_counts in models.items():
                image_count = embedding_counts['image']
                text_count = embedding_counts['text']
                
                image_coverage = (image_count / total_images * 100) if total_images > 0 else 0
                
                self.stdout.write(f'  Model: {model_name}')
                self.stdout.write(f'    Image embeddings: {image_count:,} ({image_coverage:.1f}% coverage)')
                self.stdout.write(f'    Text embeddings:  {text_count:,}')
                
                if image_count > 0:
                    avg_embeddings_per_image = (image_count + text_count) / image_count
                    self.stdout.write(f'    Avg embeddings per image: {avg_embeddings_per_image:.1f}')
                self.stdout.write('')

        # Show detailed breakdown by image set if requested
        if options['detailed']:
            self.show_detailed_breakdown(options)

    def output_json(self, stats_by_provider, total_images, total_image_sets):
        """Output statistics in JSON format."""
        output = {
            'total_images': total_images,
            'total_image_sets': total_image_sets,
            'providers': {}
        }
        
        for provider_name, models in stats_by_provider.items():
            output['providers'][provider_name] = {}
            
            for model_name, embedding_counts in models.items():
                image_count = embedding_counts['image']
                text_count = embedding_counts['text']
                
                output['providers'][provider_name][model_name] = {
                    'image_embeddings': image_count,
                    'text_embeddings': text_count,
                    'coverage_percentage': (image_count / total_images * 100) if total_images > 0 else 0
                }
        
        self.stdout.write(json.dumps(output, indent=2))

    def show_detailed_breakdown(self, options):
        """Show detailed breakdown by image set."""
        self.stdout.write(self.style.SUCCESS('=== Detailed Breakdown by Image Set ==='))
        
        # Get embedding stats by image set
        set_stats = (
            Embedding.objects
            .select_related('image__set')
            .values(
                'image__set__name',
                'provider_name', 
                'model_name', 
                'embedding_type'
            )
            .annotate(count=Count('id'))
            .order_by('image__set__name', 'provider_name', 'model_name')
        )

        # Filter by provider/model if specified
        if options['provider']:
            set_stats = set_stats.filter(provider_name=options['provider'])
        if options['model']:
            set_stats = set_stats.filter(model_name=options['model'])

        # Organize by image set
        stats_by_set = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'image': 0, 'text': 0})))
        
        for stat in set_stats:
            set_name = stat['image__set__name']
            provider = stat['provider_name']
            model = stat['model_name']
            embedding_type = stat['embedding_type']
            count = stat['count']
            
            stats_by_set[set_name][provider][model][embedding_type] = count

        # Get image counts per set
        set_image_counts = dict(
            ImageSet.objects
            .annotate(image_count=Count('images'))
            .values_list('name', 'image_count')
        )

        for set_name, providers in stats_by_set.items():
            total_set_images = set_image_counts.get(set_name, 0)
            self.stdout.write(f'\nImage Set: {set_name} ({total_set_images} images)')
            self.stdout.write('-' * 60)
            
            for provider_name, models in providers.items():
                for model_name, embedding_counts in models.items():
                    image_count = embedding_counts['image']
                    text_count = embedding_counts['text']
                    
                    coverage = (image_count / total_set_images * 100) if total_set_images > 0 else 0
                    
                    self.stdout.write(f'  {provider_name}:{model_name}')
                    self.stdout.write(f'    Images: {image_count:,} ({coverage:.1f}%), Texts: {text_count:,}')

    def show_missing_embeddings(self, options):
        """Show images that are missing embeddings for specific models."""
        self.stdout.write(self.style.SUCCESS('=== Images Missing Embeddings ==='))
        
        # Get all unique provider/model combinations
        provider_models = (
            Embedding.objects
            .values('provider_name', 'model_name')
            .distinct()
            .order_by('provider_name', 'model_name')
        )

        # Filter by provider/model if specified
        if options['provider']:
            provider_models = provider_models.filter(provider_name=options['provider'])
        if options['model']:
            provider_models = provider_models.filter(model_name=options['model'])

        for pm in provider_models:
            provider_name = pm['provider_name']
            model_name = pm['model_name']
            
            self.stdout.write(f'\nProvider: {provider_name}, Model: {model_name}')
            self.stdout.write('-' * 60)
            
            # Find images missing image embeddings
            images_with_embeddings = Embedding.objects.filter(
                provider_name=provider_name,
                model_name=model_name,
                embedding_type='image'
            ).values_list('image_id', flat=True)
            
            missing_image_embeddings = Image.objects.exclude(
                id__in=images_with_embeddings
            ).select_related('set')
            
            # Find images missing text embeddings (only for images with descriptions)
            images_with_text_embeddings = Embedding.objects.filter(
                provider_name=provider_name,
                model_name=model_name,
                embedding_type='text'
            ).values_list('image_id', flat=True)
            
            missing_text_embeddings = Image.objects.exclude(
                Q(description='') | Q(description__isnull=True)
            ).exclude(
                id__in=images_with_text_embeddings
            ).select_related('set')
            
            if missing_image_embeddings.exists():
                self.stdout.write(f'  Missing image embeddings: {missing_image_embeddings.count()}')
                if options['format'] == 'table':
                    for img in missing_image_embeddings[:10]:  # Show first 10
                        self.stdout.write(f'    - {img.set.name}/{img.filename}')
                    if missing_image_embeddings.count() > 10:
                        self.stdout.write(f'    ... and {missing_image_embeddings.count() - 10} more')
            
            if missing_text_embeddings.exists():
                self.stdout.write(f'  Missing text embeddings: {missing_text_embeddings.count()}')
                if options['format'] == 'table':
                    for img in missing_text_embeddings[:10]:  # Show first 10
                        self.stdout.write(f'    - {img.set.name}/{img.filename}')
                    if missing_text_embeddings.count() > 10:
                        self.stdout.write(f'    ... and {missing_text_embeddings.count() - 10} more')
            
            if not missing_image_embeddings.exists() and not missing_text_embeddings.exists():
                self.stdout.write('  ✓ All images have embeddings for this model')