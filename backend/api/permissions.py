"""
Custom DRF permission classes for authentication.

Supports both:
- OTP authentication (email + code, session-based)
- Auth0 JWT authentication (ooiplayground integration)
"""
from rest_framework.permissions import BasePermission
from django.conf import settings


class IsOTPAuthenticated(BasePermission):
    """
    Permission class that requires the user to be authenticated via OTP.
    Works with Django's session authentication after successful OTP verification.
    """
    message = "Authentication required. Please log in with your email."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsPlaygroundAuthenticated(BasePermission):
    """
    Permission class that requires the user to be authenticated via Auth0 JWT.
    Used for ooiplayground integration.

    Validates:
    - User is authenticated (valid JWT token)
    - User has access to this project (optional, based on allowed-projects claim)
    """
    message = "Authentication required. Please provide a valid access token."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if this is an Auth0User (has allowed_projects attribute)
        if hasattr(request.user, 'allowed_projects'):
            # Optionally check project access
            project_name = getattr(settings, 'AUTH0_PROJECT_NAME', 'easyread')
            check_project_access = getattr(settings, 'AUTH0_CHECK_PROJECT_ACCESS', False)

            if check_project_access and project_name:
                if not request.user.has_project_access(project_name):
                    self.message = f"You don't have access to the '{project_name}' project."
                    return False

        return True


class IsPlaygroundOrOTPAuthenticated(BasePermission):
    """
    Permission class that allows either:
    - Auth0 JWT authentication (ooiplayground)
    - OTP session authentication (standalone mode)

    This is useful for endpoints that should work in both deployment modes.
    """
    message = "Authentication required. Please log in or provide a valid access token."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Auth0User (JWT) or Django User (session) - both are valid
        return True


class HasProjectAccess(BasePermission):
    """
    Permission class that checks if the user has access to a specific project.
    Only applies to Auth0 JWT users; session users are always allowed.

    Configure the project name in settings:
        AUTH0_PROJECT_NAME = 'easyread'
        AUTH0_CHECK_PROJECT_ACCESS = True
    """
    message = "You don't have access to this project."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # For session-authenticated users (OTP), allow access
        if not hasattr(request.user, 'allowed_projects'):
            return True

        # For Auth0 users, check project access
        project_name = getattr(settings, 'AUTH0_PROJECT_NAME', 'easyread')
        if project_name and not request.user.has_project_access(project_name):
            self.message = f"You don't have access to the '{project_name}' project."
            return False

        return True
