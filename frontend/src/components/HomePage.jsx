import React, { useState, useCallback, useEffect } from 'react';
import { GLOBALSYMBOLS_URL } from '../constants';
import { useNavigate } from 'react-router-dom';
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
import BookmarkIcon from '@mui/icons-material/Bookmark';
import { extractMarkdown, generateEasyRead, getImageSets, listImages } from '../apiClient';
import { config } from '../config.js';
import LoadingOverlay from './LoadingOverlay';

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
  onProcessingComplete,
  // PDF converter credentials (can be passed from parent/platform or use env vars)
  // Prop names match new-frontend for consistency
  token,
  apiKey,
  email,
}) {
  const [fileName, setFileName] = useState('');
  const [imageSets, setImageSets] = useState([]);
  const [selectedSets, setSelectedSets] = useState(new Set());
  const [setsLoading, setSetsLoading] = useState(false);
  const [preventDuplicateImages, setPreventDuplicateImages] = useState(true);
  const [conversionProgress, setConversionProgress] = useState('');
  const [showConversionOverlay, setShowConversionOverlay] = useState(false);

  const navigate = useNavigate();

  // Get PDF converter credentials (props take precedence over env vars)
  const getCredentials = useCallback(() => ({
    token: token,
    apiKey: apiKey,
    email: email,
  }), [token, apiKey, email]);

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
    setShowConversionOverlay(true);
    setError(null);
    setTotalPages(0); // Reset progress
    setPagesProcessed(0); // Reset progress
    setConversionProgress('Starting PDF conversion...');

    try {
      // Get credentials (from props or env vars)
      const credentials = getCredentials();

      // Check if using external converter (normalize to handle different values)
      const envValue = import.meta.env.VITE_USE_EXTERNAL_PDF_CONVERTER;
      const useExternal = envValue && ['true', '1', 'yes'].includes(String(envValue).toLowerCase().trim());

      // Validate credentials only if using external service
      if (useExternal && (!credentials.token || !credentials.email)) {
        throw new Error('External PDF converter credentials not configured. Please check your environment variables or provide credentials via props.');
      }

      // Progress callback for PDF converter
      const onProgress = (message) => {
        setConversionProgress(message);
      };

      const response = await extractMarkdown(
        file,
        credentials.token,
        credentials.apiKey,
        credentials.email,
        onProgress
      );
      console.log("Received response from PDF converter:", response);

      const pageBreak = "\n\n---PAGE_BREAK---\n\n";
      const fullMarkdown = response.data.pages.join(pageBreak);
      setMarkdownContent(fullMarkdown);
      setConversionProgress('Conversion complete!');
    } catch (err) {
      // --- DETAILED LOGGING ---
      console.error("Detailed error in handlePdfUpload:", err);
      if (err.response) {
        console.error("Error Response Data:", err.response.data);
        console.error("Error Response Status:", err.response.status);
        console.error("Error Response Headers:", err.response.headers);
        setError(err.response?.data?.error || `Server responded with status ${err.response.status}`);
      } else if (err.request) {
        console.error("Error Request:", err.request);
        setError('No response received from PDF converter. Check network or service status.');
      } else {
        console.error('Error Message:', err.message);
        setError(err.message || 'An unexpected error occurred during PDF processing.');
      }
      console.error("Error Config:", err.config);
      // --- END DETAILED LOGGING ---
      setMarkdownContent(''); // Clear on error
    } finally {
      setIsLoading(false);
      setShowConversionOverlay(false);
      setConversionProgress('');
    }
  }, [setIsLoading, setError, setTotalPages, setPagesProcessed, setMarkdownContent, getCredentials]);

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
        console.log(`Processing page ${i + 1} of ${markdownPages.length}`);

        // Progress callback for enhanced steps
        const onProgress = (step) => {
          console.log(`Page ${i + 1}: ${step}`);
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
              console.info(`Page ${i + 1} had no meaningful content to process - skipping`);
            }
          } else { // Handle page-specific error or invalid format
            console.warn("Invalid or missing easy_read_sentences for page:", response.data);
            allEasyReadSentences.push({
              sentence: `Error processing content on this page.`,
              image_retrieval: 'error'
            });
            if (!processingError) processingError = 'Some pages failed to process correctly.'; // Set a general error
          }
        } catch (pageErr) {
          console.error(`Error processing page ${i + 1}:`, pageErr);
          allEasyReadSentences.push({
            sentence: `Error processing content on this page.`,
            image_retrieval: 'error'
          });
          if (!processingError) processingError = 'Error during page processing.';
        }
        // Update progress
        setPagesProcessed(i + 1);
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
    <>
      <LoadingOverlay open={showConversionOverlay} message={conversionProgress} />
      <Container maxWidth="md" sx={{ mt: 5, mb: 8 }}>
        <Paper elevation={3} sx={{
          p: 4,
          mb: 4,
          borderRadius: 'var(--border-radius-md)',
          boxShadow: '0 6px 18px rgba(0, 0, 0, 0.06)',
        }}>
          <Box sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 3,
            flexWrap: 'wrap',
            gap: 2
          }}>
            <Typography variant="h4" sx={{
              color: 'var(--color-primary)',
              fontWeight: 600,
              m: 0
            }}>
              Create Easy Read Content
            </Typography>
            <Button
              variant="contained"
              startIcon={<BookmarkIcon />}
              onClick={() => navigate('/saved')}
              sx={{
                backgroundColor: '#1976d2',
                color: 'white',
                px: 3,
                py: 1.5,
                borderRadius: 2,
                fontWeight: 600,
                fontSize: '0.95rem',
                textTransform: 'none',
                boxShadow: '0 2px 8px rgba(25, 118, 210, 0.25)',
                transition: 'all 0.2s ease',
                '&:hover': {
                  backgroundColor: '#1565c0',
                  transform: 'translateY(-2px)',
                  boxShadow: '0 4px 12px rgba(25, 118, 210, 0.35)'
                }
              }}
            >
              View Saved Content
            </Button>
          </Box>

          <Box sx={{ mb: 4 }}>
            <Typography variant="body1" sx={{
              mb: 2,
              color: 'text.primary',
              fontWeight: 500,
              maxWidth: '700px',
            }}>
              Transform your documents into accessible Easy Read format in 3 simple steps:
            </Typography>

            <Box component="ol" sx={{
              pl: 3,
              color: 'text.secondary',
              '& li': { mb: 1, lineHeight: 1.6 }
            }}>
              <li><strong>Upload content:</strong> Choose a PDF file or paste your text directly</li>
              <li><strong>Select image sets:</strong> Pick symbol collections that match your content theme</li>
              <li><strong>Process:</strong> Let AI simplify the language and suggest relevant images from the chosen sets</li>
            </Box>

            <Typography variant="body2" sx={{
              mt: 2,
              p: 2,
              bgcolor: '#f0f7ff',
              borderLeft: '4px solid #1976d2',
              borderRadius: 1,
              color: 'text.secondary',
              fontStyle: 'italic'
            }}>
              💡 <strong>Tip:</strong> PDFs work best when they contain selectable text. Scanned documents may need OCR processing first.
            </Typography>
          </Box>

          {/* File Upload Section */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 1, color: 'text.primary', fontWeight: 600 }}>
              Step 1: Upload Your Document
            </Typography>
            <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
              Upload a PDF document to automatically extract and process its content
            </Typography>
          </Box>

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
              Drop your PDF here
            </Typography>
            <Typography variant="body2" sx={{ color: 'var(--medium-gray)', mb: 1 }}>
              or click to browse and select a file
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Supported: PDF files up to 50MB
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
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6" sx={{ mb: 1, color: 'text.primary', fontWeight: 600 }}>
              Step 1 Alternative: Paste Your Text
            </Typography>
            <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
              Alternatively, paste or type your content directly. You can edit extracted PDF content here too.
            </Typography>

            <TextField
              label="Paste your content here (markdown format supported)"
              placeholder="Enter or paste your text content here. You can use basic markdown formatting like **bold** and *italic*."
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

            <Typography variant="caption" sx={{
              display: 'block',
              mt: 1,
              color: 'text.secondary',
              fontStyle: 'italic'
            }}>
            </Typography>
          </Box>

          {/* Symbol Sets Selection Section */}
          <Box sx={{ mt: 5, mb: 4 }}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" sx={{ mb: 1, color: 'text.primary', fontWeight: 600 }}>
                Step 2: Choose Image Sets
              </Typography>
              <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                Select symbol collections that best match your content theme. Images from these sets will be suggested for your Easy Read sentences.
              </Typography>
              <Typography variant="body2" sx={{
                mb: 2,
                color: 'text.secondary',
                fontStyle: 'italic',
                fontSize: '0.875rem'
              }}>
                🌍 <strong>Symbols kindly provided by <a href={GLOBALSYMBOLS_URL} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'none' }}>GlobalSymbols</a></strong> - making communication accessible worldwide
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary' }}>
                Available Symbol Collections
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

          <Divider sx={{ my: 4 }} />

          <Box sx={{ mt: 4, textAlign: 'center' }}>
            <Typography variant="h6" sx={{ mb: 2, color: 'text.primary', fontWeight: 600 }}>
              Step 3: Generate Easy Read Content
            </Typography>
            <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary', maxWidth: 500, mx: 'auto' }}>
              Ready to transform your content? The AI will simplify the language, break it into clear sentences, and suggest appropriate images.
            </Typography>

            <Button
              variant="contained"
              size="large"
              onClick={handleProcessContent}
              disabled={!currentMarkdown || currentMarkdown.trim() === ''}
              sx={{
                px: 6,
                py: 2,
                borderRadius: 'var(--border-radius-md)',
                backgroundColor: 'var(--color-accent)',
                fontWeight: 600,
                fontSize: '1.1rem',
                '&:hover': {
                  backgroundColor: '#0b8043',
                  transform: 'translateY(-2px)',
                  boxShadow: '0 4px 12px rgba(15, 157, 88, 0.2)'
                },
                '&:disabled': {
                  backgroundColor: '#ccc',
                  color: '#666'
                },
                transition: 'all 0.2s ease'
              }}
            >
              {!currentMarkdown || currentMarkdown.trim() === ''
                ? 'Add content to begin'
                : `Start Processing ${selectedSets.size > 0 ? `(${selectedSets.size} image sets)` : '(text only)'}`
              }
            </Button>

            {currentMarkdown && currentMarkdown.trim() !== '' && (
              <Typography variant="caption" sx={{
                display: 'block',
                mt: 2,
                color: 'text.secondary',
                fontStyle: 'italic'
              }}>
                ⏱️ Processing typically takes 1-3 minutes depending on content length
              </Typography>
            )}

            {/* Disclaimer */}
            <Box sx={{
              mt: 4,
              p: 3,
              backgroundColor: '#fff3cd',
              borderLeft: '4px solid #ffc107',
              borderRadius: 2,
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              textAlign: 'left',
              maxWidth: 700,
              mx: 'auto'
            }}>
              <Typography variant="body2" sx={{
                color: '#856404',
                lineHeight: 1.6,
                fontSize: '0.9rem'
              }}>
                <strong>Please note:</strong> This prototype is provided for exploration and testing purposes only and is not intended for use in UNICEF programs or by program partners. It uses artificial intelligence to simplify text and suggest images. While we strive for accuracy, all content should be carefully reviewed before use. The generated output must be verified for appropriateness and accuracy in your specific context.
              </Typography>
            </Box>
          </Box>
        </Paper>
      </Container>
    </>
  );
}

export default HomePage; 