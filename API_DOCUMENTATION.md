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
  "markdown_page": "# Title\n\nContent to convert..."
}
```

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
  ]
}
```

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
  "extra_info": "Information about extra content"
}
```

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
  "height": 600
}
```

**Supported Formats:** PNG, JPEG, SVG, WebP  
**Max File Size:** 50MB

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

### 7. Generate Image
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

### 8. List Images
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

### 9. Find Similar Images
Search for images similar to a text query.

**Endpoint:** `POST /find-similar-images/`  
**Content-Type:** `application/json`

**Request:**
```json
{
  "query": "red vehicle",
  "n_results": 10,
  "image_set": "Vehicles",
  "exclude_ids": [1, 2, 3]
}
```

**Parameters:**
- `query` (required): Text description to search for
- `n_results` (required): Number of results to return
- `image_set` (optional): Filter by specific image set
- `exclude_ids` (optional): List of image IDs to exclude

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

---

## Image Set Management

### 10. Get Image Sets
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

### 11. Get Images in Set
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

### 12. Save Processed Content
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

### 13. List Saved Content
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

### 14. Get Saved Content Details
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

### 15. Delete Saved Content
Delete saved content.

**Endpoint:** `DELETE /saved-content/{content_id}/`

**Response:** HTTP 204 No Content

### 16. Update Content Image
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

---

## System Health Endpoint

### 17. Health Check
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

## Rate Limits

Currently, no rate limits are enforced. This may change in production deployments.

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