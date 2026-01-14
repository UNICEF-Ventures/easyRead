"""
Tests for JWT authentication module.

Tests cover:
- Token extraction from headers
- Token validation (signature, expiration, issuer, audience)
- Auth0User object creation
- DRF authentication class integration
- Permission classes

Note: Uses SimpleTestCase to avoid database setup requirements.
These are unit tests with mocked dependencies.
"""
import json
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import SimpleTestCase, RequestFactory, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import AuthenticationFailed

from .jwt_auth import (
    Auth0User,
    Auth0JWTAuthentication,
    get_token_from_header,
    validate_token,
)
from .permissions import (
    IsPlaygroundAuthenticated,
    IsPlaygroundOrOTPAuthenticated,
    HasProjectAccess,
)


# Sample JWT payload for testing
SAMPLE_PAYLOAD = {
    'sub': 'auth0|123456789',
    'iss': 'https://auth.ooiplayground.com/',
    'aud': ['https://dev-sl2hec54ogo7vjrm.us.auth0.com/api/v2/'],
    'exp': int(time.time()) + 3600,  # Valid for 1 hour
    'iat': int(time.time()),
    'azp': 'test-client-id',
    'scope': 'openid profile email',
    'https://ooi-playground.com/email': 'test@unicef.org',
    'https://ooi-playground.com/roles': 'unicef',
    'https://ooi-playground.com/allowed-projects': ['easyread', 'cpd', 'eshu'],
}

EXPIRED_PAYLOAD = {
    **SAMPLE_PAYLOAD,
    'exp': int(time.time()) - 3600,  # Expired 1 hour ago
}


class Auth0UserTests(SimpleTestCase):
    """Tests for the Auth0User class."""

    def test_user_creation_from_payload(self):
        """Test creating an Auth0User from a JWT payload."""
        user = Auth0User(SAMPLE_PAYLOAD)

        self.assertEqual(user.token_sub, 'auth0|123456789')
        self.assertEqual(user.email, 'test@unicef.org')
        self.assertEqual(user.roles, 'unicef')
        self.assertIn('easyread', user.allowed_projects)
        self.assertTrue(user.is_authenticated)
        self.assertFalse(user.is_anonymous)

    def test_user_has_project_access(self):
        """Test project access checking."""
        user = Auth0User(SAMPLE_PAYLOAD)

        self.assertTrue(user.has_project_access('easyread'))
        self.assertTrue(user.has_project_access('cpd'))
        self.assertFalse(user.has_project_access('nonexistent-project'))

    def test_user_str_representation(self):
        """Test string representation of Auth0User."""
        user = Auth0User(SAMPLE_PAYLOAD)
        self.assertEqual(str(user), 'test@unicef.org')

    def test_user_without_email(self):
        """Test user creation when email is not in custom claim."""
        payload = {**SAMPLE_PAYLOAD}
        del payload['https://ooi-playground.com/email']
        payload['email'] = 'fallback@example.com'

        user = Auth0User(payload)
        self.assertEqual(user.email, 'fallback@example.com')

    def test_user_id_property(self):
        """Test that id property returns the sub claim."""
        user = Auth0User(SAMPLE_PAYLOAD)
        self.assertEqual(user.id, 'auth0|123456789')


class TokenExtractionTests(SimpleTestCase):
    """Tests for token extraction from request headers."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_extract_valid_bearer_token(self):
        """Test extracting a valid Bearer token from header."""
        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer test-token-123'

        token = get_token_from_header(request)
        self.assertEqual(token, 'test-token-123')

    def test_extract_token_no_header(self):
        """Test extraction when no Authorization header present."""
        request = self.factory.get('/')

        token = get_token_from_header(request)
        self.assertIsNone(token)

    def test_extract_token_invalid_format(self):
        """Test extraction with invalid header format."""
        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = 'InvalidFormat'

        with self.assertRaises(AuthenticationFailed) as context:
            get_token_from_header(request)
        self.assertIn('Invalid Authorization header format', str(context.exception.detail))

    def test_extract_token_wrong_scheme(self):
        """Test extraction with wrong auth scheme (not Bearer)."""
        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = 'Basic dXNlcjpwYXNz'

        with self.assertRaises(AuthenticationFailed) as context:
            get_token_from_header(request)
        self.assertIn('must start with Bearer', str(context.exception.detail))

    def test_extract_token_case_insensitive_bearer(self):
        """Test that Bearer is case-insensitive."""
        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = 'bearer test-token'

        token = get_token_from_header(request)
        self.assertEqual(token, 'test-token')


class TokenValidationTests(SimpleTestCase):
    """Tests for JWT token validation."""

    @patch('api.jwt_auth._jwks_client')
    def test_validate_valid_token(self, mock_jwks_client):
        """Test validation of a valid token."""
        import jwt

        # Create a mock signing key
        mock_key = MagicMock()
        mock_key.key = 'test-key'
        mock_jwks_client.get_signing_key.return_value = mock_key

        # Mock jwt.decode to return our sample payload
        with patch('api.jwt_auth.jwt.decode') as mock_decode:
            mock_decode.return_value = SAMPLE_PAYLOAD

            payload = validate_token('fake-token')

            self.assertEqual(payload['sub'], 'auth0|123456789')
            mock_decode.assert_called_once()

    @patch('api.jwt_auth._jwks_client')
    def test_validate_expired_token(self, mock_jwks_client):
        """Test validation rejects expired tokens."""
        import jwt

        mock_key = MagicMock()
        mock_key.key = 'test-key'
        mock_jwks_client.get_signing_key.return_value = mock_key

        with patch('api.jwt_auth.jwt.decode') as mock_decode:
            mock_decode.side_effect = jwt.ExpiredSignatureError('Token expired')

            with self.assertRaises(AuthenticationFailed) as context:
                validate_token('expired-token')

            self.assertIn('expired', str(context.exception.detail).lower())

    @patch('api.jwt_auth._jwks_client')
    def test_validate_invalid_signature(self, mock_jwks_client):
        """Test validation rejects tokens with invalid signatures."""
        import jwt

        mock_key = MagicMock()
        mock_key.key = 'test-key'
        mock_jwks_client.get_signing_key.return_value = mock_key

        with patch('api.jwt_auth.jwt.decode') as mock_decode:
            mock_decode.side_effect = jwt.InvalidSignatureError('Bad signature')

            with self.assertRaises(AuthenticationFailed) as context:
                validate_token('bad-signature-token')

            self.assertIn('signature', str(context.exception.detail).lower())

    @patch('api.jwt_auth._jwks_client')
    def test_validate_invalid_audience(self, mock_jwks_client):
        """Test validation rejects tokens with wrong audience."""
        import jwt

        mock_key = MagicMock()
        mock_key.key = 'test-key'
        mock_jwks_client.get_signing_key.return_value = mock_key

        with patch('api.jwt_auth.jwt.decode') as mock_decode:
            mock_decode.side_effect = jwt.InvalidAudienceError('Wrong audience')

            with self.assertRaises(AuthenticationFailed) as context:
                validate_token('wrong-audience-token')

            self.assertIn('audience', str(context.exception.detail).lower())

    @patch('api.jwt_auth._jwks_client')
    def test_validate_invalid_issuer(self, mock_jwks_client):
        """Test validation rejects tokens with wrong issuer."""
        import jwt

        mock_key = MagicMock()
        mock_key.key = 'test-key'
        mock_jwks_client.get_signing_key.return_value = mock_key

        with patch('api.jwt_auth.jwt.decode') as mock_decode:
            mock_decode.side_effect = jwt.InvalidIssuerError('Wrong issuer')

            with self.assertRaises(AuthenticationFailed) as context:
                validate_token('wrong-issuer-token')

            self.assertIn('issuer', str(context.exception.detail).lower())


class Auth0JWTAuthenticationTests(SimpleTestCase):
    """Tests for the DRF authentication class."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.auth = Auth0JWTAuthentication()

    def test_authenticate_no_token(self):
        """Test authentication returns None when no token provided."""
        request = self.factory.get('/')

        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    @patch('api.jwt_auth.validate_token')
    def test_authenticate_valid_token(self, mock_validate):
        """Test authentication with a valid token."""
        mock_validate.return_value = SAMPLE_PAYLOAD

        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer valid-token'

        user, token = self.auth.authenticate(request)

        self.assertIsInstance(user, Auth0User)
        self.assertEqual(user.email, 'test@unicef.org')
        self.assertEqual(token, 'valid-token')

    @patch('api.jwt_auth.validate_token')
    def test_authenticate_invalid_token(self, mock_validate):
        """Test authentication raises exception for invalid token."""
        mock_validate.side_effect = AuthenticationFailed('Invalid token')

        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer invalid-token'

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_header(self):
        """Test WWW-Authenticate header value."""
        request = self.factory.get('/')
        header = self.auth.authenticate_header(request)
        self.assertEqual(header, 'Bearer realm="api"')


class PermissionTests(SimpleTestCase):
    """Tests for permission classes."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_is_playground_authenticated_with_auth0_user(self):
        """Test IsPlaygroundAuthenticated with Auth0 user."""
        permission = IsPlaygroundAuthenticated()
        request = self.factory.get('/')
        request.user = Auth0User(SAMPLE_PAYLOAD)

        self.assertTrue(permission.has_permission(request, None))

    def test_is_playground_authenticated_anonymous(self):
        """Test IsPlaygroundAuthenticated with anonymous user."""
        permission = IsPlaygroundAuthenticated()
        request = self.factory.get('/')
        request.user = Mock()
        request.user.is_authenticated = False

        self.assertFalse(permission.has_permission(request, None))

    def test_is_playground_or_otp_with_auth0_user(self):
        """Test IsPlaygroundOrOTPAuthenticated with Auth0 user."""
        permission = IsPlaygroundOrOTPAuthenticated()
        request = self.factory.get('/')
        request.user = Auth0User(SAMPLE_PAYLOAD)

        self.assertTrue(permission.has_permission(request, None))

    def test_is_playground_or_otp_with_django_user(self):
        """Test IsPlaygroundOrOTPAuthenticated with Django session user."""
        permission = IsPlaygroundOrOTPAuthenticated()
        request = self.factory.get('/')
        request.user = Mock()
        request.user.is_authenticated = True
        # Django user doesn't have allowed_projects
        del request.user.allowed_projects

        self.assertTrue(permission.has_permission(request, None))

    def test_has_project_access_session_user_bypasses_check(self):
        """Test HasProjectAccess allows session users (no allowed_projects attr)."""
        permission = HasProjectAccess()
        request = self.factory.get('/')

        # Django session user (doesn't have allowed_projects attribute)
        request.user = Mock()
        request.user.is_authenticated = True
        # Simulate Django user without allowed_projects
        if hasattr(request.user, 'allowed_projects'):
            del request.user.allowed_projects

        # Should pass because session users bypass project check
        self.assertTrue(permission.has_permission(request, None))

    def test_has_project_access_user_has_access(self):
        """Test HasProjectAccess when user has the project."""
        permission = HasProjectAccess()
        request = self.factory.get('/')
        request.user = Auth0User(SAMPLE_PAYLOAD)  # Has 'easyread' in allowed_projects

        with override_settings(AUTH0_PROJECT_NAME='easyread'):
            self.assertTrue(permission.has_permission(request, None))

    def test_has_project_access_user_no_access(self):
        """Test HasProjectAccess when user lacks the project."""
        permission = HasProjectAccess()
        request = self.factory.get('/')

        payload = {**SAMPLE_PAYLOAD}
        payload['https://ooi-playground.com/allowed-projects'] = ['other-project']
        request.user = Auth0User(payload)

        with override_settings(AUTH0_PROJECT_NAME='easyread'):
            self.assertFalse(permission.has_permission(request, None))


class JWTTestEndpointTests(SimpleTestCase):
    """Integration tests for the JWT test endpoint."""

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch('api.jwt_auth.validate_token')
    def test_jwt_test_endpoint_get_authenticated(self, mock_validate):
        """Test GET /api/auth/jwt-test/ with valid token."""
        from .jwt_auth_views import jwt_test

        mock_validate.return_value = SAMPLE_PAYLOAD

        request = self.factory.get('/api/auth/jwt-test/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer valid-token'

        # Manually run authentication
        auth = Auth0JWTAuthentication()
        user, _ = auth.authenticate(request)
        request.user = user

        response = jwt_test(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['authenticated'])
        self.assertEqual(response.data['auth_method'], 'jwt')
        self.assertEqual(response.data['user']['email'], 'test@unicef.org')

    def test_jwt_test_endpoint_get_unauthenticated(self):
        """Test GET /api/auth/jwt-test/ without token."""
        from .jwt_auth_views import jwt_test

        request = self.factory.get('/api/auth/jwt-test/')
        request.user = Mock()
        request.user.is_authenticated = False

        response = jwt_test(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['authenticated'])
        self.assertIn('auth0_config', response.data)

    @patch('api.jwt_auth_views.validate_token')
    def test_jwt_test_endpoint_post_valid_token(self, mock_validate):
        """Test POST /api/auth/jwt-test/ with token in body."""
        from .jwt_auth_views import jwt_test

        mock_validate.return_value = SAMPLE_PAYLOAD

        request = self.factory.post(
            '/api/auth/jwt-test/',
            {'token': 'test-token'},
            format='json'
        )
        request.user = Mock()
        request.user.is_authenticated = False

        response = jwt_test(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['authenticated'])
        self.assertTrue(response.data['token_valid'])

    def test_jwt_test_endpoint_post_no_token(self):
        """Test POST /api/auth/jwt-test/ without token in body."""
        from .jwt_auth_views import jwt_test

        request = self.factory.post('/api/auth/jwt-test/', {}, format='json')
        request.user = Mock()
        request.user.is_authenticated = False

        response = jwt_test(request)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['authenticated'])
