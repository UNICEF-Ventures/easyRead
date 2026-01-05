"""
Custom DRF permission classes for OTP authentication.
"""
from rest_framework.permissions import BasePermission


class IsOTPAuthenticated(BasePermission):
    """
    Permission class that requires the user to be authenticated via OTP.
    Works with Django's session authentication after successful OTP verification.
    """
    message = "Authentication required. Please log in with your email."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
