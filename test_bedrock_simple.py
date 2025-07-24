#!/usr/bin/env python3
"""
Simple AWS Bedrock test with proper .env loading.
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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easyread.settings')
import django
django.setup()


def test_credentials():
    """Test if credentials are loaded properly."""
    print("🔐 Checking AWS Credentials...")
    
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_REGION_NAME', 'us-east-1')
    
    print(f"   Access Key: {access_key[:10]}... ({'✅ Set' if access_key else '❌ Missing'})")
    print(f"   Secret Key: {secret_key[:10]}... ({'✅ Set' if secret_key else '❌ Missing'})")
    print(f"   Region: {region}")
    
    return bool(access_key and secret_key)


def test_litellm_llm():
    """Test LiteLLM with Llama 3.1."""
    print("\n🤖 Testing Llama 3.1 70B via LiteLLM...")
    
    try:
        from litellm import completion
        
        response = completion(
            model="bedrock/meta.llama3-1-70b-instruct-v1:0",
            messages=[{"role": "user", "content": "Respond with exactly: 'AWS Bedrock LLM is working!'"}],
            max_tokens=20,
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip()
        print(f"   ✅ LLM Response: {result}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_litellm_embedding():
    """Test LiteLLM with Cohere embeddings."""
    print("\n📊 Testing Cohere Multilingual Embeddings...")
    
    try:
        from litellm import embedding
        
        response = embedding(
            model="cohere.embed-multilingual-v3",
            input=["Hello world", "Test embedding"]
        )
        
        embeddings = [item.embedding for item in response.data]
        print(f"   ✅ Generated {len(embeddings)} embeddings")
        print(f"   ✅ Dimension: {len(embeddings[0])}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_embedding_provider():
    """Test our custom embedding provider."""
    print("\n🏭 Testing Custom Embedding Provider...")
    
    try:
        from api.embedding_providers.factory import EmbeddingProviderFactory
        
        # Create provider
        provider = EmbeddingProviderFactory.create_provider(
            'cohere_bedrock',
            {'language': 'multilingual'}
        )
        
        # Test availability
        available = provider.is_available()
        print(f"   Provider available: {'✅ Yes' if available else '❌ No'}")
        
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


def main():
    """Run tests."""
    print("🧪 AWS Bedrock Test (Simple)")
    print("=" * 40)
    
    # Test credentials first
    if not test_credentials():
        print("❌ Cannot proceed without AWS credentials")
        return
    
    # Run tests
    llm_result = test_litellm_llm()
    embed_result = test_litellm_embedding()
    provider_result = test_embedding_provider()
    
    # Summary
    print(f"\n📊 Results:")
    print(f"   LLM (Llama 3.1):        {'✅ PASS' if llm_result else '❌ FAIL'}")
    print(f"   Embeddings (Cohere):    {'✅ PASS' if embed_result else '❌ FAIL'}")
    print(f"   Custom Provider:        {'✅ PASS' if provider_result else '❌ FAIL'}")
    
    if all([llm_result, embed_result, provider_result]):
        print("\n🎉 All AWS Bedrock integration tests passed!")
    else:
        print("\n⚠️ Some tests failed. Check error messages above.")


if __name__ == "__main__":
    main()