import os
import tempfile
from io import BytesIO
import json
import unittest
import yaml

from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from reportlab.lib.pagesizes import letter
from unittest.mock import patch, MagicMock, mock_open, ANY
from .models import ProcessedContent
from PIL import Image
import numpy as np

class PdfToMarkdownTests(APITestCase):

    def test_pdf_to_markdown_success(self):
        """
        Test successful PDF to Markdown conversion using a real file.
        """
        url = reverse('markdown_extraction')
        pdf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'resources', 'example_pdf.pdf') # Construct path relative to tests.py

        try:
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
        except FileNotFoundError:
            self.fail(f"Test PDF file not found at: {pdf_path}")

        # Create a SimpleUploadedFile
        pdf_file = SimpleUploadedFile(
            name='example_pdf.pdf', # Use the actual filename
            content=pdf_content, 
            content_type='application/pdf'
        )

        response = self.client.post(url, {'file': pdf_file}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check for 'pages' key and that it's a list
        self.assertIn('pages', response.data)
        self.assertTrue(isinstance(response.data['pages'], list))
        # Check that the list is not empty (assuming example_pdf has content)
        self.assertGreater(len(response.data['pages']), 0)
        # Check that the first page content is a non-empty string
        self.assertTrue(isinstance(response.data['pages'][0], str))
        self.assertGreater(len(response.data['pages'][0].strip()), 0)

    def test_pdf_to_markdown_no_file(self):
        """
        Test request without providing a file.
        """
        url = reverse('markdown_extraction')
        response = self.client.post(url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'No file provided')

    def test_pdf_to_markdown_invalid_file_type(self):
        """
        Test request with a non-PDF file.
        """
        url = reverse('markdown_extraction')
        # Create a simple text file in memory
        txt_buffer = BytesIO(b"This is not a PDF.")
        txt_buffer.name = 'not_a_pdf.txt' # Important for checking extension
        txt_buffer.seek(0)

        response = self.client.post(url, {'file': txt_buffer}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Invalid file type, please upload a PDF')

    # Optional: Test with a more complex PDF or an empty PDF if needed

# --- Tests for process_markdown endpoint ---

# Mock response structure from litellm
class MockLLMResponseChoice:
    def __init__(self, content):
        self.message = MagicMock()
        self.message.content = content

class MockLLMResponse:
    def __init__(self, content_input):
        # Input can be a dict (for valid JSON object responses),
        # a list (for testing invalid JSON array responses),
        # or a string (for testing non-JSON responses).
        if isinstance(content_input, str):
            # Pass raw string for non-JSON tests
            json_content = content_input
        else:
            # Serialize dicts or lists to JSON strings for the mock message content
            json_content = json.dumps(content_input)
        self.choices = [MockLLMResponseChoice(json_content)]

class ProcessPageTests(APITestCase):

    @patch('api.views.litellm.completion') 
    def test_process_page_success(self, mock_completion):
        """
        Test successful markdown page processing.
        """
        url = reverse('easy_read_generation')
        markdown_input = "# Page 1\nSome complex text."
        
        # Expected list of sentences
        expected_sentences = [
            {"sentence": "Page 1 simple.", "image_retrieval": "page one simple"},
            {"sentence": "More simple text.", "image_retrieval": "simple text example"}
        ]
        
        # Configure the mock to return the full JSON object structure
        mock_llm_output = {"easy_read_sentences": expected_sentences}
        mock_completion.return_value = MockLLMResponse(mock_llm_output)

        # Send single page in the correct format
        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check the final API response structure
        self.assertIn('easy_read_sentences', response.data)
        self.assertEqual(response.data['easy_read_sentences'], expected_sentences) # API should return the extracted list
        mock_completion.assert_called_once() 

    def test_process_page_invalid_input_format(self):
        """
        Test sending data that is not a dict or missing key.
        """
        url = reverse('easy_read_generation')
        response = self.client.post(url, ["page1"], format='json') 
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

        response = self.client.post(url, {"wrong_key": "test"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_process_page_invalid_value_type(self):
        """
        Test sending non-string for markdown_page.
        """
        url = reverse('easy_read_generation')
        response = self.client.post(url, {"markdown_page": ["not a string"]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    @patch('api.views.litellm.completion')
    def test_process_page_llm_error(self, mock_completion):
        """
        Test handling of LLM API errors (check dict format).
        """
        url = reverse('easy_read_generation')
        markdown_input = "Page 1 content."
        mock_completion.side_effect = Exception("LLM API Error")

        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('easy_read_sentences', response.data)
        self.assertEqual(len(response.data['easy_read_sentences']), 1) # Should be a list containing one error dict
        error_dict = response.data['easy_read_sentences'][0]
        self.assertIn('sentence', error_dict)
        self.assertIn('image_retrieval', error_dict)
        self.assertTrue(error_dict['sentence'].startswith("Error: LLM processing failed"))
        self.assertEqual(error_dict['image_retrieval'], "error processing")

    @patch('api.views.litellm.completion')
    def test_process_page_llm_invalid_json(self, mock_completion):
        """
        Test handling when LLM returns non-JSON or invalid structure.
        """
        url = reverse('easy_read_generation')
        markdown_input = "Page 1 content."
        
        # Simulate non-JSON string
        mock_completion.return_value = MockLLMResponse("This is not JSON.") 
        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('easy_read_sentences', response.data)
        self.assertEqual(len(response.data['easy_read_sentences']), 1) # Should contain one error dict
        error_dict_non_json = response.data['easy_read_sentences'][0]
        self.assertTrue(error_dict_non_json['sentence'].startswith("Error: Failed to parse/validate LLM response"))

        # Simulate JSON that is not a dictionary
        mock_completion.return_value = MockLLMResponse(["sentence 1", "sentence 2"])
        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('easy_read_sentences', response.data)
        self.assertEqual(len(response.data['easy_read_sentences']), 1)
        error_dict_list = response.data['easy_read_sentences'][0]
        self.assertTrue(error_dict_list['sentence'].startswith("Error: Failed to parse/validate LLM response")) # Expect error

        # Simulate correct dict structure but wrong key
        mock_completion.return_value = MockLLMResponse({"wrong_key": [{"sentence": "s1", "image_retrieval": "k1"}]})
        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('easy_read_sentences', response.data)
        self.assertEqual(len(response.data['easy_read_sentences']), 1)
        error_dict_wrong_key = response.data['easy_read_sentences'][0]
        self.assertTrue(error_dict_wrong_key['sentence'].startswith("Error: Failed to parse/validate LLM response")) # Expect error

        # Simulate correct dict key but value is not a list
        mock_completion.return_value = MockLLMResponse({"easy_read_sentences": {"sentence": "s1", "image_retrieval": "k1"}})
        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('easy_read_sentences', response.data)
        self.assertEqual(len(response.data['easy_read_sentences']), 1)
        error_dict_not_list = response.data['easy_read_sentences'][0]
        self.assertTrue(error_dict_not_list['sentence'].startswith("Error: Failed to parse/validate LLM response")) # Expect error

        # Simulate list of dicts with missing keys inside the correct structure
        mock_completion.return_value = MockLLMResponse({"easy_read_sentences": [{"sentence": "ok"}, {"image_retrieval": "also ok"}]})
        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('easy_read_sentences', response.data)
        self.assertEqual(len(response.data['easy_read_sentences']), 1)
        error_dict_missing_keys = response.data['easy_read_sentences'][0]
        self.assertTrue(error_dict_missing_keys['sentence'].startswith("Error: Failed to parse/validate LLM response")) # Expect error

    @patch('api.views.load_prompt_template')
    def test_process_page_prompt_load_error(self, mock_load_prompt):
        """
        Test handling when the prompt YAML cannot be loaded.
        """
        url = reverse('easy_read_generation')
        markdown_input = "Page 1 content."
        mock_load_prompt.return_value = None 

        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Failed to load or parse prompt template YAML, or missing required keys.")
    
    @unittest.skipUnless(
        os.environ.get('RUN_LIVE_LLM_TESTS') == 'true',
        "Skipping live LLM test. Set RUN_LIVE_LLM_TESTS=true environment variable to run."
    )
    def test_process_page_live_llm_call(self):
        """
        Test the process_page endpoint with a real LLM call.
        Requires RUN_LIVE_LLM_TESTS=true env var and valid API key.
        """
        url = reverse('easy_read_generation')
        # Use a single, slightly more complex page for live test
        markdown_input = "# Complex Title\nThis first sentence has two parts, making it complex. The second idea involves multiple concepts and should also be split."

        response = self.client.post(url, {"markdown_page": markdown_input}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Live LLM call failed: {response.content}")
        self.assertIn('easy_read_sentences', response.data)
        output_data = response.data['easy_read_sentences']

        # Basic structure check (should be a list)
        self.assertTrue(isinstance(output_data, list))
        self.assertGreater(len(output_data), 0, "LLM returned an empty list") # Expect at least one sentence
        # Check structure of the first item 
        item = output_data[0]
        self.assertTrue(isinstance(item, dict), f"Item is not a dict: {item}")
        self.assertIn('sentence', item)
        self.assertIn('image_retrieval', item)
        self.assertTrue(isinstance(item['sentence'], str))
        self.assertTrue(isinstance(item['image_retrieval'], str))
        self.assertGreater(len(item['sentence'].strip()), 0)
        self.assertGreater(len(item['image_retrieval'].strip()), 0)
        # Optionally, check if more than one dict was returned for complex input
        # self.assertGreater(len(output_data), 1, "LLM did not split complex input into multiple sentences")


# --- Integration Tests ---

class EasyReadIntegrationTests(APITestCase):

    @patch('api.views.litellm.completion') 
    def test_pdf_to_easy_read_flow(self, mock_llm_completion):
        """
        Test the full flow from PDF upload to Easy Read dict list (using process-page).
        """
        # --- Step 1: Call pdf-to-markdown endpoint --- 
        pdf_to_md_url = reverse('markdown_extraction')
        pdf_path = os.path.join(os.path.dirname(__file__), '..', '..', 'resources', 'example_pdf.pdf')

        try:
            with open(pdf_path, 'rb') as f:
                pdf_file = SimpleUploadedFile(
                    name='example_integration.pdf', 
                    content=f.read(), 
                    content_type='application/pdf'
                )
        except FileNotFoundError:
            self.fail(f"Integration test PDF file not found at: {pdf_path}")

        response_pdf = self.client.post(pdf_to_md_url, {'file': pdf_file}, format='multipart')
        self.assertEqual(response_pdf.status_code, status.HTTP_200_OK, f"pdf-to-markdown failed: {response_pdf.content}")
        self.assertIn('pages', response_pdf.data)
        markdown_pages = response_pdf.data['pages']
        self.assertTrue(isinstance(markdown_pages, list))
        self.assertGreater(len(markdown_pages), 0, "pdf-to-markdown returned empty pages list")
        self.assertTrue(isinstance(markdown_pages[0], str))

        # --- Step 2: Call process-page endpoint for each page --- 
        process_page_url = reverse('easy_read_generation')
        final_easy_read_pages = []
        mock_call_count = 0

        # Configure mock responses for each expected call
        mock_llm_responses = []
        for i in range(len(markdown_pages)):
            # Define the list of sentences for this page
            mock_sentences = [
                {"sentence": f"Page {i+1} mock sentence 1.", "image_retrieval": f"page {i+1} mock concept 1"},
                {"sentence": f"Page {i+1} mock sentence 2.", "image_retrieval": f"page {i+1} mock concept 2"}
            ]
            # Wrap the list in the expected dictionary structure
            mock_llm_output = {"easy_read_sentences": mock_sentences}
            mock_llm_responses.append(MockLLMResponse(mock_llm_output))
        mock_llm_completion.side_effect = mock_llm_responses

        for page_md in markdown_pages:
            payload = {"markdown_page": page_md}
            response_page = self.client.post(process_page_url, payload, format='json')
            
            self.assertEqual(response_page.status_code, status.HTTP_200_OK, f"process-page failed for a page: {response_page.content}")
            self.assertIn('easy_read_sentences', response_page.data)
            easy_read_sentences = response_page.data['easy_read_sentences']
            # Basic validation for the page result
            self.assertTrue(isinstance(easy_read_sentences, list))
            if len(easy_read_sentences) > 0:
                self.assertTrue(isinstance(easy_read_sentences[0], dict))
                self.assertIn('sentence', easy_read_sentences[0])
                self.assertIn('image_retrieval', easy_read_sentences[0])
            
            final_easy_read_pages.append(easy_read_sentences)
            mock_call_count += 1

        # --- Step 3: Assert final structure and mock calls --- 
        self.assertEqual(len(final_easy_read_pages), len(markdown_pages), "Number of processed pages doesn't match input pages")
        self.assertEqual(mock_llm_completion.call_count, mock_call_count)
        # Check structure of the first page's output (example)
        if len(final_easy_read_pages) > 0 and len(final_easy_read_pages[0]) > 0:
            first_item = final_easy_read_pages[0][0]
            self.assertIn('sentence', first_item)
            self.assertIn('image_retrieval', first_item)
            self.assertTrue(isinstance(first_item['sentence'], str))
            self.assertTrue(isinstance(first_item['image_retrieval'], str))

# --- Tests for validate_completeness endpoint ---

class ValidateCompletenessTests(APITestCase):

    @patch('api.views.litellm.completion')
    def test_validate_completeness_success(self, mock_completion):
        """Test successful validation call."""
        url = reverse('content_validation')
        markdown_input = "# Title\nSome important text. Another key point."
        sentences_input = ["This is the title.", "Here is the important text.", "We mention the key point."]
        
        # UPDATED Expected LLM output
        expected_llm_output = {
            "is_complete": True,
            "missing_info": "", # Now a string
            "extra_info": ""  # Now a string
        }
        
        # Configure mock
        mock_completion.return_value = MockLLMResponse(expected_llm_output)

        payload = {
            "original_markdown": markdown_input,
            "easy_read_sentences": sentences_input
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, expected_llm_output)
        mock_completion.assert_called_once()

    def test_validate_completeness_invalid_input(self):
        """Test various invalid input formats."""
        url = reverse('content_validation')
        valid_md = "Some markdown"
        valid_sentences = ["A sentence."]

        # Missing keys
        response = self.client.post(url, {"original_markdown": valid_md}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"easy_read_sentences": valid_sentences}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": 123, "easy_read_sentences": valid_sentences}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "easy_read_sentences": "not a list"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "easy_read_sentences": [1, 2, 3]}, format='json') # List of non-strings
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api.views.litellm.completion')
    def test_validate_completeness_llm_error(self, mock_completion):
        """Test handling of LLM API errors."""
        url = reverse('content_validation')
        payload = {"original_markdown": "md", "easy_read_sentences": ["s1"]}
        mock_completion.side_effect = Exception("LLM Connection Error")

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("LLM call failed" in response.data['error'])

    @patch('api.views.litellm.completion')
    def test_validate_completeness_llm_invalid_json(self, mock_completion):
        """Test handling when LLM returns non-JSON or invalid structure."""
        url = reverse('content_validation')
        payload = {"original_markdown": "md", "easy_read_sentences": ["s1"]}

        # Simulate non-JSON (remains the same)
        mock_completion.return_value = MockLLMResponse("invalid json string")
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("Failed to parse/validate LLM response" in response.data['error'])

        # Simulate JSON missing keys (UPDATED expected keys)
        mock_completion.return_value = MockLLMResponse({"is_complete": True}) # Missing info fields
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("missing expected keys" in response.data['error'])
        self.assertTrue("missing_info" in response.data['error'])

        # Simulate JSON with wrong types (UPDATED checks)
        mock_completion.return_value = MockLLMResponse({
            "is_complete": "maybe", # Not boolean
            "missing_info": "",
            "extra_info": ""
        })
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("Type error: 'is_complete' should be boolean" in response.data['error'])
        
        mock_completion.reset_mock() # Reset mock for next call
        mock_completion.return_value = MockLLMResponse({
            "is_complete": True, 
            "missing_info": ["list", "not", "string"], # Not string
            "extra_info": ""
        })
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("Type error: 'missing_info' should be a string" in response.data['error'])

    @patch('api.views.open', new_callable=unittest.mock.mock_open)
    @patch('api.views.yaml.safe_load')
    def test_validate_completeness_prompt_load_error(self, mock_safe_load, mock_open):
        """Test handling when the validation prompt YAML cannot be loaded or parsed."""
        url = reverse('content_validation')
        payload = {"original_markdown": "md", "easy_read_sentences": ["s1"]}
        
        # Simulate file not found
        mock_open.side_effect = FileNotFoundError
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Validation prompt file not found.")
        mock_open.reset_mock(side_effect=True) # Reset side effect

        # Simulate YAML error
        mock_open.side_effect = None # Reset FileNotFoundError side effect for open
        mock_safe_load.side_effect = yaml.YAMLError("Bad YAML")
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Error parsing validation prompt file.")
        mock_safe_load.reset_mock(side_effect=True)

        # Simulate missing keys in YAML
        mock_safe_load.side_effect = None
        mock_safe_load.return_value = {"llm_model": "test", "user_message_template": "test"} # Missing system_message
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Validation prompt file is incomplete.")

# --- Tests for revise_sentences endpoint ---

class ReviseSentencesTests(APITestCase):

    @patch('api.views.litellm.completion')
    def test_revise_sentences_success(self, mock_completion):
        """Test successful sentence revision call."""
        url = reverse('sentence_revision')
        markdown_input = "# Important Event\nThe event starts at 9 AM. Remember to bring your ID."
        current_sentences_input = [
            {"sentence": "There is an important event.", "image_retrieval": "important event calendar"},
            {"sentence": "The event starts in the morning.", "image_retrieval": "morning sunrise clock"} # Missing specific time and ID requirement
        ]
        validation_feedback_input = {
            "is_complete": False,
            "missing_info": "The specific start time (9 AM) and the requirement to bring an ID are missing.",
            "extra_info": ""
        }
        
        # Expected LLM output (revised sentences)
        expected_llm_output = {
            "easy_read_sentences": [
                {"sentence": "There is an important event.", "image_retrieval": "important event calendar icon"},
                {"sentence": "The event starts at 9 AM.", "image_retrieval": "clock showing 9 AM"},
                {"sentence": "You must bring your ID.", "image_retrieval": "identification card person holding ID"}
            ]
        }

        # Configure mock
        mock_completion.return_value = MockLLMResponse(expected_llm_output)

        payload = {
            "original_markdown": markdown_input,
            "current_sentences": current_sentences_input,
            "validation_feedback": validation_feedback_input
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, expected_llm_output)
        mock_completion.assert_called_once()
        # Optionally check args passed to mock_completion to verify prompt content

    def test_revise_sentences_invalid_input(self):
        """Test various invalid input formats for the revision endpoint."""
        url = reverse('sentence_revision')
        valid_md = "md"
        valid_current = [{"sentence": "s", "image_retrieval": "k"}]
        valid_feedback = {"is_complete": True, "missing_info": "", "extra_info": ""}

        # Missing keys
        response = self.client.post(url, {"current_sentences": valid_current, "validation_feedback": valid_feedback}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "validation_feedback": valid_feedback}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "current_sentences": valid_current}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid types
        response = self.client.post(url, {"original_markdown": 1, "current_sentences": valid_current, "validation_feedback": valid_feedback}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "current_sentences": "not a list", "validation_feedback": valid_feedback}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "current_sentences": [{"sentence": 1}], "validation_feedback": valid_feedback}, format='json') # Invalid item structure
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "current_sentences": valid_current, "validation_feedback": ["not", "a", "dict"]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(url, {"original_markdown": valid_md, "current_sentences": valid_current, "validation_feedback": {"is_complete": 1}}, format='json') # Invalid feedback structure/type
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api.views.litellm.completion')
    def test_revise_sentences_llm_error(self, mock_completion):
        """Test handling of LLM API errors during revision."""
        url = reverse('sentence_revision')
        payload = {
            "original_markdown": "md", 
            "current_sentences": [{"sentence": "s", "image_retrieval": "k"}], 
            "validation_feedback": {"is_complete": True, "missing_info": "", "extra_info": ""}
        }
        mock_completion.side_effect = Exception("LLM Revision Error")

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("LLM call failed during revision" in response.data['error'])

    @patch('api.views.litellm.completion')
    def test_revise_sentences_llm_invalid_json(self, mock_completion):
        """Test handling when revision LLM returns non-JSON or invalid structure."""
        url = reverse('sentence_revision')
        payload = {
            "original_markdown": "md", 
            "current_sentences": [{"sentence": "s", "image_retrieval": "k"}], 
            "validation_feedback": {"is_complete": True, "missing_info": "", "extra_info": ""}
        }

        # Simulate non-JSON
        mock_completion.return_value = MockLLMResponse("garbage string")
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("Failed to parse/validate LLM response for revision" in response.data['error'])

        # Simulate JSON missing 'easy_read_sentences' key
        mock_completion.return_value = MockLLMResponse({"some_other_key": []})
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("missing 'easy_read_sentences' key" in response.data['error'])
        
        # Simulate 'easy_read_sentences' not being a list
        mock_completion.return_value = MockLLMResponse({"easy_read_sentences": "not a list"})
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("'easy_read_sentences' should contain a list" in response.data['error'])

        # Simulate invalid item structure within the list
        mock_completion.return_value = MockLLMResponse({"easy_read_sentences": [{"sentence": 123}]}) # Missing/wrong type keys
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertTrue("Items in 'easy_read_sentences' list do not match expected structure" in response.data['error'])

    @patch('api.views.open', new_callable=unittest.mock.mock_open)
    @patch('api.views.yaml.safe_load')
    def test_revise_sentences_prompt_load_error(self, mock_safe_load, mock_open):
        """Test handling when the revision prompt YAML cannot be loaded or parsed."""
        url = reverse('sentence_revision')
        payload = {
            "original_markdown": "md", 
            "current_sentences": [{"sentence": "s", "image_retrieval": "k"}], 
            "validation_feedback": {"is_complete": True, "missing_info": "", "extra_info": ""}
        }
        
        # Simulate file not found
        mock_open.side_effect = FileNotFoundError
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Revision prompt file not found.")
        mock_open.reset_mock(side_effect=True)

        # Simulate YAML error
        mock_open.side_effect = None 
        mock_safe_load.side_effect = yaml.YAMLError("Bad Revision YAML")
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Error parsing revision prompt file.")
        mock_safe_load.reset_mock(side_effect=True)

        # Simulate missing keys in YAML
        mock_safe_load.side_effect = None
        mock_safe_load.return_value = {"llm_model": "test"} # Missing templates
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Revision prompt file is incomplete.")

# --- Tests for image_upload endpoint ---

# Mock the SentenceTransformer model and its encode method
# We need to mock it where it's loaded in views.py
# @patch('api.views.embedding_model') # REMOVED from class level
# We also need to mock ChromaDB interactions
# @patch('api.views.image_collection') # REMOVED from class level
class ImageUploadTests(APITestCase):

    def create_dummy_image(self, name="test.png", content_type="image/png", size=(10, 10)):
        """Creates an in-memory image file for testing."""
        file = BytesIO()
        # Use a simple grayscale image to avoid potential PIL format issues
        image = Image.new('L', size, color = 128) # 'L' is grayscale, 128 is mid-gray
        # Ensure saving as PNG, as CLIP might be sensitive to format details
        image.save(file, format='PNG') 
        file.name = name
        file.seek(0)
        return SimpleUploadedFile(name, file.read(), content_type='image/png') # Keep content type as png

    # Add decorators to individual tests that need both mocks
    @patch('api.views.image_collection')
    @patch('api.views.embedding_model')
    def test_image_upload_success(self, mock_embedding_model, mock_collection):
        # Note: Mocks are passed in reverse order of decoration
        """Test successful image upload, embedding, and storage."""
        url = reverse('image_upload')
        image_file = self.create_dummy_image()
        description = "Test image description"
        
        # Configure mock embedding model
        mock_embedding = np.array([0.1, 0.2, 0.3])
        mock_embedding_model.encode.return_value = [mock_embedding]
        
        # Configure mock ChromaDB collection
        mock_collection.get.return_value = {'ids': []} # Simulate image not existing

        response = self.client.post(url, {'image': image_file, 'description': description}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['description'], description)
        self.assertTrue(response.data['embedding_generated'])
        self.assertTrue(response.data['embedding_stored'])
        image_path = response.data['image_path']
        self.assertTrue(image_path.startswith('uploaded_images/test_'))
        self.assertTrue(image_path.endswith('.png'))

        # Check that embedding model was called with the file path string
        mock_embedding_model.encode.assert_called_once()
        call_args, _ = mock_embedding_model.encode.call_args
        # self.assertIsInstance(call_args[0][0], Image.Image) # Old assertion
        self.assertIsInstance(call_args[0][0], str) # Check it was called with a string
        self.assertTrue(call_args[0][0].endswith('.png')) # Check the string looks like the path

        # Check that ChromaDB add was called correctly
        mock_collection.add.assert_called_once()
        add_args, add_kwargs = mock_collection.add.call_args
        self.assertEqual(add_kwargs['ids'], [response.data['image_path']])
        self.assertEqual(add_kwargs['embeddings'], [mock_embedding.tolist()])
        self.assertEqual(add_kwargs['metadatas'], [{'image_path': response.data['image_path'], 'description': description}])

    @patch('api.views.image_collection')
    @patch('api.views.embedding_model')
    def test_image_upload_no_description(self, mock_embedding_model, mock_collection):
        """Test upload without an optional description."""
        url = reverse('image_upload')
        image_file = self.create_dummy_image()
        mock_embedding = np.array([0.4, 0.5, 0.6])
        mock_embedding_model.encode.return_value = [mock_embedding]
        mock_collection.get.return_value = {'ids': []}

        response = self.client.post(url, {'image': image_file}, format='multipart') # No description

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['description'], '') # Default empty string
        self.assertTrue(response.data['embedding_generated'])
        self.assertTrue(response.data['embedding_stored'])
        mock_collection.add.assert_called_once()
        _, add_kwargs = mock_collection.add.call_args
        self.assertEqual(add_kwargs['metadatas'][0]['description'], '')

    @patch('api.views.image_collection')
    @patch('api.views.embedding_model')
    def test_image_upload_existing_update(self, mock_embedding_model, mock_collection):
        """Test updating an existing image entry in ChromaDB."""
        url = reverse('image_upload')
        image_file = self.create_dummy_image(name="existing.png")
        description = "Updated description"
        mock_embedding = np.array([0.7, 0.8, 0.9])
        mock_embedding_model.encode.return_value = [mock_embedding]
        
        # Simulate the image already existing in ChromaDB
        existing_id = 'uploaded_images/existing.png' 
        mock_collection.get.return_value = {'ids': [existing_id]}

        response = self.client.post(url, {'image': image_file, 'description': description}, format='multipart')

        # It should still succeed, but use update instead of add
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_collection.add.assert_not_called() # Should not call add
        mock_collection.update.assert_called_once()
        _, update_kwargs = mock_collection.update.call_args
        self.assertEqual(update_kwargs['ids'], [response.data['image_path']]) # ID might have UUID suffix now
        self.assertEqual(update_kwargs['embeddings'], [mock_embedding.tolist()])
        self.assertEqual(update_kwargs['metadatas'], [{'image_path': response.data['image_path'], 'description': description}])
        
    @patch('api.views.image_collection') 
    @patch('api.views.embedding_model') 
    def test_image_upload_no_file(self, mock_embedding_model, mock_collection):
        """Test request without image file."""
        url = reverse('image_upload')
        response = self.client.post(url, {'description': 'test'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No image file provided', response.data['error'])

    @patch('api.views.image_collection')
    @patch('api.views.embedding_model') 
    def test_image_upload_invalid_type(self, mock_embedding_model, mock_collection):
        """Test uploading a non-image file."""
        url = reverse('image_upload')
        # Create a non-image file
        txt_file = SimpleUploadedFile("test.txt", b"not an image", content_type="text/plain")
        response = self.client.post(url, {'image': txt_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid file type', response.data['error'])

    @patch('api.views.image_collection')
    @patch('api.views.embedding_model')
    def test_image_upload_embedding_model_failure(self, mock_embedding_model, mock_collection):
        """Test failure during embedding generation."""
        url = reverse('image_upload')
        image_file = self.create_dummy_image()
        mock_embedding_model.encode.side_effect = Exception("Embedding failed")
        mock_collection.get.return_value = {'ids': []}

        response = self.client.post(url, {'image': image_file}, format='multipart')

        # Should still succeed in saving image, but report embedding failure
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['embedding_generated'])
        self.assertFalse(response.data['embedding_stored'])
        mock_collection.add.assert_not_called() # Embedding failed, so add shouldn't be called

    @patch('api.views.image_collection')
    @patch('api.views.embedding_model')
    def test_image_upload_chroma_failure(self, mock_embedding_model, mock_collection):
        """Test failure during ChromaDB storage."""
        url = reverse('image_upload')
        image_file = self.create_dummy_image()
        mock_embedding = np.array([0.1, 0.2, 0.3])
        mock_embedding_model.encode.return_value = [mock_embedding]
        mock_collection.get.return_value = {'ids': []}
        mock_collection.add.side_effect = Exception("ChromaDB error")

        response = self.client.post(url, {'image': image_file}, format='multipart')

        # Should succeed in saving image and generating embedding, but report store failure
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['embedding_generated'])
        self.assertFalse(response.data['embedding_stored'])
        mock_collection.add.assert_called_once() # Add was attempted

    # New test using the real embedding model (only mocking ChromaDB)
    @patch('api.views.image_collection') # Only apply collection mock
    def test_image_upload_with_real_embedding_model(self, mock_collection):
        # Now the signature only expects mock_collection
        """Test image upload using the actual Sentence Transformer model (mocking DB)."""
        # Skip this test if the model wasn't loaded (e.g., in CI without model download)
        # Dynamically import views inside test to check model after patching
        from api import views as api_views_module
        if not api_views_module.embedding_model:
             self.skipTest("Sentence Transformer model not loaded, skipping real model test.")
             
        url = reverse('image_upload')
        image_file = self.create_dummy_image()
        description = "Real model test"

        # Configure mock ChromaDB collection
        mock_collection.get.return_value = {'ids': []} # Simulate image not existing

        response = self.client.post(url, {'image': image_file, 'description': description}, format='multipart')

        # Check that the request succeeded and embedding was reported as generated
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['embedding_generated'], "Embedding should have been generated by the real model")
        self.assertTrue(response.data['embedding_stored'], "Mocked DB storing should be considered successful") # Since add will be called

        # Verify ChromaDB add was called (meaning embedding likely succeeded)
        mock_collection.add.assert_called_once()
        _, add_kwargs = mock_collection.add.call_args
        # Check the structure of the saved data
        self.assertIn('ids', add_kwargs)
        self.assertIn('embeddings', add_kwargs)
        self.assertIn('metadatas', add_kwargs)
        self.assertEqual(len(add_kwargs['embeddings']), 1) 
        # Check embedding dimensionality (512 for clip-ViT-B-32-multilingual-v1)
        self.assertEqual(len(add_kwargs['embeddings'][0]), 512) 

# --- Tests for find_similar_images endpoint ---

# @patch('api.views.embedding_model') # REMOVED from class level
# @patch('api.views.image_collection') # REMOVED from class level
class FindSimilarImagesTests(APITestCase):

    @patch('api.views.image_collection') # Add decorator
    @patch('api.views.embedding_model') # Add decorator
    def test_find_similar_images_success(self, mock_embedding_model, mock_collection):
        """Test successful similarity search."""
        url = reverse('find_similar_images')
        query_text = "a green snake"
        n_results = 2
        
        # Configure mock embedding model for the text query
        mock_query_embedding = np.array([0.9, 0.8, 0.7])
        mock_embedding_model.encode.return_value = [mock_query_embedding]
        
        # Configure mock ChromaDB query results
        mock_chroma_results = {
            'ids': [['img/snake1.png', 'img/snake2.jpg']],
            'distances': [[0.1, 0.5]],
            'metadatas': [[{'image_path': 'img/snake1.png', 'description': 'Snake'}, {'image_path': 'img/snake2.jpg', 'description': 'Another snake'}]]
        }
        mock_collection.query.return_value = mock_chroma_results

        response = self.client.post(url, {'query': query_text, 'n_results': n_results}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), n_results)

        # Check structure of first result
        first_result = response.data['results'][0]
        self.assertEqual(first_result['id'], mock_chroma_results['ids'][0][0])
        self.assertEqual(first_result['image_path'], mock_chroma_results['metadatas'][0][0]['image_path'])
        self.assertEqual(first_result['description'], mock_chroma_results['metadatas'][0][0]['description'])
        self.assertEqual(first_result['distance'], mock_chroma_results['distances'][0][0])

        # Verify embedding model call
        mock_embedding_model.encode.assert_called_once_with([query_text])

        # Verify ChromaDB query call
        mock_collection.query.assert_called_once()
        _, query_kwargs = mock_collection.query.call_args
        self.assertEqual(query_kwargs['query_embeddings'], [mock_query_embedding.tolist()])
        self.assertEqual(query_kwargs['n_results'], n_results)
        self.assertEqual(query_kwargs['include'], ['metadatas', 'distances'])

    @patch('api.views.image_collection') # Add decorator
    @patch('api.views.embedding_model') # Add decorator
    def test_find_similar_images_no_query(self, mock_embedding_model, mock_collection):
        """Test request without query."""
        url = reverse('find_similar_images')
        response = self.client.post(url, {'n_results': 3}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing or invalid \'query\'', response.data['error'])

    @patch('api.views.image_collection') # Add decorator
    @patch('api.views.embedding_model') # Add decorator
    def test_find_similar_images_invalid_n(self, mock_embedding_model, mock_collection):
        """Test request with invalid n_results."""
        url = reverse('find_similar_images')
        response = self.client.post(url, {'query': 'test', 'n_results': 'abc'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid \'n_results\'', response.data['error'])

        response = self.client.post(url, {'query': 'test', 'n_results': 0}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid \'n_results\'', response.data['error'])
        
    @patch('api.views.image_collection') # Add decorator
    @patch('api.views.embedding_model') # Add decorator
    def test_find_similar_images_no_results(self, mock_embedding_model, mock_collection):
        """Test scenario where ChromaDB returns no results."""
        url = reverse('find_similar_images')
        mock_query_embedding = np.array([0.1, 0.1, 0.1])
        mock_embedding_model.encode.return_value = [mock_query_embedding]
        mock_collection.query.return_value = {'ids': [[]], 'distances': [[]], 'metadatas': [[]]} # Empty results

        response = self.client.post(url, {'query': 'unlikely query', 'n_results': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], []) # Expect empty list

    @patch('api.views.image_collection') # Add decorator
    @patch('api.views.embedding_model') # Add decorator
    def test_find_similar_images_embedding_failure(self, mock_embedding_model, mock_collection):
        """Test failure during query embedding."""
        url = reverse('find_similar_images')
        mock_embedding_model.encode.side_effect = Exception("Embedding failed")

        response = self.client.post(url, {'query': 'test', 'n_results': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error occurred while processing the query', response.data['error'])

    @patch('api.views.image_collection') # Add decorator
    @patch('api.views.embedding_model') # Add decorator
    def test_find_similar_images_chroma_failure(self, mock_embedding_model, mock_collection):
        """Test failure during ChromaDB query."""
        url = reverse('find_similar_images')
        mock_query_embedding = np.array([0.2, 0.2, 0.2])
        mock_embedding_model.encode.return_value = [mock_query_embedding]
        mock_collection.query.side_effect = Exception("ChromaDB query failed")

        response = self.client.post(url, {'query': 'test', 'n_results': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Failed to query the image database', response.data['error'])

# --- Tests for save_processed_content endpoint ---

class SaveContentTests(APITestCase):

    def test_save_content_success(self):
        """
        Test successful saving of processed content.
        """
        url = reverse('save_content')
        data = {
            "original_markdown": "# Title\nOriginal text.",
            "easy_read_json": [
                {"sentence": "Simple title.", "image_retrieval": "title", "selected_image_path": "img/a.png"},
                {"sentence": "Simple text.", "image_retrieval": "text", "selected_image_path": None}
            ]
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['message'], "Content saved successfully.")
        self.assertIn('id', response.data)
        
        # Verify data in database
        content_id = response.data['id']
        saved_content = ProcessedContent.objects.get(id=content_id)
        self.assertEqual(saved_content.original_markdown, data["original_markdown"])
        self.assertEqual(saved_content.easy_read_json, data["easy_read_json"])

    def test_save_content_invalid_input(self):
        """
        Test saving with missing or invalid input.
        """
        url = reverse('save_content')
        
        # Missing markdown
        response = self.client.post(url, {"easy_read_json": []}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing or invalid \'original_markdown\'', response.data['error'])

        # Missing easy_read_json
        response = self.client.post(url, {"original_markdown": "test"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing or invalid \'easy_read_json\'', response.data['error'])

        # Invalid easy_read_json (not a list)
        response = self.client.post(url, {"original_markdown": "test", "easy_read_json": {"key": "val"}}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Missing or invalid \'easy_read_json\'', response.data['error'])
