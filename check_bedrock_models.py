#!/usr/bin/env python3
"""
Check available AWS Bedrock models in the configured region.
"""

import os
import boto3
from dotenv import load_dotenv

# Load environment
load_dotenv()

def main():
    """Check available Bedrock models."""
    print("🔍 Checking Available AWS Bedrock Models")
    print("=" * 50)
    
    try:
        region = os.getenv('AWS_REGION_NAME', 'us-east-1')
        print(f"Region: {region}")
        
        # Create Bedrock client
        bedrock = boto3.client('bedrock', region_name=region)
        
        # List foundation models
        response = bedrock.list_foundation_models()
        models = response.get('modelSummaries', [])
        
        print(f"Total models available: {len(models)}")
        
        # Group by provider
        by_provider = {}
        for model in models:
            provider = model['providerName']
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(model)
        
        print(f"\nProviders: {', '.join(by_provider.keys())}")
        
        # Show Llama models
        print("\n🦙 Llama Models:")
        llama_models = [m for m in models if 'llama' in m['modelId'].lower()]
        if llama_models:
            for model in llama_models:
                print(f"   {model['modelId']} ({model['providerName']})")
                for mode in model.get('inferenceTypesSupported', []):
                    print(f"     - {mode}")
        else:
            print("   No Llama models found")
        
        # Show Cohere models  
        print("\n🔍 Cohere Models:")
        cohere_models = [m for m in models if 'cohere' in m['providerName'].lower()]
        if cohere_models:
            for model in cohere_models:
                print(f"   {model['modelId']} ({model['modelName']})")
                for mode in model.get('inferenceTypesSupported', []):
                    print(f"     - {mode}")
        else:
            print("   No Cohere models found")
        
        # Show Titan models
        print("\n🏛️ Amazon Titan Models:")
        titan_models = [m for m in models if 'amazon' in m['providerName'].lower() and 'titan' in m['modelId'].lower()]
        if titan_models:
            for model in titan_models:
                print(f"   {model['modelId']} ({model['modelName']})")
                for mode in model.get('inferenceTypesSupported', []):
                    print(f"     - {mode}")
        else:
            print("   No Titan models found")
        
        # Check inference profiles
        try:
            bedrock_runtime = boto3.client('bedrock', region_name=region)
            profiles_response = bedrock_runtime.list_inference_profiles()
            profiles = profiles_response.get('inferenceProfileSummaries', [])
            
            print(f"\n🎯 Inference Profiles: {len(profiles)}")
            for profile in profiles[:5]:  # Show first 5
                print(f"   {profile['inferenceProfileId']} ({profile['status']})")
                
        except Exception as e:
            print(f"\n⚠️ Could not list inference profiles: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()