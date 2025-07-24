#!/usr/bin/env python3
"""
Test AWS Bedrock with available models (Llama inference profile + Titan embeddings).
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


def test_llama_inference_profile():
    """Test Llama 3.1 70B with correct inference profile."""
    print("🦙 Testing Llama 3.1 70B (Inference Profile)...")
    
    try:
        from litellm import completion
        
        response = completion(
            model="bedrock/us.meta.llama3-1-70b-instruct-v1:0",
            messages=[{
                "role": "user", 
                "content": "Convert this to Easy Read: 'The meeting will be held tomorrow at 3 PM in the conference room.'"
            }],
            max_tokens=100,
            temperature=0.3
        )
        
        result = response.choices[0].message.content.strip()
        print(f"   ✅ LLM Response: {result[:100]}...")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_titan_embeddings():
    """Test Amazon Titan embeddings."""
    print("\n🏛️ Testing Amazon Titan Embeddings...")
    
    try:
        from litellm import embedding
        
        response = embedding(
            model="amazon.titan-embed-text-v2:0",
            input=["Easy read document", "Accessible content", "UNICEF supports children"]
        )
        
        embeddings = [item.embedding for item in response.data]
        print(f"   ✅ Generated {len(embeddings)} embeddings")
        print(f"   ✅ Dimension: {len(embeddings[0])}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_titan_provider():
    """Test Titan embedding provider."""
    print("\n🔧 Testing Titan Embedding Provider...")
    
    try:
        from api.embedding_providers.factory import EmbeddingProviderFactory
        
        # Create Titan provider
        provider = EmbeddingProviderFactory.create_provider(
            'titan',
            {'version': 'v2'}
        )
        
        print(f"   Provider info: {provider.get_provider_info()}")
        
        # Test availability
        available = provider.is_available()
        print(f"   Available: {'✅ Yes' if available else '❌ No'}")
        
        if available:
            # Test encoding
            texts = ["Easy read document", "Clear and simple text"]
            embeddings = provider.encode_texts(texts)
            print(f"   ✅ Encoded {len(texts)} texts to {embeddings.shape} embeddings")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_full_workflow():
    """Test a complete workflow with the working models."""
    print("\n🔄 Testing Complete Easy Read Workflow...")
    
    try:
        from api.views import EasyReadProcessor
        
        # Create processor with updated config
        processor = EasyReadProcessor()
        
        # Test with simple content
        test_content = """
        # Meeting Information
        
        The monthly team meeting will be held tomorrow at 3 PM in the conference room.
        Please bring your project reports and be prepared to discuss your progress.
        """
        
        # Process content (this will use the updated Llama model)
        result = processor.process_content(test_content)
        
        if result and 'easy_read_sentences' in result:
            sentences = result['easy_read_sentences']
            print(f"   ✅ Generated {len(sentences)} Easy Read sentences")
            print(f"   ✅ First sentence: {sentences[0]['sentence']}")
            return True
        else:
            print("   ❌ Failed to process content")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Run all tests with working models."""
    print("🧪 AWS Bedrock Test (Working Models)")
    print("=" * 45)
    
    print(f"Region: {os.getenv('AWS_REGION_NAME', 'us-east-1')}")
    print(f"Access Key: {os.getenv('AWS_ACCESS_KEY_ID', 'Not set')[:10]}...")
    
    # Run tests
    tests = [
        ("Llama 3.1 70B (Inference Profile)", test_llama_inference_profile),
        ("Titan Embeddings (v2)", test_titan_embeddings),
        ("Titan Provider", test_titan_provider),
        ("Full Workflow", test_full_workflow),
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
    passed = 0
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<35} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 AWS Bedrock integration fully working!")
    elif passed > 0:
        print("⚠️ Partial success - some components working")
    else:
        print("❌ No tests passed - check configuration")


if __name__ == "__main__":
    main()