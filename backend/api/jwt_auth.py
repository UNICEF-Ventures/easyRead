"""
JWT Authentication for Auth0/OIDC integration with ooiplayground.

This module provides JWT token validation for tokens issued by the
ooiplayground Auth0 tenant. It validates tokens using JWKS (JSON Web Key Set)
and extracts user information from token claims.
"""
import logging
import jwt
from jwt import PyJWKClient, PyJWKClientError
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from functools import lru_cache
import time

logger = logging.getLogger(__name__)


class Auth0User:
    """
    Represents an authenticated user from Auth0 JWT token.
    This is a lightweight user object that doesn't require database storage.
    """
    def __init__(self, payload):
        self.payload = payload
        self.token_sub = payload.get('sub', '')

        # Extract email from custom claim namespace or standard claim
        namespace = getattr(settings, 'AUTH0_NAMESPACE', 'https://ooi-playground.com')
        self.email = payload.get(f'{namespace}/email') or payload.get('email', '')

        # Extract roles and allowed projects from custom claims
        self.roles = payload.get(f'{namespace}/roles', '')
        self.allowed_projects = payload.get(f'{namespace}/allowed-projects', [])

        # Standard claims
        self.scope = payload.get('scope', '')
        self.azp = payload.get('azp', '')  # Authorized party (client ID)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def id(self):
        """Return sub as the user ID."""
        return self.token_sub

    def has_project_access(self, project_name):
        """Check if user has access to a specific project."""
        return project_name in self.allowed_projects

    def __str__(self):
        return self.email or self.token_sub


class JWKSClientSingleton:
    """
    Singleton wrapper for PyJWKClient to avoid recreating it on every request.
    Includes caching of signing keys with configurable TTL.
    """
    _instance = None
    _client = None
    _last_refresh = 0
    _cache_ttl = 3600  # 1 hour default

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_client(self):
        """Get or create the JWKS client."""
        current_time = time.time()

        # Refresh client if TTL expired or not initialized
        if self._client is None or (current_time - self._last_refresh) > self._cache_ttl:
            jwks_url = getattr(settings, 'AUTH0_JWKS_URL', None)
            if not jwks_url:
                domain = getattr(settings, 'AUTH0_DOMAIN', '')
                jwks_url = f"{domain.rstrip('/')}/.well-known/jwks.json"

            self._client = PyJWKClient(jwks_url, cache_keys=True)
            self._last_refresh = current_time
            logger.debug(f"JWKS client initialized/refreshed from {jwks_url}")

        return self._client

    def get_signing_key(self, token):
        """Get the signing key for a specific token."""
        client = self.get_client()
        return client.get_signing_key_from_jwt(token)


# Global JWKS client instance
_jwks_client = JWKSClientSingleton()


def get_token_from_header(request):
    """
    Extract JWT token from Authorization header.
    Expects format: "Bearer <token>"
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')

    if not auth_header:
        return None

    parts = auth_header.split()

    if len(parts) != 2:
        raise AuthenticationFailed('Invalid Authorization header format')

    if parts[0].lower() != 'bearer':
        raise AuthenticationFailed('Authorization header must start with Bearer')

    return parts[1]


def validate_token(token):
    """
    Validate a JWT token and return the decoded payload.

    Validates:
    - Token signature using JWKS
    - Token expiration (exp claim)
    - Issuer (iss claim)
    - Audience (aud claim)

    Returns:
        dict: Decoded token payload if valid

    Raises:
        AuthenticationFailed: If token is invalid
    """
    try:
        # Get signing key from JWKS
        signing_key = _jwks_client.get_signing_key(token)

        # Get validation settings
        issuer = getattr(settings, 'AUTH0_ISSUER', None)
        audience = getattr(settings, 'AUTH0_AUDIENCE', None)
        algorithms = getattr(settings, 'AUTH0_ALGORITHMS', ['RS256'])

        # Build decode options
        decode_options = {
            'verify_signature': True,
            'verify_exp': True,
            'verify_iat': True,
            'require': ['exp', 'iat', 'sub'],
        }

        # Decode and validate token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options=decode_options,
        )

        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise AuthenticationFailed('Token has expired')

    except jwt.InvalidAudienceError:
        logger.warning("JWT token has invalid audience")
        raise AuthenticationFailed('Invalid token audience')

    except jwt.InvalidIssuerError:
        logger.warning("JWT token has invalid issuer")
        raise AuthenticationFailed('Invalid token issuer')

    except jwt.InvalidSignatureError:
        logger.warning("JWT token has invalid signature")
        raise AuthenticationFailed('Invalid token signature')

    except PyJWKClientError as e:
        logger.error(f"JWKS client error: {e}")
        raise AuthenticationFailed('Unable to verify token signature')

    except jwt.PyJWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise AuthenticationFailed(f'Token validation failed: {str(e)}')


class Auth0JWTAuthentication(BaseAuthentication):
    """
    DRF Authentication class for Auth0 JWT tokens.

    Usage in views:
        @api_view(['GET'])
        @authentication_classes([Auth0JWTAuthentication])
        @permission_classes([IsAuthenticated])
        def my_view(request):
            user = request.user  # Auth0User instance
            email = user.email
            ...

    Or set globally in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'api.jwt_auth.Auth0JWTAuthentication',
            ],
        }
    """

    def authenticate(self, request):
        """
        Authenticate the request and return a tuple of (user, token).

        Returns:
            tuple: (Auth0User, token) if authentication succeeds
            None: If no Authorization header present (allows other auth methods)

        Raises:
            AuthenticationFailed: If token is present but invalid
        """
        token = get_token_from_header(request)

        if token is None:
            # No token provided - let other authentication methods try
            return None

        # Validate token and get payload
        payload = validate_token(token)

        # Create user object from payload
        user = Auth0User(payload)

        logger.debug(f"Authenticated user: {user.email} via Auth0 JWT")

        return (user, token)

    def authenticate_header(self, request):
        """
        Return the WWW-Authenticate header value for 401 responses.
        """
        return 'Bearer realm="api"'


class OptionalAuth0JWTAuthentication(Auth0JWTAuthentication):
    """
    Optional JWT authentication that doesn't fail if no token is provided.
    Useful for endpoints that work for both authenticated and anonymous users.
    """

    def authenticate(self, request):
        """
        Try to authenticate but don't fail if no token is provided.
        """
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None
