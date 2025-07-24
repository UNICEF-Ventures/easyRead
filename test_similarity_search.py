#!/usr/bin/env python3
"""
Test similarity search with Cohere Bedrock embeddings.
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


def test_similarity_search():
    """Test similarity search with Cohere embeddings."""
    print("🔍 Testing Similarity Search with Cohere Bedrock...")
    
    try:
        from api.similarity_search import search_similar_images
        
        # Test various search queries
        test_queries = [
            "credit and money",
            "trust and relationships", 
            "research and study",
            "communication",
            "employee work"
        ]
        
        for query in test_queries:
            print(f"\n📝 Searching for: '{query}'")
            
            # Find similar images
            results = search_similar_images(query, n_results=3)
            
            if results:
                print(f"   Found {len(results)} results:")
                for i, result in enumerate(results, 1):
                    print(f"   {i}. {result['description']} (score: {result['similarity']:.3f})")
            else:
                print("   No results found")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_embedding_provider_info():
    """Test current embedding provider information."""
    print("\n⚙️ Current Embedding Provider Info...")
    
    try:
        from api.embedding_providers.factory import get_embedding_provider
        
        provider = get_embedding_provider()
        info = provider.get_provider_info()
        
        print(f"   Provider: {info['name']}")
        print(f"   Model: {info['model']}")
        print(f"   Dimension: {info['embedding_dimension']}")
        print(f"   Supports Text: {info['supports_text']}")
        print(f"   Supports Images: {info['supports_images']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_database_stats():
    """Show database statistics."""
    print("\n📊 Database Statistics...")
    
    try:
        from api.models import Image, Embedding, ImageSet
        
        image_count = Image.objects.count()
        embedding_count = Embedding.objects.count() 
        set_count = ImageSet.objects.count()
        
        print(f"   Images: {image_count}")
        print(f"   Embeddings: {embedding_count}")
        print(f"   Image Sets: {set_count}")
        
        # Check latest images from CSV
        latest_images = Image.objects.filter(
            description__in=['Credit', 'Trust', 'Research', 'Communication', 'Employee']
        )
        
        print(f"\n   Recent CSV images found: {len(latest_images)}")
        for img in latest_images[:3]:
            print(f"     - {img.description}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Run similarity search tests."""
    print("🧪 Similarity Search Test with Cohere Bedrock")
    print("=" * 50)
    
    tests = [
        ("Database Stats", test_database_stats),
        ("Provider Info", test_embedding_provider_info),
        ("Similarity Search", test_similarity_search),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n📊 Test Results:")
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<20} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 Cohere Bedrock similarity search is working!")
    else:
        print("⚠️ Some issues found - check details above")


if __name__ == "__main__":
    main()