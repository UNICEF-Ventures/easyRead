"""
Management command to validate embedding API keys and connectivity.
"""

from django.core.management.base import BaseCommand, CommandError
from api.embedding_providers.factory import EmbeddingProviderFactory, auto_configure_provider, ProviderError
import logging
import os

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Validate embedding API keys and connectivity'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            help='Test specific provider (optional)',
            choices=['openai', 'cohere', 'cohere_bedrock', 'titan', 'bedrock']
        )
        parser.add_argument(
            '--test-embedding',
            action='store_true',
            help='Test actual embedding generation',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 Validating Embedding API Configuration...'))
        
        # Check environment variables
        self.check_environment_variables()
        
        # Test auto-configuration
        try:
            config = auto_configure_provider()
            provider_name = config.get('provider', 'unknown')
            self.stdout.write(
                self.style.SUCCESS(f"✅ Auto-configuration successful: {provider_name}")
            )
        except ProviderError as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Auto-configuration failed: {e}")
            )
            raise CommandError(f"API validation failed: {e}")
        
        # Test specific provider if requested
        if options['provider']:
            self.test_provider(options['provider'], options['test_embedding'])
        else:
            # Test the auto-configured provider
            self.test_provider(provider_name, options['test_embedding'])
        
        self.stdout.write(self.style.SUCCESS('🎉 All API validations passed!'))

    def check_environment_variables(self):
        """Check for required environment variables."""
        self.stdout.write('🔧 Checking environment variables...')
        
        # Check for any valid API key combination
        aws_access = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        cohere_key = os.getenv('COHERE_API_KEY')
        
        found_keys = []
        
        if aws_access and aws_secret:
            found_keys.append('AWS Bedrock (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)')
            region = os.getenv('AWS_REGION_NAME', 'us-east-1')
            self.stdout.write(f"  ✅ AWS credentials found (region: {region})")
        
        if openai_key:
            found_keys.append('OpenAI (OPENAI_API_KEY)')
            masked_key = openai_key[:8] + '...' + openai_key[-4:] if len(openai_key) > 12 else '***'
            self.stdout.write(f"  ✅ OpenAI API key found ({masked_key})")
        
        if cohere_key:
            found_keys.append('Cohere (COHERE_API_KEY)')
            masked_key = cohere_key[:8] + '...' + cohere_key[-4:] if len(cohere_key) > 12 else '***'
            self.stdout.write(f"  ✅ Cohere API key found ({masked_key})")
        
        if not found_keys:
            self.stdout.write(
                self.style.ERROR('  ❌ No API keys found! Please set one of:')
            )
            self.stdout.write('     - AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY')
            self.stdout.write('     - OPENAI_API_KEY') 
            self.stdout.write('     - COHERE_API_KEY')
            raise CommandError("No valid API keys found")
        
        self.stdout.write(f"  📋 Available providers: {', '.join(found_keys)}")

    def test_provider(self, provider_name, test_embedding=False):
        """Test a specific provider."""
        self.stdout.write(f'🧪 Testing provider: {provider_name}')
        
        try:
            # Create provider instance
            provider = EmbeddingProviderFactory.create_provider(provider_name)
            
            # Check if available
            if not provider.is_available():
                raise ProviderError(f"Provider {provider_name} reports not available")
            
            self.stdout.write(f"  ✅ Provider {provider_name} initialized successfully")
            
            # Get provider metadata
            try:
                metadata = provider.get_model_metadata()
                self.stdout.write(f"  📊 Model: {metadata.get('model_name', 'unknown')}")
                self.stdout.write(f"  📊 Dimensions: {metadata.get('embedding_dimension', 'unknown')}")
                self.stdout.write(f"  📊 Provider: {metadata.get('provider_name', 'unknown')}")
            except Exception as e:
                self.stdout.write(f"  ⚠️ Could not get metadata: {e}")
            
            # Test embedding generation if requested
            if test_embedding:
                self.stdout.write('  🔄 Testing embedding generation...')
                try:
                    test_text = "This is a test sentence for embedding generation."
                    embedding = provider.encode_single_text(test_text)
                    if embedding is not None and len(embedding) > 0:
                        self.stdout.write(f"  ✅ Embedding generated successfully ({len(embedding)} dimensions)")
                    else:
                        raise Exception("Embedding generation returned empty result")
                except Exception as e:
                    self.stdout.write(f"  ❌ Embedding generation failed: {e}")
                    raise CommandError(f"Embedding test failed for {provider_name}: {e}")
            
            # Clean up
            provider.cleanup()
            
        except Exception as e:
            self.stdout.write(f"  ❌ Provider {provider_name} failed: {e}")
            raise CommandError(f"Provider validation failed: {e}")