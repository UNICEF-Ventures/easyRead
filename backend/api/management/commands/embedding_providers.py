"""
Management command for embedding provider configuration and testing.
"""

import logging
from django.core.management.base import BaseCommand
from django.utils.termcolors import make_style
from api.embedding_providers import list_available_providers
from api.embedding_adapter import test_provider, get_provider_info

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage and test embedding providers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available providers',
        )
        parser.add_argument(
            '--test',
            type=str,
            help='Test a specific provider (openclip, openai, cohere)',
        )
        parser.add_argument(
            '--current',
            action='store_true',
            help='Show current provider information',
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key for testing API-based providers',
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Model name for testing',
        )
        parser.add_argument(
            '--config-example',
            type=str,
            help='Show configuration example for a provider',
        )

    def handle(self, *args, **options):
        # Style definitions
        self.success_style = make_style(opts=('bold',), fg='green')
        self.warning_style = make_style(opts=('bold',), fg='yellow')
        self.error_style = make_style(opts=('bold',), fg='red')
        self.info_style = make_style(opts=('bold',), fg='blue')
        
        self.stdout.write(self.success_style('🤖 Embedding Provider Manager'))
        self.stdout.write('=' * 50)
        
        if options['list']:
            self.list_providers()
        
        if options['current']:
            self.show_current_provider()
        
        if options['test']:
            self.test_provider(options['test'], options.get('api_key'), options.get('model'))
        
        if options['config_example']:
            self.show_config_example(options['config_example'])

    def list_providers(self):
        """List all available providers."""
        self.stdout.write(self.info_style('\n📋 Available Providers:'))
        
        providers = list_available_providers()
        
        for name, info in providers.items():
            if info.get('error'):
                self.stdout.write(f"\n  ❌ {name.upper()}")
                self.stdout.write(f"     Error: {info['error']}")
            else:
                self.stdout.write(f"\n  ✅ {name.upper()}")
                self.stdout.write(f"     Class: {info.get('class', 'Unknown')}")
                self.stdout.write(f"     Supports Text: {info.get('supports_texts', 'Unknown')}")
                self.stdout.write(f"     Supports Images: {info.get('supports_images', 'Unknown')}")

    def show_current_provider(self):
        """Show information about the current provider."""
        self.stdout.write(self.info_style('\n🔍 Current Provider:'))
        
        try:
            info = get_provider_info()
            
            if info.get('error'):
                self.stdout.write(self.error_style(f"  Error: {info['error']}"))
                return
            
            self.stdout.write(f"  Name: {info.get('name', 'Unknown')}")
            self.stdout.write(f"  Type: {info.get('type', 'Unknown')}")
            
            if info.get('model'):
                self.stdout.write(f"  Model: {info['model']}")
            elif info.get('model_name'):
                self.stdout.write(f"  Model: {info['model_name']}")
            
            self.stdout.write(f"  Embedding Dimension: {info.get('embedding_dimension', 'Unknown')}")
            self.stdout.write(f"  Supports Images: {info.get('supports_images', False)}")
            self.stdout.write(f"  Supports Texts: {info.get('supports_texts', False)}")
            
            if info.get('estimated_memory_mb'):
                memory_gb = info['estimated_memory_mb'] / 1024
                self.stdout.write(f"  Estimated Memory: ~{memory_gb:.1f}GB")
            
            if info.get('device'):
                self.stdout.write(f"  Device: {info['device']}")
                
        except Exception as e:
            self.stdout.write(self.error_style(f"  Error getting provider info: {e}"))

    def test_provider(self, provider_name: str, api_key: str = None, model: str = None):
        """Test a specific provider."""
        self.stdout.write(self.info_style(f'\n🧪 Testing {provider_name.upper()} Provider:'))
        
        # Build configuration
        config = {}
        
        if provider_name in ['openai', 'openai_vision']:
            if not api_key:
                self.stdout.write(self.error_style("  API key required for OpenAI provider"))
                self.stdout.write("  Use: --api-key YOUR_OPENAI_KEY")
                return
            
            config['api_key'] = api_key
            if model:
                config['model'] = model
                
        elif provider_name == 'cohere':
            if not api_key:
                self.stdout.write(self.error_style("  API key required for Cohere provider"))
                self.stdout.write("  Use: --api-key YOUR_COHERE_KEY")
                return
            
            config['api_key'] = api_key
            if model:
                config['model'] = model
                
        elif provider_name == 'openclip':
            if model:
                # For OpenCLIP, model parameter could be model_size
                if model in ['tiny', 'small', 'medium', 'large']:
                    config['model_size'] = model
                else:
                    config['model_name'] = model
        
        # Run test
        try:
            result = test_provider(provider_name, config)
            
            if result['success']:
                self.stdout.write(self.success_style("  ✅ Provider test successful!"))
                
                info = result['provider_info']
                self.stdout.write(f"  Provider: {info.get('name', 'Unknown')}")
                self.stdout.write(f"  Type: {info.get('type', 'Unknown')}")
                self.stdout.write(f"  Embedding Dimension: {info.get('embedding_dimension', 'Unknown')}")
                
                if result.get('text_embedding_shape'):
                    self.stdout.write(f"  Text Embedding Shape: {result['text_embedding_shape']}")
                
                if result.get('image_embedding_shape'):
                    self.stdout.write(f"  Image Embedding Shape: {result['image_embedding_shape']}")
                elif not result.get('supports_images'):
                    self.stdout.write("  Image Support: Not available")
                
                # Show additional info for specific providers
                if provider_name in ['openai', 'cohere']:
                    cost = info.get('cost_per_1k_tokens') or info.get('cost_estimate')
                    if cost:
                        self.stdout.write(f"  Cost: {cost}")
                
            else:
                self.stdout.write(self.error_style(f"  ❌ Provider test failed: {result['error']}"))
                
        except Exception as e:
            self.stdout.write(self.error_style(f"  ❌ Test error: {e}"))

    def show_config_example(self, provider_name: str):
        """Show configuration example for a provider."""
        self.stdout.write(self.info_style(f'\n⚙️ Configuration Example for {provider_name.upper()}:'))
        
        if provider_name == 'openclip':
            self.stdout.write("""
# Django settings.py
EMBEDDING_PROVIDER_CONFIG = {
    'provider': 'openclip',
    'config': {
        'model_size': 'tiny',  # or 'small', 'medium', 'large'
        # OR specify exact model:
        # 'model_name': 'ViT-B-32',
        # 'pretrained': 'openai',
        'device': 'auto',  # or 'cpu', 'cuda'
        'batch_size_images': 8,
        'batch_size_texts': 16
    }
}

# Environment variables (optional)
export EMBEDDING_MODEL_SIZE=tiny
            """)
            
        elif provider_name == 'openai':
            self.stdout.write("""
# Django settings.py
EMBEDDING_PROVIDER_CONFIG = {
    'provider': 'openai',
    'config': {
        'api_key': 'your-openai-api-key',
        'model': 'text-embedding-3-small',  # or text-embedding-3-large
        'batch_size': 100,
        'rate_limit_delay': 0.1,
        'max_retries': 3
    }
}

# Environment variables
export OPENAI_API_KEY=your-openai-api-key

# Cost: ~$0.00002 per 1K tokens (text-embedding-3-small)
# Memory: ~0MB (API-based)
            """)
            
        elif provider_name == 'openai_vision':
            self.stdout.write("""
# Django settings.py
EMBEDDING_PROVIDER_CONFIG = {
    'provider': 'openai_vision',
    'config': {
        'api_key': 'your-openai-api-key',
        'vision_model': 'gpt-4-vision-preview',
        'embedding_model': 'text-embedding-3-small',
        'description_prompt': 'Describe this image for search purposes.',
        'batch_size': 50,
        'rate_limit_delay': 0.2
    }
}

# Note: Uses GPT-4 Vision to describe images, then embeds descriptions
# Higher cost but supports both text and images
            """)
            
        elif provider_name == 'cohere':
            self.stdout.write("""
# Django settings.py
EMBEDDING_PROVIDER_CONFIG = {
    'provider': 'cohere',
    'config': {
        'api_key': 'your-cohere-api-key',
        'model': 'embed-english-v3.0',  # or embed-multilingual-v3.0
        'input_type': 'search_document',
        'batch_size': 96,
        'rate_limit_delay': 0.1,
        'max_retries': 3
    }
}

# Environment variables
export COHERE_API_KEY=your-cohere-api-key

# Memory: ~0MB (API-based)
            """)
            
        else:
            self.stdout.write(f"  No configuration example available for '{provider_name}'")
            self.stdout.write("  Available providers: openclip, openai, openai_vision, cohere")

        # Show automatic configuration info
        self.stdout.write(self.warning_style('\n💡 Automatic Configuration:'))
        self.stdout.write("""
# The system can automatically choose the best provider:
from api.embedding_providers.factory import auto_configure_provider

config = auto_configure_provider()
# This will:
# 1. Use OpenAI if OPENAI_API_KEY is set
# 2. Use Cohere if COHERE_API_KEY is set  
# 3. Fall back to OpenCLIP with optimal model size for your system
        """)