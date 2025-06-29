from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from docling.document_converter import DocumentConverter, PdfFormatOption
# Import OCR options
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions # Using Tesseract CLI as an example
import tempfile
import os
import logging
import yaml
import json
from pathlib import Path
import litellm
from django.conf import settings
from django.http import JsonResponse
import base64
# import cohere # Removed Cohere
import chromadb
from dotenv import load_dotenv
from PIL import Image
import io
import glob # Might not be needed here if not listing
import uuid # Moved import to top
from .models import ProcessedContent, ImageMetadata # Import the new model
from sentence_transformers import SentenceTransformer # Added SentenceTransformer
from openai import OpenAI
from django.core.files.base import ContentFile
from gradio_client import Client, handle_file # Added Gradio client import

# Setup logger for this module
logger = logging.getLogger(__name__)

# Create your views here.

# Setup LiteLLM logging (optional, but helpful)
# litellm.set_verbose=True 

# Define path to prompts directory relative to BASE_DIR
# Assuming BASE_DIR in settings.py points to the 'backend' directory
# If BASE_DIR points to the root, adjust the path.
# Let's check settings.py for BASE_DIR definition first.
# Reading settings.py confirmed BASE_DIR is backend parent (project root)
PROMPTS_DIR = settings.BASE_DIR.parent / 'prompts'
EASY_READ_PROMPT_FILE = PROMPTS_DIR / 'easy_read.yaml'
VALIDATE_COMPLETENESS_PROMPT_FILE = PROMPTS_DIR / 'validate_completeness.yaml'
REVISE_SENTENCES_PROMPT_FILE = PROMPTS_DIR / 'revise_sentences.yaml'
GENERATE_IMAGE_PROMPT_FILE = PROMPTS_DIR / 'generate_image.yaml'

# --- Configuration (Consider moving to settings.py) ---
load_dotenv(settings.BASE_DIR.parent / '.env') # Load .env from project root

# COHERE_API_KEY = os.getenv("COHERE_API_KEY") # Removed Cohere API Key
IMAGE_UPLOAD_DIR = settings.MEDIA_ROOT / "uploaded_images"
CHROMA_DB_PATH = settings.BASE_DIR.parent / "chroma_db" # Relative to project root
IMAGE_COLLECTION_NAME = "image_embeddings"
# COHERE_MODEL = "embed-english-light-v3.0" # Removed Cohere model
CLIP_MODEL_NAME = 'sentence-transformers/clip-ViT-B-32-multilingual-v1' # New CLIP model

# Ensure upload directory exists
IMAGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Initialize Clients ---
# co = None # Removed Cohere client initialization
# if COHERE_API_KEY:
#     try:
#         co = cohere.Client(COHERE_API_KEY)
#         logger.info("Cohere client initialized for image embedding.")
#     except Exception as e:
#         logger.error(f"Error initializing Cohere client: {e}")
# else:
#     logger.warning("COHERE_API_KEY not found. Image embedding will be skipped.")

# --- Initialize Sentence Transformer Model --- 
embedding_model = None
try:
    # Load the CLIP model
    embedding_model = SentenceTransformer(CLIP_MODEL_NAME)
    logger.info(f"Sentence Transformer model '{CLIP_MODEL_NAME}' loaded.")
except Exception as e:
     logger.error(f"Error loading Sentence Transformer model '{CLIP_MODEL_NAME}': {e}")
     # Application might not be usable without the model, consider raising an error or specific handling

# --- ChromaDB Initialization (remains the same, will create new db/collection) ---
chroma_client = None
image_collection = None
try:
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    # Get existing collection or create new one if it doesn't exist
    image_collection = chroma_client.get_or_create_collection(name=IMAGE_COLLECTION_NAME)
    logger.info(f"Connected to ChromaDB. Collection '{IMAGE_COLLECTION_NAME}' loaded/created.")
except Exception as e:
    logger.error(f"Error connecting to or setting up ChromaDB for images: {e}")

# --- OpenAI Client Initialization ---
openai_client = None
try:
    openai_client = OpenAI() # Assumes OPENAI_API_KEY is in environment
    logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    # Handle the error appropriately (e.g., disable the feature)

# --- Gradio Client Initialization ---
gradio_client = None
try:
    gradio_client = Client("https://scai.globalsymbols.com/")
    logger.info("Gradio client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Gradio client: {e}")

def load_prompt_template():
    """Loads the prompt template from the YAML file."""
    try:
        with open(EASY_READ_PROMPT_FILE, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {EASY_READ_PROMPT_FILE}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        return None

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def pdf_to_markdown(request):
    """
    API endpoint that accepts a PDF file upload and returns its Markdown conversion.
    """
    if 'file' not in request.FILES:
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    pdf_file = request.FILES['file']

    if not pdf_file.name.lower().endswith('.pdf'):
        return Response({"error": "Invalid file type, please upload a PDF"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            for chunk in pdf_file.chunks():
                temp_pdf.write(chunk)
            temp_pdf_path = temp_pdf.name

        # Convert PDF to Markdown using docling
        # Configure basic OCR
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False # Disable OCR for potentially faster text extraction
        # You might need Tesseract installed on the system for TesseractCliOcrOptions
        # pipeline_options.ocr_options = TesseractCliOcrOptions(force_full_page_ocr=True) 
        # Let's try default OCR settings first if available with just do_ocr=True
        
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        result = converter.convert(temp_pdf_path)
        # Define a unique page break placeholder
        page_break = "\n\n---DOCLING_PAGE_BREAK---\n\n"
        # Export with the placeholder
        full_markdown = result.document.export_to_markdown(page_break_placeholder=page_break)
        # Split the markdown into pages
        markdown_pages = full_markdown.split(page_break)

        # Clean up the temporary file
        os.remove(temp_pdf_path)

        # Return the list of pages
        return Response({"pages": markdown_pages}, status=status.HTTP_200_OK)

    except Exception as e:
        # Clean up temp file in case of error
        if 'temp_pdf_path' in locals() and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        # Add logging for the exception
        logger.exception(f"Error converting PDF: {e}") 
        return Response({"error": f"Error converting PDF: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def process_page(request):
    """
    API endpoint that receives a single markdown page string and returns 
    a list of dictionaries containing Easy Read sentences generated by an LLM.
    Expects JSON: {"markdown_page": "page_content_md"}
    Returns JSON: {"easy_read_sentences": [{"sentence": "s1", "kw": "k1"}, ...]}
    """
    logger = logging.getLogger(__name__)
    
    # --- Input Validation ---
    if not isinstance(request.data, dict) or 'markdown_page' not in request.data:
        return Response({"error": "Invalid request format. Expected JSON object with 'markdown_page' key."}, status=status.HTTP_400_BAD_REQUEST)

    markdown_page_content = request.data['markdown_page']

    if not isinstance(markdown_page_content, str):
        return Response({"error": "'markdown_page' must be a string."}, status=status.HTTP_400_BAD_REQUEST)

    # --- Load Prompt --- 
    prompt_config = load_prompt_template()
    required_keys = ['system_message', 'user_message_template', 'llm_model']
    if prompt_config is None or not all(key in prompt_config for key in required_keys):
        logger.error(f"Prompt template file {EASY_READ_PROMPT_FILE} is missing required keys: {required_keys}")
        return Response({"error": "Failed to load or parse prompt template YAML, or missing required keys."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    system_message = prompt_config['system_message']
    user_template = prompt_config['user_message_template']
    llm_model = prompt_config['llm_model'] 

    # --- Prepare LLM Call --- 
    user_message = user_template.format(markdown_content=markdown_page_content)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
    
    # --- LLM Call and Response Handling --- 
    try:
        response = litellm.completion(
            model=llm_model, 
            messages=messages,
            response_format={"type": "json_object"} 
        )
        
        llm_output_content = response.choices[0].message.content
        
        # Initialize results
        llm_parsed_object = {}
        easy_read_sentences = []
        title = "Untitled Conversion"
        
        # Parse and Validate LLM JSON output
        try:
            # ADD CHECK FOR NONE CONTENT
            if llm_output_content is None:
                raise ValueError("LLM returned None content.")

            llm_parsed_object = json.loads(llm_output_content)
            
            # Validate the structure
            if not isinstance(llm_parsed_object, dict) or 'title' not in llm_parsed_object or 'easy_read_sentences' not in llm_parsed_object:
                raise ValueError("LLM response is not a JSON dictionary with the required keys 'title' and 'easy_read_sentences'.")

            # Extract title
            title = llm_parsed_object.get('title', "Untitled Conversion")
            if not isinstance(title, str):
                 title = "Untitled Conversion" # Fallback if title is not string
                 logger.warning(f"LLM returned non-string title. Using default.")

            # Extract and validate sentences
            items_to_validate = llm_parsed_object['easy_read_sentences']
            if not isinstance(items_to_validate, list):
                 raise ValueError("The 'easy_read_sentences' key does not contain a list.")
            
            if not all(isinstance(item, dict) for item in items_to_validate):
                raise ValueError("LLM list/dict contains non-dictionary elements.")
            if not all('sentence' in item and 'image_retrieval' in item for item in items_to_validate):
                raise ValueError("LLM dictionaries are missing required keys ('sentence', 'image_retrieval').")
            if not all(isinstance(item['sentence'], str) and isinstance(item['image_retrieval'], str) for item in items_to_validate):
                raise ValueError("LLM dictionary values are not strings.")
            
            # If validation passed, assign to result
            easy_read_sentences = items_to_validate

        except (json.JSONDecodeError, ValueError) as json_e:
            # Log the error and the problematic content (which might be None)
            logger.error(f"Failed to parse or validate LLM JSON response: {json_e}\nRaw content received: {llm_output_content}")
            # Return error structure within the list for consistency
            easy_read_sentences = [{ "sentence": f"Error: {json_e}", "image_retrieval": "error processing" }]
            title = "Error Processing Title" # Set error title

    except Exception as e:
        logger.exception(f"LLM call failed: {e}")
        easy_read_sentences = [{ "sentence": "Error: LLM call failed.", "image_retrieval": "error processing" }]
        title = "Error Processing Title" # Set error title

    # --- Return Response --- 
    return Response({
        "title": title,
        "easy_read_sentences": easy_read_sentences
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def validate_completeness(request):
    """
    API endpoint that receives original markdown and a list of Easy Read sentences,
    and returns an LLM analysis of content coverage.
    Expects JSON: {
        "original_markdown": "markdown_content",
        "easy_read_sentences": ["sentence1", "sentence2", ...]
    }
    Returns JSON: {
        "is_complete": <boolean>,
        "missing_info": [<str>, ...],
        "extra_info": [<str>, ...],
        "explanation": <str>
    } or {"error": "..."}
    """
    logger = logging.getLogger(__name__)

    # --- Input Validation --- 
    if not isinstance(request.data, dict): 
        return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
    
    required_input_keys = ['original_markdown', 'easy_read_sentences']
    if not all(key in request.data for key in required_input_keys):
        return Response({"error": f"Invalid request format. Missing keys: {required_input_keys}"}, status=status.HTTP_400_BAD_REQUEST)

    original_markdown = request.data['original_markdown']
    easy_read_sentences = request.data['easy_read_sentences']

    if not isinstance(original_markdown, str):
         return Response({"error": "'original_markdown' must be a string."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(easy_read_sentences, list) or not all(isinstance(s, str) for s in easy_read_sentences):
        return Response({"error": "'easy_read_sentences' must be a list of strings."}, status=status.HTTP_400_BAD_REQUEST)

    # --- Load Prompt ---
    try:
        with open(VALIDATE_COMPLETENESS_PROMPT_FILE, 'r') as f:
            prompt_config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {VALIDATE_COMPLETENESS_PROMPT_FILE}")
        return Response({"error": "Validation prompt file not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing validation YAML file: {e}")
        return Response({"error": "Error parsing validation prompt file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    required_prompt_keys = ['system_message', 'user_message_template', 'llm_model']
    if prompt_config is None or not all(key in prompt_config for key in required_prompt_keys):
        logger.error(f"Validation prompt file {VALIDATE_COMPLETENESS_PROMPT_FILE} is missing required keys: {required_prompt_keys}")
        return Response({"error": "Validation prompt file is incomplete."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    system_message = prompt_config['system_message']
    user_template = prompt_config['user_message_template']
    llm_model = prompt_config['llm_model']

    # --- Prepare LLM Call --- 
    # Format sentences as a JSON string list for the prompt
    sentences_json_string = json.dumps(easy_read_sentences, indent=2) 
    user_message = user_template.format(
        original_markdown=original_markdown,
        easy_read_sentences=sentences_json_string
    )
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    # --- LLM Call and Response Handling --- 
    try:
        response = litellm.completion(
            model=llm_model, 
            messages=messages,
            response_format={"type": "json_object"} 
        )
        
        llm_output_content = response.choices[0].message.content
        
        # Parse and Validate LLM JSON output
        try:
            if llm_output_content is None:
                raise ValueError("LLM returned None content.")

            llm_parsed_object = json.loads(llm_output_content)
            
            # Basic structure validation based on the NEW prompt's expected output
            expected_keys = ["is_complete", "missing_info", "extra_info"]
            if not isinstance(llm_parsed_object, dict) or not all(key in llm_parsed_object for key in expected_keys):
                 raise ValueError(f"LLM response missing expected keys: {expected_keys}")
            
            # Type validation for the new structure
            if not isinstance(llm_parsed_object.get("is_complete"), bool): 
                 raise ValueError("Type error: 'is_complete' should be boolean.")
            if not isinstance(llm_parsed_object.get("missing_info"), str):
                 raise ValueError("Type error: 'missing_info' should be a string.")
            if not isinstance(llm_parsed_object.get("extra_info"), str):
                 raise ValueError("Type error: 'extra_info' should be a string.")

            # If validation passes, return the parsed object directly
            return Response(llm_parsed_object, status=status.HTTP_200_OK)

        except (json.JSONDecodeError, ValueError) as json_e:
            logger.error(f"Failed to parse or validate LLM JSON response for validation endpoint: {json_e}\nRaw content received: {llm_output_content}")
            return Response({
                "error": f"Failed to parse/validate LLM response for validation. Reason: {json_e}",
                "raw_llm_output": llm_output_content # Optionally include raw output for debugging
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.exception(f"LLM call failed for validation endpoint: {e}")
        return Response({"error": f"LLM call failed during validation. Reason: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def revise_sentences(request):
    """
    API endpoint that receives original markdown, current sentences (with image queries),
    and validation feedback, then returns revised Easy Read sentences based on LLM feedback.
    Expects JSON: {
        "original_markdown": "...",
        "current_sentences": [{"sentence": "...", "image_retrieval": "..."}, ...],
        "validation_feedback": {"is_complete": bool, "missing_info": str, "extra_info": str}
    }
    Returns JSON: {
        "easy_read_sentences": [{"sentence": "...", "image_retrieval": "..."}, ...]
    } or {"error": "..."}
    """
    logger = logging.getLogger(__name__)

    # --- Input Validation ---
    if not isinstance(request.data, dict):
        return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)

    required_keys = ['original_markdown', 'current_sentences', 'validation_feedback']
    if not all(key in request.data for key in required_keys):
        return Response({"error": f"Invalid request format. Missing keys: {required_keys}"}, status=status.HTTP_400_BAD_REQUEST)

    original_markdown = request.data['original_markdown']
    current_sentences = request.data['current_sentences']
    validation_feedback = request.data['validation_feedback']

    # Detailed type validation
    if not isinstance(original_markdown, str):
         return Response({"error": "'original_markdown' must be a string."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(current_sentences, list):
        return Response({"error": "'current_sentences' must be a list."}, status=status.HTTP_400_BAD_REQUEST)
    if not all(isinstance(item, dict) and 'sentence' in item and 'image_retrieval' in item and isinstance(item['sentence'], str) and isinstance(item['image_retrieval'], str) for item in current_sentences):
         return Response({"error": "'current_sentences' must be a list of dicts, each with 'sentence' (string) and 'image_retrieval' (string) keys."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(validation_feedback, dict):
         return Response({"error": "'validation_feedback' must be a dictionary."}, status=status.HTTP_400_BAD_REQUEST)
    if not all(key in validation_feedback for key in ['is_complete', 'missing_info', 'extra_info']):
         return Response({"error": "'validation_feedback' dictionary missing required keys ('is_complete', 'missing_info', 'extra_info')."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(validation_feedback.get('is_complete'), bool) or not isinstance(validation_feedback.get('missing_info'), str) or not isinstance(validation_feedback.get('extra_info'), str):
         return Response({"error": "'validation_feedback' has keys with incorrect types (expected bool, str, str)."}, status=status.HTTP_400_BAD_REQUEST)


    # --- Load Prompt ---
    try:
        with open(REVISE_SENTENCES_PROMPT_FILE, 'r') as f:
            prompt_config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {REVISE_SENTENCES_PROMPT_FILE}")
        return Response({"error": "Revision prompt file not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing revision YAML file: {e}")
        return Response({"error": "Error parsing revision prompt file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    required_prompt_keys = ['system_message', 'user_message_template', 'llm_model']
    if prompt_config is None or not all(key in prompt_config for key in required_prompt_keys):
        logger.error(f"Revision prompt file {REVISE_SENTENCES_PROMPT_FILE} is missing required keys: {required_prompt_keys}")
        return Response({"error": "Revision prompt file is incomplete."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    system_message = prompt_config['system_message']
    user_template = prompt_config['user_message_template']
    llm_model = prompt_config['llm_model']

    # --- Prepare LLM Call ---
    current_sentences_json = json.dumps(current_sentences, indent=2)
    validation_feedback_json = json.dumps(validation_feedback, indent=2)

    user_message = user_template.format(
        original_markdown=original_markdown,
        current_sentences=current_sentences_json,
        validation_feedback=validation_feedback_json
    )
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    # --- LLM Call and Response Handling ---
    try:
        response = litellm.completion(
            model=llm_model,
            messages=messages,
            response_format={"type": "json_object"}
        )

        llm_output_content = response.choices[0].message.content

        # Parse and Validate LLM JSON output
        try:
            if llm_output_content is None:
                raise ValueError("LLM returned None content.")

            llm_parsed_object = json.loads(llm_output_content)

            # Validate the structure matches the expected output for this prompt
            if not isinstance(llm_parsed_object, dict) or 'easy_read_sentences' not in llm_parsed_object:
                 raise ValueError("LLM response missing 'easy_read_sentences' key.")
            
            revised_sentences = llm_parsed_object['easy_read_sentences']
            if not isinstance(revised_sentences, list):
                raise ValueError("'easy_read_sentences' should contain a list.")
            if not all(isinstance(item, dict) and 'sentence' in item and 'image_retrieval' in item and isinstance(item['sentence'], str) and isinstance(item['image_retrieval'], str) for item in revised_sentences):
                 raise ValueError("Items in 'easy_read_sentences' list do not match expected structure ({'sentence': str, 'image_retrieval': str}).")

            # If validation passes, return the parsed object
            return Response(llm_parsed_object, status=status.HTTP_200_OK)

        except (json.JSONDecodeError, ValueError) as json_e:
            logger.error(f"Failed to parse or validate LLM JSON response for revision endpoint: {json_e}\nRaw content received: {llm_output_content}")
            return Response({
                "error": f"Failed to parse/validate LLM response for revision. Reason: {json_e}",
                "raw_llm_output": llm_output_content
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.exception(f"LLM call failed for revision endpoint: {e}")
        return Response({"error": f"LLM call failed during revision. Reason: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Updated Image Upload Endpoint ---
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser]) # Allow file uploads and form data
def upload_image(request):
    """
    API endpoint to upload an image, optionally with a description.
    Stores the image file, generates an embedding, and stores the embedding.
    Expects form-data with 'image' (file) and optional 'description' (text).
    """
    logger = logging.getLogger(__name__)

    if 'image' not in request.FILES:
        return Response({"error": "No image file provided"}, status=status.HTTP_400_BAD_REQUEST)

    image_file = request.FILES['image']
    description = request.POST.get('description', '') # Get description, default to empty

    # Basic file type check (can be more robust)
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp']
    file_ext = os.path.splitext(image_file.name)[1].lower()
    if file_ext not in allowed_extensions:
        return Response({"error": f"Invalid file type '{file_ext}'. Allowed types: {allowed_extensions}"}, status=status.HTTP_400_BAD_REQUEST)

    # Generate a unique filename or use the original (careful with collisions/sanitization)
    # For simplicity, let's use the original name sanitized, but UUID is safer
    # Sanitize filename (replace spaces, etc.) - implement a proper sanitization function if needed
    safe_filename = image_file.name.replace(" ", "_") 
    image_save_path = IMAGE_UPLOAD_DIR / safe_filename
    relative_image_path = os.path.relpath(image_save_path, settings.MEDIA_ROOT)

    # --- Store Image File ---
    try:
        # Check if file already exists to prevent overwriting (optional)
        if image_save_path.exists():
             # Option 1: Return error
             # return Response({"error": f"Image file '{safe_filename}' already exists."}, status=status.HTTP_409_CONFLICT)
             # Option 2: Generate unique name (e.g., using uuid)
             name, ext = os.path.splitext(safe_filename)
             safe_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
             image_save_path = IMAGE_UPLOAD_DIR / safe_filename
             relative_image_path = os.path.relpath(image_save_path, settings.MEDIA_ROOT)

        with open(image_save_path, 'wb+') as destination:
            for chunk in image_file.chunks():
                destination.write(chunk)
        logger.info(f"Image saved to: {image_save_path}")
    except Exception as e:
        logger.error(f"Error saving image file '{safe_filename}': {e}")
        return Response({"error": f"Failed to save image file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Create ImageMetadata Record FIRST ---
    image_metadata = None
    try:
        image_metadata = ImageMetadata.objects.create(
            image=relative_image_path,
            description=description,
            is_generated=False
        )
        logger.info(f"Created ImageMetadata record for uploaded image: {image_metadata.id}")
    except Exception as e:
        logger.error(f"Error creating ImageMetadata record for uploaded image: {e}")
        # If metadata fails, we probably shouldn't proceed with embedding/chroma
        return Response({"error": "Failed to create database record for image."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Generate Embedding (Using Sentence Transformer) ---
    embedding = None
    if embedding_model: # Check if model loaded successfully
        try:
            # Try passing the file path directly
            image_path_str = str(image_save_path)  # Convert to string
            embedding_list = embedding_model.encode([image_path_str])
            
            if embedding_list is not None and len(embedding_list) > 0:
                embedding = embedding_list[0].tolist() # Convert numpy array to list for JSON compatibility
                logger.info(f"CLIP Embedding generated for '{safe_filename}'")
            else:
                logger.warning(f"Sentence Transformer did not return embedding for '{safe_filename}'")
        except Exception as e:
            logger.error(f"An unexpected error occurred during CLIP embedding for '{safe_filename}': {e}")
            # Decide if we should still return success or error
    else:
        logger.error("Embedding model not available, skipping embedding generation.")

    # --- Store Embedding in ChromaDB (uses metadata ID now) ---
    embedding_stored = False
    if chroma_client and image_collection and embedding and image_metadata:
        try:
            # Use the numeric ImageMetadata ID as the ChromaDB ID (as string)
            chroma_id = str(image_metadata.id)
            
            # Check if ID already exists (should be unique based on metadata PK)
            existing = image_collection.get(ids=[chroma_id])
            if existing['ids']:
                logger.warning(f"ChromaDB ID '{chroma_id}' (from ImageMetadata) already exists. Updating metadata/embedding.")
                image_collection.update(
                    ids=[chroma_id],
                    embeddings=[embedding],
                    # Store relative path in metadata still for potential use
                    metadatas=[{"image_path": relative_image_path, "description": description}]
                )
            else:
                image_collection.add(
                    embeddings=[embedding],
                    # Store relative path in metadata still for potential use
                    metadatas=[{"image_path": relative_image_path, "description": description}],
                    ids=[chroma_id]
                )
            embedding_stored = True
            logger.info(f"Embedding stored in ChromaDB for ID '{chroma_id}'")
        except Exception as e:
            logger.error(f"Error storing embedding in ChromaDB for '{chroma_id}': {e}")
            # Continue with response, embedding storage is not critical for image upload success
    elif not image_metadata:
        logger.warning("Skipping ChromaDB storage because ImageMetadata record creation failed.")
    elif not embedding:
         logger.warning(f"Skipping ChromaDB storage for image {relative_image_path} because embedding generation failed.")
    elif not chroma_client or not image_collection:
         logger.warning(f"Skipping ChromaDB storage for image {relative_image_path} because ChromaDB is not available.")

    # --- Return Response (Metadata ID is the primary identifier now) ---
    response_data = {
        "message": "Image uploaded successfully.",
        "image_id": image_metadata.id, # Return the DB ID
        "image_path": relative_image_path, # Relative path within MEDIA_ROOT
        "description": description,
        "embedding_generated": embedding is not None,
        "embedding_stored": embedding_stored
    }
    return Response(response_data, status=status.HTTP_201_CREATED)

# --- Updated Image Similarity Search Endpoint ---
@api_view(['POST'])
def find_similar_images(request):
    """
    API endpoint to find N most similar images based on a text query.
    Expects JSON: {
        "query": "text description", 
        "n_results": <integer>,
        "exclude_ids": [<string>, ...] (optional)
    }
    Returns JSON: {"results": [
        {"id": <str>, "url": <str>, "description": <str>, "distance": <float>}, ...
    ]} or {"error": "..."}
    """
    logger.error("--- find_similar_images view entered ---") 
    
    # --- Input Validation ---
    if not isinstance(request.data, dict): 
        return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
    
    query = request.data.get('query')
    n_results = request.data.get('n_results')
    exclude_ids = request.data.get('exclude_ids', [])

    if not query or not isinstance(query, str):
        return Response({"error": "Missing or invalid 'query' (must be a non-empty string)."}, status=status.HTTP_400_BAD_REQUEST)
    
    if n_results is None:
         return Response({"error": "Missing 'n_results' parameter."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        n_results = int(n_results)
        if n_results <= 0:
            raise ValueError("n_results must be positive")
    except (ValueError, TypeError):
        return Response({"error": "Invalid 'n_results' (must be a positive integer)."}, status=status.HTTP_400_BAD_REQUEST)
    
    if exclude_ids and not isinstance(exclude_ids, list):
        return Response({"error": "Invalid 'exclude_ids' (must be a list of strings)."}, status=status.HTTP_400_BAD_REQUEST)

    # --- Check Model Initialization ---
    if not embedding_model: 
        logger.error("Embedding model not loaded for image search.")
        return Response({"error": "Image search unavailable (Embedding model not loaded)."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Connect to ChromaDB ---
    try:
        # Convert PosixPath to string to avoid type errors
        chroma_db_path_str = str(CHROMA_DB_PATH)
        chroma_client = chromadb.PersistentClient(path=chroma_db_path_str)
        image_collection = chroma_client.get_or_create_collection(name=IMAGE_COLLECTION_NAME)
        logger.info(f"Connected to ChromaDB collection '{IMAGE_COLLECTION_NAME}'")
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB: {e}")
        return Response({"error": "Image search unavailable (Image DB not configured)."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Embed Query (Using Sentence Transformer) ---
    try:
        # Embed the text query
        embedding_list = embedding_model.encode([query]) 
        if embedding_list is not None and len(embedding_list) > 0:
            query_embedding = embedding_list[0].tolist()
        else:
            logger.error(f"Sentence Transformer did not return embedding for query: '{query}'")
            return Response({"error": "Failed to generate embedding for the query."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.exception(f"Unexpected error during query embedding: {e}")
        return Response({"error": "An unexpected error occurred while processing the query."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Query ChromaDB ---
    try:
        # If we have IDs to exclude, we need to get more results and filter afterward
        n_results_to_fetch = n_results
        # Convert exclude_ids from frontend (expected to be numeric IDs) to strings for logging/potential direct use if needed
        exclude_ids_str = [str(eid) for eid in exclude_ids if eid is not None] 

        if exclude_ids_str:
            # Get significantly more results because some might be filtered out
            exclude_factor = min(5, 1 + (len(exclude_ids_str) / 20))
            n_results_to_fetch = max(50, int(n_results * exclude_factor))
        
        # Always limit to a reasonable number to prevent performance issues
        n_results_to_fetch = min(n_results_to_fetch, 100)
        
        # Log what is being queried
        logger.warning(f"Querying ChromaDB for '{query}' with n_results={n_results_to_fetch}")
        if exclude_ids_str:
             logger.warning(f"Frontend requested exclusion of IDs: {exclude_ids}") # Log original numeric IDs
        
        results = image_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results_to_fetch,
            include=['metadatas', 'distances'] # IDs are included by default
        )
        
        # Log raw results count
        raw_ids_count = len(results['ids'][0]) if results and results.get('ids') and results['ids'][0] else 0
        logger.info(f"ChromaDB returned {raw_ids_count} raw results (IDs are stringified ImageMetadata IDs).")
        
    except Exception as e:
        logger.exception(f"Error querying ChromaDB: {e}")
        return Response({"error": f"Failed to query the image database: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Process and Filter Results based on Numeric IDs ---
    potential_ids = [] # List of potential numeric IDs from Chroma results
    distances_map = {} # Map numeric ID to distance
    if results and results.get('ids') and results['ids'][0]:
        chroma_ids_str = results['ids'][0]
        distances = results['distances'][0]
        for i, chroma_id_str in enumerate(chroma_ids_str):
            try:
                numeric_id = int(chroma_id_str) # Convert Chroma string ID back to numeric
                # Check against the numeric exclude list provided by frontend
                if exclude_ids and numeric_id in exclude_ids:
                    logger.warning(f"Skipping ChromaDB result ID {numeric_id} because it is in frontend exclude_ids.")
                    continue
                potential_ids.append(numeric_id)
                distances_map[numeric_id] = distances[i]
            except (ValueError, TypeError):
                 logger.warning(f"Could not convert ChromaDB ID '{chroma_id_str}' to integer. Skipping.")
                 continue
            # Limit the number of potential IDs to fetch from DB to avoid huge queries
            if len(potential_ids) >= n_results_to_fetch: # Use the larger fetch number here
                break 
    
    logger.info(f"Identified {len(potential_ids)} potential candidate ImageMetadata IDs after initial exclusion.")

    # --- Fetch ImageMetadata for filtered IDs ---
    final_results = []
    if potential_ids:
        try:
            # Fetch metadata objects in bulk, preserving order if possible (though order isn't guaranteed)
            image_metadata_qs = ImageMetadata.objects.filter(id__in=potential_ids)
            # Create a map for quick lookup
            metadata_map = {meta.id: meta for meta in image_metadata_qs}
            
            # Reconstruct results in the order they came from ChromaDB (potential_ids)
            for pid in potential_ids:
                if pid in metadata_map:
                    metadata = metadata_map[pid]
                    final_results.append({
                        "id": metadata.id, # Return the numeric ID
                        "url": request.build_absolute_uri(metadata.image.url), # Full URL
                        "description": metadata.description or '',
                        "distance": distances_map.get(pid) # Get distance using numeric ID
                    })
                    # Stop once we have enough results
                    if len(final_results) >= n_results:
                        break
                else:
                    logger.warning(f"ImageMetadata record not found for ID {pid}, which was present in ChromaDB. Data inconsistency?")

        except Exception as e:
            logger.exception(f"Error fetching ImageMetadata for IDs {potential_ids}: {e}")
            # Don't fail the whole request, return what we have (might be empty)
            pass # Fall through to return final_results as is

    if not final_results:
        logger.info(f"No suitable images found after filtering for query: '{query}'")

    logger.info(f"Finished processing. Returning {len(final_results)} results matching the query.")
    return Response({"results": final_results}, status=status.HTTP_200_OK)

# --- New Save Content Endpoint ---
@api_view(['POST'])
def save_processed_content(request):
    """
    API endpoint to save the original markdown, title, and the generated Easy Read JSON.
    Expects JSON: {
        "original_markdown": "...",
        "title": "...",
        "easy_read_json": [{"sentence": "...", "image_retrieval": "...", "selected_image_path": "...", "alternative_images": [...]}, ...]
    }
    Returns JSON: {"message": "Content saved successfully.", "id": <saved_object_id>}
    or {"error": "..."}
    """
    logger = logging.getLogger(__name__)

    # --- Input Validation ---
    if not isinstance(request.data, dict): 
        return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
    
    original_markdown = request.data.get('original_markdown')
    title = request.data.get('title', '') # Get title, default to empty string
    easy_read_json = request.data.get('easy_read_json')

    if not original_markdown or not isinstance(original_markdown, str):
        return Response({"error": "Missing or invalid 'original_markdown' (must be a non-empty string)."}, status=status.HTTP_400_BAD_REQUEST)
        
    if not isinstance(title, str):
         return Response({"error": "Invalid 'title' (must be a string)."}, status=status.HTTP_400_BAD_REQUEST)

    if not easy_read_json or not isinstance(easy_read_json, list):
         return Response({"error": "Missing or invalid 'easy_read_json' (must be a list)."}, status=status.HTTP_400_BAD_REQUEST)
    # Optional: Add more detailed validation for the list items if needed

    # --- Save to Database ---
    try:
        processed_content = ProcessedContent.objects.create(
            title=title,
            original_markdown=original_markdown,
            easy_read_json=easy_read_json
        )
        logger.info(f"Saved processed content with ID: {processed_content.id}, Title: {title}")
        return Response({
            "message": "Content saved successfully.",
            "id": processed_content.id
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.exception(f"Error saving processed content to database: {e}")
        return Response({"error": "Failed to save content to the database."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Image List Endpoint --- (Revised to query Database and separate)
@api_view(['GET'])
def list_images(request):
    """
    API endpoint to list all images stored in the database, separated by source.
    Returns two lists: 'generated_images' and 'uploaded_images',
    each sorted by upload date (newest first).
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Query generated images
        generated_metadata = ImageMetadata.objects.filter(is_generated=True).order_by('-uploaded_at')
        # Query uploaded images
        uploaded_metadata = ImageMetadata.objects.filter(is_generated=False).order_by('-uploaded_at')
        
        # Helper function to format data
        def format_image_data(metadata_qs):
            images = []
            for item in metadata_qs:
                try:
                    image_path = item.image.name if item.image else 'N/A'
                    image_url = request.build_absolute_uri(item.image.url) if item.image and hasattr(item.image, 'url') else None
                    
                    images.append({
                        "id": item.id, # Use numeric DB ID as the primary ID
                        "image_path": image_path, # Keep path for reference if needed
                        "image_url": image_url,
                        "description": item.description,
                        "uploaded_at": item.uploaded_at.isoformat() if item.uploaded_at else None
                    })
                except Exception as item_err:
                     logger.error(f"Error processing ImageMetadata item ID {item.id} (is_generated={item.is_generated}): {item_err}")
                     continue # Skip this image if formatting fails
            return images

        # Format both lists
        generated_images = format_image_data(generated_metadata)
        uploaded_images = format_image_data(uploaded_metadata)
        
        logger.info(f"Retrieved {len(generated_images)} generated and {len(uploaded_images)} uploaded images from the database.")
        
        # Return the separated lists
        return Response({
            "generated_images": generated_images,
            "uploaded_images": uploaded_images
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error retrieving images from database: {e}")
        # Return empty lists in case of a major error
        return Response({
            "generated_images": [], 
            "uploaded_images": [], 
            "error": "Failed to retrieve images from database"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Batch Image Upload Endpoint ---
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def batch_upload_images(request):
    """
    API endpoint to upload multiple images at once, optionally with a shared description.
    Stores the image files, generates embeddings, and stores the embeddings.
    Expects form-data with 'images' (files) and optional 'description' (text).
    """
    logger = logging.getLogger(__name__)

    if 'images' not in request.FILES:
        return Response({"error": "No image files provided"}, status=status.HTTP_400_BAD_REQUEST)

    # Get all files from the request
    image_files = request.FILES.getlist('images')
    description = request.POST.get('description', '')  # Get description, default to empty
    
    if not image_files:
        return Response({"error": "Empty file list"}, status=status.HTTP_400_BAD_REQUEST)

    # Initialize ChromaDB client and collection
    try:
        # Convert PosixPath to string to avoid type errors
        chroma_db_path_str = str(CHROMA_DB_PATH)
        chroma_client = chromadb.PersistentClient(path=chroma_db_path_str)
        image_collection = chroma_client.get_or_create_collection(name=IMAGE_COLLECTION_NAME)
        logger.info(f"Connected to ChromaDB collection '{IMAGE_COLLECTION_NAME}'")
        chroma_available = True
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB: {e}")
        chroma_available = False
        image_collection = None

    # Store results for each file
    results = []
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp']

    for image_file in image_files:
        result = {
            "filename": image_file.name,
            "success": False,
            "error": None,
            "image_path": None
        }

        # Basic file type check
        file_ext = os.path.splitext(image_file.name)[1].lower()
        if file_ext not in allowed_extensions:
            result["error"] = f"Invalid file type '{file_ext}'. Allowed types: {allowed_extensions}"
            results.append(result)
            continue

        # Generate a unique filename
        safe_filename = image_file.name.replace(" ", "_")
        image_save_path = IMAGE_UPLOAD_DIR / safe_filename
        
        # Check if file already exists
        if image_save_path.exists():
            # Generate unique name with UUID
            name, ext = os.path.splitext(safe_filename)
            safe_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            image_save_path = IMAGE_UPLOAD_DIR / safe_filename
        
        relative_image_path = os.path.relpath(image_save_path, settings.MEDIA_ROOT)
        result["image_path"] = relative_image_path

        # --- Store Image File ---
        try:
            with open(image_save_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)
            logger.info(f"Image saved to: {image_save_path}")
            
            # --- Create ImageMetadata Record FIRST ---
            image_metadata = None
            try:
                image_metadata = ImageMetadata.objects.create(
                    image=relative_image_path,
                    description=description,
                    is_generated=False
                )
                logger.info(f"Created ImageMetadata record for uploaded image: {image_metadata.id}")
            except Exception as e:
                logger.error(f"Error creating ImageMetadata record for uploaded image: {e}")
                result["error"] = "Failed to create database record for image."
                # Skip ChromaDB if metadata creation failed
                results.append(result) # Append the failed result here
                continue # Move to the next file

            # --- Generate Embedding (Using Sentence Transformer) ---
            embedding = None
            if embedding_model:  # Check if model loaded successfully
                try:
                    # Generate embedding
                    image_path_str = str(image_save_path)  # Convert to string
                    embedding_list = embedding_model.encode([image_path_str])
                    
                    if embedding_list is not None and len(embedding_list) > 0:
                        embedding = embedding_list[0].tolist()
                        logger.info(f"CLIP Embedding generated for '{safe_filename}'")
                    else:
                        logger.warning(f"Sentence Transformer did not return embedding for '{safe_filename}'")
                except Exception as e:
                    logger.error(f"Error generating embedding for '{safe_filename}': {e}")
                    # Continue processing even if embedding fails
            
            # --- Store Embedding in ChromaDB (uses metadata ID now) ---
            embedding_stored = False
            if chroma_available and image_collection and embedding and image_metadata:
                try:
                    # Use the numeric ImageMetadata ID as the ChromaDB ID (as string)
                    chroma_id = str(image_metadata.id)
                    
                    # Check if ID already exists (should be unique based on metadata PK)
                    existing = image_collection.get(ids=[chroma_id])
                    if existing['ids']:
                        image_collection.update(
                            ids=[chroma_id],
                            embeddings=[embedding],
                            # Store relative path in metadata still for potential use
                            metadatas=[{"image_path": relative_image_path, "description": description}]
                        )
                    else:
                        image_collection.add(
                            embeddings=[embedding],
                            # Store relative path in metadata still for potential use
                            metadatas=[{"image_path": relative_image_path, "description": description}],
                            ids=[chroma_id]
                        )
                    embedding_stored = True
                    logger.info(f"Embedding stored in ChromaDB for ID '{chroma_id}'")
                except Exception as e:
                    logger.error(f"Error storing embedding in ChromaDB for '{chroma_id}': {e}")
                    # Continue with response, embedding storage is not critical for image upload success
            
            # Mark as successful
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Error processing image '{safe_filename}': {e}")
            result["error"] = str(e)
            # Continue with other images even if one fails
        
        results.append(result)

    # Calculate overall success metrics (moved outside the loop)
    successful_uploads = sum(1 for r in results if r["success"])
    
    return Response({
        "message": f"Processed {len(results)} images: {successful_uploads} succeeded, {len(results) - successful_uploads} failed",
        "results": results,
        "description": description
    }, status=status.HTTP_200_OK if successful_uploads > 0 else status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- List Saved Content Endpoint ---
@api_view(['GET'])
def list_saved_content(request):
    """
    API endpoint to list all saved content.
    Returns a list of all saved content with basic metadata.
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Query all saved content from the database
        saved_content = ProcessedContent.objects.all().order_by('-created_at')
        
        # Prepare response data with summary information
        content_list = []
        for item in saved_content:
            # Calculate sentence count
            sentence_count = len(item.easy_read_json) if item.easy_read_json else 0
            
            # Find first image to use as preview (if any)
            preview_image = None
            if item.easy_read_json:
                for sentence in item.easy_read_json:
                    if 'selected_image_path' in sentence and sentence['selected_image_path']:
                        preview_image = sentence['selected_image_path']
                        break
            
            content_list.append({
                'id': item.id,
                'title': item.title,
                'created_at': item.created_at,
                'sentence_count': sentence_count,
                'preview_image': preview_image
            })
        
        return Response({"content": content_list}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error retrieving saved content: {e}")
        return Response({"error": "Failed to retrieve saved content"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Get Saved Content Detail Endpoint ---
@api_view(['GET', 'DELETE'])
def get_saved_content_detail(request, content_id):
    """Retrieves or deletes the details of a specific saved content."""
    content = get_object_or_404(ProcessedContent, pk=content_id)

    if request.method == 'GET':
        easy_read_data = [] # Default to empty list
        try:
            # Directly use the field, assuming Django's JSONField handled deserialization
            if isinstance(content.easy_read_json, list):
                easy_read_data = content.easy_read_json
            elif isinstance(content.easy_read_json, str): # Handle case where it might be a string for older records
                logger.warning(f"easy_read_json for ID {content_id} was a string, attempting json.loads")
                try:
                    easy_read_data = json.loads(content.easy_read_json)
                    if not isinstance(easy_read_data, list):
                         logger.error(f"Decoded easy_read_json string for ID {content_id} is not a list.")
                         easy_read_data = [] # Reset if decoded data isn't a list
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode easy_read_json string for ID {content_id}")
                    easy_read_data = []
            else:
                 logger.error(f"easy_read_json for ID {content_id} is neither a list nor a string. Type: {type(content.easy_read_json)}")
                 easy_read_data = []

        except Exception as e:
             logger.error(f"Unexpected error processing easy_read_json for ID {content_id}: {e}")
             easy_read_data = [] # Ensure it defaults to empty list on any error

        response_data = {
            'id': content.id,
            'title': content.title,
            'original_markdown': content.original_markdown,
            'easy_read_content': easy_read_data, # Use the processed data
            'created_at': content.created_at.isoformat(),
        }
        return Response(response_data)
    
    elif request.method == 'DELETE':
        try:
            content.delete()
            logger.info(f"Successfully deleted ProcessedContent with ID: {content_id}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting ProcessedContent with ID {content_id}: {e}")
            return Response({"error": "Failed to delete content"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Update Saved Content Image Endpoint ---
@api_view(['PATCH'])
def update_saved_content_image(request, content_id):
    """
    API endpoint to update the image for a specific sentence in saved content.
    Expects JSON: {
        "sentence_index": <int>,
        "image_url": <string>,
        "all_images": [<string>, ...]  # Optional list of all alternative images
    }
    Returns the updated content.
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Validate input
        if not isinstance(request.data, dict):
            return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
        
        sentence_index = request.data.get('sentence_index')
        image_url = request.data.get('image_url')
        all_images = request.data.get('all_images', [])
        
        if sentence_index is None or not isinstance(sentence_index, int):
            return Response({"error": "Missing or invalid 'sentence_index' (must be an integer)."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not image_url or not isinstance(image_url, str):
            return Response({"error": "Missing or invalid 'image_url' (must be a non-empty string)."}, status=status.HTTP_400_BAD_REQUEST)
        
        if all_images and not isinstance(all_images, list):
            return Response({"error": "Invalid 'all_images' (must be a list of strings)."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Try to find the content with the given ID
        try:
            content = ProcessedContent.objects.get(id=content_id)
        except ProcessedContent.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Validate sentence_index is within range
        if sentence_index < 0 or sentence_index >= len(content.easy_read_json):
            return Response({"error": f"Invalid sentence_index: {sentence_index}. Must be between 0 and {len(content.easy_read_json) - 1}."}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Update the image path for the specified sentence
        content.easy_read_json[sentence_index]['selected_image_path'] = image_url
        
        # Add all alternative images if provided
        if all_images:
            content.easy_read_json[sentence_index]['alternative_images'] = all_images
        
        content.save()
        
        # Prepare response data
        response_data = {
            'id': content.id,
            'title': content.title,
            'created_at': content.created_at,
            'original_markdown': content.original_markdown,
            'easy_read_content': content.easy_read_json
        }
        
        logger.info(f"Updated image for content ID: {content.id}, sentence index: {sentence_index}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error updating saved content image: {e}")
        return Response({"error": "Failed to update content image"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def generate_image_view(request):
    """
    Generates image(s) using a Gradio client based on a prompt.
    Saves the image(s) and returns their URLs and IDs.
    Expects JSON: {"prompt": "description for the image"}
    Returns JSON: {"generated_images": [{"id": 1, "url": "path/to/image1.png"}, ...]}
    """
    if not gradio_client:
        return Response({"error": "Image generation service (Gradio) is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    prompt = request.data.get('prompt')
    if not prompt:
        return Response({"error": "'prompt' is required."}, status=status.HTTP_400_BAD_REQUEST)

    logger.info(f"Generating images for prompt: '{prompt}' using Gradio client.")

    try:
        # --- Call Gradio Client for Image Generation ---
        # Parameters based on the example: prompts/temp/gradio.py
        # client.predict("Mulberry", "A red bus with a yellow stripe", None, "No", 50, 3, 0.75, 7.5, None, api_name="/process_symbol_generation")
        prediction_result = gradio_client.predict(
            "Mulberry",  # First argument (style/category)
            prompt,      # Second argument (the actual prompt)
            None,        # Third argument (reference image, not used)
            "No",        # Fourth argument
            50,          # Fifth argument
            3,           # Sixth argument
            0.75,        # Seventh argument
            7.5,         # Eighth argument
            None,        # Ninth argument
            api_name="/process_symbol_generation"
        )

        if not prediction_result or not isinstance(prediction_result, tuple) or len(prediction_result) == 0:
            logger.error(f"Gradio client returned an unexpected result: {prediction_result}")
            return Response({"error": "Image generation failed: Unexpected response from service."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        image_data_list = prediction_result[0] # First element of the tuple is the list of image dicts

        if not isinstance(image_data_list, list):
            logger.error(f"Gradio client did not return a list of images. Got: {image_data_list}")
            return Response({"error": "Image generation failed: Unexpected image data format from service."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        generated_images_details = []

        for item in image_data_list:
            if not isinstance(item, dict) or 'image' not in item or not item['image']:
                logger.warning(f"Skipping invalid image item from Gradio: {item}")
                continue

            temp_image_path = item['image']

            try:
                # --- Read the temporary image file ---
                with open(temp_image_path, 'rb') as f_temp_image:
                    image_bytes = f_temp_image.read()
                
                if not image_bytes:
                    logger.warning(f"Skipping empty image file from Gradio: {temp_image_path}")
                    continue

                # --- Save the generated image ---
                image_name = f"generated_{uuid.uuid4().hex[:10]}.png"
                image_save_path = IMAGE_UPLOAD_DIR / image_name
                relative_image_path = os.path.relpath(image_save_path, settings.MEDIA_ROOT)

                with open(image_save_path, "wb") as f_save:
                    f_save.write(image_bytes)
                logger.info(f"Generated image saved to: {image_save_path}")

                # --- Create ImageMetadata record ---
                image_metadata = ImageMetadata.objects.create(
                    image=relative_image_path,
                    description=prompt,  # Use the generation prompt as description
                    is_generated=True    # Mark as generated
                )
                logger.info(f"Created ImageMetadata record for generated image: {image_metadata.id}")

                # --- Generate and Store Embedding in ChromaDB ---
                embedding_stored_chroma = False
                current_embedding = None
                if embedding_model:
                    try:
                        image_path_str = str(image_save_path)
                        embedding_list = embedding_model.encode([image_path_str])
                        if embedding_list is not None and len(embedding_list) > 0:
                            current_embedding = embedding_list[0].tolist()
                            logger.info(f"CLIP Embedding generated for '{image_name}'")
                        else:
                            logger.warning(f"Sentence Transformer did not return embedding for '{image_name}'")
                    except Exception as e_embed:
                        logger.error(f"Error generating embedding for '{image_name}': {e_embed}")

                if chroma_client and image_collection and current_embedding and image_metadata:
                    try:
                        chroma_id = str(image_metadata.id)
                        existing = image_collection.get(ids=[chroma_id])
                        if existing['ids']:
                            image_collection.update(
                                ids=[chroma_id],
                                embeddings=[current_embedding],
                                metadatas=[{"image_path": relative_image_path, "description": prompt}]
                            )
                        else:
                            image_collection.add(
                                embeddings=[current_embedding],
                                metadatas=[{"image_path": relative_image_path, "description": prompt}],
                                ids=[chroma_id]
                            )
                        embedding_stored_chroma = True
                        logger.info(f"Embedding stored in ChromaDB for generated image ID '{chroma_id}'")
                    except Exception as e_chroma:
                        logger.error(f"Error storing embedding for '{chroma_id}': {e_chroma}")
                
                generated_images_details.append({
                    "id": image_metadata.id,
                    "url": request.build_absolute_uri(settings.MEDIA_URL + relative_image_path),
                    "embedding_stored": embedding_stored_chroma
                })

            except FileNotFoundError:
                logger.error(f"Temporary image file from Gradio not found: {temp_image_path}")
                # Continue to next image if one is not found
            except Exception as e_single_image:
                logger.error(f"Error processing generated image {temp_image_path}: {e_single_image}")
                # Continue to next image if one fails

        if not generated_images_details:
             return Response({"error": "Image generation completed, but no valid images were processed or saved."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- TEMPORARY WORKAROUND: Return only the first image in the old format ---
        first_image = generated_images_details[0]
        return Response({
            "message": f"Images generated (showing 1 of {len(generated_images_details)}). Frontend update needed for multiple images.",
            "new_image_id": first_image["id"],
            "new_image_url": first_image["url"],
            "embedding_stored": first_image["embedding_stored"],
            "all_generated_images": generated_images_details # Optionally include all for future frontend use or debugging
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.exception(f"Error during Gradio image generation for prompt '{prompt}': {e}")
        return Response({"error": f"Image generation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
