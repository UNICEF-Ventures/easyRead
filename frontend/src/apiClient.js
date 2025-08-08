import axios from 'axios';
import { config } from './config.js';

// Function to get CSRF token from cookie
const getCsrfToken = () => {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue;
};

const apiClient = axios.create({
  baseURL: config.API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Always include cookies for authentication
});

// Log the API base URL for debugging (only in development)
if (import.meta.env.DEV) {
  console.log('🔗 API Client initialized with base URL:', config.API_BASE_URL);
  console.log('🔗 Axios instance baseURL:', apiClient.defaults.baseURL);
}

// Add request interceptor to include CSRF token
apiClient.interceptors.request.use(request => {
  // Add CSRF token to requests that need it (POST, PUT, PATCH, DELETE)
  if (['post', 'put', 'patch', 'delete'].includes(request.method.toLowerCase())) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      request.headers['X-CSRFToken'] = csrfToken;
    }
  }

  // Debug logging (only in development)
  if (import.meta.env.DEV) {
    console.log('🚀 Making request to:', request.baseURL + request.url);
    console.log('🚀 Full request config:', request);
    console.log('🔒 CSRF Token:', request.headers['X-CSRFToken'] || 'None');
  }

  return request;
});

// Function to extract markdown from PDF
export const extractMarkdown = (file) => {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient.post('/pdf-to-markdown/', formData, {
    headers: {
      'Content-Type': undefined, // Let browser set Content-Type with boundary
    },
    timeout: 60000, // Add timeout: 60 seconds (in milliseconds)
  });
};

// Internal validation function (not exported)
const validateCompleteness = (originalMarkdown, sentences) => {
  return apiClient.post('/validate-completeness/', {
    original_markdown: originalMarkdown,
    easy_read_sentences: sentences
  }, {
    timeout: 60000 // 60 seconds for validation
  });
};

// Internal revision function (not exported)
const reviseSentences = (originalMarkdown, currentSentences, validationFeedback) => {
  return apiClient.post('/revise-sentences/', {
    original_markdown: originalMarkdown,
    current_sentences: currentSentences,
    validation_feedback: validationFeedback
  }, {
    timeout: 90000 // 90 seconds for revision
  });
};

// Function to generate easy read sentences from a markdown page with validation and revision
export const generateEasyRead = async (markdownPage, selectedSets = [], onProgress = null) => {
  try {
    // Step 1: Generate initial Easy Read content
    onProgress?.("Converting to Easy Read...");
    const initialResponse = await apiClient.post('/process-page/', {
      markdown_page: markdownPage,
      selected_sets: selectedSets,
    }, {
      timeout: 90000 // Extend timeout for initial processing
    });
    
    const { title, easy_read_sentences } = initialResponse.data;
    
    // Step 2: Validate completeness
    onProgress?.("Validating content quality...");
    try {
      const validationResponse = await validateCompleteness(
        markdownPage, 
        easy_read_sentences.map(s => s.sentence)
      );
      
      if (import.meta.env.DEV || import.meta.env.VITE_DEBUG_VALIDATION) {
        console.log('✅ Validation completed successfully');
        console.log('📋 Validation feedback received:');
        console.log('  Missing info:', validationResponse.data.missing_info || 'None');
        console.log('  Extra info:', validationResponse.data.extra_info || 'None');
        console.log('  Other feedback:', validationResponse.data.other_feedback || 'None');
      }
      
      // Step 3: Always revise content (regardless of validation result)
      onProgress?.("Revising content...");
      try {
        const revisionResponse = await reviseSentences(
          markdownPage, 
          easy_read_sentences, 
          validationResponse.data
        );
        
        if (import.meta.env.DEV || import.meta.env.VITE_DEBUG_VALIDATION) {
          console.log('✨ Content revised and enhanced');
          console.log('📋 Validation feedback:');
          console.log('  Missing info:', validationResponse.data.missing_info || 'None');
          console.log('  Extra info:', validationResponse.data.extra_info || 'None');
          console.log('  Other feedback:', validationResponse.data.other_feedback || 'None');
        }
        
        return {
          data: {
            title,
            easy_read_sentences: revisionResponse.data.easy_read_sentences
          }
        };
      } catch (revisionError) {
        console.warn('Revision failed, using original content:', revisionError);
        return initialResponse;
      }
      
    } catch (validationError) {
      if (import.meta.env.DEV || import.meta.env.VITE_DEBUG_VALIDATION) {
        console.warn('⚠️ Validation failed, using original content:', validationError);
        if (validationError.response?.data) {
          console.log('📋 Validation error details:', validationError.response.data);
        }
      }
    }
    
    return initialResponse;
    
  } catch (error) {
    console.error('Easy Read generation failed:', error);
    throw error; // Re-throw to maintain existing error handling
  }
};

// Function to save processed content
export const saveContent = (title, originalMarkdown, easyReadJson) => {
  return apiClient.post('/save-processed-content/', {
    title: title,
    original_markdown: originalMarkdown,
    easy_read_json: easyReadJson,
  });
};

// Function to retrieve saved content by tokens
export const getSavedContentByTokens = (tokens = []) => {
  const query = Array.isArray(tokens) && tokens.length > 0 ? `?tokens=${tokens.join(',')}` : '?tokens=';
  return apiClient.get(`/list-saved-content/${query}`);
};

// Keep for backward compatibility (admin or legacy)
export const getSavedContent = () => {
  return apiClient.get('/list-saved-content/');
};

// Function to find similar images based on a query
export const findSimilarImages = (query, n_results = 3, excludeIds = [], signal = null, imageSets = null) => {
  const config = {
    signal: signal, // Add AbortController signal support
    timeout: 45000 // 45 seconds timeout for ViT-L-14 model processing
  };
  
  const requestData = {
    query: query,
    n_results: n_results,
    exclude_ids: excludeIds
  };
  
  if (imageSets && Array.isArray(imageSets) && imageSets.length > 0) {
    requestData.image_sets = imageSets;
  }
  
  return apiClient.post('/find-similar-images/', requestData, config);
};

// Function to find similar images for multiple queries in a batch
export const findSimilarImagesBatch = (queries, excludeIds = [], signal = null, imageSets = null) => {
  const config = {
    signal: signal, // Add AbortController signal support
    timeout: 60000 // 60 seconds timeout for batch processing
  };
  
  const requestData = {
    queries: queries, // Array of {index, query, n_results} objects
    exclude_ids: excludeIds
  };
  
  if (imageSets && Array.isArray(imageSets) && imageSets.length > 0) {
    requestData.image_sets = imageSets;
  }
  
  return apiClient.post('/find-similar-images-batch/', requestData, config);
};

// Function to get all images
export const listImages = () => {
  return apiClient.get('/list-images/');
};

// Function to get image sets
export const getImageSets = () => {
  return apiClient.get('/list-images/').then(response => {
    // Extract set names from the images_by_set structure
    const imagesBySet = response.data.images_by_set || {};
    const sets = Object.keys(imagesBySet).map(setName => ({
      name: setName,
      imageCount: imagesBySet[setName].length
    }));
    return { data: { sets } };
  });
};

// Function to upload a new image
export const uploadImage = (imageFile, description = '', setName = '') => {
  const formData = new FormData();
  formData.append('image', imageFile);
  if (description) {
    formData.append('description', description);
  }
  if (setName) {
    formData.append('set_name', setName);
  }

  return apiClient.post('/upload-image/', formData, {
    headers: {
      'Content-Type': undefined // Remove the default application/json header
    },
  });
};

// Function to upload multiple images at once
export const batchUploadImages = (imageFiles, description = '', setName = '') => {
  const formData = new FormData();
  
  // Add each file to the form data with the same key name 'images'
  for (let i = 0; i < imageFiles.length; i++) {
    // When using react-dropzone, we get the raw File object with added preview property
    // The backend expects files with the key 'images'
    formData.append('images', imageFiles[i]);
  }
  
  if (description) {
    formData.append('description', description);
  }
  
  if (setName) {
    formData.append('set_name', setName);
  }

  return apiClient.post('/batch-upload-images/', formData, {
    headers: {
      'Content-Type': undefined // Remove the default application/json header
    },
    // Extend timeout for multiple files
    timeout: 120000, // 2 minutes
  });
};

// Function for optimized large batch uploads (1000+ images)
export const optimizedBatchUpload = (imageFiles, description = '', setName = '', batchSize = 50, sessionId = null) => {
  const formData = new FormData();
  
  // Add each file to the form data
  for (let i = 0; i < imageFiles.length; i++) {
    formData.append('images', imageFiles[i]);
  }
  
  if (description) {
    formData.append('description', description);
  }
  
  if (setName) {
    formData.append('set_name', setName);
  }
  
  if (batchSize) {
    formData.append('batch_size', batchSize.toString());
  }
  
  if (sessionId) {
    formData.append('session_id', sessionId);
  }

  return apiClient.post('/optimized-batch-upload/', formData, {
    headers: {
      'Content-Type': undefined
    },
    // Extended timeout for large batches
    timeout: 600000, // 10 minutes
  });
};

// Function to check upload progress
export const getUploadProgress = (sessionId) => {
  return apiClient.get(`/upload-progress/${sessionId}/`, {
    timeout: 30000 // 30 seconds
  });
};

// Function to upload folder structure with automatic set creation
export const uploadFolder = (files, onProgress = null) => {
  // For very large uploads, use chunked approach
  const CHUNK_SIZE = 50; // Process in chunks of 50 files
  const LARGE_UPLOAD_THRESHOLD = 100; // Use chunking for 100+ files
  
  if (files.length >= LARGE_UPLOAD_THRESHOLD) {
    return uploadFolderChunked(files, onProgress);
  }
  
  // Standard upload for smaller batches
  return uploadFolderStandard(files, onProgress);
};

// Standard folder upload for smaller batches (< 100 files)
const uploadFolderStandard = (files, onProgress = null) => {
  const formData = new FormData();
  
  // Add files with their relative paths as keys
  files.forEach((file) => {
    let relativePath = file.webkitRelativePath || file.name;
    
    // Use the folder name from the file preview if available
    if (file.folderName) {
      // Build path using the clean folder name from preview
      const pathParts = relativePath.split('/');
      if (pathParts.length > 1) {
        pathParts[0] = file.folderName; // Use the folder name from preview
        relativePath = pathParts.join('/');
      } else {
        relativePath = `${file.folderName}/${file.name}`;
      }
    }
    
    formData.append(relativePath, file);
  });

  // More aggressive dynamic timeout calculation
  const calculateTimeout = (fileCount) => {
    const baseTime = 180000; // 3 minutes base
    const timePerFile = 4000; // 4 seconds per file (embedding generation can be slow)
    const networkBuffer = 120000; // 2 minutes network buffer
    const totalTime = baseTime + (fileCount * timePerFile) + networkBuffer;
    
    // Cap at 45 minutes for chunk uploads (was 30)
    return Math.min(totalTime, 2700000);
  };

  const config = {
    headers: {
      'Content-Type': undefined // Let browser set multipart boundary
    },
    timeout: calculateTimeout(files.length),
  };

  // Add upload progress tracking if callback provided
  if (onProgress && typeof onProgress === 'function') {
    config.onUploadProgress = (progressEvent) => {
      const percentCompleted = Math.round(
        (progressEvent.loaded * 100) / progressEvent.total
      );
      // Calculate estimated files processed based on upload progress
      const estimatedFilesProcessed = Math.floor((progressEvent.loaded / progressEvent.total) * files.length);
      
      console.log('📊 Standard Upload Progress:', {
        bytesLoaded: progressEvent.loaded,
        totalBytes: progressEvent.total,
        percentage: percentCompleted,
        estimatedFiles: estimatedFilesProcessed,
        totalFiles: files.length
      });
      
      onProgress({
        loaded: progressEvent.loaded, // Keep original for internal use
        total: progressEvent.total,
        percentage: percentCompleted,
        files: estimatedFilesProcessed, // Add estimated file count
        totalFiles: files.length,
        currentChunk: 1,
        totalChunks: 1,
        isChunked: false
      });
    };
  }

  return apiClient.post('/upload-folder/', formData, config);
};

// Chunked folder upload for large batches (100+ files)
const uploadFolderChunked = async (files, onProgress = null) => {
  const CHUNK_SIZE = 50;
  const totalFiles = files.length;
  const totalChunks = Math.ceil(totalFiles / CHUNK_SIZE);
  
  let totalProcessed = 0;
  let totalFailed = 0;
  let allResults = {
    folders: {},
    total_successful: 0,
    total_uploads: 0,
    sets_created: 0,
    message: '',
    errors: [] // Track errors for user feedback
  };
  
  console.log(`📦 Starting chunked upload: ${totalFiles} files in ${totalChunks} chunks`);
  
  // Process each chunk sequentially (avoids creating all chunks in memory at once)
  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const chunkNumber = chunkIndex + 1;
    const startIdx = chunkIndex * CHUNK_SIZE;
    const endIdx = Math.min(startIdx + CHUNK_SIZE, totalFiles);
    const chunk = files.slice(startIdx, endIdx); // Create chunk on-demand
    
    console.log(`📦 Processing chunk ${chunkNumber}/${totalChunks} (${chunk.length} files)`);
    
    try {
      // Upload this chunk
      const chunkResult = await uploadFolderStandard(chunk, (chunkProgress) => {
        // Calculate progress within this chunk only
        const currentChunkContribution = Math.round((chunkProgress.percentage / 100) * chunk.length);
        const totalLoadedFiles = totalProcessed + currentChunkContribution;
        const overallProgress = Math.round((totalLoadedFiles / totalFiles) * 100);
        
        console.log('📊 Chunked Upload Progress:', {
          chunkNumber,
          totalChunks,
          chunkProgress: chunkProgress.percentage,
          currentChunkContribution,
          totalProcessed,
          totalLoadedFiles,
          overallProgress
        });
        
        if (onProgress) {
          onProgress({
            loaded: totalLoadedFiles, // This is now file count, not bytes
            total: totalFiles,
            percentage: Math.min(overallProgress, 99), // Don't show 100% until we're truly done
            files: totalLoadedFiles, // Add explicit file count
            totalFiles: totalFiles,
            currentChunk: chunkNumber,
            totalChunks: totalChunks,
            isChunked: true,
            chunkProgress: chunkProgress.percentage
          });
        }
      }); // Folder names are already in file objects
      
      // Merge results
      if (chunkResult.data) {
        const chunkData = chunkResult.data.data || chunkResult.data;
        
        // Merge folder results
        if (chunkData.folders) {
          Object.keys(chunkData.folders).forEach(folderName => {
            if (!allResults.folders[folderName]) {
              allResults.folders[folderName] = {
                set_name: folderName,
                results: [],
                successful_uploads: 0,
                total_files: 0
              };
            }
            
            const existingFolder = allResults.folders[folderName];
            const chunkFolder = chunkData.folders[folderName];
            
            existingFolder.results.push(...chunkFolder.results);
            existingFolder.successful_uploads += chunkFolder.successful_uploads;
            existingFolder.total_files += chunkFolder.total_files;
          });
        }
        
        // Update totals
        allResults.total_successful += chunkData.total_successful || 0;
        allResults.total_uploads += chunkData.total_uploads || 0;
        
        totalProcessed += chunk.length;
      }
      
      const chunkResponseData = chunkResult.data?.data || chunkResult.data;
      console.log(`✅ Chunk ${chunkNumber} completed: ${chunkResponseData?.total_successful || 0}/${chunk.length} files successful`);
      
      // Update progress after chunk completion
      if (onProgress) {
        const isLastChunk = chunkIndex === totalChunks - 1;
        const finalProgress = isLastChunk ? 100 : Math.round(((totalProcessed + chunk.length) / totalFiles) * 99);
        const completedFiles = totalProcessed + chunk.length;
        
        console.log(`✅ Chunk ${chunkNumber} completed:`, {
          completedFiles,
          totalFiles,
          finalProgress,
          isLastChunk
        });
        
        onProgress({
          loaded: completedFiles, // This is file count
          total: totalFiles,
          percentage: finalProgress,
          files: completedFiles, // Add explicit file count
          totalFiles: totalFiles,
          currentChunk: chunkNumber,
          totalChunks: totalChunks,
          isChunked: true,
          chunkProgress: 100 // This chunk is complete
        });
      }
      
      // Short delay between chunks to prevent overwhelming the server
      if (chunkIndex < totalChunks - 1) {
        await new Promise(resolve => setTimeout(resolve, 1000)); // 1 second delay
      }
      
    } catch (error) {
      console.error(`❌ Error in chunk ${chunkNumber}:`, error);
      
      // Track errors for user feedback
      const errorMsg = error.response?.data?.message || error.message || 'Unknown error';
      allResults.errors.push(`Chunk ${chunkNumber}: ${errorMsg}`);
      
      // Count chunk files as failed, not processed
      totalFailed += chunk.length;
      console.error(`Chunk ${chunkNumber} failed: ${chunk.length} files affected`);
      
      // Update progress to show failed chunk
      if (onProgress) {
        const overallProgress = Math.min(99, Math.round(((totalProcessed + totalFailed) / totalFiles) * 100));
        
        console.error(`❌ Chunk ${chunkNumber} failed:`, {
          totalProcessed,
          totalFailed,
          overallProgress,
          error
        });
        
        onProgress({
          loaded: totalProcessed, // Don't count failed files as loaded
          total: totalFiles,
          percentage: overallProgress,
          files: totalProcessed, // Add explicit file count
          totalFiles: totalFiles,
          currentChunk: chunkNumber,
          totalChunks: totalChunks,
          isChunked: true,
          error: `Chunk ${chunkNumber} failed`
        });
      }
      
      // Continue with remaining chunks
    }
  }
  
  // Don't set to 100% here - let the last chunk do it naturally
  console.log(`📦 All chunks processed. Total successful: ${allResults.total_successful}/${totalFiles}`);
  
  // Count unique sets created
  allResults.sets_created = Object.keys(allResults.folders).length;
  allResults.total_uploads = totalProcessed + totalFailed; // Accurate total
  
  const successMessage = `Processed ${totalFiles} files in ${totalChunks} chunks: ${allResults.total_successful} succeeded`;
  const failureMessage = totalFailed > 0 ? `, ${totalFailed} failed` : '';
  allResults.message = successMessage + failureMessage;
  
  console.log(`🎉 Chunked upload completed: ${allResults.total_successful}/${totalFiles} files successful across ${allResults.sets_created} sets`);
  
  if (allResults.errors.length > 0) {
    console.warn('Upload completed with errors:', allResults.errors);
  }
  
  return { data: allResults };
};

// Function to update the selected image for a saved sentence
export const updateSavedContentImage = (contentId, sentenceIndex, imageUrl, allImages = []) => {
  // Ensure sentenceIndex is a number to prevent validation errors
  const index = parseInt(sentenceIndex, 10);
  
  return apiClient.patch(`/update-saved-content-image/by-token/${contentId}/`, {
    sentence_index: index,
    image_url: imageUrl,
    all_images: allImages // Add all images to be saved
  });
};

export const generateNewImage = async (prompt) => {
  if (import.meta.env.DEV) {
    console.log(`API Client: Generating image with prompt: "${prompt}"`);
  }
  try {
    const response = await apiClient.post('/generate-image/', { prompt });
    if (import.meta.env.DEV) {
      console.log('API Client: Image generation response:', response.data);
    }
    // Assuming backend returns { new_image_url: 'path/to/image.png' }
    return response.data; 
  } catch (error) {
    if (import.meta.env.DEV) {
      console.error('API Client: Error generating new image:', error.response ? error.response.data : error.message);
    }
    throw error; // Re-throw the error to be handled by the caller
  }
};

// Function to delete saved content by ID (legacy)
export const deleteSavedContent = (contentId) => {
  return apiClient.delete(`/saved-content/${contentId}/`);
};

// Function to get saved content detail by token
export const getSavedContentDetailByToken = (token) => {
  return apiClient.get(`/saved-content/by-token/${token}/`);
};

// Function to delete saved content by token
export const deleteSavedContentByToken = (token) => {
  return apiClient.delete(`/saved-content/by-token/${token}/`);
};

// Function to bulk update all image selections for saved content
export const bulkUpdateSavedContentImages = (contentId, imageSelections) => {
  return apiClient.put(`/bulk-update-saved-content-images/${contentId}/`, {
    image_selections: imageSelections
  });
};

// Function to export saved content as DOCX
export const exportSavedContentDocx = (contentId) => {
  return apiClient.get(`/export/docx/${contentId}/`, {
    responseType: 'blob' // Important for file downloads
  });
};

// Function to export current content as DOCX
export const exportCurrentContentDocx = (title, easyReadContent, originalMarkdown) => {
  return apiClient.post('/export/docx/', {
    title: title,
    easy_read_content: easyReadContent,
    original_markdown: originalMarkdown
  }, {
    responseType: 'blob' // Important for file downloads
  });
};

export default apiClient; 