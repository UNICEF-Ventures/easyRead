import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Container,
  TextField,
  Button,
  CircularProgress,
  Paper,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { extractMarkdown, generateEasyRead } from '../apiClient';

// Styled component for the drop zone
const DropZone = styled(Box)(({ theme }) => ({
  border: `2px dashed ${theme.palette.primary.main}`,
  borderRadius: theme.shape.borderRadius * 2,
  padding: theme.spacing(5),
  textAlign: 'center',
  cursor: 'pointer',
  backgroundColor: 'rgba(66, 133, 244, 0.04)',
  transition: 'all 0.3s ease',
  '&:hover': {
    backgroundColor: 'rgba(66, 133, 244, 0.08)',
    borderColor: theme.palette.primary.dark,
    transform: 'translateY(-2px)',
  },
  marginBottom: theme.spacing(3),
}));

function HomePage({ 
  setMarkdownContent, 
  setIsLoading, 
  setIsProcessingPages,
  setTotalPages,
  setPagesProcessed,
  setError, 
  currentMarkdown,
  onProcessingComplete
}) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileName, setFileName] = useState('');

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file);
      setFileName(file.name);
      handlePdfUpload(file);
    } else {
      setError('Please select a valid PDF file.');
      setSelectedFile(null);
      setFileName('');
    }
  };

  const handleDrop = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    const file = event.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file);
      setFileName(file.name);
      handlePdfUpload(file);
    } else {
      setError('Please drop a valid PDF file.');
      setSelectedFile(null);
      setFileName('');
    }
  }, []); // Dependencies need to be checked/added if needed

  const handleDragOver = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);

  const handlePdfUpload = async (file) => {
    setIsLoading(true);
    setError(null);
    setTotalPages(0); // Reset progress
    setPagesProcessed(0); // Reset progress
    try {
      const response = await extractMarkdown(file);
      // Assuming backend returns { pages: ["page1", "page2", ...] }
      console.log("Received response from /markdown-extraction/:", response); // Log successful response
      const pageBreak = "\n\n---DOCLING_PAGE_BREAK---\n\n";
      const fullMarkdown = response.data.pages.join(pageBreak);
      setMarkdownContent(fullMarkdown);
    } catch (err) {
      // --- DETAILED LOGGING --- 
      console.error("Detailed error in handlePdfUpload:", err);
      if (err.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        console.error("Error Response Data:", err.response.data);
        console.error("Error Response Status:", err.response.status);
        console.error("Error Response Headers:", err.response.headers);
        setError(err.response?.data?.error || `Server responded with status ${err.response.status}`);
      } else if (err.request) {
        // The request was made but no response was received
        // `err.request` is an instance of XMLHttpRequest in the browser and an instance of
        // http.ClientRequest in node.js
        console.error("Error Request:", err.request);
        setError('No response received from server. Check network or server status.');
      } else {
        // Something happened in setting up the request that triggered an Error
        console.error('Error Message:', err.message);
        setError(err.message || 'An unexpected error occurred during PDF processing.');
      }
      console.error("Error Config:", err.config); // Log Axios config used
      // --- END DETAILED LOGGING ---
      setMarkdownContent(''); // Clear on error
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkdownChange = (event) => {
    setMarkdownContent(event.target.value);
    setSelectedFile(null);
    setFileName('');
    setTotalPages(0); // Reset progress
    setPagesProcessed(0); // Reset progress
  };

  const handleProcessContent = async () => {
     if (!currentMarkdown || currentMarkdown.trim() === '') {
      setError('No content to process. Please upload a PDF or enter text.');
      return;
    }
    // Make sure loading indicator from PDF extraction is off
    setIsLoading(false);
    
    // Use the new state for page processing
    console.log('Setting isProcessingPages to true');
    setIsProcessingPages(true); // Start page processing indicator
    setError(null);
    setTotalPages(0); // Reset progress
    setPagesProcessed(0); // Reset progress

    let processingError = null; // Track errors during page processing
    let allEasyReadSentences = [];
    let finalTitle = 'Untitled'; // Initialize title
    let firstPage = true; // Flag to capture title from the first page

    try {
        const pageBreak = "\n\n---DOCLING_PAGE_BREAK---\n\n";
        const markdownPages = currentMarkdown.split(pageBreak).filter(page => page.trim() !== ''); // Filter empty pages
        console.log(`Total pages: ${markdownPages.length}`);
        setTotalPages(markdownPages.length); // Set total pages

        for (let i = 0; i < markdownPages.length; i++) {
            const page = markdownPages[i];
            // No need to check for empty page again due to filter
            console.log(`Processing page ${i+1} of ${markdownPages.length}`);
            try {
              const response = await generateEasyRead(page);
              
              // Check response structure
              if (response.data && typeof response.data === 'object' && response.data.easy_read_sentences) {
                  // Capture title from the first page's response
                  if (firstPage && response.data.title) {
                    finalTitle = response.data.title;
                    firstPage = false; // Only capture title once
                  }
                  
                  // Accumulate sentences
                  allEasyReadSentences.push(...response.data.easy_read_sentences); 
              } else { // Handle page-specific error or invalid format
                  console.warn("Invalid or missing easy_read_sentences for page:", response.data);
                   allEasyReadSentences.push({
                      sentence: `Error processing content on this page.`, 
                      image_retrieval: 'error'
                  });
                  if (!processingError) processingError = 'Some pages failed to process correctly.'; // Set a general error
              }
            } catch(pageErr) {
               console.error(`Error processing page ${i+1}:`, pageErr);
               allEasyReadSentences.push({
                  sentence: `Error processing content on this page.`, 
                  image_retrieval: 'error'
               });
               if (!processingError) processingError = 'Error during page processing.';
            }
            // Update progress
            setPagesProcessed(i+1);
        }

        // If there was an error during page processing, set it now
        if (processingError) {
           setError(processingError);
        }
        
        // Prepare the final structured result for the callback
        const finalResult = {
          title: finalTitle,
          easy_read_sentences: allEasyReadSentences
        };

        // Call the completion callback with the final structured result
        onProcessingComplete(currentMarkdown, finalResult);

    } catch (err) { // Catch errors before the loop starts (e.g., splitting markdown) 
      console.error("Error during Easy Read preparation:", err);
      setError(err.response?.data?.error || 'Failed to start Easy Read generation.');
      // Clear state if setup fails
       setTotalPages(0);
       setPagesProcessed(0);
       setIsProcessingPages(false); // Explicitly turn off if setup fails
    } 
    // No finally block needed here, navigation happens via callback
  };

  return (
    <Container maxWidth="md" sx={{ mt: 5, mb: 8 }}>
      <Paper elevation={3} sx={{ 
        p: 4, 
        mb: 4, 
        borderRadius: 'var(--border-radius-md)',
        boxShadow: '0 6px 18px rgba(0, 0, 0, 0.06)',
      }}>
        <Typography variant="h4" gutterBottom sx={{ 
          color: 'var(--color-primary)', 
          fontWeight: 600,
          mb: 3
        }}>
          Create Easy Read Content
        </Typography>
        
        <Typography variant="body1" sx={{ 
          mb: 4, 
          color: 'var(--medium-gray)', 
          maxWidth: '700px',
        }}>
          Upload a PDF document or paste text to generate accessible Easy Read content with appropriate images.
        </Typography>
        
        {/* File Upload Section */}
        <DropZone 
          onDrop={handleDrop} 
          onDragOver={handleDragOver}
          onClick={() => document.getElementById('pdf-upload-input').click()}
        >
          <input
            type="file"
            id="pdf-upload-input"
            hidden
            accept="application/pdf"
            onChange={handleFileChange}
          />
          <CloudUploadIcon sx={{ fontSize: 60, color: 'var(--color-primary)', mb: 2 }} />
          <Typography variant="h6" sx={{ fontWeight: 500, mb: 1 }}>
            Drag & drop a PDF here
          </Typography>
          <Typography variant="body2" sx={{ color: 'var(--medium-gray)' }}>
            or click to select a file
          </Typography>
          {fileName && (
            <Box sx={{ 
              mt: 2, 
              p: 1, 
              bgcolor: 'rgba(15, 157, 88, 0.1)', 
              borderRadius: 'var(--border-radius-sm)',
              display: 'inline-block'
            }}>
              <Typography sx={{ color: 'var(--color-accent)', fontWeight: 500 }}>
                Selected: {fileName}
              </Typography>
            </Box>
          )}
        </DropZone>

        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          my: 3 
        }}>
          <Box sx={{ 
            height: '1px', 
            bgcolor: 'var(--lighter-gray)', 
            width: '100px', 
            mr: 2 
          }} />
          <Typography sx={{ 
            color: 'var(--medium-gray)', 
            fontWeight: 500, 
            fontSize: '0.9rem',
            textTransform: 'uppercase',
            letterSpacing: '1px'
          }}>
            OR
          </Typography>
          <Box sx={{ 
            height: '1px', 
            bgcolor: 'var(--lighter-gray)', 
            width: '100px', 
            ml: 2 
          }} />
        </Box>

        {/* Text Area Section */}
        <Typography variant="h6" sx={{ mb: 2, color: 'var(--dark-gray)' }}>
          Paste or Edit Text
        </Typography>
        <TextField
          label="Content Markdown"
          multiline
          rows={12}
          fullWidth
          variant="outlined"
          value={currentMarkdown}
          onChange={handleMarkdownChange}
          sx={{ 
            backgroundColor: 'white',
            '& .MuiOutlinedInput-root': {
              '&.Mui-focused fieldset': {
                borderColor: 'var(--color-primary)',
                borderWidth: '2px'
              }
            }
          }}
        />

        <Box sx={{ mt: 4, textAlign: 'center' }}>
          <Button
            variant="contained"
            size="large"
            onClick={handleProcessContent}
            disabled={!currentMarkdown || currentMarkdown.trim() === ''}
            sx={{ 
              px: 4, 
              py: 1.5,
              borderRadius: 'var(--border-radius-md)',
              backgroundColor: 'var(--color-accent)',
              fontWeight: 500,
              '&:hover': {
                backgroundColor: '#0b8043',
                transform: 'translateY(-2px)',
                boxShadow: '0 4px 12px rgba(15, 157, 88, 0.2)'
              },
              transition: 'all 0.2s ease'
            }}
          >
            Process Content
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}

export default HomePage; 