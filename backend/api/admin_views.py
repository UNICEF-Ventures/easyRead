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
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from datetime import timedelta
import json
import subprocess
import os


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


@require_http_methods(["GET"])
@login_required
def analytics_api(request):
    """
    API endpoint for dashboard analytics data.
    """
    try:
        from .models import UserSession, SessionEvent, ImageSetSelection
        
        # Get query parameters
        days = int(request.GET.get('days', 30))
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get sessions in date range
        sessions = UserSession.objects.filter(
            started_at__gte=start_date
        )
        
        total_sessions = sessions.count()
        sessions_with_pdf = sessions.filter(pdf_uploaded=True).count()
        sessions_with_processing = sessions.filter(sentences_generated__gt=0).count()
        sessions_with_export = sessions.filter(exported_result=True).count()
        
        # Calculate conversion rates
        pdf_to_processing = (sessions_with_processing / sessions_with_pdf * 100) if sessions_with_pdf > 0 else 0
        processing_to_export = (sessions_with_export / sessions_with_processing * 100) if sessions_with_processing > 0 else 0
        pdf_to_export = (sessions_with_export / sessions_with_pdf * 100) if sessions_with_pdf > 0 else 0
        
        # Session duration analytics - calculate average duration differently
        # Note: Django doesn't support arithmetic on aggregates directly
        avg_duration = None  # We'll calculate this separately if needed
        
        # Content analytics
        content_stats = sessions.aggregate(
            total_sentences=Sum('sentences_generated'),
            avg_sentences=Avg('sentences_generated'),
            total_pdf_size=Sum('pdf_size_bytes'),
            avg_pdf_size=Avg('pdf_size_bytes'),
            total_input_size=Sum('input_content_size'),
            avg_input_size=Avg('input_content_size')
        )
        
        # Event analytics
        events = SessionEvent.objects.filter(
            timestamp__gte=start_date
        )
        
        event_types = events.values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Popular image sets
        image_set_selections = ImageSetSelection.objects.filter(
            session__started_at__gte=start_date
        ).values('image_set__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Daily activity over the period
        daily_stats = []
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_sessions = sessions.filter(
                started_at__gte=day_start,
                started_at__lt=day_end
            ).count()
            
            day_events = events.filter(
                timestamp__gte=day_start,
                timestamp__lt=day_end
            ).count()
            
            daily_stats.append({
                'date': day_start.date().isoformat(),
                'sessions': day_sessions,
                'events': day_events
            })
        
        # Recent active sessions
        recent_sessions = sessions.order_by('-last_activity')[:10].values(
            'session_id', 'ip_address', 'started_at', 'last_activity',
            'pdf_uploaded', 'sentences_generated', 'exported_result'
        )
        
        # Top user agents (browsers/devices)
        user_agents = sessions.values('user_agent').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # System health metrics
        total_images = 0
        total_image_sets = 0
        try:
            from .models import Image, ImageSet
            total_images = Image.objects.count()
            total_image_sets = ImageSet.objects.count()
        except:
            pass
        
        return JsonResponse({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'summary': {
                'total_sessions': total_sessions,
                'sessions_with_pdf': sessions_with_pdf,
                'sessions_with_processing': sessions_with_processing,
                'sessions_with_export': sessions_with_export,
                'conversion_rates': {
                    'pdf_to_processing': round(pdf_to_processing, 1),
                    'processing_to_export': round(processing_to_export, 1),
                    'pdf_to_export': round(pdf_to_export, 1)
                }
            },
            'content': {
                'total_sentences': content_stats['total_sentences'] or 0,
                'avg_sentences_per_session': round(content_stats['avg_sentences'] or 0, 1),
                'total_pdf_size_bytes': content_stats['total_pdf_size'] or 0,
                'avg_pdf_size_bytes': round(content_stats['avg_pdf_size'] or 0),
                'total_input_content_chars': content_stats['total_input_size'] or 0,
                'avg_input_content_chars': round(content_stats['avg_input_size'] or 0)
            },
            'events': {
                'total': events.count(),
                'by_type': list(event_types)
            },
            'images': {
                'popular_sets': list(image_set_selections),
                'total_images': total_images,
                'total_image_sets': total_image_sets
            },
            'daily_activity': daily_stats,
            'recent_sessions': list(recent_sessions),
            'user_agents': list(user_agents)
        })
        
    except Exception as e:
        return JsonResponse({
            'error': 'Failed to fetch analytics data',
            'details': str(e)
        }, status=500)