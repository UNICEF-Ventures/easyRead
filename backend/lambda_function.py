import os
from mangum import Mangum
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "easyread_backend.settings")  # <-- replace with your project name

application = get_asgi_application()
lambda_handler = Mangum(application, lifespan="off")   # <-- this is your Lambda handler
