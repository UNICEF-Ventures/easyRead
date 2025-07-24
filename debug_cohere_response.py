#!/usr/bin/env python3
"""
Debug Cohere Bedrock response format.
"""

import os
from dotenv import load_dotenv
load_dotenv()

try:
    from litellm import embedding
    
    print("🔍 Testing Cohere Response Format...")
    
    response = embedding(
        model="cohere.embed-multilingual-v3",
        input=["Hello world"]
    )
    
    print(f"Response type: {type(response)}")
    print(f"Response keys: {response.__dict__.keys() if hasattr(response, '__dict__') else 'No __dict__'}")
    
    if hasattr(response, 'data'):
        print(f"Data type: {type(response.data)}")
        print(f"Data length: {len(response.data)}")
        
        if response.data:
            first_item = response.data[0]
            print(f"First item type: {type(first_item)}")
            print(f"First item: {first_item}")
            
            if hasattr(first_item, '__dict__'):
                print(f"First item attributes: {first_item.__dict__.keys()}")
            elif isinstance(first_item, dict):
                print(f"First item dict keys: {first_item.keys()}")
    
    print(f"\nFull response: {response}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()