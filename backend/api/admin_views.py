"""
Admin authentication views for EasyRead project.
Provides simple password-based authentication for accessing image management.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.urls import reverse
import json


def admin_login_view(request):
    """
    Display login form and handle authentication.
    """
    if request.method == 'POST':
        username = request.POST.get('username', 'admin')
        password = request.POST.get('password')
        
        if password:
            # Try to authenticate with the provided password
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Invalid password. Please try again.')
        else:
            messages.error(request, 'Password is required.')
    
    return render(request, 'admin/login.html')


@login_required
def admin_dashboard_view(request):
    """
    Serve the React admin interface for authenticated users.
    """
    return render(request, 'admin/dashboard.html')


@login_required 
def admin_logout_view(request):
    """
    Log out the user and redirect to login.
    """
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('admin_login')


@require_http_methods(["GET"])
def check_auth_status(request):
    """
    API endpoint to check if user is authenticated.
    Returns JSON response for frontend consumption.
    """
    return JsonResponse({
        'authenticated': request.user.is_authenticated,
        'username': request.user.username if request.user.is_authenticated else None
    })


@csrf_exempt
@require_http_methods(["POST"]) 
def admin_api_login(request):
    """
    API endpoint for frontend login requests.
    Accepts JSON payload with username/password.
    """
    try:
        data = json.loads(request.body)
        username = data.get('username', 'admin')
        password = data.get('password')
        
        if not password:
            return JsonResponse({
                'success': False,
                'error': 'Password is required'
            }, status=400)
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
                'username': user.username
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid credentials'
            }, status=401)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON payload'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Login failed'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def admin_api_logout(request):
    """
    API endpoint for frontend logout requests.
    """
    try:
        logout(request)
        return JsonResponse({
            'success': True,
            'message': 'Logout successful'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Logout failed'
        }, status=500)