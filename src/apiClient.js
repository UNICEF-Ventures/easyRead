// Function to save processed content
export const saveContent = (originalMarkdown, easyReadJson) => {
  return apiClient.post('/save-content/', {
    original_markdown: originalMarkdown,
    easy_read_json: easyReadJson,
  });
};

// Function to retrieve all saved content
export const getSavedContent = () => {
  return apiClient.get('/saved-content/');
};

// Function to find similar images based on a query
export const findSimilarImages = (query, n_results = 3) => {
  return apiClient.post('/find-similar-images/', {
    query: query,
    n_results: n_results,
  });
}; 