import axios from 'axios';
import { config } from './config.js';

const apiClient = axios.create({
  baseURL: config.API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Log the API base URL for debugging (only in development)
if (import.meta.env.DEV) {
  console.log('🔗 API Client initialized with base URL:', config.API_BASE_URL);
  console.log('🔗 Axios instance baseURL:', apiClient.defaults.baseURL);

  // Add request interceptor for debugging (only in development)
  apiClient.interceptors.request.use(request => {
    console.log('🚀 Making request to:', request.baseURL + request.url);
    console.log('🚀 Full request config:', request);
    return request;
  });
}

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

// Function to generate easy read sentences from a markdown page
export const generateEasyRead = (markdownPage, selectedSets = []) => {
  return apiClient.post('/process-page/', {
    markdown_page: markdownPage,
    selected_sets: selectedSets,
  });
};

// Function to save processed content
export const saveContent = (title, originalMarkdown, easyReadJson) => {
  return apiClient.post('/save-processed-content/', {
    title: title,
    original_markdown: originalMarkdown,
    easy_read_json: easyReadJson,
  });
};

// Function to retrieve all saved content
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

// Function to update the selected image for a saved sentence
export const updateSavedContentImage = (contentId, sentenceIndex, imageUrl, allImages = []) => {
  // Ensure sentenceIndex is a number to prevent validation errors
  const index = parseInt(sentenceIndex, 10);
  
  return apiClient.patch(`/update-saved-content-image/${contentId}/`, {
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

// Function to delete saved content
export const deleteSavedContent = (contentId) => {
  return apiClient.delete(`/saved-content/${contentId}/`);
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