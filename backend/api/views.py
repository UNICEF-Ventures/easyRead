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
import re
from django.conf import settings
from django.http import JsonResponse
import base64
# import cohere # Removed Cohere
# ChromaDB removed - now using PostgreSQL with pgvector
from dotenv import load_dotenv
from PIL import Image
import io
import glob # Might not be needed here if not listing
import uuid # Moved import to top
import time # Added for health check
from .models import ProcessedContent, ImageMetadata # Import the new model
from sentence_transformers import SentenceTransformer # Added SentenceTransformer
from openai import OpenAI
from .config import get_retry_config, load_prompt_template, VALIDATE_COMPLETENESS_PROMPT_FILE, REVISE_SENTENCES_PROMPT_FILE
from django.core.files.base import ContentFile
from gradio_client import Client, handle_file # Added Gradio client import
from django.http import HttpResponse
from .docx_export import create_docx_export, get_safe_filename

# Setup logger for this module
logger = logging.getLogger(__name__)

def has_meaningful_content(markdown_content, min_words=5):
    """
    Check if markdown content has meaningful text content to process.
    
    Args:
        markdown_content: String containing markdown content
        min_words: Minimum number of words required for content to be considered meaningful
    
    Returns:
        Boolean indicating if content has meaningful text
    """
    if not markdown_content or not isinstance(markdown_content, str):
        return False
    
    # Strip whitespace
    content = markdown_content.strip()
    
    if not content:
        return False
    
    # Remove markdown formatting elements but keep the text content
    # Remove image references ![alt](url)
    content = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', content)
    # Remove links but keep the text [text](url) -> text
    content = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', content)
    # Remove code blocks ```
    content = re.sub(r'```[^`]*```', '', content, flags=re.DOTALL)
    # Remove inline code `code`
    content = re.sub(r'`[^`]*`', '', content)
    # Remove markdown headers # ## ### etc. but keep the text
    content = re.sub(r'^#{1,6}\s*', '', content, flags=re.MULTILINE)
    # Remove markdown formatting *, **, _ but keep the text
    content = re.sub(r'[*_]{1,2}([^*_]*)[*_]{1,2}', r'\1', content)
    # Remove horizontal rules --- or ***
    content = re.sub(r'^[-*]{3,}$', '', content, flags=re.MULTILINE)
    # Remove HTML tags
    content = re.sub(r'<[^>]+>', '', content)
    # Normalize whitespace
    content = re.sub(r'\s+', ' ', content)
    
    # Clean up the content and count words
    cleaned_content = content.strip()
    
    if not cleaned_content:
        return False
    
    # Count words (split by whitespace and filter out empty strings)
    words = [word for word in cleaned_content.split() if word]
    word_count = len(words)
    
    # Check if we have enough words
    return word_count >= min_words

# Create your views here.

# Setup LiteLLM logging (optional, but helpful)
# litellm.set_verbose=True 

# File paths and settings are now managed in config.py

# --- Configuration (Consider moving to settings.py) ---
load_dotenv(settings.BASE_DIR.parent / '.env') # Load .env from project root

# COHERE_API_KEY = os.getenv("COHERE_API_KEY") # Removed Cohere API Key
IMAGE_UPLOAD_DIR = settings.MEDIA_ROOT / "uploaded_images"
# ChromaDB configuration removed - now using PostgreSQL with pgvector
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

# ChromaDB initialization removed - now using PostgreSQL with pgvector for embeddings

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

# Settings and prompt loading functions moved to config.py

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
        # Define our generic page break placeholder
        page_break = "\n\n---PAGE_BREAK---\n\n"
        # Export with our placeholder directly
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
    selected_sets = request.data.get('selected_sets', [])

    if not isinstance(markdown_page_content, str):
        return Response({"error": "'markdown_page' must be a string."}, status=status.HTTP_400_BAD_REQUEST)
    
    if not isinstance(selected_sets, list):
        return Response({"error": "'selected_sets' must be a list."}, status=status.HTTP_400_BAD_REQUEST)

    # --- Check if content has meaningful text ---
    if not has_meaningful_content(markdown_page_content):
        logger.info(f"Skipping page with no meaningful content: '{markdown_page_content[:100]}...'")
        # Return empty response instead of processing meaningless content
        return Response({
            "title": "Empty Page",
            "easy_read_sentences": []
        }, status=status.HTTP_200_OK)

    # --- Load Prompt and Settings --- 
    prompt_config = load_prompt_template()
    required_keys = ['system_message', 'user_message_template', 'llm_model']
    if prompt_config is None or not all(key in prompt_config for key in required_keys):
        logger.error(f"Prompt template file is missing required keys: {required_keys}")
        return Response({"error": "Failed to load or parse prompt template YAML, or missing required keys."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    system_message = prompt_config['system_message']
    user_template = prompt_config['user_message_template']
    llm_model = prompt_config['llm_model']
    
    # Load settings for retry configuration
    retry_config = get_retry_config()
    max_retries = retry_config.get('max_retries', 3)
    initial_delay = retry_config.get('initial_delay', 1.0)
    exponential_backoff = retry_config.get('exponential_backoff', True)
    max_delay = retry_config.get('max_delay', 10.0) 

    # --- Prepare LLM Call --- 
    user_message = user_template.format(markdown_content=markdown_page_content)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
    
    # --- LLM Call and Response Handling with Retry Logic --- 
    retry_delay = initial_delay
    
    easy_read_sentences = []
    title = "Untitled Conversion"
    
    for attempt in range(max_retries):
        try:
            logger.info(f"LLM call attempt {attempt + 1}/{max_retries}")
            
            response = litellm.completion(
                model=llm_model, 
                messages=messages,
                response_format={"type": "json_object"} 
            )
            
            # Check for empty response
            if not response.choices:
                raise ValueError("LLM returned empty response.")
            
            llm_output_content = response.choices[0].message.content
            
            # Parse and Validate LLM JSON output
            try:
                # Check for None content
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
                
                # Check for missing keys and provide detailed error information
                missing_keys_items = []
                for i, item in enumerate(items_to_validate):
                    missing_keys = []
                    if 'sentence' not in item:
                        missing_keys.append('sentence')
                    if 'image_retrieval' not in item:
                        missing_keys.append('image_retrieval')
                    if missing_keys:
                        missing_keys_items.append(f"Item {i}: missing {missing_keys}, got keys: {list(item.keys())}")
                
                if missing_keys_items:
                    detailed_error = f"LLM dictionaries are missing required keys ('sentence', 'image_retrieval'). Details: {'; '.join(missing_keys_items)}"
                    raise ValueError(detailed_error)
                
                # Validate string types
                if not all(isinstance(item['sentence'], str) and isinstance(item['image_retrieval'], str) for item in items_to_validate):
                    raise ValueError("LLM dictionary values are not strings.")
                
                # If validation passed, assign to result and break the retry loop
                easy_read_sentences = items_to_validate
                logger.info(f"LLM call successful on attempt {attempt + 1}")
                break  # Success, exit retry loop

            except (json.JSONDecodeError, ValueError) as json_e:
                # Log the error and the problematic content
                logger.error(f"Attempt {attempt + 1}/{max_retries} failed to parse or validate LLM JSON response: {json_e}\nRaw content received: {llm_output_content}")
                
                # If this is the last attempt, set error response
                if attempt == max_retries - 1:
                    easy_read_sentences = [{ "sentence": f"Error: {json_e}", "image_retrieval": "error processing" }]
                    title = "Error Processing Title"
                    break
                else:
                    # Wait before retrying with configurable backoff
                    time.sleep(retry_delay)
                    if exponential_backoff:
                        retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff with cap
                    continue  # Try again

        except Exception as e:
            logger.exception(f"Attempt {attempt + 1}/{max_retries} - LLM call failed: {e}")
            
            # If this is the last attempt, set error response
            if attempt == max_retries - 1:
                easy_read_sentences = [{ "sentence": "Error: LLM call failed.", "image_retrieval": "error processing" }]
                title = "Error Processing Title"
                break
            else:
                # Wait before retrying with configurable backoff
                time.sleep(retry_delay)
                if exponential_backoff:
                    retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff with cap
                continue  # Try again

    # --- Return Response --- 
    return Response({
        "title": title,
        "easy_read_sentences": easy_read_sentences,
        "selected_sets": selected_sets
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
        
        # Check for empty response
        if not response.choices:
            raise ValueError("LLM returned empty response.")
        
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

        # Check for empty response
        if not response.choices:
            raise ValueError("LLM returned empty response.")

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
    Uses the new database schema with ImageSet, Image, and Embedding models.
    Expects form-data with 'image' (file), optional 'description' (text), and optional 'set_name' (text).
    Enhanced with comprehensive security validation.
    """
    from api.upload_handlers import handle_image_upload
    from api.security_utils import validate_upload_request, SecurityLogger
    from api.analytics import track_image_upload
    
    logger = logging.getLogger(__name__)

    if 'image' not in request.FILES:
        return Response(
            {"error": "No image file provided", "code": "MISSING_FILE"},
            status=status.HTTP_400_BAD_REQUEST
        )

    image_file = request.FILES['image']
    description = request.POST.get('description', '') # Get description, default to empty
    set_name = request.POST.get('set_name', 'General') # Get set name, default to 'General'

    # Comprehensive security validation
    validation = validate_upload_request(request, image_file, 'image')
    if not validation['valid']:
        SecurityLogger.log_upload_attempt(
            request, image_file.name, 'blocked',
            {'reason': validation['errors']}
        )
        return Response(
            {
                "error": "File validation failed",
                "errors": validation['errors'],
                "code": "VALIDATION_FAILED"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Handle the upload using the new system
    result = handle_image_upload(image_file, description, set_name, is_generated=False)
    
    if result.get("success"):
        # Track successful upload
        try:
            track_image_upload(request, result["filename"], result.get("file_size", 0))
        except Exception as e:
            logger.warning(f"Failed to track image upload: {e}")
        
        # Log successful upload
        SecurityLogger.log_upload_attempt(
            request, image_file.name, 'success',
            {'image_id': result["image_id"], 'set_name': set_name}
        )
        
        # Build image URL for response
        try:
            image_url = request.build_absolute_uri(settings.MEDIA_URL + result['image_path'])
        except Exception as e:
            logger.error(f"Error building image URL: {e}")
            image_url = None
        
        response_data = {
            "success": True,
            "message": result["message"],
            "data": {
                "image_id": result["image_id"],
                "image_path": result["image_path"],
                "image_url": image_url,
                "filename": result["filename"],
                "set_name": result["set_name"],
                "description": result["description"],
                "embeddings_created": result["embeddings_created"],
                "file_format": result["file_format"],
                "file_size": result.get("file_size"),
                "width": result.get("width"),
                "height": result.get("height")
            }
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
    else:
        # Log failed upload
        SecurityLogger.log_upload_attempt(
            request, image_file.name, 'failure',
            {'errors': result.get("errors", result.get("error"))}
        )
        return Response(
            {
                "success": False,
                "error": result.get("error", "Upload failed"),
                "errors": result.get("errors", [result.get("error", "Unknown error")]),
                "code": "UPLOAD_FAILED"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# --- Updated Image Similarity Search Endpoint ---
@api_view(['POST'])
def find_similar_images(request):
    """
    API endpoint to find N most similar images based on a text query.
    Uses the new PostgreSQL database with embeddings instead of ChromaDB.
    Expects JSON: {
        "query": "text description", 
        "n_results": <integer>,
        "exclude_ids": [<integer>, ...] (optional),
        "image_set": <string> (optional),
        "image_sets": [<string>, ...] (optional)
    }
    Returns JSON: {"results": [
        {"id": <int>, "url": <str>, "description": <str>, "similarity": <float>}, ...
    ]} or {"error": "..."}
    """
    from api.similarity_search import search_similar_images
    from django.conf import settings
    
    logger.info("--- find_similar_images view entered (NEW VERSION) ---") 
    
    # --- Input Validation ---
    if not isinstance(request.data, dict): 
        return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
    
    query = request.data.get('query')
    n_results = request.data.get('n_results')
    exclude_ids = request.data.get('exclude_ids', [])
    image_set = request.data.get('image_set')
    image_sets = request.data.get('image_sets')

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
        return Response({"error": "Invalid 'exclude_ids' (must be a list of integers)."}, status=status.HTTP_400_BAD_REQUEST)
    
    if image_set and not isinstance(image_set, str):
        return Response({"error": "Invalid 'image_set' (must be a string)."}, status=status.HTTP_400_BAD_REQUEST)
    
    if image_sets and not isinstance(image_sets, list):
        return Response({"error": "Invalid 'image_sets' (must be a list of strings)."}, status=status.HTTP_400_BAD_REQUEST)

    # --- Search for Similar Images ---
    try:
        logger.info(f"Searching for similar images with query: '{query}', n_results: {n_results}, image_set: {image_set}, image_sets: {image_sets}")
        
        # Use the new similarity search function
        similar_images = search_similar_images(
            query_text=query,
            n_results=n_results,
            image_set=image_set,
            image_sets=image_sets,
            exclude_image_ids=exclude_ids
        )
        
        # Format results for API response
        final_results = []
        for img in similar_images:
            try:
                # Build the image URL
                if img.get('processed_path'):
                    # Use processed path if available (e.g., PNG converted from SVG)
                    image_path = img['processed_path']
                else:
                    # Fall back to original path
                    image_path = img['original_path']
                
                # Create relative path from media root
                from pathlib import Path
                image_path = Path(image_path)
                if image_path.is_absolute():
                    # Try to make it relative to media root
                    try:
                        relative_path = image_path.relative_to(settings.MEDIA_ROOT)
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + str(relative_path))
                    except ValueError:
                        # If path is not under media root, just use the filename
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + 'images/' + image_path.name)
                else:
                    # Already relative
                    image_url = request.build_absolute_uri(settings.MEDIA_URL + str(image_path))
                
                final_results.append({
                    "id": img['id'],
                    "url": image_url,
                    "description": img.get('description', ''),
                    "similarity": img.get('similarity', 0.0),
                    "filename": img.get('filename', ''),
                    "set_name": img.get('set_name', ''),
                    "file_format": img.get('file_format', '')
                })
                
            except Exception as e:
                logger.error(f"Error formatting image result {img.get('id')}: {e}")
                continue
        
        logger.info(f"Returning {len(final_results)} similar images for query: '{query}'")
        return Response({"results": final_results}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error in find_similar_images: {e}")
        return Response({"error": f"Failed to search for similar images: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

# --- Image List Endpoint --- (Updated for new database schema)
@api_view(['GET'])
def list_images(request):
    """
    API endpoint to list all images stored in the database, organized by sets.
    Returns images grouped by their sets, with metadata.
    """
    from api.upload_handlers import get_image_list_formatted
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get formatted image list using the new system
        result = get_image_list_formatted(request)
        
        if result.get("error"):
            logger.error(f"Error getting image list: {result['error']}")
            return Response({
                "images_by_set": {},
                "total_images": 0,
                "total_sets": 0,
                "error": result["error"]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.info(f"Retrieved {result['total_images']} images from {result['total_sets']} sets")
        
        return Response({
            "images_by_set": result["images_by_set"],
            "total_images": result["total_images"],
            "total_sets": result["total_sets"]
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error retrieving images from database: {e}")
        return Response({
            "images_by_set": {},
            "total_images": 0,
            "total_sets": 0,
            "error": "Failed to retrieve images from database"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Batch Image Upload Endpoint ---
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def batch_upload_images(request):
    """
    API endpoint to upload multiple images at once, optionally with a shared description.
    Uses the new database schema with ImageSet, Image, and Embedding models.
    Expects form-data with 'images' (files), optional 'description' (text), and optional 'set_name' (text).
    Enhanced with security validation and rate limiting.
    """
    from api.upload_handlers import handle_batch_image_upload
    from api.security_utils import RateLimiter
    from api.analytics import get_client_ip
    
    logger = logging.getLogger(__name__)
    
    # Check rate limiting for batch uploads (stricter limit)
    ip_address = get_client_ip(request)
    rate_check = RateLimiter.check_rate_limit(
        identifier=ip_address,
        action='batch_upload',
        max_requests=50,  # 50 batch uploads per minute (for large sets)
        window_seconds=60
    )
    
    if not rate_check['allowed']:
        return Response(
            {
                "error": rate_check['message'],
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after": rate_check['retry_after']
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    if 'images' not in request.FILES:
        return Response(
            {"error": "No image files provided", "code": "MISSING_FILES"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get all files from the request
    image_files = request.FILES.getlist('images')
    description = request.POST.get('description', '')  # Get description, default to empty
    set_name = request.POST.get('set_name', 'General')  # Get set name, default to 'General'
    
    if not image_files:
        return Response(
            {"error": "Empty file list", "code": "EMPTY_FILES"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Handle batch upload using the new system with request for validation
    result = handle_batch_image_upload(image_files, description, set_name, request=request)
    
    # Build image URLs for successful uploads
    for upload_result in result.get("results", []):
        if upload_result.get("success") and upload_result.get("image_path"):
            try:
                upload_result["image_url"] = request.build_absolute_uri(
                    settings.MEDIA_URL + upload_result["image_path"]
                )
            except Exception as e:
                logger.error(f"Error building image URL for {upload_result.get('filename')}: {e}")
    
    # Standardize response format
    response_data = {
        "success": result["successful_uploads"] > 0,
        "message": result["message"],
        "data": {
            "results": result["results"],
            "successful_uploads": result["successful_uploads"],
            "total_uploads": result["total_uploads"],
            "description": result["description"],
            "set_name": result["set_name"]
        }
    }
    
    # Determine HTTP status based on success rate
    if result["successful_uploads"] > 0:
        status_code = status.HTTP_200_OK if result["successful_uploads"] == result["total_uploads"] else status.HTTP_207_MULTI_STATUS
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    
    return Response(response_data, status=status_code)


# --- Folder Upload Endpoint ---
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_folder(request):
    """
    API endpoint to upload a folder structure with automatic set creation.
    Expects form-data with files that include webkitRelativePath information.
    Creates image sets based on folder names automatically.
    Enhanced with security validation and rate limiting.
    """
    from api.upload_handlers import handle_folder_upload
    from api.analytics import track_event
    from api.security_utils import RateLimiter
    from api.analytics import get_client_ip
    
    logger = logging.getLogger(__name__)
    
    # Check rate limiting for folder uploads
    ip_address = get_client_ip(request)
    rate_check = RateLimiter.check_rate_limit(
        identifier=ip_address,
        action='folder_upload',
        max_requests=50,  # 50 folder uploads per minute (for large sets)
        window_seconds=60
    )
    
    if not rate_check['allowed']:
        return Response(
            {
                "error": rate_check['message'],
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after": rate_check['retry_after']
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    if not request.FILES:
        return Response(
            {"error": "No files provided", "code": "MISSING_FILES"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Extract folder structure from files
    folder_data = {}
    for key in request.FILES:
        file_obj = request.FILES[key]
        # Extract relative path from file name or form key
        # Frontend should send files with keys like "folder_name/image.jpg"
        if hasattr(file_obj, 'webkitRelativePath') and file_obj.webkitRelativePath:
            relative_path = file_obj.webkitRelativePath
        else:
            # Fallback to using the form key as path
            relative_path = key
        
        folder_data[relative_path] = file_obj

    if not folder_data:
        return Response(
            {"error": "No valid folder structure found", "code": "INVALID_STRUCTURE"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Track analytics
    try:
        track_event(request, 'folder_upload', {
            'total_files': len(folder_data),
            'folder_paths': list(folder_data.keys())[:5]  # Store first 5 paths for analysis
        })
    except Exception as e:
        logger.warning(f"Failed to track folder upload analytics: {e}")

    # Handle folder upload with request for validation
    result = handle_folder_upload(folder_data, request=request)
    
    # Debug logging for folder upload result
    logger.info(f"📋 Folder upload result: {result}")
    logger.info(f"📋 Total successful: {result.get('total_successful', 0)}")
    logger.info(f"📋 Total uploads: {result.get('total_uploads', 0)}")
    logger.info(f"📋 Folders: {list(result.get('folders', {}).keys())}")
    
    # Build image URLs for successful uploads
    for folder_name, folder_result in result.get("folders", {}).items():
        for upload_result in folder_result.get("results", []):
            if upload_result.get("success") and upload_result.get("image_path"):
                upload_result["image_url"] = request.build_absolute_uri(
                    f"{settings.MEDIA_URL}{upload_result['image_path']}"
                )

    # Standardize response format
    response_data = {
        "success": result.get("total_successful", 0) > 0,
        "message": result["message"],
        "data": {
            "folders": result["folders"],
            "total_successful": result["total_successful"],
            "total_uploads": result["total_uploads"],
            "sets_created": result["sets_created"]
        }
    }
    
    # Determine HTTP status
    if result.get("total_successful", 0) > 0:
        status_code = status.HTTP_200_OK if result["total_successful"] == result["total_uploads"] else status.HTTP_207_MULTI_STATUS
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    
    return Response(response_data, status=status_code)


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
    
    # Debug logging
    logger.info(f"Update saved content image called - Content ID: {content_id}")
    logger.info(f"Request data: {request.data}")
    
    try:
        # Validate input
        if not isinstance(request.data, dict):
            return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
        
        sentence_index = request.data.get('sentence_index')
        image_url = request.data.get('image_url')
        all_images = request.data.get('all_images', [])
        
        logger.info(f"Parsed data - sentence_index: {sentence_index}, image_url: {image_url}, all_images count: {len(all_images) if all_images else 0}")
        
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
        old_image_path = content.easy_read_json[sentence_index].get('selected_image_path')
        content.easy_read_json[sentence_index]['selected_image_path'] = image_url
        
        # Add all alternative images if provided
        if all_images:
            content.easy_read_json[sentence_index]['alternative_images'] = all_images
        
        content.save()
        
        logger.info(f"Successfully updated content {content_id}, sentence {sentence_index}: '{old_image_path}' -> '{image_url}'")
        
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
        # Parameters based on the example: config/temp/gradio.py
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

                # Save the generated image using the new upload handler
                from api.upload_handlers import handle_image_upload
                from django.core.files.uploadedfile import SimpleUploadedFile
                
                # Create a Django file object from the saved image
                with open(image_save_path, 'rb') as f:
                    image_content = f.read()
                
                django_file = SimpleUploadedFile(
                    name=image_name,
                    content=image_content,
                    content_type='image/png'
                )
                
                # Use the upload handler to process the generated image
                upload_result = handle_image_upload(
                    image_file=django_file,
                    description=prompt,
                    set_name='Generated',
                    is_generated=True
                )
                
                if upload_result.get("success"):
                    generated_images_details.append({
                        "id": upload_result["image_id"],
                        "url": request.build_absolute_uri(settings.MEDIA_URL + upload_result["image_path"]),
                        "embeddings_created": upload_result["embeddings_created"],
                        "filename": upload_result["filename"],
                        "set_name": upload_result["set_name"]
                    })
                    logger.info(f"Generated image processed successfully: {upload_result['filename']}")
                else:
                    logger.error(f"Failed to process generated image: {upload_result.get('error')}")
                
                # Clean up the temporary file
                try:
                    os.remove(image_save_path)
                except Exception as e_cleanup:
                    logger.warning(f"Failed to clean up temporary file {image_save_path}: {e_cleanup}")

            except FileNotFoundError:
                logger.error(f"Temporary image file from Gradio not found: {temp_image_path}")
                # Continue to next image if one is not found
            except Exception as e_single_image:
                logger.error(f"Error processing generated image {temp_image_path}: {e_single_image}")
                # Continue to next image if one fails

        if not generated_images_details:
             return Response({"error": "Image generation completed, but no valid images were processed or saved."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Return the results in the updated format ---
        if len(generated_images_details) == 1:
            # Single image response (backward compatibility)
            first_image = generated_images_details[0]
            return Response({
                "message": "Image generated successfully.",
                "new_image_id": first_image["id"],
                "new_image_url": first_image["url"],
                "embeddings_created": first_image["embeddings_created"],
                "filename": first_image["filename"],
                "set_name": first_image["set_name"],
                "all_generated_images": generated_images_details
            }, status=status.HTTP_201_CREATED)
        else:
            # Multiple images response
            return Response({
                "message": f"Generated {len(generated_images_details)} images successfully.",
                "all_generated_images": generated_images_details,
                "total_generated": len(generated_images_details)
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.exception(f"Error during Gradio image generation for prompt '{prompt}': {e}")
        return Response({"error": f"Image generation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- New Image Sets Endpoints ---
@api_view(['GET'])
def get_image_sets(request):
    """
    API endpoint to get all available image sets.
    Returns a list of image sets with metadata.
    """
    from api.similarity_search import get_all_image_sets
    
    logger = logging.getLogger(__name__)
    
    try:
        image_sets = get_all_image_sets()
        logger.info(f"Retrieved {len(image_sets)} image sets")
        
        return Response({
            "image_sets": image_sets,
            "total_sets": len(image_sets)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error retrieving image sets: {e}")
        return Response({
            "error": "Failed to retrieve image sets"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_images_in_set(request, set_name):
    """
    API endpoint to get images in a specific set.
    Returns a list of images in the specified set.
    """
    from api.similarity_search import get_images_in_set
    
    logger = logging.getLogger(__name__)
    
    try:
        limit = request.GET.get('limit', 50)
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 50
        
        images = get_images_in_set(set_name, limit)
        logger.info(f"Retrieved {len(images)} images from set '{set_name}'")
        
        # Add image URLs
        for image in images:
            try:
                if image.get('processed_path'):
                    image_path = image['processed_path']
                else:
                    image_path = image['original_path']
                
                # Create relative path from media root
                from pathlib import Path
                image_path = Path(image_path)
                if image_path.is_absolute():
                    try:
                        relative_path = image_path.relative_to(settings.MEDIA_ROOT)
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + str(relative_path))
                    except ValueError:
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + 'images/' + image_path.name)
                else:
                    image_url = request.build_absolute_uri(settings.MEDIA_URL + str(image_path))
                
                image['url'] = image_url
                
            except Exception as e:
                logger.error(f"Error building URL for image {image.get('id')}: {e}")
                image['url'] = None
        
        return Response({
            "set_name": set_name,
            "images": images,
            "total_images": len(images),
            "limit": limit
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error retrieving images in set '{set_name}': {e}")
        return Response({
            "error": f"Failed to retrieve images in set '{set_name}'"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- Health Check Endpoint ---
@api_view(['GET'])
def health_check(request):
    """
    API endpoint for system health monitoring.
    Returns comprehensive health status of the embedding system.
    """
    from api.monitoring import EmbeddingHealthCheck
    
    try:
        health_status = EmbeddingHealthCheck.full_health_check()
        
        # Determine overall status
        model_healthy = health_status['model']['status'] == 'healthy'
        db_healthy = health_status['database']['status'] == 'healthy'
        storage_healthy = health_status['storage']['status'] in ['healthy', 'degraded']
        
        overall_status = 'healthy' if all([model_healthy, db_healthy, storage_healthy]) else 'unhealthy'
        
        response_data = {
            'status': overall_status,
            'timestamp': health_status['timestamp'],
            'components': {
                'embedding_model': health_status['model'],
                'database': health_status['database'],
                'storage': health_status['storage']
            },
            'metrics': health_status['metrics']
        }
        
        status_code = status.HTTP_200_OK if overall_status == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(response_data, status=status_code)
        
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['PUT'])
def bulk_update_saved_content_images(request, content_id):
    """
    API endpoint to bulk update all image selections for saved content.
    Expects JSON: {
        "image_selections": {
            "0": "image_url_for_sentence_0",
            "1": "image_url_for_sentence_1",
            ...
        }
    }
    Returns JSON: {"message": "Content updated successfully."}
    """
    try:
        # Validate input
        if not isinstance(request.data, dict):
            return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
        
        image_selections = request.data.get('image_selections', {})
        if not isinstance(image_selections, dict):
            return Response({"error": "Invalid 'image_selections' format. Expected object."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the content object
        content = get_object_or_404(ProcessedContent, pk=content_id)
        
        # Parse the current JSON data
        try:
            if isinstance(content.easy_read_json, list):
                easy_read_data = content.easy_read_json
            elif isinstance(content.easy_read_json, str):
                easy_read_data = json.loads(content.easy_read_json)
            else:
                return Response({"error": "Invalid content data format."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except (json.JSONDecodeError, AttributeError) as e:
            return Response({"error": f"Failed to parse content data: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Update the image selections
        for index_str, image_url in image_selections.items():
            try:
                index = int(index_str)
                if 0 <= index < len(easy_read_data):
                    easy_read_data[index]['selected_image_path'] = image_url
            except (ValueError, IndexError):
                continue  # Skip invalid indices
        
        # Save the updated data
        content.easy_read_json = easy_read_data
        content.save()
        
        return Response({"message": "Content updated successfully."}, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def export_content_docx(request, content_id=None):
    """
    Export EasyRead content as a DOCX document.
    Can be used for both saved content (with content_id) and current results (via POST data).
    """
    try:
        if content_id:
            # Export saved content
            try:
                content = ProcessedContent.objects.get(id=content_id)
                title = content.title
                easy_read_content = content.easy_read_json
                original_markdown = content.original_markdown
            except ProcessedContent.DoesNotExist:
                return HttpResponse("Content not found", status=404)
        else:
            # Export from request data (for current results)
            title = request.GET.get('title', 'EasyRead Document')
            easy_read_data = request.GET.get('content')
            original_markdown = request.GET.get('original_markdown')
            
            if not easy_read_data:
                return HttpResponse("No content provided for export", status=400)
            
            try:
                easy_read_content = json.loads(easy_read_data)
            except json.JSONDecodeError:
                return HttpResponse("Invalid content format", status=400)
        
        # Create the DOCX document
        docx_buffer = create_docx_export(title, easy_read_content, original_markdown)
        
        # Generate safe filename
        safe_filename = get_safe_filename(title)
        filename = f"{safe_filename}.docx"
        
        # Create HTTP response with DOCX content
        response = HttpResponse(
            docx_buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(docx_buffer.getvalue())
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting DOCX: {str(e)}")
        return HttpResponse(f"Export failed: {str(e)}", status=500)


@api_view(['POST'])
def export_current_content_docx(request):
    """
    Export current EasyRead content as DOCX (for ResultPage).
    Expects JSON: {
        "title": "Document Title",
        "easy_read_content": [...],
        "original_markdown": "..."
    }
    """
    try:
        title = request.data.get('title', 'EasyRead Document')
        easy_read_content = request.data.get('easy_read_content', [])
        original_markdown = request.data.get('original_markdown', '')
        
        if not easy_read_content:
            return HttpResponse("No content provided for export", status=400)
        
        # Create the DOCX document
        docx_buffer = create_docx_export(title, easy_read_content, original_markdown)
        
        # Generate safe filename
        safe_filename = get_safe_filename(title)
        filename = f"{safe_filename}.docx"
        
        # Create HTTP response with DOCX content
        response = HttpResponse(
            docx_buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(docx_buffer.getvalue())
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting current content DOCX: {str(e)}")
        return HttpResponse(f"Export failed: {str(e)}", status=500)


@api_view(['POST'])
def find_similar_images_batch(request):
    """
    API endpoint to find similar images for multiple queries in a single request.
    This optimizes performance by processing all image searches together.
    Expects JSON: {
        "queries": [
            {"index": 0, "query": "text description", "n_results": <integer>},
            {"index": 1, "query": "another description", "n_results": <integer>},
            ...
        ],
        "exclude_ids": [<integer>, ...] (optional),
        "image_set": <string> (optional),
        "image_sets": [<string>, ...] (optional)
    }
    Returns JSON: {
        "results": {
            "0": [{"id": <int>, "url": <str>, "description": <str>, "similarity": <float>}, ...],
            "1": [{"id": <int>, "url": <str>, "description": <str>, "similarity": <float>}, ...],
            ...
        }
    } or {"error": "..."}
    """
    from api.similarity_search import search_similar_images
    from api.analytics import get_or_create_session, track_event
    from api.image_allocation import optimize_image_allocation
    from django.conf import settings
    import concurrent.futures
    import threading
    
    logger = logging.getLogger(__name__)
    logger.info("--- find_similar_images_batch view entered ---")
    
    # Track analytics for batch image search
    try:
        session = get_or_create_session(request)
        track_event(request, 'image_search_batch', {
            'query_count': len(request.data.get('queries', [])),
            'exclude_ids_count': len(request.data.get('exclude_ids', [])),
            'image_sets': request.data.get('image_sets', [])
        })
    except Exception as e:
        logger.warning(f"Analytics tracking failed for batch image search: {e}")
    
    # --- Input Validation ---
    if not isinstance(request.data, dict):
        return Response({"error": "Invalid request format. Expected JSON object."}, status=status.HTTP_400_BAD_REQUEST)
    
    queries = request.data.get('queries', [])
    exclude_ids = request.data.get('exclude_ids', [])
    image_set = request.data.get('image_set')
    image_sets = request.data.get('image_sets')
    
    if not queries or not isinstance(queries, list):
        return Response({"error": "Missing or invalid 'queries' (must be a non-empty list)."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate each query
    for i, query_item in enumerate(queries):
        if not isinstance(query_item, dict):
            return Response({"error": f"Query {i} must be a dictionary."}, status=status.HTTP_400_BAD_REQUEST)
        
        if 'index' not in query_item or 'query' not in query_item:
            return Response({"error": f"Query {i} missing required 'index' or 'query' fields."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(query_item['query'], str) or not query_item['query'].strip():
            return Response({"error": f"Query {i} 'query' must be a non-empty string."}, status=status.HTTP_400_BAD_REQUEST)
        
        n_results = query_item.get('n_results', 3)
        try:
            n_results = int(n_results)
            if n_results <= 0:
                raise ValueError("n_results must be positive")
            query_item['n_results'] = n_results
        except (ValueError, TypeError):
            return Response({"error": f"Query {i} 'n_results' must be a positive integer."}, status=status.HTTP_400_BAD_REQUEST)
    
    if exclude_ids and not isinstance(exclude_ids, list):
        return Response({"error": "Invalid 'exclude_ids' (must be a list of integers)."}, status=status.HTTP_400_BAD_REQUEST)
    
    if image_set and not isinstance(image_set, str):
        return Response({"error": "Invalid 'image_set' (must be a string)."}, status=status.HTTP_400_BAD_REQUEST)
    
    if image_sets and not isinstance(image_sets, list):
        return Response({"error": "Invalid 'image_sets' (must be a list of strings)."}, status=status.HTTP_400_BAD_REQUEST)
    
    logger.info(f"Processing batch of {len(queries)} image search queries")
    
    # --- Process Queries in Parallel ---
    def process_single_query(query_item):
        """Process a single query and return results with error handling."""
        index = query_item['index']
        query_text = query_item['query']
        n_results = query_item['n_results']
        
        try:
            logger.info(f"Processing query {index}: '{query_text}' (n_results: {n_results})")
            
            # Use the existing similarity search function
            similar_images = search_similar_images(
                query_text=query_text,
                n_results=n_results,
                image_set=image_set,
                image_sets=image_sets,
                exclude_image_ids=exclude_ids
            )
            
            # Format results for API response
            formatted_results = []
            for img in similar_images:
                try:
                    # Build the image URL (same logic as individual endpoint)
                    if img.get('processed_path'):
                        image_path = img['processed_path']
                    else:
                        image_path = img['original_path']
                    
                    # Create relative path from media root
                    from pathlib import Path
                    image_path = Path(image_path)
                    if image_path.is_absolute():
                        try:
                            relative_path = image_path.relative_to(settings.MEDIA_ROOT)
                            image_url = request.build_absolute_uri(settings.MEDIA_URL + str(relative_path))
                        except ValueError:
                            image_url = request.build_absolute_uri(settings.MEDIA_URL + 'images/' + image_path.name)
                    else:
                        image_url = request.build_absolute_uri(settings.MEDIA_URL + str(image_path))
                    
                    formatted_results.append({
                        "id": img['id'],
                        "url": image_url,
                        "description": img.get('description', ''),
                        "similarity": img.get('similarity', 0.0),
                        "filename": img.get('filename', ''),
                        "set_name": img.get('set_name', ''),
                        "file_format": img.get('file_format', '')
                    })
                    
                except Exception as e:
                    logger.error(f"Error formatting image result {img.get('id')} for query {index}: {e}")
                    continue
            
            logger.info(f"Query {index} completed: found {len(formatted_results)} images")
            return {
                "index": str(index),
                "results": formatted_results,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error processing query {index} ('{query_text}'): {e}")
            return {
                "index": str(index),
                "results": [],
                "success": False,
                "error": str(e)
            }
    
    # --- Execute Queries in Parallel ---
    try:
        batch_results = {}
        
        # Use ThreadPoolExecutor for I/O-bound database operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(queries), 5)) as executor:
            # Submit all queries
            future_to_query = {executor.submit(process_single_query, query): query for query in queries}
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_query, timeout=60):
                try:
                    result = future.result()
                    batch_results[result["index"]] = result["results"]
                    
                    if not result["success"]:
                        logger.warning(f"Query {result['index']} failed: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    query_item = future_to_query[future]
                    logger.error(f"Error getting result for query {query_item.get('index', 'unknown')}: {e}")
                    batch_results[str(query_item.get('index', 'error'))] = []
        
        logger.info(f"Batch processing completed: {len(batch_results)} results returned")
        
        # Apply optimal image allocation if duplicate prevention is requested
        optimal_allocation = None
        allocation_metrics = None
        
        try:
            # Check if we should apply allocation optimization
            # For now, always apply it to improve image selection
            if len(batch_results) > 1:  # Only optimize if multiple sentences
                logger.info("Applying optimal image allocation...")
                
                allocation_result = optimize_image_allocation(
                    batch_results=batch_results,
                    prevent_duplicates=True,  # Always prevent duplicates for better user experience
                    options={
                        'similarity_threshold': 0.1,
                        'uniqueness_bonus': 0.15,
                        'high_similarity_threshold': 0.8,
                        'local_search_iterations': 2,
                        'enable_local_search': len(batch_results) <= 30  # Only for reasonable sizes
                    }
                )
                
                optimal_allocation = allocation_result.get("allocation", {})
                allocation_metrics = allocation_result.get("metrics", {})
                
                logger.info(f"Image allocation completed: {allocation_metrics}")
                
                # Track allocation analytics
                track_event(request, 'image_allocation_applied', {
                    'sentences_count': len(batch_results),
                    'algorithm': allocation_metrics.get('algorithm', 'unknown'),
                    'assignment_rate': allocation_metrics.get('assignment_rate', 0),
                    'processing_time_ms': allocation_metrics.get('processing_time_ms', 0)
                })
                
        except Exception as e:
            logger.error(f"Error in image allocation optimization: {e}")
            # Continue without allocation - don't fail the entire request
        
        response_data = {
            "results": batch_results
        }
        
        # Include allocation in response if available
        if optimal_allocation:
            response_data["optimal_allocation"] = optimal_allocation
            
        if allocation_metrics:
            response_data["allocation_metrics"] = allocation_metrics
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except concurrent.futures.TimeoutError:
        logger.error("Batch processing timed out")
        return Response({"error": "Batch processing timed out"}, status=status.HTTP_408_REQUEST_TIMEOUT)
        
    except Exception as e:
        logger.exception(f"Error in find_similar_images_batch: {e}")
        return Response({"error": f"Failed to process batch image search: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
