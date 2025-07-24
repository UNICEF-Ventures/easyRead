#!/usr/bin/env python3
"""
Comprehensive AWS Bedrock integration test script.
Tests both LLM and embedding functionality.
"""

import os
import sys
import django
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easyread.settings')
django.setup()

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import requests
import json
from api.embedding_providers.factory import EmbeddingProviderFactory


def test_aws_credentials():
    """Test basic AWS credentials and access."""
    print("🔐 Testing AWS Credentials...")
    
    try:
        # Get credentials from environment
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_REGION_NAME', 'us-east-1')
        
        print(f"   Access Key: {'✅ Set' if access_key else '❌ Missing'}")
        print(f"   Secret Key: {'✅ Set' if secret_key else '❌ Missing'}")
        print(f"   Region: {region}")
        
        if not access_key or not secret_key:
            print("❌ AWS credentials not found in environment")
            return False
        
        # Test basic AWS access
        sts_client = boto3.client(
            'sts',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        identity = sts_client.get_caller_identity()
        print(f"   Account ID: {identity.get('Account', 'Unknown')}")
        print(f"   User ARN: {identity.get('Arn', 'Unknown')}")
        print("✅ AWS credentials valid")
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not configured")
        return False
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"❌ AWS error: {error_code} - {e.response['Error']['Message']}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_bedrock_access():
    """Test AWS Bedrock service access."""
    print("\n🏗️ Testing AWS Bedrock Access...")
    
    try:
        region = os.getenv('AWS_REGION_NAME', 'us-east-1')
        bedrock_client = boto3.client('bedrock', region_name=region)
        
        # List available foundation models
        response = bedrock_client.list_foundation_models()
        models = response.get('modelSummaries', [])
        
        print(f"   Found {len(models)} available models")
        
        # Check for Llama models
        llama_models = [m for m in models if 'llama' in m['modelId'].lower()]
        print(f"   Llama models available: {len(llama_models)}")
        
        # Check for Cohere embedding models
        cohere_models = [m for m in models if 'cohere' in m['modelId'].lower() and 'embed' in m['modelId'].lower()]
        print(f"   Cohere embedding models: {len(cohere_models)}")
        
        if llama_models:
            print("   ✅ Llama models found:")
            for model in llama_models[:3]:  # Show first 3
                print(f"      - {model['modelId']}")
        
        if cohere_models:
            print("   ✅ Cohere embedding models found:")
            for model in cohere_models:
                print(f"      - {model['modelId']}")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'UnauthorizedOperation':
            print("❌ Access denied to Bedrock. Check IAM permissions.")
        else:
            print(f"❌ Bedrock error: {error_code} - {e.response['Error']['Message']}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_litellm_integration():
    """Test LiteLLM with AWS Bedrock."""
    print("\n🤖 Testing LiteLLM Integration...")
    
    try:
        from litellm import completion, embedding
        
        # Test Llama 3.1 70B
        print("   Testing Llama 3.1 70B...")
        response = completion(
            model="bedrock/meta.llama3-1-70b-instruct-v1:0",
            messages=[{"role": "user", "content": "Say 'Hello from AWS Bedrock'"}],
            max_tokens=50
        )
        
        print(f"   ✅ LLM Response: {response.choices[0].message.content}")
        
        # Test Cohere embedding
        print("   Testing Cohere Multilingual embedding...")
        embed_response = embedding(
            model="cohere.embed-multilingual-v3",
            input=["Hello", "World", "Test embedding"]
        )
        
        embeddings = [item.embedding for item in embed_response.data]
        print(f"   ✅ Generated {len(embeddings)} embeddings, dimension: {len(embeddings[0])}")
        
        return True
        
    except ImportError as e:
        print(f"❌ LiteLLM import error: {e}")
        return False
    except Exception as e:
        print(f"❌ LiteLLM error: {e}")
        return False


def test_embedding_provider():
    """Test our custom embedding provider."""
    print("\n📊 Testing Custom Embedding Provider...")
    
    try:
        # Create Cohere Bedrock provider
        provider = EmbeddingProviderFactory.create_provider(
            'cohere_bedrock',
            {'language': 'multilingual'}
        )
        
        print(f"   Provider info: {provider.get_provider_info()}")
        
        # Test availability
        if provider.is_available():
            print("   ✅ Provider is available")
        else:
            print("   ❌ Provider is not available")
            return False
        
        # Test text encoding
        test_texts = [
            "This is a test document",
            "EasyRead makes documents accessible",
            "UNICEF supports children worldwide"
        ]
        
        embeddings = provider.encode_texts(test_texts)
        print(f"   ✅ Encoded {len(test_texts)} texts to {embeddings.shape} embeddings")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding provider error: {e}")
        return False


def test_api_endpoints():
    """Test API endpoints with analytics tracking."""
    print("\n🌐 Testing API Endpoints...")
    
    try:
        # Start the server in a separate process or assume it's running
        base_url = "http://localhost:8000/api"
        
        # Test health check
        response = requests.get(f"{base_url}/health/", timeout=5)
        if response.status_code == 200:
            print("   ✅ API server is running")
        else:
            print(f"   ❌ API server not responding: {response.status_code}")
            return False
        
        # Test embedding endpoint
        embed_data = {
            "texts": ["Test text for embedding"]
        }
        
        response = requests.post(f"{base_url}/embed-texts/", json=embed_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Embedding API working: {len(result.get('embeddings', []))} embeddings")
        else:
            print(f"   ❌ Embedding API error: {response.status_code}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("   ⚠️ API server not running (this is optional)")
        return True  # Don't fail the test if server isn't running
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 AWS Bedrock Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("AWS Credentials", test_aws_credentials),
        ("Bedrock Access", test_bedrock_access),
        ("LiteLLM Integration", test_litellm_integration),
        ("Embedding Provider", test_embedding_provider),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n📊 Test Results Summary")
    print("=" * 30)
    
    passed = 0
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{test_name:.<25} {status}")
        if passed_test:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! AWS Bedrock integration is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the details above for troubleshooting.")
        
        # Provide troubleshooting hints
        if not results.get("AWS Credentials", False):
            print("\n💡 Troubleshooting hints:")
            print("   - Verify AWS credentials in .env file")
            print("   - Check if credentials have expired")
            print("   - Ensure proper IAM permissions")
        
        if not results.get("Bedrock Access", False):
            print("\n💡 Bedrock troubleshooting:")
            print("   - Check if Bedrock is available in your region")
            print("   - Verify IAM policies include Bedrock permissions")
            print("   - Some models might need to be enabled in Bedrock console")


if __name__ == "__main__":
    main()