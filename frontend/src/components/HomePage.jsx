import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Typography,
  Container,
  TextField,
  Button,
  CircularProgress,
  Paper,
  Checkbox,
  FormControlLabel,
  Card,
  CardMedia,
  Grid,
  Divider,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { extractMarkdown, generateEasyRead, getImageSets, listImages } from '../apiClient';
import { config } from '../config.js';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = config.MEDIA_BASE_URL;

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
  setCurrentProcessingStep,
  setError, 
  currentMarkdown,
  onProcessingComplete
}) {
  const [fileName, setFileName] = useState('');
  const [imageSets, setImageSets] = useState([]);
  const [selectedSets, setSelectedSets] = useState(new Set());
  const [setsLoading, setSetsLoading] = useState(false);
  const [preventDuplicateImages, setPreventDuplicateImages] = useState(true);

  // Load image sets and sample images on component mount
  useEffect(() => {
    const loadImageSets = async () => {
      setSetsLoading(true);
      try {
        const response = await listImages();
        const imagesBySet = response.data.images_by_set || {};
        
        // Convert to array with random sample images
        const setsArray = Object.keys(imagesBySet).map(setName => {
          const images = imagesBySet[setName];
          // Get 3 random images from the set
          const shuffled = [...images].sort(() => 0.5 - Math.random());
          const sampleImages = shuffled.slice(0, 3);
          
          return {
            name: setName,
            imageCount: images.length,
            sampleImages
          };
        });

        setImageSets(setsArray);
        // Select all sets by default
        setSelectedSets(new Set(setsArray.map(set => set.name)));
      } catch (error) {
        console.error('Error loading image sets:', error);
        setError('Failed to load image sets');
      } finally {
        setSetsLoading(false);
      }
    };

    loadImageSets();
  }, [setError]);

  const handleSetSelection = (setName) => {
    const newSelectedSets = new Set(selectedSets);
    if (newSelectedSets.has(setName)) {
      newSelectedSets.delete(setName);
    } else {
      newSelectedSets.add(setName);
    }
    setSelectedSets(newSelectedSets);
  };

  const handleSelectAll = () => {
    setSelectedSets(new Set(imageSets.map(set => set.name)));
  };

  const handleSelectNone = () => {
    setSelectedSets(new Set());
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file && file.type === 'application/pdf') {
      setFileName(file.name);
      handlePdfUpload(file);
    } else {
      setError('Please select a valid PDF file.');
      setFileName('');
    }
  };

  const handlePdfUpload = useCallback(async (file) => {
    setIsLoading(true);
    setError(null);
    setTotalPages(0); // Reset progress
    setPagesProcessed(0); // Reset progress
    try {
      const response = await extractMarkdown(file);
      // Assuming backend returns { pages: ["page1", "page2", ...] }
      console.log("Received response from /pdf-to-markdown/:", response); // Log successful response
      const pageBreak = "\n\n---PAGE_BREAK---\n\n";
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
  }, [setIsLoading, setError, setTotalPages, setPagesProcessed, setMarkdownContent]);

  const handleDrop = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    const file = event.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      setFileName(file.name);
      handlePdfUpload(file);
    } else {
      setError('Please drop a valid PDF file.');
      setFileName('');
    }
  }, [setError, handlePdfUpload]);

  const handleDragOver = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);


  const handleMarkdownChange = (event) => {
    setMarkdownContent(event.target.value);
    setFileName('');
    setTotalPages(0); // Reset progress
    setPagesProcessed(0); // Reset progress
  };

  const handleProcessContent = async () => {
     if (!currentMarkdown || currentMarkdown.trim() === '') {
      setError('No content to process. Please upload a PDF or enter text.');
      return;
    }
    
    // Allow processing without images - in this case, no images will be retrieved/displayed
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
    let capturedSelectedSets = Array.from(selectedSets); // Capture selected sets for image retrieval
    let capturedPreventDuplicates = preventDuplicateImages; // Capture duplicate prevention setting

    try {
        const pageBreak = "\n\n---PAGE_BREAK---\n\n";
        const markdownPages = currentMarkdown.split(pageBreak).filter(page => page.trim() !== ''); // Filter empty pages
        console.log(`Total pages: ${markdownPages.length}`);
        setTotalPages(markdownPages.length); // Set total pages

        for (let i = 0; i < markdownPages.length; i++) {
            const page = markdownPages[i];
            // No need to check for empty page again due to filter
            console.log(`Processing page ${i+1} of ${markdownPages.length}`);
            
            // Progress callback for enhanced steps
            const onProgress = (step) => {
              console.log(`Page ${i+1}: ${step}`);
              setCurrentProcessingStep(step);
              
              // Calculate sub-step progress within this page
              let stepProgress = 0;
              if (step.includes("Converting")) stepProgress = 0.25; // 25% of page
              else if (step.includes("Validating")) stepProgress = 0.50; // 50% of page  
              else if (step.includes("Revising")) stepProgress = 0.75; // 75% of page
              
              // Calculate total progress including sub-steps
              // For single page: i=0, so progress goes 0.25 → 0.50 → 0.75 → 1.0
              // For multi-page: distributed across all pages
              const totalProgress = i + stepProgress;
              setPagesProcessed(Math.min(totalProgress, markdownPages.length));
            };
            
            try {
              const response = await generateEasyRead(page, Array.from(selectedSets), onProgress);
              
              // Check response structure
              if (response.data && typeof response.data === 'object' && response.data.easy_read_sentences) {
                  // Capture title from the first page's response
                  if (firstPage && response.data.title) {
                    finalTitle = response.data.title;
                    firstPage = false; // Only capture title once
                  }
                  
                  // Accumulate sentences only if there are any
                  if (response.data.easy_read_sentences.length > 0) {
                    allEasyReadSentences.push(...response.data.easy_read_sentences); 
                  } else {
                    console.info(`Page ${i+1} had no meaningful content to process - skipping`);
                  }
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
          easy_read_sentences: allEasyReadSentences,
          selected_sets: capturedSelectedSets,
          prevent_duplicate_images: capturedPreventDuplicates
        };

        // Clear processing step and call completion callback
        setCurrentProcessingStep('');
        onProcessingComplete(currentMarkdown, finalResult);

    } catch (err) { // Catch errors before the loop starts (e.g., splitting markdown) 
      console.error("Error during Easy Read preparation:", err);
      setError(err.response?.data?.error || 'Failed to start Easy Read generation.');
      // Clear state if setup fails
       setTotalPages(0);
       setPagesProcessed(0);
       setCurrentProcessingStep('');
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

        {/* Symbol Sets Selection Section */}
        <Box sx={{ mt: 4, mb: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Select Symbol Sets for Image Matching
            </Typography>
            {!setsLoading && imageSets.length > 0 && (
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button 
                  variant="outlined" 
                  size="small" 
                  onClick={handleSelectAll}
                  disabled={selectedSets.size === imageSets.length}
                >
                  Select All
                </Button>
                <Button 
                  variant="outlined" 
                  size="small" 
                  onClick={handleSelectNone}
                  disabled={selectedSets.size === 0}
                >
                  Select None
                </Button>
              </Box>
            )}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Choose which symbol sets will be used to find relevant images for your content. If no sets are selected, content will be processed without images.
          </Typography>
          
          {setsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Grid container spacing={2}>
              {imageSets.map((set) => (
                <Grid item xs={12} sm={6} md={4} key={set.name}>
                  <Box
                    sx={{
                      p: 2,
                      border: selectedSets.has(set.name) ? '3px solid #1976d2' : '2px solid #e0e0e0',
                      borderRadius: 2,
                      backgroundColor: selectedSets.has(set.name) ? '#f3f7ff' : 'white',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      textAlign: 'center',
                      '&:hover': {
                        backgroundColor: selectedSets.has(set.name) ? '#e8f2ff' : '#f9f9f9',
                        transform: 'translateY(-2px)',
                        boxShadow: 2
                      }
                    }}
                    onClick={() => handleSetSelection(set.name)}
                  >
                    {/* Sample Images in a 3-image grid */}
                    <Box sx={{ 
                      display: 'grid', 
                      gridTemplateColumns: 'repeat(3, 1fr)', 
                      gap: 1, 
                      mb: 2,
                      minHeight: 60
                    }}>
                      {set.sampleImages.map((image, index) => (
                        <Box
                          key={image.id || index}
                          sx={{
                            width: '100%',
                            height: 60,
                            border: '1px solid #e0e0e0',
                            borderRadius: 1,
                            overflow: 'hidden',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            backgroundColor: '#fafafa'
                          }}
                        >
                          <CardMedia
                            component="img"
                            height="60"
                            image={(image.image_url && (image.image_url.startsWith('http://') || image.image_url.startsWith('https://')))
                              ? image.image_url
                              : (image.image_url ? `${MEDIA_BASE_URL}${image.image_url.startsWith('/') ? '' : '/'}${image.image_url}` : 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><rect width="60" height="60" fill="%23f0f0f0"/><text x="30" y="35" text-anchor="middle" fill="%23666" font-family="Arial" font-size="10">No Image</text></svg>')}
                            alt={image.description || 'Sample image'}
                            sx={{ 
                              objectFit: 'contain',
                              maxWidth: '100%',
                              maxHeight: '100%'
                            }}
                            onError={(e) => { 
                              // Prevent infinite loop by hiding the image instead of loading another URL
                              e.target.style.display = 'none';
                            }}
                          />
                        </Box>
                      ))}
                    </Box>
                    
                    {/* Set Name and Count */}
                    <Typography 
                      variant="subtitle2" 
                      sx={{ 
                        fontWeight: selectedSets.has(set.name) ? 600 : 500,
                        color: selectedSets.has(set.name) ? '#1976d2' : 'text.primary',
                        fontSize: '0.9rem'
                      }}
                    >
                      {set.name}
                    </Typography>
                    <Typography 
                      variant="caption" 
                      color="text.secondary"
                      sx={{ display: 'block', mt: 0.5 }}
                    >
                      {set.imageCount} images
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          )}
          
          <Box sx={{ mt: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Selected: {selectedSets.size} of {imageSets.length} sets
            </Typography>
          </Box>
          
          {/* Duplicate Prevention Setting */}
          <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={preventDuplicateImages}
                  onChange={(e) => setPreventDuplicateImages(e.target.checked)}
                  color="primary"
                />
              }
              label={
                <Box>
                  <Typography variant="body2" component="span">
                    Avoid duplicate images
                  </Typography>
                  <Typography variant="caption" display="block" color="text.secondary">
                    Try to avoid using the same image for different sentences
                  </Typography>
                </Box>
              }
            />
          </Box>
        </Box>

        <Divider sx={{ my: 3 }} />

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
            Process Content{selectedSets.size > 0 ? ` (${selectedSets.size} image sets selected)` : ' (no images)'}
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}

export default HomePage; 