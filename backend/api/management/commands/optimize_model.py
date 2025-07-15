"""
Management command to help optimize model selection based on system resources.
"""

import logging
from django.core.management.base import BaseCommand
from django.utils.termcolors import make_style
from api.model_config import ModelConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Optimize embedding model selection based on system resources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list-models',
            action='store_true',
            help='List all available models',
        )
        parser.add_argument(
            '--recommend',
            action='store_true',
            help='Recommend optimal model for current system',
        )
        parser.add_argument(
            '--test-model',
            type=str,
            help='Test a specific model size (tiny, small, medium, large)',
        )
        parser.add_argument(
            '--memory-check',
            action='store_true',
            help='Check current memory usage',
        )

    def handle(self, *args, **options):
        # Style definitions
        self.success_style = make_style(opts=('bold',), fg='green')
        self.warning_style = make_style(opts=('bold',), fg='yellow')
        self.error_style = make_style(opts=('bold',), fg='red')
        self.info_style = make_style(opts=('bold',), fg='blue')
        
        self.stdout.write(self.success_style('🧠 EasyRead Model Optimizer'))
        self.stdout.write('=' * 50)
        
        if options['list_models']:
            self.list_models()
        
        if options['memory_check']:
            self.check_memory()
        
        if options['recommend']:
            self.recommend_model()
        
        if options['test_model']:
            self.test_model(options['test_model'])

    def list_models(self):
        """List all available model configurations."""
        self.stdout.write(self.info_style('\n📋 Available Models:'))
        
        models = ModelConfig.list_available_models()
        
        for size, config in models.items():
            default_marker = ' (DEFAULT)' if config['is_default'] else ''
            memory_gb = config['memory_mb'] / 1024
            
            self.stdout.write(f"\n  🔹 {size.upper()}{default_marker}")
            self.stdout.write(f"     Model: {config['model_name']}")
            self.stdout.write(f"     Memory: ~{memory_gb:.1f}GB")
            self.stdout.write(f"     Description: {config['description']}")

    def check_memory(self):
        """Check current system memory."""
        try:
            import psutil
            import os
            
            self.stdout.write(self.info_style('\n💾 System Memory Status:'))
            
            # System memory
            memory = psutil.virtual_memory()
            total_gb = memory.total / 1024 / 1024 / 1024
            available_gb = memory.available / 1024 / 1024 / 1024
            used_gb = memory.used / 1024 / 1024 / 1024
            
            self.stdout.write(f"  Total Memory: {total_gb:.1f}GB")
            self.stdout.write(f"  Used Memory: {used_gb:.1f}GB ({memory.percent:.1f}%)")
            self.stdout.write(f"  Available Memory: {available_gb:.1f}GB")
            
            # Current process
            process = psutil.Process(os.getpid())
            process_memory_mb = process.memory_info().rss / 1024 / 1024
            
            self.stdout.write(f"  Current Process: {process_memory_mb:.1f}MB")
            
            # Memory recommendations
            if available_gb > 12:
                self.stdout.write(self.success_style("  ✅ Sufficient memory for all models"))
            elif available_gb > 3:
                self.stdout.write(self.warning_style("  ⚠️ Use medium or smaller models"))
            elif available_gb > 1:
                self.stdout.write(self.warning_style("  ⚠️ Use small or tiny models only"))
            else:
                self.stdout.write(self.error_style("  ❌ Very low memory - use tiny model only"))
                
        except ImportError:
            self.stdout.write(self.error_style("psutil not available - cannot check memory"))

    def recommend_model(self):
        """Recommend optimal model for current system."""
        try:
            import psutil
            import os
            
            self.stdout.write(self.info_style('\n🎯 Model Recommendation:'))
            
            # Get available memory
            available_memory = psutil.virtual_memory().available / 1024 / 1024  # MB
            
            # Get current process memory
            process = psutil.Process(os.getpid())
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Calculate free memory for model
            free_memory = available_memory - current_memory
            
            recommended_size = ModelConfig.recommend_model_for_memory(free_memory)
            config = ModelConfig.list_available_models()[recommended_size]
            
            self.stdout.write(f"  Available for Model: {free_memory:.0f}MB")
            self.stdout.write(f"  Recommended Size: {recommended_size.upper()}")
            self.stdout.write(f"  Model: {config['model_name']}")
            self.stdout.write(f"  Expected Memory: ~{config['memory_mb']}MB")
            self.stdout.write(f"  Description: {config['description']}")
            
            # Configuration instructions
            self.stdout.write(self.success_style('\n⚙️ To use this model:'))
            self.stdout.write('  Add to your Django settings:')
            self.stdout.write(f"  EMBEDDING_MODEL_SIZE = '{recommended_size}'")
            
        except ImportError:
            self.stdout.write(self.error_style("psutil not available - cannot recommend model"))

    def test_model(self, model_size):
        """Test loading a specific model."""
        if model_size not in ModelConfig.MODELS:
            self.stdout.write(self.error_style(f"Invalid model size: {model_size}"))
            self.stdout.write("Available sizes: " + ", ".join(ModelConfig.MODELS.keys()))
            return
        
        self.stdout.write(self.info_style(f'\n🧪 Testing {model_size.upper()} model:'))
        
        try:
            import psutil
            import os
            
            # Get memory before
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024
            
            self.stdout.write(f"  Memory before: {memory_before:.1f}MB")
            
            # Test model loading
            from api.embedding_utils import temporary_model
            
            self.stdout.write("  Loading model...")
            
            with temporary_model(model_size=model_size) as model:
                memory_after = process.memory_info().rss / 1024 / 1024
                memory_used = memory_after - memory_before
                
                self.stdout.write(f"  Memory after: {memory_after:.1f}MB")
                self.stdout.write(f"  Memory used: {memory_used:.1f}MB")
                
                # Test encoding
                self.stdout.write("  Testing text encoding...")
                embeddings = model.encode_texts(['Hello world'])
                
                if embeddings is not None and len(embeddings) > 0:
                    self.stdout.write(self.success_style("  ✅ Model test successful"))
                    self.stdout.write(f"  Embedding dimension: {embeddings.shape[1]}")
                else:
                    self.stdout.write(self.error_style("  ❌ Model test failed"))
            
            # Memory after cleanup
            memory_final = process.memory_info().rss / 1024 / 1024
            self.stdout.write(f"  Memory after cleanup: {memory_final:.1f}MB")
            
        except Exception as e:
            self.stdout.write(self.error_style(f"  ❌ Model test failed: {e}"))