"""
Django management command to clean up ML model resources and check memory usage.
"""

from django.core.management.base import BaseCommand
import psutil
import os
import gc
import torch


class Command(BaseCommand):
    help = 'Clean up ML model resources and show memory usage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-memory',
            action='store_true',
            help='Show detailed memory usage information',
        )
        parser.add_argument(
            '--force-cleanup',
            action='store_true',
            help='Force cleanup of all resources',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧹 Cleaning up ML model resources...'))
        
        # Show memory usage before cleanup
        if options['show_memory']:
            self.show_memory_usage("Before cleanup")
        
        # Cleanup ML model resources
        try:
            from api.embedding_utils import cleanup_embedding_model
            from api.similarity_search import cleanup_similarity_searcher
            
            # Clean up embedding model
            cleanup_embedding_model()
            
            # Clean up similarity searcher
            cleanup_similarity_searcher()
            
            self.stdout.write(self.style.SUCCESS('✅ ML model resources cleaned up'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error cleaning up ML resources: {e}'))
        
        # Force garbage collection
        if options['force_cleanup']:
            self.stdout.write('🗑️  Running garbage collection...')
            gc.collect()
            
            # Clear PyTorch cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                self.stdout.write('🔥 Cleared CUDA cache')
        
        # Show memory usage after cleanup
        if options['show_memory']:
            self.show_memory_usage("After cleanup")
        
        self.stdout.write(self.style.SUCCESS('✅ Resource cleanup completed'))
    
    def show_memory_usage(self, label):
        """Show current memory usage."""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            # Convert bytes to MB
            rss_mb = memory_info.rss / 1024 / 1024
            vms_mb = memory_info.vms / 1024 / 1024
            
            self.stdout.write(f'\n📊 Memory Usage ({label}):')
            self.stdout.write(f'   RSS (Physical): {rss_mb:.1f} MB')
            self.stdout.write(f'   VMS (Virtual):  {vms_mb:.1f} MB')
            
            # Show system memory if available
            system_memory = psutil.virtual_memory()
            self.stdout.write(f'   System Available: {system_memory.available / 1024 / 1024:.1f} MB')
            self.stdout.write(f'   System Used: {system_memory.percent:.1f}%')
            
            # Show GPU memory if CUDA is available
            if torch.cuda.is_available():
                gpu_memory = torch.cuda.memory_allocated() / 1024 / 1024
                gpu_cached = torch.cuda.memory_reserved() / 1024 / 1024
                self.stdout.write(f'   GPU Allocated: {gpu_memory:.1f} MB')
                self.stdout.write(f'   GPU Cached: {gpu_cached:.1f} MB')
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Could not get memory info: {e}'))