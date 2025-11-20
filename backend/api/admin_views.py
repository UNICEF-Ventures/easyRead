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

from .image_utils import parse_s3_url

MEDIA_STORE = os.getenv('MEDIA_STORE', 'server')

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
        total_saved_content = 0
        try:
            from .models import Image, ImageSet, ProcessedContent
            total_images = Image.objects.count()
            total_image_sets = ImageSet.objects.count()
            total_saved_content = ProcessedContent.objects.filter(deleted_at__isnull=True).count()
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
            'saved_content': {
                'total_saved': total_saved_content
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

import boto3

bucket_name = os.getenv("S3_BUCKET_NAME")
region_name = os.getenv("S3_BUCKET_REGION")
s3 = boto3.client("s3", region_name=region_name)

def delete_s3_image_by_url(url: str):
    """
    Delete a single S3 object given its S3 URL.
    """
    bucket, key = parse_s3_url(url)

    s3.delete_object(Bucket=bucket, Key=key)
    # Optional: return something
    return {"bucket": bucket, "key": key}

@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_image(request, image_id):
    """
    API endpoint to delete a single image.
    Removes the image record and optionally deletes the file from disk.
    """
    try:
        from .models import Image
        
        # Get the image
        image = Image.objects.get(id=image_id)
        image_filename = image.filename
        image_set_name = image.set.name
        
        # Get file path before deleting the record
        file_path = image.get_absolute_path()
        
        # Delete the database record (this will cascade to embeddings)
        image.delete()
        
        # Optionally delete the physical file
        try:
            if(MEDIA_STORE == "server"):
                if os.path.exists(file_path):
                    os.remove(file_path)
            elif(MEDIA_STORE == "S3"):
                delete_s3_image_by_url(file_path)
        except Exception as file_error:
            # Log but don't fail if file deletion fails
            print(f"Warning: Could not delete file {file_path}: {file_error}")
        
        return JsonResponse({
            'success': True,
            'message': f'Image "{image_filename}" deleted successfully',
            'deleted_image_id': image_id,
            'set_name': image_set_name
        })
        
    except Image.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Image not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to delete image: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_images_batch(request):
    """
    API endpoint to delete multiple images by ID.
    Accepts a JSON payload with an array of image IDs.
    """
    try:
        from .models import Image
        
        data = json.loads(request.body)
        image_ids = data.get('image_ids', [])
        
        if not image_ids:
            return JsonResponse({
                'success': False,
                'error': 'No image IDs provided'
            }, status=400)
        
        # Get all images
        images = Image.objects.filter(id__in=image_ids)
        found_count = images.count()
        
        if found_count == 0:
            return JsonResponse({
                'success': False,
                'error': 'No images found with provided IDs'
            }, status=404)
        
        # Collect file paths before deletion
        file_paths = [img.get_absolute_path() for img in images]
        # Delete the database records
        images.delete()
        
        # Optionally delete the physical files
        deleted_files = 0
        failed_files = 0

        if(MEDIA_STORE == "server"):
            for file_path in file_paths:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_files += 1
                except Exception as file_error:
                    failed_files += 1
                    print(f"Warning: Could not delete file {file_path}: {file_error}")
        elif(MEDIA_STORE == "S3"):
            for file_path in file_paths:
                try:
                    delete_s3_image_by_url(file_path)
                    deleted_files += 1
                except Exception as file_error:
                    failed_files += 1
                    print(f"Warning: Could not delete file {file_path}: {file_error}")
                
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {found_count} images',
            'deleted_count': found_count,
            'deleted_files': deleted_files,
            'failed_files': failed_files
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON payload'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to delete images: {str(e)}'
        }, status=500)



def delete_s3_folder(bucket: str, prefix: str):
    """
    Deletes all objects under the given prefix (folder) in an S3 bucket.
    e.g. prefix='photos/2024/' will delete everything under that path.
    """
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" not in page:
            continue

        deletes = [{"Key": obj["Key"]} for obj in page["Contents"]]

        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": deletes}
        )

    print(f"Deleted all objects under: s3://{bucket}/{prefix}")


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_image_set(request, set_id):
    """
    API endpoint to delete an entire image set and all its images.
    """
    try:
        from .models import ImageSet, Image
        
        # Get the image set
        image_set = ImageSet.objects.get(id=set_id)
        set_name = image_set.name
        
        # Get all images in the set
        images = Image.objects.filter(set=image_set)
        image_count = images.count()
        
        # Collect file paths before deletion
        file_paths = [img.get_absolute_path() for img in images]
        # Delete the image set (this will cascade to images and embeddings)
        image_set.delete()
        # Optionally delete the physical files
        if(MEDIA_STORE == "server"):
            deleted_files = 0
            failed_files = 0
            for file_path in file_paths:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_files += 1
                except Exception as file_error:
                    failed_files += 1
                    print(f"Warning: Could not delete file {file_path}: {file_error}")
        elif(MEDIA_STORE == "S3"):
            try:
                delete_s3_folder(bucket_name, set_name)
                deleted_files = image_count
                failed_files = 0
            except Exception as file_error:
                print(f"Warning: Could not delete folder {set_name}")
                failed_files = image_count
                deleted_files = 0
                
        return JsonResponse({
            'success': True,
            'message': f'Image set "{set_name}" and {image_count} images deleted successfully',
            'deleted_set_name': set_name,
            'deleted_image_count': image_count,
            'deleted_files': deleted_files,
            'failed_files': failed_files
        })
        
    except ImageSet.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Image set not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to delete image set: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
@login_required
def list_image_sets(request):
    """
    API endpoint to list all image sets with their metadata and image counts.
    """
    try:
        from .models import ImageSet, Image
        
        sets = ImageSet.objects.all().order_by('name')
        
        sets_data = []
        for image_set in sets:
            # Get image count and stats
            images = Image.objects.filter(set=image_set)
            image_count = images.count()
            
            # Count images with embeddings
            images_with_embeddings = images.filter(embeddings__isnull=False).distinct().count()
            
            # Get a sample of image URLs for preview (first 3 images)
            sample_images = []
            for img in images[:3]:
                sample_images.append({
                    'id': img.id,
                    'url': img.get_url(),
                    'description': img.description
                })
            
            sets_data.append({
                'id': image_set.id,
                'name': image_set.name,
                'description': image_set.description,
                'image_count': image_count,
                'images_with_embeddings': images_with_embeddings,
                'embedding_coverage_percent': round((images_with_embeddings / image_count * 100) if image_count > 0 else 0, 1),
                'created_at': image_set.created_at.isoformat(),
                'sample_images': sample_images
            })
        
        return JsonResponse({
            'success': True,
            'sets': sets_data,
            'total_sets': len(sets_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to fetch image sets: {str(e)}'
        }, status=500)