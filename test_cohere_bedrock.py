#!/usr/bin/env python3
"""
Test Cohere models specifically in us-east-1.
"""

import os
import sys
from pathlib import Path

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Add backend to path
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easyread_backend.settings')
import django
django.setup()


def test_cohere_embedding_direct():
    """Test Cohere embedding via LiteLLM directly."""
    print("🔍 Testing Cohere Multilingual Embedding (Direct)...")
    
    try:
        from litellm import embedding
        
        response = embedding(
            model="cohere.embed-multilingual-v3",
            input=["Hello world", "Test embedding", "Easy read document"]
        )
        
        embeddings = [item.embedding for item in response.data]
        print(f"   ✅ Generated {len(embeddings)} embeddings")
        print(f"   ✅ Dimension: {len(embeddings[0])}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_cohere_english_embedding():
    """Test Cohere English embedding."""
    print("\n🔍 Testing Cohere English Embedding...")
    
    try:
        from litellm import embedding
        
        response = embedding(
            model="cohere.embed-english-v3",
            input=["Hello world", "Test embedding"]
        )
        
        embeddings = [item.embedding for item in response.data]
        print(f"   ✅ Generated {len(embeddings)} embeddings")
        print(f"   ✅ Dimension: {len(embeddings[0])}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_cohere_provider():
    """Test our Cohere Bedrock provider."""
    print("\n🏭 Testing Cohere Bedrock Provider...")
    
    try:
        from api.embedding_providers.factory import EmbeddingProviderFactory
        
        # Create Cohere provider
        provider = EmbeddingProviderFactory.create_provider(
            'cohere_bedrock',
            {'language': 'multilingual'}
        )
        
        info = provider.get_provider_info()
        print(f"   Provider: {info['name']}")
        print(f"   Model: {info['model']}")
        print(f"   Dimension: {info['embedding_dimension']}")
        
        # Test availability
        available = provider.is_available()
        print(f"   Available: {'✅ Yes' if available else '❌ No'}")
        
        if available:
            # Test encoding
            texts = ["Easy read document", "Accessible content"]
            embeddings = provider.encode_texts(texts)
            print(f"   ✅ Encoded texts: {embeddings.shape}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_provider_from_settings():
    """Test provider created from Django settings."""
    print("\n⚙️ Testing Provider from Settings...")
    
    try:
        from api.embedding_providers.factory import EmbeddingProviderFactory
        
        provider = EmbeddingProviderFactory.create_from_settings()
        
        info = provider.get_provider_info()
        print(f"   Settings Provider: {info['name']}")
        print(f"   Model: {info['model']}")
        
        available = provider.is_available()
        print(f"   Available: {'✅ Yes' if available else '❌ No'}")
        
        return available
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Test Cohere models in us-east-1."""
    print("🧪 Cohere Bedrock Test (us-east-1)")
    print("=" * 40)
    
    print(f"Region: {os.getenv('AWS_REGION_NAME')}")
    print(f"Access Key: {os.getenv('AWS_ACCESS_KEY_ID', 'Not set')[:10]}...")
    
    # Run tests
    tests = [
        ("Cohere Multilingual (Direct)", test_cohere_embedding_direct),
        ("Cohere English (Direct)", test_cohere_english_embedding),
        ("Cohere Provider", test_cohere_provider),
        ("Provider from Settings", test_provider_from_settings),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n📊 Results:")
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<30} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == 0:
        print("\n⚠️ Model Access Required:")
        print("   1. Go to AWS Bedrock Console")
        print("   2. Navigate to 'Model access'")
        print("   3. Request access to:")
        print("      - Cohere: Embed Multilingual")
        print("      - Cohere: Embed English") 
        print("      - Meta: Llama 3.1 models")
        print("   4. Wait for approval (usually instant)")
    elif passed == total:
        print("🎉 Cohere Bedrock integration working!")
    else:
        print("⚠️ Partial success - check model access settings")


if __name__ == "__main__":
    main()