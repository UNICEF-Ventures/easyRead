"""
Centralized error handling for the EasyRead API.
Provides consistent error response formats and logging.
"""

import logging
import traceback
from typing import Dict, Any, Optional
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, 
                 error_code: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Exception for input validation errors."""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            details={"field": field, **(details or {})}
        )


class FileUploadError(APIError):
    """Exception for file upload errors."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="FILE_UPLOAD_ERROR",
            details=details
        )


class ProcessingError(APIError):
    """Exception for content processing errors."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="PROCESSING_ERROR",
            details=details
        )


class AIServiceError(APIError):
    """Exception for AI service errors."""
    def __init__(self, message: str, service: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="AI_SERVICE_ERROR",
            details={"service": service, **(details or {})}
        )


class ResourceNotFoundError(APIError):
    """Exception for resource not found errors."""
    def __init__(self, message: str, resource_type: Optional[str] = None, resource_id: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


def format_error_response(error: APIError, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Format an APIError into a standardized error response.
    
    Args:
        error: The APIError instance
        request_id: Optional request ID for tracking
        
    Returns:
        Standardized error response dictionary
    """
    response = {
        "error": {
            "code": error.error_code,
            "message": error.message,
            "status_code": error.status_code
        }
    }
    
    if error.details:
        response["error"]["details"] = error.details
    
    if request_id:
        response["error"]["request_id"] = request_id
    
    return response


def format_validation_error_response(field_errors: Dict[str, list], 
                                   request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Format field validation errors into a standardized response.
    
    Args:
        field_errors: Dictionary of field names to error lists
        request_id: Optional request ID for tracking
        
    Returns:
        Standardized validation error response
    """
    response = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "status_code": status.HTTP_400_BAD_REQUEST,
            "details": {
                "field_errors": field_errors
            }
        }
    }
    
    if request_id:
        response["error"]["request_id"] = request_id
    
    return response


def handle_api_exception(exception: Exception, request_id: Optional[str] = None) -> Response:
    """
    Handle an exception and return a standardized error response.
    
    Args:
        exception: The exception that occurred
        request_id: Optional request ID for tracking
        
    Returns:
        DRF Response with standardized error format
    """
    if isinstance(exception, APIError):
        # Log the error with context
        logger.error(
            f"API Error: {exception.error_code} - {exception.message}",
            extra={
                "error_code": exception.error_code,
                "status_code": exception.status_code,
                "details": exception.details,
                "request_id": request_id
            }
        )
        
        response_data = format_error_response(exception, request_id)
        return Response(response_data, status=exception.status_code)
    
    else:
        # Handle unexpected exceptions
        error_message = "An unexpected error occurred"
        
        # Log the full traceback for debugging (but don't expose it)
        logger.error(
            f"Unexpected error: {str(exception)}",
            extra={
                "exception_type": type(exception).__name__,
                "request_id": request_id,
                "traceback": traceback.format_exc()
            }
        )
        
        response_data = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": error_message,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        }
        
        if request_id:
            response_data["error"]["request_id"] = request_id
        
        return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def validate_file_upload(file, max_size_mb: int = 50, allowed_extensions: list = None) -> None:
    """
    Validate uploaded file and raise appropriate errors.
    
    Args:
        file: Uploaded file object
        max_size_mb: Maximum file size in MB
        allowed_extensions: List of allowed file extensions
        
    Raises:
        FileUploadError: If validation fails
    """
    if not file:
        raise FileUploadError("No file provided")
    
    # Check file size
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        raise FileUploadError(
            f"File size exceeds maximum allowed size of {max_size_mb}MB",
            details={"file_size": file.size, "max_size": max_size_bytes}
        )
    
    # Check file extension
    if allowed_extensions:
        file_extension = file.name.lower().split('.')[-1] if '.' in file.name else ''
        if file_extension not in [ext.lower() for ext in allowed_extensions]:
            raise FileUploadError(
                f"File type '{file_extension}' not allowed",
                details={
                    "file_extension": file_extension,
                    "allowed_extensions": allowed_extensions
                }
            )


def validate_required_fields(data: Dict, required_fields: list) -> None:
    """
    Validate that required fields are present in data.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        
    Raises:
        ValidationError: If any required field is missing
    """
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f"Required fields missing: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields}
        )


def validate_json_structure(data: Any, expected_type: type, field_name: str = "data") -> None:
    """
    Validate JSON data structure.
    
    Args:
        data: Data to validate
        expected_type: Expected data type
        field_name: Name of the field being validated
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(data, expected_type):
        raise ValidationError(
            f"Invalid {field_name} format",
            field=field_name,
            details={
                "expected_type": expected_type.__name__,
                "actual_type": type(data).__name__
            }
        )


class ErrorResponseMiddleware:
    """
    Middleware to handle uncaught exceptions and provide consistent error responses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Process uncaught exceptions and return standardized error responses.
        """
        # Generate a request ID for tracking
        request_id = getattr(request, 'id', None) or id(request)
        
        # Handle API exceptions
        if request.path.startswith('/api/'):
            return handle_api_exception(exception, str(request_id))
        
        # Let Django handle non-API exceptions normally
        return None


# Utility functions for common response patterns
def success_response(data: Any = None, message: str = "Success", status_code: int = status.HTTP_200_OK) -> Response:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
        
    Returns:
        DRF Response with standardized success format
    """
    response_data = {
        "success": True,
        "message": message
    }
    
    if data is not None:
        response_data["data"] = data
    
    return Response(response_data, status=status_code)


def paginated_response(data: list, page: int, page_size: int, total_count: int) -> Dict[str, Any]:
    """
    Create a standardized paginated response.
    
    Args:
        data: List of data items
        page: Current page number
        page_size: Items per page
        total_count: Total number of items
        
    Returns:
        Standardized paginated response dictionary
    """
    total_pages = (total_count + page_size - 1) // page_size
    
    return {
        "success": True,
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
    }