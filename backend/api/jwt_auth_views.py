"""
JWT Authentication test views for verifying Auth0/ooiplayground integration.
"""
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from .jwt_auth import Auth0JWTAuthentication, get_token_from_header, validate_token
from .permissions import IsPlaygroundAuthenticated


@api_view(['GET', 'POST'])
@authentication_classes([Auth0JWTAuthentication])
@permission_classes([AllowAny])  # Allow unauthenticated to see the error message
def jwt_test(request):
    """
    Test endpoint to verify JWT authentication is working.

    GET /api/auth/jwt-test/
    - Without token: Returns 200 with "not authenticated"
    - With valid token: Returns 200 with user info
    - With invalid token: Returns 401 with error message

    POST /api/auth/jwt-test/
    - Validates a token passed in the request body
    - Body: {"token": "your-jwt-token"}

    Example usage with curl:
        # Test with Authorization header
        curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/auth/jwt-test/

        # Test token in body
        curl -X POST -H "Content-Type: application/json" \
             -d '{"token": "YOUR_TOKEN"}' \
             http://localhost:8000/api/auth/jwt-test/
    """
    if request.method == 'POST':
        # Validate a token from the request body
        token = request.data.get('token')
        if not token:
            return Response({
                'authenticated': False,
                'error': 'No token provided in request body',
                'usage': 'POST with {"token": "your-jwt-token"}'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = validate_token(token)
            namespace = getattr(settings, 'AUTH0_NAMESPACE', 'https://ooi-playground.com')

            return Response({
                'authenticated': True,
                'token_valid': True,
                'user': {
                    'sub': payload.get('sub'),
                    'email': payload.get(f'{namespace}/email') or payload.get('email'),
                    'roles': payload.get(f'{namespace}/roles'),
                    'allowed_projects': payload.get(f'{namespace}/allowed-projects', []),
                },
                'token_claims': {
                    'iss': payload.get('iss'),
                    'aud': payload.get('aud'),
                    'exp': payload.get('exp'),
                    'iat': payload.get('iat'),
                    'azp': payload.get('azp'),
                    'scope': payload.get('scope'),
                }
            })
        except Exception as e:
            return Response({
                'authenticated': False,
                'token_valid': False,
                'error': str(e)
            }, status=status.HTTP_401_UNAUTHORIZED)

    # GET request - check if authenticated via header
    if request.user and request.user.is_authenticated:
        user = request.user
        user_info = {
            'authenticated': True,
            'auth_method': 'jwt' if hasattr(user, 'allowed_projects') else 'session',
        }

        if hasattr(user, 'allowed_projects'):
            # Auth0 JWT user
            user_info['user'] = {
                'sub': user.token_sub,
                'email': user.email,
                'roles': user.roles,
                'allowed_projects': user.allowed_projects,
            }
            user_info['project_access'] = {
                'project_name': getattr(settings, 'AUTH0_PROJECT_NAME', 'easyread'),
                'has_access': user.has_project_access(getattr(settings, 'AUTH0_PROJECT_NAME', 'easyread')),
            }
        else:
            # Session user (OTP)
            user_info['user'] = {
                'email': getattr(user, 'email', str(user)),
                'username': getattr(user, 'username', None),
            }

        return Response(user_info)

    # Not authenticated
    return Response({
        'authenticated': False,
        'message': 'No valid authentication provided',
        'auth0_config': {
            'domain': getattr(settings, 'AUTH0_DOMAIN', None),
            'issuer': getattr(settings, 'AUTH0_ISSUER', None),
            'audience': getattr(settings, 'AUTH0_AUDIENCE', None),
            'jwks_url': getattr(settings, 'AUTH0_JWKS_URL', None),
        },
        'usage': {
            'header': 'Authorization: Bearer YOUR_JWT_TOKEN',
            'endpoint': request.build_absolute_uri(),
        }
    })
