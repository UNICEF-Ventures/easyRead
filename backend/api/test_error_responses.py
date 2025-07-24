"""
Test file to demonstrate the new consistent error response formats.
This shows examples of the different error response types that will be returned by the API.
"""

# Example of successful response:
SUCCESS_RESPONSE = {
    "success": True,
    "message": "PDF converted successfully",
    "data": {
        "pages": ["Page 1 content...", "Page 2 content..."]
    }
}

# Example of validation error response:
VALIDATION_ERROR_RESPONSE = {
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Required fields missing: markdown_page",
        "status_code": 400,
        "details": {
            "missing_fields": ["markdown_page"]
        }
    }
}

# Example of file upload error response:
FILE_UPLOAD_ERROR_RESPONSE = {
    "error": {
        "code": "FILE_UPLOAD_ERROR", 
        "message": "File size exceeds maximum allowed size of 50MB",
        "status_code": 400,
        "details": {
            "file_size": 52428800,
            "max_size": 52428800
        }
    }
}

# Example of AI service error response:
AI_SERVICE_ERROR_RESPONSE = {
    "error": {
        "code": "AI_SERVICE_ERROR",
        "message": "LLM service temporarily unavailable",
        "status_code": 503,
        "details": {
            "service": "litellm"
        }
    }
}

# Example of processing error response:
PROCESSING_ERROR_RESPONSE = {
    "error": {
        "code": "PROCESSING_ERROR",
        "message": "Failed to convert PDF document",
        "status_code": 422
    }
}

# Example of resource not found error response:
RESOURCE_NOT_FOUND_ERROR_RESPONSE = {
    "error": {
        "code": "RESOURCE_NOT_FOUND",
        "message": "Processed content not found",
        "status_code": 404,
        "details": {
            "resource_type": "ProcessedContent",
            "resource_id": "123"
        }
    }
}

# Example of unexpected error response (sanitized):
INTERNAL_ERROR_RESPONSE = {
    "error": {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred",
        "status_code": 500
    }
}

# Example of paginated response:
PAGINATED_RESPONSE = {
    "success": True,
    "data": [
        {"id": 1, "filename": "image1.png"},
        {"id": 2, "filename": "image2.png"}
    ],
    "pagination": {
        "page": 1,
        "page_size": 10,
        "total_count": 25,
        "total_pages": 3,
        "has_next": True,
        "has_previous": False
    }
}