"""
Management command to diagnose and clean up semaphore leaks.
"""

import logging
from django.core.management.base import BaseCommand
from django.utils.termcolors import make_style

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Diagnose and clean up semaphore leaks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Perform cleanup of resources',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.cleanup = options['cleanup']
        
        # Style definitions
        self.success_style = make_style(opts=('bold',), fg='green')
        self.warning_style = make_style(opts=('bold',), fg='yellow')
        self.error_style = make_style(opts=('bold',), fg='red')
        
        self.stdout.write(self.success_style('🔍 Semaphore Leak Diagnosis'))
        self.stdout.write('=' * 50)
        
        # Check current multiprocessing resources
        self.check_multiprocessing_resources()
        
        # Check OpenCLIP resources
        self.check_openclip_resources()
        
        # Check PyTorch resources
        self.check_pytorch_resources()
        
        if self.cleanup:
            self.stdout.write(self.warning_style('🧹 Performing cleanup...'))
            self.perform_cleanup()
        
        self.stdout.write(self.success_style('✅ Diagnosis completed'))

    def check_multiprocessing_resources(self):
        """Check multiprocessing resources for potential leaks."""
        try:
            import multiprocessing
            import multiprocessing.synchronize
            import multiprocessing.resource_tracker
            
            self.stdout.write(self.success_style('📊 Multiprocessing Resources:'))
            
            # Check semaphore tracker
            if hasattr(multiprocessing.synchronize, '_semaphore_tracker'):
                tracker = multiprocessing.synchronize._semaphore_tracker
                self.stdout.write(f'  Semaphore tracker: {tracker}')
                
                if hasattr(tracker, '_lock'):
                    self.stdout.write(f'  Tracker lock: {tracker._lock}')
                    
                if hasattr(tracker, '_cache'):
                    cache_size = len(tracker._cache) if tracker._cache else 0
                    self.stdout.write(f'  Tracker cache size: {cache_size}')
            
            # Check resource tracker
            if hasattr(multiprocessing.resource_tracker, '_resource_tracker'):
                tracker = multiprocessing.resource_tracker._resource_tracker
                self.stdout.write(f'  Resource tracker: {tracker}')
                
                if hasattr(tracker, '_lock'):
                    self.stdout.write(f'  Resource tracker lock: {tracker._lock}')
            
            # Check for active processes
            active_children = multiprocessing.active_children()
            self.stdout.write(f'  Active children: {len(active_children)}')
            
            if self.verbose:
                for child in active_children:
                    self.stdout.write(f'    - {child.name} (PID: {child.pid})')
                    
        except Exception as e:
            self.stdout.write(self.error_style(f'❌ Error checking multiprocessing resources: {e}'))

    def check_openclip_resources(self):
        """Check OpenCLIP resources."""
        try:
            import open_clip
            
            self.stdout.write(self.success_style('🖼️ OpenCLIP Resources:'))
            
            # Check for cached models
            if hasattr(open_clip, '_CACHE'):
                cache_size = len(open_clip._CACHE) if open_clip._CACHE else 0
                self.stdout.write(f'  OpenCLIP cache size: {cache_size}')
                
                if self.verbose and open_clip._CACHE:
                    for key in open_clip._CACHE:
                        self.stdout.write(f'    - {key}')
            
            # Check for model registry
            if hasattr(open_clip, '_MODEL_REGISTRY'):
                registry_size = len(open_clip._MODEL_REGISTRY) if open_clip._MODEL_REGISTRY else 0
                self.stdout.write(f'  Model registry size: {registry_size}')
                
        except ImportError:
            self.stdout.write(self.warning_style('⚠️ OpenCLIP not available'))
        except Exception as e:
            self.stdout.write(self.error_style(f'❌ Error checking OpenCLIP resources: {e}'))

    def check_pytorch_resources(self):
        """Check PyTorch resources."""
        try:
            import torch
            
            self.stdout.write(self.success_style('🔥 PyTorch Resources:'))
            
            # Check CUDA status
            if torch.cuda.is_available():
                self.stdout.write(f'  CUDA available: Yes')
                self.stdout.write(f'  CUDA devices: {torch.cuda.device_count()}')
                
                # Check memory usage
                for i in range(torch.cuda.device_count()):
                    allocated = torch.cuda.memory_allocated(i) / 1024 / 1024
                    cached = torch.cuda.memory_reserved(i) / 1024 / 1024
                    self.stdout.write(f'    Device {i}: {allocated:.1f}MB allocated, {cached:.1f}MB cached')
            else:
                self.stdout.write(f'  CUDA available: No')
            
            # Check for multiprocessing settings
            if hasattr(torch, 'multiprocessing'):
                mp = torch.multiprocessing
                self.stdout.write(f'  PyTorch multiprocessing: {mp}')
                
                if hasattr(mp, 'get_all_sharing_strategies'):
                    strategies = mp.get_all_sharing_strategies()
                    self.stdout.write(f'  Sharing strategies: {strategies}')
                    
        except ImportError:
            self.stdout.write(self.warning_style('⚠️ PyTorch not available'))
        except Exception as e:
            self.stdout.write(self.error_style(f'❌ Error checking PyTorch resources: {e}'))

    def perform_cleanup(self):
        """Perform comprehensive cleanup."""
        try:
            # Clean up embedding model
            from api.embedding_utils import cleanup_embedding_model, force_cleanup_openclip_resources
            cleanup_embedding_model()
            
            # Force cleanup of OpenCLIP resources
            force_cleanup_openclip_resources()
            
            # Clean up similarity searcher
            from api.similarity_search import cleanup_similarity_searcher
            cleanup_similarity_searcher()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            self.stdout.write(self.success_style('✅ Cleanup completed'))
            
        except Exception as e:
            self.stdout.write(self.error_style(f'❌ Error during cleanup: {e}'))