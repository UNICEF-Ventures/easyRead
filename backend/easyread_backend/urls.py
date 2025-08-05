"""
URL configuration for easyread_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from api import urls as api_urls # Import directly
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static

def redirect_to_admin_login(request):
    """Redirect /admin/ to our custom admin login"""
    return redirect('/api/admin/login/')

urlpatterns = [
    path("admin/", redirect_to_admin_login),
    path("django-admin/", admin.site.urls),  # Keep Django admin at different URL
    path("api/", include(api_urls)), # Use the imported variable
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
