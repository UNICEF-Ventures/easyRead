"""
Analytics utilities for tracking user sessions and events.
"""

import uuid
from django.utils import timezone
from django.contrib.sessions.models import Session
from .models import UserSession, SessionEvent, ImageSetSelection, ImageSelectionChange


def get_client_ip(request):
    """Get the client's IP address from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get the user agent from request headers."""
    return request.META.get('HTTP_USER_AGENT', '')


def get_or_create_session(request):
    """
    Get or create a UserSession based on session ID.
    If no session exists, creates a new one.
    """
    session_id = request.session.get('analytics_session_id')
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    if session_id:
        try:
            session = UserSession.objects.get(session_id=session_id)
            # Update last activity
            session.last_activity = timezone.now()
            session.save(update_fields=['last_activity'])
            return session
        except UserSession.DoesNotExist:
            pass
    
    # Create new session
    session = UserSession.objects.create(
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Store session ID in Django session
    request.session['analytics_session_id'] = str(session.session_id)
    
    return session


def track_event(request, event_type, event_data=None):
    """
    Track a user event for analytics.
    
    Args:
        request: Django request object
        event_type: Type of event from SessionEvent.EVENT_TYPES
        event_data: Optional dictionary with event-specific data
    """
    if event_data is None:
        event_data = {}
    
    session = get_or_create_session(request)
    
    SessionEvent.objects.create(
        session=session,
        event_type=event_type,
        event_data=event_data
    )
    
    return session


def track_pdf_upload(request, file_size):
    """Track PDF upload event and update session summary."""
    session = track_event(request, 'pdf_upload', {
        'file_size_bytes': file_size
    })
    
    # Update session summary
    session.pdf_uploaded = True
    session.pdf_size_bytes = file_size
    session.save(update_fields=['pdf_uploaded', 'pdf_size_bytes'])
    
    return session


def track_content_input(request, content_size):
    """Track content input (after PDF conversion or pasted content)."""
    session = track_event(request, 'content_input', {
        'content_size_chars': content_size
    })
    
    # Update session summary
    session.input_content_size = content_size
    session.save(update_fields=['input_content_size'])
    
    return session


def track_page_processing(request, page_number, sentences_count):
    """Track page processing and update sentence count."""
    session = track_event(request, 'page_process', {
        'page_number': page_number,
        'sentences_generated': sentences_count
    })
    
    # Update session summary
    session.sentences_generated += sentences_count
    session.save(update_fields=['sentences_generated'])
    
    return session


def track_image_set_selection(request, image_set):
    """Track image set selection."""
    session = get_or_create_session(request)
    
    # Create or update image set selection
    ImageSetSelection.objects.get_or_create(
        session=session,
        image_set=image_set
    )
    
    track_event(request, 'image_select', {
        'image_set_id': image_set.id,
        'image_set_name': image_set.name
    })
    
    return session


def track_image_selection_change(request, sentence_index, old_image=None, new_image=None, old_ranking=None, new_ranking=None):
    """Track changes in image selection for a specific sentence."""
    session = get_or_create_session(request)
    
    # Record the change
    ImageSelectionChange.objects.create(
        session=session,
        sentence_index=sentence_index,
        old_image=old_image,
        new_image=new_image,
        old_ranking=old_ranking,
        new_ranking=new_ranking
    )
    
    # Track the event
    event_data = {
        'sentence_index': sentence_index,
        'old_ranking': old_ranking,
        'new_ranking': new_ranking
    }
    
    if old_image:
        event_data['old_image_id'] = old_image.id
        event_data['old_image_filename'] = old_image.filename
    
    if new_image:
        event_data['new_image_id'] = new_image.id
        event_data['new_image_filename'] = new_image.filename
    
    track_event(request, 'image_change', event_data)
    
    return session


def track_content_validation(request, missing_info="", extra_info="", other_feedback="", issues_found=None):
    """Track content validation results."""
    return track_event(request, 'content_validate', {
        'has_missing_info': bool(missing_info.strip()),
        'has_extra_info': bool(extra_info.strip()),
        'has_other_feedback': bool(other_feedback.strip()),
        'missing_info_length': len(missing_info),
        'extra_info_length': len(extra_info),
        'other_feedback_length': len(other_feedback),
        'issues_found': issues_found or []
    })


def track_sentence_revision(request, sentence_index, original_text, revised_text):
    """Track sentence revision."""
    return track_event(request, 'sentence_revise', {
        'sentence_index': sentence_index,
        'original_length': len(original_text),
        'revised_length': len(revised_text)
    })


def track_image_search(request, query, results_count):
    """Track image search queries."""
    return track_event(request, 'image_search', {
        'query': query,
        'results_count': results_count
    })


def track_content_save(request, content_id, title):
    """Track content save event."""
    return track_event(request, 'content_save', {
        'content_id': content_id,
        'title': title
    })


def track_content_export(request, content_id=None, export_format='docx'):
    """Track content export and update session summary."""
    session = track_event(request, 'content_export', {
        'content_id': content_id,
        'export_format': export_format
    })
    
    # Update session summary
    session.exported_result = True
    session.save(update_fields=['exported_result'])
    
    return session


def track_image_upload(request, filename, file_size):
    """Track image upload events."""
    return track_event(request, 'image_upload', {
        'filename': filename,
        'file_size_bytes': file_size
    })


def track_image_generation(request, prompt, success=True):
    """Track image generation events."""
    return track_event(request, 'image_generate', {
        'prompt': prompt,
        'success': success
    })


def get_session_analytics(session_id):
    """Get comprehensive analytics for a specific session."""
    try:
        session = UserSession.objects.get(session_id=session_id)
        
        analytics = {
            'session_info': {
                'session_id': str(session.session_id),
                'ip_address': session.ip_address,
                'user_agent': session.user_agent,
                'started_at': session.started_at,
                'last_activity': session.last_activity,
                'duration_minutes': (session.last_activity - session.started_at).total_seconds() / 60
            },
            'summary': {
                'pdf_uploaded': session.pdf_uploaded,
                'pdf_size_bytes': session.pdf_size_bytes,
                'input_content_size': session.input_content_size,
                'sentences_generated': session.sentences_generated,
                'exported_result': session.exported_result
            },
            'events': list(session.events.all().values()),
            'image_sets_selected': list(session.image_set_selections.all().values_list('image_set__name', flat=True)),
            'image_changes': list(session.image_changes.all().values())
        }
        
        return analytics
    except UserSession.DoesNotExist:
        return None