import { useState, useEffect, useCallback, useRef } from 'react';
import { findSimilarImages, generateNewImage, updateSavedContentImage } from '../apiClient';

// Custom hook to manage image state and actions for EasyRead content
function useEasyReadImageManager(initialContent = [], contentId = null) {
  const [imageState, setImageState] = useState({});
  const [preventDuplicateImages, setPreventDuplicateImages] = useState(true);
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState(0);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'success' });
  // Use ref to track fetch status for each index to prevent duplicate fetches
  const fetchingRef = useRef({});
  // Use ref to track content identity to avoid unnecessary refetches
  const contentRef = useRef(null);

  // Initialize or update image state when content changes
  useEffect(() => {
    if (!initialContent || initialContent.length === 0) {
      console.log("useEasyReadImageManager: Empty or null initialContent, skipping initialization");
      setImageState({});
      contentRef.current = null;
      return;
    }

    // Check if this is the same content reference we've already processed
    const isSameContentRef = initialContent === contentRef.current;
    if (isSameContentRef) {
      console.log("useEasyReadImageManager: Skipping initialization for same content reference");
      return;
    }

    // Update our content reference
    contentRef.current = initialContent;
    console.log("useEasyReadImageManager: Initializing/Updating image state for content:", initialContent);
    
    // Log first few items to inspect them
    initialContent.slice(0, 3).forEach((item, idx) => {
      console.log(`CONTENT ITEM ${idx}:`, JSON.stringify(item));
    });
    
    const initialImageState = {};
    const needsFetching = [];

    initialContent.forEach((item, index) => {
      if (!imageState[index]) {
        // Debug each item's image retrieval keyword
        console.log(`Item ${index} image_retrieval:`, item.image_retrieval);
        
        const shouldFetch = !item.selected_image_path && item.image_retrieval && item.image_retrieval !== 'error';
        
        // Log the decision logic
        console.log(`Item ${index} fetchable: ${shouldFetch} (selected_path: ${!!item.selected_image_path}, has retrieval: ${!!item.image_retrieval}, is error: ${item.image_retrieval === 'error'})`);
        
        initialImageState[index] = {
          images: item.alternative_images 
                      ? item.alternative_images.map(url => ({ url })) 
                      : (item.selected_image_path ? [{ url: item.selected_image_path }] : []),
          selectedPath: item.selected_image_path || null,
          isLoading: shouldFetch,
          isGenerating: false,
          error: item.image_retrieval === 'error' ? 'Invalid Keyword' : null 
        };
        if (shouldFetch && !fetchingRef.current[index]) {
          needsFetching.push(index);
          fetchingRef.current[index] = true;
        }
      }
    });
    
    if (Object.keys(initialImageState).length > 0) {
       setImageState(prev => ({ ...prev, ...initialImageState }));
    }

    // Fetch initial images if any were marked
    const fetchMissingImages = async () => {
        if (needsFetching.length === 0) {
          console.log("useEasyReadImageManager: No indices need fetching, skipping API calls");
          // Ensure fetchingRef is cleared even if no fetch happens
          needsFetching.forEach(index => { fetchingRef.current[index] = false; }); 
          return;
        }
          
        console.log("useEasyReadImageManager: useEffect triggering fetch for indices:", needsFetching);

        // Ensure isLoading is true for items we are about to fetch
        setImageState(prev => {
            const loadingUpdates = { ...prev }; 
            needsFetching.forEach(index => {
                if(loadingUpdates[index]) {
                    loadingUpdates[index].isLoading = true;
                }
            });
            return loadingUpdates;
        });

        // Array to hold results from each promise
        let fetchResults = []; 
        try {
            fetchResults = await Promise.all(needsFetching.map(async (index) => {
                const item = initialContent[index];
                // No need to read current state here, we build the update from scratch

                if (item.image_retrieval && item.image_retrieval !== 'error') {
                    console.log(`useEasyReadImageManager: useEffect fetching for index ${index} with keyword "${item.image_retrieval}"`);
                    try {
                        console.log(`Making API call to findSimilarImages with query: "${item.image_retrieval}", n_results: 3`);
                        const response = await findSimilarImages(item.image_retrieval, 3);
                        console.log(`API response for "${item.image_retrieval}":`, response.data);
                        
                        const images = response.data.results || [];
                        console.log(`Got ${images.length} images for index ${index}`);
                        
                        // Return the update object for this index
                        return {
                            index: index,
                            update: {
                                images: images,
                                selectedPath: images.length > 0 ? images[0].url : null,
                                isLoading: false,
                                error: images.length === 0 ? 'No images found' : null
                            }
                        };
                    } catch (err) {
                        console.error(`useEasyReadImageManager: useEffect fetch error for index ${index}:`, err);
                        console.error(`Error details:`, err.response?.data || err.message);
                        // Return an error update object
                        return {
                            index: index,
                            update: {
                                isLoading: false,
                                error: 'Failed to fetch'
                            }
                        };
                    }
                } else {
                    // Keyword invalid or missing - return state reset object
                    console.warn(`useEasyReadImageManager: useEffect skipping fetch for index ${index}, resetting loading.`);
                     return {
                        index: index,
                        update: { isLoading: false, error: 'Fetch cancelled or invalid keyword' }
                    };                   
                }
            }));
        } catch (promiseAllError) {
              console.error("useEasyReadImageManager: Unexpected error during Promise.all in useEffect fetch:", promiseAllError);
              // If Promise.all fails catastrophically, we might not have individual results
              // Create error updates for all initially requested indices
              fetchResults = needsFetching.map(index => ({
                index: index,
                update: { isLoading: false, error: 'Batch fetch failed' }
              }));
        } finally {
              console.log("useEasyReadImageManager: Consolidating fetch results.");
              // Consolidate results into a single update object
              const finalUpdates = {};
              fetchResults.forEach(result => {
                  if (result) { // Check if the result is valid
                     // Merge the update with the existing state for that index
                     finalUpdates[result.index] = (prevState) => ({
                         ...(prevState || {}), // Keep existing state like isGenerating
                         ...result.update
                     });
                  }
              });

              console.log("useEasyReadImageManager: Applying final updates after useEffect fetch. Update count:", Object.keys(finalUpdates).length);
              // Apply the consolidated updates using functional updates
              setImageState(prev => {
                  const newState = {...prev};
                  Object.keys(finalUpdates).forEach(idx => {
                      newState[idx] = finalUpdates[idx](prev[idx]);
                  });
                  return newState;
              });
              
              // Reset fetching status for all initially targeted indices
              needsFetching.forEach(index => {
                fetchingRef.current[index] = false;
              });
        }
    };

    fetchMissingImages();
    
  // IMPORTANT: Only run this effect when initialContent reference changes.
  }, [initialContent]); 

  // Handle selection change - updates local state and backend if contentId is present
  const handleImageSelectionChange = useCallback(async (sentenceIndex, newPath) => {
    const currentState = imageState[sentenceIndex];
    if (!currentState) return;

    // Optimistic UI update
    setImageState(prev => ({
      ...prev,
      [sentenceIndex]: {
        ...currentState,
        selectedPath: newPath,
        isGenerating: false, // Ensure generation stops on selection
        error: null // Clear errors on new selection
      }
    }));

    // If it's saved content, update the backend
    if (contentId !== null) {
      try {
        const allImageUrls = currentState.images.map(img => img.url);
        // Ensure the newly selected path is included if it wasn't already an option
        if (newPath && !allImageUrls.includes(newPath)) {
           allImageUrls.push(newPath); // Or maybe prepend? Depends on desired UX
        }
        await updateSavedContentImage(contentId, sentenceIndex, newPath, allImageUrls);
        setNotification({ open: true, message: 'Image selection saved', severity: 'success' });
      } catch (err) {
        console.error(`useEasyReadImageManager: Error updating saved image for sentence ${sentenceIndex}:`, err);
        setNotification({ open: true, message: 'Failed to save image selection', severity: 'error' });
        // Revert optimistic update on error
        setImageState(prev => ({
          ...prev,
          [sentenceIndex]: currentState // Revert to the original state for this index
        }));
      }
    }
  }, [contentId, imageState]); // Depend on imageState to get current images

  // Handle generating a new image
  const handleGenerateImage = useCallback(async (sentenceIndex, prompt) => {
    if (!prompt) {
      setNotification({ open: true, message: 'Cannot generate image without a prompt.', severity: 'warning' });
      return;
    }

    const originalState = imageState[sentenceIndex] || { images: [], selectedPath: null, error: null, isLoading: false };

    setImageState(prev => ({
      ...prev,
      [sentenceIndex]: {
        ...originalState,
        isLoading: false,
        isGenerating: true,
        error: null
      }
    }));

    try {
      const response = await generateNewImage(prompt);
      // const newImageUrl = response.new_image_url;
      // const newImageId = response.new_image_id; // Get the numeric ID from the response
      
      // if (newImageUrl && newImageId) { // Check both ID and URL exist
      //   const newImageObject = { url: newImageUrl, id: newImageId }; // Assuming ID is useful for selection or key
      
      let newImages = [];
      let newSelectedPath = null;

      if (response && response.all_generated_images && response.all_generated_images.length > 0) {
        console.log("useEasyReadImageManager: Processing all_generated_images from backend:", response.all_generated_images);
        newImages = response.all_generated_images.map(img => ({ url: img.url, id: img.id })); // Ensure objects have url and id
        newSelectedPath = newImages[0].url; // Select the first image by default
        setNotification({ open: true, message: `Generated ${newImages.length} images. First one selected.`, severity: 'success' });
      } else if (response && response.new_image_url && response.new_image_id) {
        // Fallback for the temporary backend workaround (single image)
        console.warn("useEasyReadImageManager: Using single image from backend (new_image_url). Frontend should be updated to use all_generated_images.");
        newImages = [{ url: response.new_image_url, id: response.new_image_id }];
        newSelectedPath = response.new_image_url;
        setNotification({ open: true, message: 'Image generated successfully (single)', severity: 'success' });
      } else {
        console.error("useEasyReadImageManager: Backend did not return valid image data (all_generated_images or new_image_url).");
        throw new Error("Backend did not return a valid new image ID and URL.");
      }
      
      // Combine existing images with new images, ensuring uniqueness
      const existingImages = originalState.images || [];
      const combinedImagesMap = new Map();

      // Add existing images to the map first
      existingImages.forEach(img => {
        const key = img.id || img.url; // Prefer ID, fallback to URL for keying
        if (key) combinedImagesMap.set(key, img);
      });

      // Add new images, potentially overwriting if keys conflict (though new IDs should be unique)
      newImages.forEach(img => {
        const key = img.id || img.url;
        if (key) combinedImagesMap.set(key, img);
      });
      
      const finalCombinedImages = Array.from(combinedImagesMap.values());
      
      setImageState(prev => ({
        ...prev,
        [sentenceIndex]: {
          ...originalState, // Keep other properties like keyword
          images: finalCombinedImages, // Use the combined and de-duplicated list
          selectedPath: newSelectedPath, // Still select the first of the NEWLY generated images
          isLoading: false,
          isGenerating: false,
          error: null
        }
      }));

      // If it's saved content, update the backend with the newly selected image and all its alternatives
      if (contentId !== null) {
        try {
          // All images in the combined list become the alternatives
          const allAlternativeUrls = finalCombinedImages.map(img => img.url);
          await updateSavedContentImage(contentId, sentenceIndex, newSelectedPath, allAlternativeUrls);
          // Notification for saving is handled by updateSavedContentImage or a separate mechanism if needed
        } catch (err) {
          console.error(`useEasyReadImageManager: Error updating saved image after generation for sentence ${sentenceIndex}:`, err);
          setNotification({ open: true, message: 'Failed to save newly generated image selection', severity: 'error' });
          // Potentially revert, but the image is already generated and in state.
          // The user can manually re-select if saving fails.
        }
      }
    } catch (err) {
      console.error(`useEasyReadImageManager: Error generating image for sentence ${sentenceIndex}:`, err);
      // Revert state on error
      setImageState(prev => ({
        ...prev,
        [sentenceIndex]: { ...originalState, isGenerating: false, error: 'Image generation failed' }
      }));
      setNotification({ open: true, message: 'Image generation failed. Please try again.', severity: 'error' });
    }
  }, [contentId, imageState]); // Depend on imageState to access current images

  // Handle refreshing all images
  const handleRefreshAllImages = useCallback(async () => {
    if (!initialContent || initialContent.length === 0) {
      setNotification({ open: true, message: 'No content available to refresh images', severity: 'warning' });
      return;
    }

    setRefreshingAll(true);
    setRefreshProgress(0);

    const currentStateSnapshot = { ...imageState };
    const loadingState = {};
    initialContent.forEach((_, index) => {
      loadingState[index] = {
        ...(currentStateSnapshot[index] || { images: [], selectedPath: null }),
        isLoading: true,
        isGenerating: false,
        error: null
      };
    });
    setImageState(loadingState);

    let successCount = 0;
    let failureCount = 0;
    // Initialize usedImageIds *before* the loop
    const usedImageIds = preventDuplicateImages ? [] : null;
    const resultsPerQuery = 5;
    const stateUpdates = {}; // Accumulate state updates

    for (let i = 0; i < initialContent.length; i++) {
      const sentenceItem = initialContent[i];
      const imageQuery = sentenceItem.image_retrieval;

      if (!imageQuery || imageQuery === 'error') {
        console.warn(`useEasyReadImageManager: Skipping sentence ${i} due to missing/error query.`);
        stateUpdates[i] = { ...loadingState[i], isLoading: false, error: 'No query available' };
        failureCount++;
        setRefreshProgress(Math.round(((i + 1) / initialContent.length) * 100));
        continue;
      }

      let retryCount = 0;
      let fetchedImages = [];
      // Create excludeList for *this* iteration using current usedImageIds
      const excludeList = preventDuplicateImages ? [...usedImageIds] : []; 
      
      // Log the exclude list being sent for this iteration
      console.log(`Hook - Sentence ${i}: Querying with excludeList:`, JSON.stringify(excludeList));

      while (retryCount < 3 && fetchedImages.length === 0) {
        try {
          const response = await findSimilarImages(imageQuery, resultsPerQuery, excludeList);
          if (response.data.results && response.data.results.length > 0) {
            fetchedImages = response.data.results;
          } else if (preventDuplicateImages && usedImageIds && usedImageIds.length > 0 && retryCount === 0) {
             const fallbackResponse = await findSimilarImages(imageQuery, resultsPerQuery, []);
             if (fallbackResponse.data.results && fallbackResponse.data.results.length > 0) {
               fetchedImages = fallbackResponse.data.results;
             }
          }
        } catch (error) {
          console.error(`useEasyReadImageManager: Error in findSimilarImages retry ${retryCount} for sentence ${i}:`, error);
        }
        retryCount++;
        if (fetchedImages.length === 0 && retryCount < 3) await new Promise(resolve => setTimeout(resolve, 500));
      }

      // Filter the fetched images AFTER the loop (handles both initial and fallback results)
      let finalSelectableImages = fetchedImages;
      if (preventDuplicateImages && excludeList.length > 0) {
          finalSelectableImages = fetchedImages.filter(img => {
              const imageId = img.id || img.url; // Use ID or URL as identifier
              return imageId && !excludeList.includes(imageId); // Check if identifier is in exclude list
          });
          if (finalSelectableImages.length < fetchedImages.length) {
              console.log(`Hook - Sentence ${i}: Filtered ${fetchedImages.length - finalSelectableImages.length} image(s) based on excludeList.`);
          }
      }
      
      if (finalSelectableImages.length > 0) {
        // De-duplicate based on ID or URL
        const imageMap = new Map();
        finalSelectableImages.forEach(img => { 
            const imageId = img.id || img.url; // Use consistent identifier
            if (imageId && !imageMap.has(imageId)) { 
                imageMap.set(imageId, img); 
            }
        });
        const uniqueImages = Array.from(imageMap.values());

        const bestImage = uniqueImages[0];
        const bestImagePath = bestImage.url;
        // Explicitly define the ID we will use for exclusion
        const bestImageIdToExclude = bestImage.id || bestImage.url; 
        
        console.log(`Hook - Sentence ${i}: Best image ID selected (for exclusion): ${bestImageIdToExclude}`);

        // Update the main usedImageIds list *immediately* if needed, for the *next* iteration
        if (preventDuplicateImages && bestImageIdToExclude && usedImageIds) {
          if (!usedImageIds.includes(bestImageIdToExclude)) { 
              console.log(`Hook - Sentence ${i}: Adding ID ${bestImageIdToExclude} to usedImageIds for next exclusion.`);
              usedImageIds.push(bestImageIdToExclude); 
          } else {
              console.log(`Hook - Sentence ${i}: ID ${bestImageIdToExclude} was already in usedImageIds.`);
          }
        } else if (preventDuplicateImages && !bestImageIdToExclude) {
             // This should be less likely now with the fallback
             console.warn(`Hook - Sentence ${i}: Best image result missing a usable ID (id or url). Cannot add to exclusion list.`);
        }

        // Prepare state update for this sentence
        stateUpdates[i] = {
          images: uniqueImages, // Use the de-duplicated list based on the identifier
          selectedPath: bestImagePath,
          isLoading: false,
          isGenerating: false,
          error: null
        };
        
        // Trigger backend update (fire and forget in loop)
        if (contentId !== null) {
            updateSavedContentImage(contentId, i, bestImagePath, uniqueImages.map(img => img.url))
                .catch(err => console.error(`useEasyReadImageManager: Failed background update for sentence ${i}:`, err));
        }
        successCount++;
      } else {
        // Handle case where filtering left no usable images
        const reason = preventDuplicateImages && excludeList.length > 0 ? "after filtering excluded IDs" : "after retries";
        console.warn(`useEasyReadImageManager: Failed to find usable images for sentence ${i} ${reason}.`);
        stateUpdates[i] = { ...(loadingState[i] || {}), isLoading: false, error: 'No suitable image found' };
        failureCount++;
      }
       setRefreshProgress(Math.round(((i + 1) / initialContent.length) * 100));
       // Log the state of usedImageIds *at the end* of this iteration
       if (preventDuplicateImages) {
           console.log(`Hook - Sentence ${i}: End of iteration. Current usedImageIds:`, JSON.stringify(usedImageIds));
       }
    }

    // Apply all accumulated state updates at once after the loop
    setImageState(prev => ({ ...prev, ...stateUpdates }));
    setRefreshingAll(false);

    setNotification({
      open: true,
      message: `Image refresh complete: ${successCount} success, ${failureCount} failed`,
      severity: successCount > 0 ? (failureCount > 0 ? 'warning' : 'success') : 'error'
    });
    // Dependency array: Re-run if initialContent, contentId, or preventDuplicateImages changes.
    // Avoid including imageState here if possible to prevent potential loops, unless absolutely necessary for logic dependent on the *absolute latest* state during the async loop (which we try to avoid here by using snapshots and accumulating updates).
  }, [initialContent, contentId, preventDuplicateImages]); 

  // Function to close the notification snackbar
  const handleCloseNotification = useCallback((event, reason) => {
    if (reason === 'clickaway') return;
    setNotification(prev => ({ ...prev, open: false }));
  }, []);

  return {
    imageState,
    setImageState, // Expose if direct manipulation is needed outside
    preventDuplicateImages,
    setPreventDuplicateImages,
    refreshingAll,
    refreshProgress,
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleRefreshAllImages,
    handleCloseNotification
  };
}

export default useEasyReadImageManager; 