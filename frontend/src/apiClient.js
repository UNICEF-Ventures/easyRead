import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api', // Your Django backend API base URL
  headers: {
    'Content-Type': 'application/json',
  },
});

// Function to extract markdown from PDF
export const extractMarkdown = (file) => {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient.post('/markdown-extraction/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data', // Important for file uploads
    },
    timeout: 60000, // Add timeout: 60 seconds (in milliseconds)
  });
};

// Function to generate easy read sentences from a markdown page
export const generateEasyRead = (markdownPage) => {
  return apiClient.post('/easy-read-generation/', {
    markdown_page: markdownPage,
  });
};

// Function to save processed content
export const saveContent = (title, originalMarkdown, easyReadJson) => {
  return apiClient.post('/save-content/', {
    title: title,
    original_markdown: originalMarkdown,
    easy_read_json: easyReadJson,
  });
};

// Function to retrieve all saved content
export const getSavedContent = () => {
  return apiClient.get('/saved-content/');
};

// Function to find similar images based on a query
export const findSimilarImages = (query, n_results = 3, excludeIds = []) => {
  return apiClient.post('/find-similar-images/', {
    query: query,
    n_results: n_results,
    exclude_ids: excludeIds
  });
};

// Function to get all images
export const listImages = () => {
  return apiClient.get('/list-images/');
};

// Function to upload a new image
export const uploadImage = (imageFile, description = '') => {
  const formData = new FormData();
  formData.append('image', imageFile);
  if (description) {
    formData.append('description', description);
  }

  return apiClient.post('/image-upload/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

// Function to upload multiple images at once
export const batchUploadImages = (imageFiles, description = '') => {
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

  return apiClient.post('/batch-upload-images/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    // Extend timeout for multiple files
    timeout: 120000, // 2 minutes
  });
};

// Function to update the selected image for a saved sentence
export const updateSavedContentImage = (contentId, sentenceIndex, imageUrl, allImages = []) => {
  // Ensure sentenceIndex is a number to prevent validation errors
  const index = parseInt(sentenceIndex, 10);
  
  return apiClient.patch(`/saved-content/${contentId}/update-image/`, {
    sentence_index: index,
    image_url: imageUrl,
    all_images: allImages // Add all images to be saved
  });
};

export const generateNewImage = async (prompt) => {
  console.log(`API Client: Generating image with prompt: "${prompt}"`);
  try {
    const response = await apiClient.post('/generate-image/', { prompt });
    console.log('API Client: Image generation response:', response.data);
    // Assuming backend returns { new_image_url: 'path/to/image.png' }
    return response.data; 
  } catch (error) {
    console.error('API Client: Error generating new image:', error.response ? error.response.data : error.message);
    throw error; // Re-throw the error to be handled by the caller
  }
};

// Function to delete saved content
export const deleteSavedContent = (contentId) => {
  return apiClient.delete(`/saved-content/${contentId}/`);
};

export default apiClient; 