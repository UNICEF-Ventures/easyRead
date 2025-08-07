# EasyRead API Documentation

This document provides comprehensive documentation for the EasyRead API endpoints, including the new embedding system functionality.

## Base URL
```
http://localhost:8000/api/
```

## Authentication
Currently, the API does not require authentication. This may change in production deployments.

## Common Response Format

### Success Response
```json
{
  "data": {...},
  "status": "success"
}
```

### Error Response
```json
{
  "error": "Error message description",
  "status": "error"
}
```

---

## Document Processing Endpoints

### 1. Convert PDF to Markdown
Convert a PDF document to markdown format for processing.

**Endpoint:** `POST /pdf-to-markdown/`  
**Content-Type:** `multipart/form-data`

**Request:**
```bash
curl -X POST \
  -F "file=@document.pdf" \
  http://localhost:8000/api/pdf-to-markdown/
```

**Response:**
```json
{
  "pages": [
    "# Page 1 Content\n\nMarkdown content...",
    "# Page 2 Content\n\nMore content..."
  ]
}
```

### 2. Process Page to Easy Read
Convert a markdown page to easy-read format with image suggestions.

**Endpoint:** `POST /process-page/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "markdown_page": "# Title\n\nContent to convert...",
  "selected_sets": ["Vehicles", "Animals"]
}
```

**Parameters:**
- `markdown_page` (required): The markdown content to convert
- `selected_sets` (optional): Array of image set names to prefer for image suggestions

**Response:**
```json
{
  "title": "Easy Read Title",
  "easy_read_sentences": [
    {
      "sentence": "Simple sentence 1.",
      "image_retrieval": "keyword for image search"
    },
    {
      "sentence": "Simple sentence 2.",
      "image_retrieval": "another keyword"
    }
  ],
  "selected_sets": ["Vehicles", "Animals"]
}
```

**Notes:**
- Pages with less than 5 meaningful words are automatically skipped
- Analytics tracking records page processing metrics

### 3. Validate Content Completeness
Check if easy-read content covers all information from the original.

**Endpoint:** `POST /validate-completeness/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "original_markdown": "Original content...",
  "easy_read_sentences": ["Sentence 1", "Sentence 2"]
}
```

**Response:**
```json
{
  "is_complete": true,
  "missing_info": "Information about missing topics",
  "extra_info": "Information about extra content",
  "other_feedback": "Additional validation feedback"
}
```

**Notes:**
- Analytics tracking records validation results and completion metrics

### 4. Revise Sentences
Improve easy-read sentences based on validation feedback.

**Endpoint:** `POST /revise-sentences/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "original_markdown": "Original content...",
  "current_sentences": [
    {"sentence": "Current sentence", "image_retrieval": "keyword"}
  ],
  "validation_feedback": {
    "is_complete": false,
    "missing_info": "Missing topics",
    "extra_info": "Extra content"
  }
}
```

**Response:**
```json
{
  "easy_read_sentences": [
    {
      "sentence": "Revised sentence",
      "image_retrieval": "updated keyword"
    }
  ]
}
```

---

## Image Management Endpoints

### 5. Upload Single Image
Upload an image file with optional description and set assignment.

**Endpoint:** `POST /upload-image/`  
**Content-Type:** `multipart/form-data`

**Request:**
```bash
curl -X POST \
  -F "image=@image.png" \
  -F "description=A red car" \
  -F "set_name=Vehicles" \
  http://localhost:8000/api/upload-image/
```

**Response:**
```json
{
  "message": "Image uploaded successfully.",
  "image_id": 123,
  "image_path": "images/car.png",
  "image_url": "http://localhost:8000/media/images/car.png",
  "filename": "car.png",
  "set_name": "Vehicles",
  "description": "A red car",
  "embeddings_created": 2,
  "file_format": "PNG",
  "file_size": 45678,
  "width": 800,
  "height": 600,
  "upload_session_id": "sess_abc123"
}
```

**Supported Formats:** PNG, JPEG, SVG, WebP  
**Max File Size:** 50MB

**Security Features:**
- Comprehensive file validation with magic number checking
- Rate limiting for upload requests
- Security logging for all upload attempts
- SVG files are automatically converted to PNG for embedding compatibility

**Analytics:**
- Upload attempts and success rates are tracked
- File size and format metrics are recorded

### 6. Batch Upload Images
Upload multiple images at once.

**Endpoint:** `POST /batch-upload-images/`  
**Content-Type:** `multipart/form-data`

**Request:**
```bash
curl -X POST \
  -F "images=@image1.png" \
  -F "images=@image2.jpg" \
  -F "description=Vehicle images" \
  -F "set_name=Vehicles" \
  http://localhost:8000/api/batch-upload-images/
```

**Response:**
```json
{
  "message": "Processed 2 images: 2 succeeded, 0 failed",
  "results": [
    {
      "success": true,
      "filename": "image1.png",
      "image_path": "images/image1.png",
      "image_url": "http://localhost:8000/media/images/image1.png"
    },
    {
      "success": true,
      "filename": "image2.jpg",
      "image_path": "images/image2.jpg",
      "image_url": "http://localhost:8000/media/images/image2.jpg"
    }
  ],
  "successful_uploads": 2,
  "total_uploads": 2,
  "description": "Vehicle images",
  "set_name": "Vehicles"
}
```

### 7. Optimized Batch Upload Images (NEW)
Handle large batch uploads (1000+ images) with chunked processing and progress tracking.

**Endpoint:** `POST /optimized-batch-upload/`  
**Content-Type:** `multipart/form-data`

**Request:**
```bash
curl -X POST \
  -F "images=@image1.png" \
  -F "images=@image2.jpg" \
  -F "images=@image3.png" \
  [...many more images...] \
  -F "batch_size=50" \
  -F "set_name=LargeBatch" \
  -F "description=Large batch upload" \
  http://localhost:8000/api/optimized-batch-upload/
```

**Parameters:**
- `images` (required): Multiple image files (minimum 100 images)
- `batch_size` (optional): Chunk size for processing (10-100, default: 50)
- `set_name` (optional): Target image set name
- `description` (optional): Description for all images

**Response:**
```json
{
  "message": "Batch upload started",
  "session_id": "batch_sess_xyz789",
  "total_images": 1500,
  "batch_size": 50,
  "estimated_time": "15-20 minutes"
}
```

**Rate Limiting:** 5 large batch uploads per hour  
**Requirements:** Minimum 100 images required

### 8. Upload Progress Tracking (NEW)
Check the progress of an optimized batch upload.

**Endpoint:** `GET /upload-progress/{session_id}/`

**Example:** `GET /upload-progress/batch_sess_xyz789/`

**Response:**
```json
{
  "session_id": "batch_sess_xyz789",
  "status": "processing",
  "progress": {
    "processed": 750,
    "total": 1500,
    "percentage": 50.0,
    "current_batch": 15,
    "total_batches": 30
  },
  "results": {
    "successful": 745,
    "failed": 5,
    "success_rate": 99.33
  },
  "estimated_completion": "2024-01-01T12:30:00Z"
}
```

**Status Values:**
- `processing`: Upload in progress
- `completed`: All images processed
- `failed`: Upload encountered fatal error

### 9. Upload Folder (NEW)
Upload folder structures with automatic image set creation based on folder names.

**Endpoint:** `POST /upload-folder/`  
**Content-Type:** `multipart/form-data`

**Request:**
```bash
curl -X POST \
  -F "files=@Animals/dog.png" \
  -F "files=@Animals/cat.jpg" \
  -F "files=@Vehicles/car.png" \
  -F "files=@Vehicles/truck.jpg" \
  http://localhost:8000/api/upload-folder/
```

**Features:**
- Automatically creates image sets based on folder structure
- Processes files with `webkitRelativePath` information
- Handles nested folder hierarchies
- Rate limiting: 50 uploads per minute

**Response:**
```json
{
  "message": "Folder uploaded successfully",
  "sets_created": ["Animals", "Vehicles"],
  "total_files": 4,
  "successful_uploads": 4,
  "results": [
    {
      "filename": "dog.png",
      "set_name": "Animals",
      "success": true,
      "image_url": "http://localhost:8000/media/images/dog.png"
    }
  ]
}
```

### 10. Generate Image
Generate an image using AI based on a text prompt.

**Endpoint:** `POST /generate-image/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "prompt": "A red car driving on a sunny road"
}
```

**Response:**
```json
{
  "message": "Image generated successfully.",
  "new_image_id": 124,
  "new_image_url": "http://localhost:8000/media/images/generated_abc123.png",
  "embeddings_created": 2,
  "filename": "generated_abc123.png",
  "set_name": "Generated"
}
```

### 11. List Images
Get all images organized by sets.

**Endpoint:** `GET /list-images/`

**Response:**
```json
{
  "images_by_set": {
    "General": [
      {
        "id": 1,
        "filename": "sample.png",
        "image_url": "http://localhost:8000/media/images/sample.png",
        "description": "Sample image",
        "file_format": "PNG",
        "file_size": 12345,
        "width": 400,
        "height": 300,
        "created_at": "2024-01-01T10:00:00Z"
      }
    ],
    "Vehicles": [
      {
        "id": 123,
        "filename": "car.png",
        "image_url": "http://localhost:8000/media/images/car.png",
        "description": "A red car",
        "file_format": "PNG",
        "file_size": 45678,
        "width": 800,
        "height": 600,
        "created_at": "2024-01-01T11:00:00Z"
      }
    ]
  },
  "total_images": 2,
  "total_sets": 2
}
```

---

## Image Search Endpoints

### 12. Find Similar Images
Search for images similar to a text query.

**Endpoint:** `POST /find-similar-images/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "query": "red vehicle",
  "n_results": 10,
  "image_set": "Vehicles",
  "image_sets": ["Vehicles", "Transportation"],
  "exclude_ids": [1, 2, 3]
}
```

**Parameters:**
- `query` (required): Text description to search for
- `n_results` (required): Number of results to return
- `image_set` (optional): Filter by specific image set (single set)
- `image_sets` (optional): Filter by multiple image sets (array)
- `exclude_ids` (optional): List of image IDs to exclude

**Notes:**
- Use either `image_set` or `image_sets`, not both
- Enhanced path handling and URL building for better performance
- Analytics tracking records search queries and result metrics

**Response:**
```json
{
  "results": [
    {
      "id": 123,
      "url": "http://localhost:8000/media/images/car.png",
      "description": "A red car",
      "similarity": 0.95,
      "filename": "car.png",
      "set_name": "Vehicles",
      "file_format": "PNG"
    },
    {
      "id": 124,
      "url": "http://localhost:8000/media/images/truck.png",
      "description": "Red truck",
      "similarity": 0.87,
      "filename": "truck.png",
      "set_name": "Vehicles",
      "file_format": "PNG"
    }
  ]
}
```

### 13. Batch Image Search (NEW)
Process multiple image search queries in a single optimized request with optimal image allocation.

**Endpoint:** `POST /find-similar-images-batch/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "queries": [
    {
      "query": "red car",
      "n_results": 5,
      "image_sets": ["Vehicles"]
    },
    {
      "query": "happy dog",
      "n_results": 3,
      "image_sets": ["Animals"]
    },
    {
      "query": "blue house",
      "n_results": 4,
      "image_sets": ["Buildings"]
    }
  ],
  "prevent_duplicates": true
}
```

**Parameters:**
- `queries` (required): Array of search query objects
- `prevent_duplicates` (optional): Prevent same image appearing in multiple results (default: true)

**Response:**
```json
{
  "results": [
    {
      "query": "red car",
      "images": [
        {
          "id": 123,
          "url": "http://localhost:8000/media/images/car.png",
          "description": "A red car",
          "similarity": 0.95,
          "filename": "car.png",
          "set_name": "Vehicles"
        }
      ]
    },
    {
      "query": "happy dog", 
      "images": [...]
    }
  ],
  "allocation_stats": {
    "total_images_allocated": 12,
    "unique_images_used": 10,
    "duplicate_prevention_active": true,
    "processing_time_ms": 234
  }
}
```

**Features:**
- Parallel processing with ThreadPoolExecutor for performance
- Optimal image allocation algorithm prevents duplicate assignments
- Analytics tracking for batch search metrics
- Configurable duplicate prevention

---

## Image Set Management

### 14. Get Image Sets
List all available image sets.

**Endpoint:** `GET /image-sets/`

**Response:**
```json
{
  "image_sets": [
    {
      "id": 1,
      "name": "General",
      "description": "General images without specific category",
      "image_count": 15,
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": 2,
      "name": "Vehicles",
      "description": "Images for Vehicles set",
      "image_count": 8,
      "created_at": "2024-01-01T10:00:00Z"
    }
  ],
  "total_sets": 2
}
```

### 15. Get Images in Set
Get all images in a specific set.

**Endpoint:** `GET /image-sets/{set_name}/images/`

**Parameters:**
- `limit` (optional): Maximum number of images to return (default: 50)

**Example:** `GET /image-sets/Vehicles/images/?limit=20`

**Response:**
```json
{
  "set_name": "Vehicles",
  "images": [
    {
      "id": 123,
      "filename": "car.png",
      "set_name": "Vehicles",
      "description": "A red car",
      "url": "http://localhost:8000/media/images/car.png",
      "file_format": "PNG",
      "file_size": 45678,
      "width": 800,
      "height": 600,
      "created_at": "2024-01-01T11:00:00Z"
    }
  ],
  "total_images": 8,
  "limit": 20
}
```

---

## Content Management Endpoints

### 16. Save Processed Content
Save the completed easy-read content with images.

**Endpoint:** `POST /save-processed-content/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "original_markdown": "Original document content...",
  "title": "Easy Read Document Title",
  "easy_read_json": [
    {
      "sentence": "Easy read sentence 1.",
      "image_retrieval": "keyword",
      "selected_image_path": "/media/images/image1.png",
      "alternative_images": [
        "/media/images/alt1.png",
        "/media/images/alt2.png"
      ]
    }
  ]
}
```

**Response:**
```json
{
  "message": "Content saved successfully.",
  "id": 456
}
```

### 17. List Saved Content
Get a list of all saved content.

**Endpoint:** `GET /list-saved-content/`

**Response:**
```json
{
  "content": [
    {
      "id": 456,
      "title": "Easy Read Document Title",
      "created_at": "2024-01-01T12:00:00Z",
      "sentence_count": 5,
      "preview_image": "/media/images/image1.png"
    }
  ]
}
```

### 18. Get Saved Content Details
Retrieve full details of saved content.

**Endpoint:** `GET /saved-content/{content_id}/`

**Response:**
```json
{
  "id": 456,
  "title": "Easy Read Document Title",
  "original_markdown": "Original content...",
  "easy_read_content": [
    {
      "sentence": "Easy read sentence 1.",
      "image_retrieval": "keyword",
      "selected_image_path": "/media/images/image1.png",
      "alternative_images": ["/media/images/alt1.png"]
    }
  ],
  "created_at": "2024-01-01T12:00:00Z"
}
```

### 19. Delete Saved Content
Delete saved content.

**Endpoint:** `DELETE /saved-content/{content_id}/`

**Response:** HTTP 204 No Content

### 20. Update Content Image
Update the selected image for a specific sentence.

**Endpoint:** `PATCH /update-saved-content-image/{content_id}/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "sentence_index": 0,
  "image_url": "/media/images/new_image.png",
  "all_images": [
    "/media/images/new_image.png",
    "/media/images/alternative.png"
  ]
}
```

**Response:**
```json
{
  "id": 456,
  "title": "Easy Read Document Title",
  "created_at": "2024-01-01T12:00:00Z",
  "original_markdown": "Original content...",
  "easy_read_content": [
    {
      "sentence": "Easy read sentence 1.",
      "image_retrieval": "keyword",
      "selected_image_path": "/media/images/new_image.png",
      "alternative_images": [
        "/media/images/new_image.png",
        "/media/images/alternative.png"
      ]
    }
  ]
}
```

### 21. Bulk Update Content Images (NEW)
Update multiple image selections at once for improved efficiency.

**Endpoint:** `PUT /bulk-update-saved-content-images/{content_id}/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "image_selections": {
    "0": "/media/images/new_image1.png",
    "1": "/media/images/new_image2.png",
    "3": "/media/images/new_image3.png"
  }
}
```

**Parameters:**
- `image_selections` (required): Object mapping sentence indices to new image URLs

**Response:**
```json
{
  "id": 456,
  "title": "Easy Read Document Title",
  "updated_sentences": 3,
  "easy_read_content": [
    {
      "sentence": "Updated sentence 1.",
      "image_retrieval": "keyword",
      "selected_image_path": "/media/images/new_image1.png",
      "alternative_images": [...]
    }
  ]
}
```

---

## Content Export Endpoints

### 22. Export Current Content to DOCX (NEW)
Export current (unsaved) EasyRead content as a formatted DOCX document.

**Endpoint:** `POST /export/docx/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "title": "My Easy Read Document",
  "easy_read_content": [
    {
      "sentence": "This is an easy read sentence.",
      "image_retrieval": "keyword",
      "selected_image_path": "/media/images/image1.png"
    },
    {
      "sentence": "This is another sentence.",
      "image_retrieval": "another keyword", 
      "selected_image_path": "/media/images/image2.png"
    }
  ],
  "original_markdown": "Original document content..."
}
```

**Response:**
- **Content-Type:** `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- **Content-Disposition:** `attachment; filename="easy_read_document.docx"`
- Returns the DOCX file as binary data

**Features:**
- UNICEF-branded styling with blue borders
- Table-based layout (image + text columns)
- Automatic image path resolution with fallbacks
- Page numbering and professional formatting
- Analytics tracking for export events

### 23. Export Saved Content to DOCX (NEW)
Export previously saved content as a DOCX document.

**Endpoint:** `GET /export/docx/{content_id}/`

**Example:** `GET /export/docx/456/`

**Response:**
- **Content-Type:** `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- **Content-Disposition:** `attachment; filename="saved_content_title.docx"`
- Returns the DOCX file as binary data

**Error Responses:**
- `404 Not Found`: Content with specified ID does not exist
- `500 Internal Server Error`: Document generation failed

---

## System Health Endpoint

### 24. Health Check
Check the health status of the system components.

**Endpoint:** `GET /health/`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1704110400.0,
  "components": {
    "embedding_model": {
      "status": "healthy",
      "model_loaded": true,
      "test_embedding_generated": true,
      "embedding_dimension": 1024
    },
    "database": {
      "status": "healthy",
      "database_connected": true,
      "image_sets_count": 3,
      "images_count": 150,
      "embeddings_count": 280
    },
    "storage": {
      "status": "healthy",
      "media_root_exists": true,
      "media_root_writable": true,
      "images_dir_exists": true,
      "images_dir_writable": true,
      "media_root_path": "/path/to/media"
    }
  },
  "metrics": {
    "embedding_generation": {
      "total_requests": 150,
      "successful": 148,
      "failed": 2,
      "success_rate": 98.67,
      "avg_time": 1.25
    },
    "similarity_search": {
      "total_requests": 45,
      "successful": 45,
      "failed": 0,
      "success_rate": 100.0,
      "avg_time": 0.85
    }
  }
}
```

**HTTP Status Codes:**
- `200 OK`: System is healthy
- `503 Service Unavailable`: System has issues

---

## Admin Authentication Endpoints

The API includes a complete admin authentication system for secure access to administrative functions.

### 25. Admin Web Login (NEW)
Display login form and handle web authentication.

**Endpoint:** `GET/POST /admin/login/`

**GET Request:**
Returns HTML login form for web interface.

**POST Request:**
**Content-Type:** `application/x-www-form-urlencoded`

**Request:**
```
username=admin
password=your_password
```

**Response (Success):**
- HTTP 302 Redirect to `/admin/dashboard/`
- Sets session authentication cookies

**Response (Failure):**
- HTTP 200 with error message in login form

### 26. Admin Dashboard (NEW)
Serve React admin interface (requires authentication).

**Endpoint:** `GET /admin/dashboard/`

**Response:**
- HTML page with React admin interface (if authenticated)
- HTTP 302 Redirect to `/admin/login/` (if not authenticated)

**Requirements:**
- Valid session authentication
- Admin user privileges

### 27. Admin Web Logout (NEW)
Log out from admin interface and redirect.

**Endpoint:** `GET /admin/logout/`

**Response:**
- HTTP 302 Redirect to `/admin/login/`
- Clears session authentication cookies

### 28. Check Authentication Status (NEW)
Check current authentication status via API.

**Endpoint:** `GET /admin/check-auth/`

**Response (Authenticated):**
```json
{
  "authenticated": true,
  "username": "admin"
}
```

**Response (Not Authenticated):**
```json
{
  "authenticated": false
}
```

### 29. API Login (NEW)
Authenticate via API for programmatic access.

**Endpoint:** `POST /admin/api/login/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**Response (Success):**
```json
{
  "message": "Logged in successfully",
  "username": "admin"
}
```

**Response (Failure):**
```json
{
  "error": "Invalid credentials"
}
```

**HTTP Status Codes:**
- `200 OK`: Login successful
- `400 Bad Request`: Invalid credentials or missing fields

### 30. API Logout (NEW)
Log out from API session.

**Endpoint:** `POST /admin/api/logout/`

**Requirements:**
- Valid session authentication

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**HTTP Status Codes:**
- `200 OK`: Logout successful
- `401 Unauthorized`: Not authenticated

**Security Features:**
- Session-based authentication with Django sessions
- CSRF protection for web forms
- Secure password validation
- Rate limiting on authentication attempts
- Session timeout and cleanup

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input parameters |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource already exists |
| 413 | Payload Too Large - File size exceeds limits |
| 415 | Unsupported Media Type - Invalid file format |
| 500 | Internal Server Error - Server processing error |
| 503 | Service Unavailable - System component unavailable |

---

## Rate Limits and Security Features

### Rate Limiting Policies

The API implements comprehensive rate limiting to ensure system stability and prevent abuse:

**Upload Endpoints:**
- **Regular Image Upload** (`/upload-image/`): Standard rate limits apply
- **Batch Upload** (`/batch-upload-images/`): 50 uploads per minute
- **Optimized Batch Upload** (`/optimized-batch-upload/`): 5 large batch uploads per hour
- **Folder Upload** (`/upload-folder/`): 50 uploads per minute
- **Image Generation** (`/generate-image/`): Configurable limits based on AI service quotas

**Authentication Endpoints:**
- **Login Attempts**: Rate limited to prevent brute force attacks
- **Session Creation**: Limited concurrent sessions per user

**Search and Processing:**
- **Similarity Search**: Optimized caching reduces load
- **Document Processing**: Queued processing for large documents

### Security Features

**File Upload Security:**
- **Magic Number Validation**: Files validated beyond file extensions
- **File Size Limits**: 50MB maximum per file
- **Format Validation**: Only approved formats (PNG, JPEG, SVG, WebP)
- **Path Sanitization**: Secure file path handling and validation
- **Virus Scanning**: Optional malware detection (configurable)
- **Content Type Verification**: MIME type validation

**Authentication Security:**
- **Session Management**: Secure Django session framework
- **CSRF Protection**: Cross-Site Request Forgery protection for web forms
- **Password Security**: Secure password hashing and validation
- **Session Timeouts**: Automatic session expiration
- **Secure Cookies**: HTTP-only and secure cookie flags

**Request Validation:**
- **Input Sanitization**: All user inputs validated and sanitized
- **SQL Injection Protection**: Django ORM prevents SQL injection
- **XSS Prevention**: Output encoding and Content Security Policy
- **Request Size Limits**: Maximum request body size enforcement

**Logging and Monitoring:**
- **Security Event Logging**: Failed authentication attempts logged
- **Upload Attempt Tracking**: All file uploads logged with metadata
- **Error Monitoring**: Comprehensive error tracking and alerting
- **Access Logging**: API endpoint usage tracking

**Additional Protections:**
- **CORS Configuration**: Controlled cross-origin resource sharing
- **HTTP Security Headers**: Security headers for web interface
- **Content Validation**: AI-generated content safety checks
- **Resource Limits**: Memory and CPU usage monitoring

### Error Handling

**Rate Limit Exceeded:**
```json
{
  "error": "Rate limit exceeded. Please try again later.",
  "retry_after": 60,
  "limit_type": "upload_per_minute"
}
```

**Security Violations:**
```json
{
  "error": "Security validation failed",
  "details": "File type not allowed"
}
```

**Authentication Errors:**
```json
{
  "error": "Authentication required",
  "auth_url": "/admin/login/"
}
```

---

## Data Management Commands

### CSV Image Import
Load images from a CSV file using Django management command:

```bash
python manage.py load_images_from_csv images.csv --create-general-set
```

**CSV Format:**
```csv
set_name,image_path,image_description
Vehicles,/path/to/car.png,A red car on the road
Animals,/path/to/dog.svg,A friendly dog
General,/path/to/house.jpg,A blue house
```

**Options:**
- `--batch-size 32`: Set processing batch size
- `--skip-existing`: Skip images that already exist
- `--create-general-set`: Create "General" set automatically
- `--media-root /path`: Specify media root directory

---

## Analytics and Usage Tracking

### Overview

The EasyRead API includes comprehensive analytics tracking to monitor system usage, optimize performance, and understand user behavior. This data collection helps improve the service and provides insights for system maintenance.

### Data Collection Transparency

**What We Track:**
- **Session Information**: IP addresses, user agents, session duration
- **API Usage**: Endpoint calls, request/response times, success/failure rates
- **Content Processing**: Document sizes, processing times, conversion metrics
- **Image Interactions**: Upload counts, search queries, similarity match rates
- **User Journey**: Page processing sequences, content export events
- **System Performance**: Resource usage, error rates, processing bottlenecks

**Analytics Events Tracked:**

**Document Processing Analytics:**
- PDF upload events (file size, page count)
- Page processing metrics (sentences generated, processing time)
- Content validation results (completeness scores, revision counts)
- Sentence revision tracking (improvement metrics)

**Image System Analytics:**
- Image upload success/failure rates
- File format distribution and size metrics
- Search query patterns and result relevance
- Image set selection preferences
- Generation request patterns (AI image creation)

**Content Management Analytics:**
- Content saving events and export formats
- Image selection changes and user preferences
- Document completion rates (upload → processing → export)
- User engagement patterns and session flows

**System Health Analytics:**
- API endpoint performance metrics
- Database query optimization data
- Error tracking and resolution patterns
- Resource usage and scaling metrics

### Privacy and Data Handling

**Session Identification:**
- Sessions identified by IP address and user agent combinations
- No personally identifiable information (PII) collected
- No user authentication required for basic functionality
- Session data automatically expires after configurable timeouts

**Data Retention:**
- Analytics data retained for system optimization and maintenance
- Configurable retention periods for different data types
- Automatic cleanup of expired session data
- No permanent storage of document content without explicit user action

**Data Usage:**
- Analytics used for system performance optimization
- Usage patterns help improve AI model performance
- Error tracking enables proactive system maintenance
- No data sharing with third parties

### Analytics API Endpoints

**Generate Analytics Report:**
```bash
# Management command for generating analytics reports
python manage.py analytics_report --days 30 --format json
```

**Health Check with Metrics:**
The `/health/` endpoint includes aggregate analytics metrics:

```json
{
  "metrics": {
    "embedding_generation": {
      "total_requests": 150,
      "successful": 148,
      "failed": 2,
      "success_rate": 98.67,
      "avg_time": 1.25
    },
    "similarity_search": {
      "total_requests": 45,
      "successful": 45,
      "success_rate": 100.0,
      "avg_time": 0.85
    }
  }
}
```

### Analytics Data Models

**Key Database Models:**
- **UserSession**: Session tracking with summary metrics
- **SessionEvent**: Individual events within user sessions
- **ImageSetSelection**: Image set preference tracking
- **ImageSelectionChange**: Image selection modification tracking

**Tracked Metrics:**
- Session funnel conversion rates (upload → processing → export)
- Content volume metrics (sentences generated, document sizes)
- User engagement patterns (session duration, feature usage)
- System performance indicators (response times, error rates)

### Opting Out

While the system doesn't require user authentication, organizations deploying EasyRead can:
- Configure analytics collection levels in system settings
- Disable specific tracking categories through environment variables
- Implement custom privacy policies for their deployment
- Export or purge analytics data through management commands

---

## Performance Considerations

1. **Image Uploads**: SVG files are automatically converted to PNG for embedding generation
2. **Caching**: Embeddings and search results are cached for improved performance
3. **Batch Processing**: Use batch upload for multiple images
4. **File Sizes**: Large images may take longer to process
5. **Database**: PostgreSQL with pgvector provides optimal performance for similarity searches

---

## Migration Guide

### From ChromaDB to PostgreSQL
The new system uses PostgreSQL instead of ChromaDB. To migrate:

1. Export existing embeddings from ChromaDB
2. Set up PostgreSQL with pgvector extension
3. Run migrations to create new database schema
4. Use CSV import command to load images with embeddings
5. Update frontend to use new API response formats

### API Changes
- `list-images/` response format changed from separated lists to grouped by sets
- `find-similar-images/` now returns `similarity` instead of `distance`
- New optional parameters added to various endpoints
- New endpoints for image set management

---

For more information or support, please refer to the implementation documentation or contact the development team.