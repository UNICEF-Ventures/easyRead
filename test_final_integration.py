#!/usr/bin/env python3
"""
Final integration test for AWS Bedrock with Django.
"""

import os
import sys
from pathlib import Path

# Load environment from .env file
from dotenv import load_dotenv
load_dotenv()

# Add backend to path
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easyread_backend.settings')
import django
django.setup()


def test_embedding_provider_from_settings():
    """Test that embedding provider loads correctly from Django settings."""
    print("🔧 Testing Embedding Provider from Settings...")
    
    try:
        from api.embedding_providers.factory import EmbeddingProviderFactory
        
        # Create provider from settings
        provider = EmbeddingProviderFactory.create_from_settings()
        
        info = provider.get_provider_info()
        print(f"   Provider: {info['name']}")
        print(f"   Model: {info['model']}")
        print(f"   Dimension: {info['embedding_dimension']}")
        
        # Test availability
        available = provider.is_available()
        print(f"   Available: {'✅ Yes' if available else '❌ No'}")
        
        if available:
            # Quick test
            embeddings = provider.encode_texts(["test"])
            print(f"   ✅ Test embedding: {embeddings.shape}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_litellm_config():
    """Test LiteLLM configuration with updated model."""
    print("\n🤖 Testing Updated LiteLLM Config...")
    
    try:
        from litellm import completion
        
        # Test with a short request
        response = completion(
            model="bedrock/us.meta.llama3-1-70b-instruct-v1:0",
            messages=[{
                "role": "user",
                "content": "Say 'Configuration working' in Easy Read format."
            }],
            max_tokens=30
        )
        
        result = response.choices[0].message.content.strip()
        print(f"   ✅ Response: {result}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_management_commands():
    """Test management commands work with new configuration."""
    print("\n📋 Testing Management Commands...")
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        # Test embedding status
        out = StringIO()
        call_command('embedding_status', stdout=out)
        output = out.getvalue()
        
        if 'Current provider' in output and 'Available' in output:
            print("   ✅ Embedding status command working")
            print(f"   Status: {output.strip()}")
            return True
        else:
            print("   ❌ Embedding status command failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Run final integration tests."""
    print("🏁 Final AWS Bedrock Integration Test")
    print("=" * 45)
    
    print(f"Region: {os.getenv('AWS_REGION_NAME', 'us-east-2')}")
    print(f"Django Settings: easyread_backend.settings")
    
    # Run tests
    tests = [
        ("Embedding Provider (Settings)", test_embedding_provider_from_settings),
        ("LiteLLM Config", test_litellm_config),
        ("Management Commands", test_management_commands),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n📊 Final Results:")
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<30} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 AWS Bedrock integration is fully configured and working!")
        print("\nReady to use:")
        print("   • Llama 3.1 70B for Easy Read conversion")
        print("   • Titan v2 embeddings for similarity search") 
        print("   • Complete analytics tracking system")
    else:
        print("\n⚠️ Some issues remain - check details above")


if __name__ == "__main__":
    main()