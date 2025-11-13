# import os
# from mangum import Mangum
# from django.core.asgi import get_asgi_application

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "easyread_backend.settings")  # <-- replace with your project name

# application = get_asgi_application()
# lambda_handler = Mangum(application, lifespan="off")   # <-- this is your Lambda handler

import os
from mangum import Mangum
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "easyread_backend.settings")  # <-- replace with your project name

application = get_asgi_application()
# lambda_handler = Mangum(application, lifespan="off")   # <-- this is your Lambda handler

# lambda_function.py
# import os
import json
import base64

import django
django.setup()

def lambda_handler(event, context):
    # Debug logging
    print("="*80)
    print("INCOMING EVENT:")
    print(json.dumps(event, indent=2))
    print("="*80)
    
    # Fix headers - API Gateway may lowercase them
    if 'headers' in event:
        # Normalize headers to lowercase
        normalized_headers = {k.lower(): v for k, v in event['headers'].items()}
        event['headers'] = normalized_headers
        
        # Ensure Content-Type is set for JSON
        if event.get('body') and 'content-type' not in normalized_headers:
            event['headers']['content-type'] = 'application/json'
    
    
    # Handle base64 encoded body (if binary)
    if event.get('isBase64Encoded', False) and event.get('body'):
        event['body'] = base64.b64decode(event['body']).decode('utf-8')
        event['isBase64Encoded'] = False
    
    event['data'] = event['body']
    
    # Create Mangum handler
    asgi_handler = Mangum(
        application,
        lifespan="off",
    )
    print(" EVENT:")
    print(json.dumps(event, indent=2))
    print("="*80)
    
    response = asgi_handler(event, context)
    
    print("="*80)
    print("RESPONSE:")
    print(json.dumps(response, indent=2, default=str))
    print("="*80)
    
    return response