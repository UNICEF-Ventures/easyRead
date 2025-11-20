#!/usr/bin/env python
import os
import sys
import django

# Setup Django
if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "easyread_backend.settings")
    django.setup()
    
    from django.contrib.auth.models import User
    
    # Delete existing admin user if exists
    try:
        admin_user = User.objects.get(username='admin')
        admin_user.delete()
        print("Existing admin user deleted.")
    except User.DoesNotExist:
        print("No existing admin user found.")
    
    # Create new admin user
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123'
    )
    print("New admin user created:")
    print("Username: admin")
    print("Password: admin123")
    print("Email: admin@example.com")