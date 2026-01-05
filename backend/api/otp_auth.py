"""
OTP (One-Time Password) Authentication System

Provides passwordless authentication via email whitelist and 6-digit OTP codes.
"""
import os
import secrets
import logging
from datetime import timedelta
from functools import wraps

import resend

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import login, logout
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import WhitelistedEmail, OTPToken

logger = logging.getLogger(__name__)

# Configure Resend
resend.api_key = os.getenv('RESEND_API_KEY', '')

# Configuration
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_COOLDOWN_SECONDS = 60  # Minimum time between OTP requests


def generate_otp():
    """Generate a cryptographically secure 6-digit OTP code."""
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])


def send_otp_email(email, otp_code):
    """Send OTP code via email using Resend."""
    from_email = os.getenv('DEFAULT_FROM_EMAIL', 'OOI - EasyRead <onboarding@resend.dev>')

    try:
        r = resend.Emails.send({
            "from": from_email,
            "to": email,
            "subject": "Your EasyRead Login Code",
            "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #333; margin-bottom: 20px;">Your Login Code</h2>
                    <p style="color: #666; margin-bottom: 20px;">
                        Use this code to sign in to EasyRead:
                    </p>
                    <div style="background: #f5f5f5; padding: 20px; text-align: center; border-radius: 8px; margin-bottom: 20px;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #333;">
                            {otp_code}
                        </span>
                    </div>
                    <p style="color: #999; font-size: 14px;">
                        This code expires in {OTP_EXPIRY_MINUTES} minutes.
                    </p>
                    <p style="color: #999; font-size: 14px;">
                        If you didn't request this code, you can safely ignore this email.
                    </p>
                </div>
            """
        })
        logger.info(f"OTP email sent to {email}, id: {r.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        return False


@api_view(['POST'])
@permission_classes([AllowAny])
def request_otp(request):
    """
    Request an OTP code to be sent to the provided email.

    POST /api/auth/request-otp/
    Body: { "email": "user@example.com" }

    Returns success even if email is not whitelisted (to prevent enumeration).
    """
    email = request.data.get('email', '').lower().strip()

    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Always return success to prevent email enumeration
    success_response = Response({
        'message': 'If this email is registered, you will receive a login code shortly.',
        'expires_in_minutes': OTP_EXPIRY_MINUTES
    })

    # Check if email is whitelisted and active
    if not WhitelistedEmail.objects.filter(email=email, is_active=True).exists():
        logger.warning(f"OTP requested for non-whitelisted email: {email}")
        return success_response

    # Check cooldown - prevent spam
    recent_otp = OTPToken.objects.filter(
        email=email,
        created_at__gte=timezone.now() - timedelta(seconds=OTP_COOLDOWN_SECONDS)
    ).first()

    if recent_otp:
        logger.warning(f"OTP request too soon for {email}")
        return success_response  # Don't reveal cooldown to prevent timing attacks

    # Invalidate any existing unused OTPs for this email
    OTPToken.objects.filter(email=email, used=False).update(used=True)

    # Generate new OTP
    otp_code = generate_otp()
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    OTPToken.objects.create(
        email=email,
        token=otp_code,
        expires_at=expires_at
    )

    # Send email
    if send_otp_email(email, otp_code):
        logger.info(f"OTP created and sent for {email}")
    else:
        logger.error(f"Failed to send OTP for {email}")

    return success_response


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """
    Verify an OTP code and create a session.

    POST /api/auth/verify-otp/
    Body: { "email": "user@example.com", "otp": "123456" }
    """
    email = request.data.get('email', '').lower().strip()
    otp_code = request.data.get('otp', '').strip()

    if not email or not otp_code:
        return Response(
            {'error': 'Email and OTP are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Find the most recent valid OTP for this email
    otp_token = OTPToken.objects.filter(
        email=email,
        used=False,
        expires_at__gt=timezone.now()
    ).order_by('-created_at').first()

    if not otp_token:
        logger.warning(f"No valid OTP found for {email}")
        return Response(
            {'error': 'Invalid or expired code. Please request a new one.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Check max attempts
    if otp_token.attempts >= OTP_MAX_ATTEMPTS:
        otp_token.used = True
        otp_token.save()
        logger.warning(f"Max OTP attempts exceeded for {email}")
        return Response(
            {'error': 'Too many attempts. Please request a new code.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    # Verify OTP using constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(otp_token.token, otp_code):
        otp_token.attempts += 1
        otp_token.save()
        remaining = OTP_MAX_ATTEMPTS - otp_token.attempts
        logger.warning(f"Invalid OTP attempt for {email}, {remaining} attempts remaining")
        return Response(
            {'error': f'Invalid code. {remaining} attempts remaining.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Re-verify email is still whitelisted (admin may have removed during OTP validity)
    if not WhitelistedEmail.objects.filter(email=email, is_active=True).exists():
        otp_token.used = True
        otp_token.save()
        logger.warning(f"OTP valid but email no longer whitelisted: {email}")
        return Response(
            {'error': 'Access denied. Please contact administrator.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # OTP is valid - mark as used
    otp_token.used = True
    otp_token.used_at = timezone.now()
    otp_token.save()

    # Update last login for whitelisted email
    WhitelistedEmail.objects.filter(email=email).update(last_login=timezone.now())

    # Get or create a Django user for session management
    # Using email as username (truncated if needed)
    username = email[:150]  # Django username max length
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'email': email, 'is_active': True}
    )

    if created:
        # Set unusable password for OTP-only users
        user.set_unusable_password()
        user.save()
        logger.info(f"Created new user for {email}")

    # Log the user in (creates session)
    login(request, user)

    logger.info(f"Successful OTP login for {email}")

    return Response({
        'message': 'Login successful',
        'email': email
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_status(request):
    """
    Check current authentication status.

    GET /api/auth/status/
    """
    if request.user.is_authenticated:
        return Response({
            'authenticated': True,
            'email': request.user.email or request.user.username
        })

    return Response({
        'authenticated': False,
        'email': None
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """
    Log out the current user.

    POST /api/auth/logout/
    """
    if request.user.is_authenticated:
        email = request.user.email or request.user.username
        logout(request)
        logger.info(f"User logged out: {email}")

    return Response({'message': 'Logged out successfully'})


# Decorator for protecting views
def otp_login_required(view_func):
    """
    Decorator to require OTP authentication for a view.
    Returns 401 if user is not authenticated.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return view_func(request, *args, **kwargs)
    return wrapper
