# Experiments Folder

This folder contains experimental scripts and test utilities for the EasyRead project.

## PDF Converter Service Test

### Files

- `create_test_pdf.py` - Creates a simple test PDF document
- `test_pdf_converter.py` - Tests the external PDF Converter Service API
- `README.md` - This file

### Setup

1. **Install required packages:**
   ```bash
   pip install requests reportlab python-dotenv
   ```

2. **Configure environment variables:**

   Edit the `.env` file in the `experiments/` folder:
   ```bash
   VITE_API_URL="https://your-api-url.com"
   PDF_CONVERTER_API_KEY="your-api-key"
   PDF_CONVERTER_TOKEN="your-auth-token"
   PDF_CONVERTER_EMAIL="your@email.com"
   ```

3. **Create a test PDF (already done):**
   ```bash
   cd experiments
   python create_test_pdf.py
   ```

4. **Run the PDF converter test:**
   ```bash
   python test_pdf_converter.py
   ```

### What the Test Does

The `test_pdf_converter.py` script:

1. ✅ Requests a presigned S3 URL for file upload
2. ✅ Uploads the test PDF to S3
3. ✅ Submits a conversion request (PDF → Markdown)
4. ✅ Polls the API to check conversion status
5. ✅ Downloads the converted markdown file
6. ✅ Displays a preview of the result

### API Endpoints Used

- `?action=get-presigned-url` - Get S3 upload URL
- `?action=upload-config` - Submit conversion request
- `?action=load-config` - Check conversion status
- `?action=get-download-urls` - Get download URL for result

### Output

After successful conversion, you'll get:
- `test_document.md` - The converted markdown file
- Console output showing each step of the process

### Requirements

```bash
# Python packages needed
pip install requests reportlab python-dotenv
```

The script will automatically load configuration from the `.env` file in the experiments folder.

### Troubleshooting

**"Test PDF not found"**
- Run `create_test_pdf.py` first to generate the test PDF

**"API_BASE_URL not configured"**
- Set the `VITE_API_URL` environment variable
- Or edit the `API_BASE_URL` variable in the script

**"HTTP 401 Unauthorized"**
- Check your API key and auth token
- Ensure they are valid and not expired

**"Conversion timeout"**
- The conversion may take longer than expected
- Increase `max_attempts` in the script
- Check the API service status
