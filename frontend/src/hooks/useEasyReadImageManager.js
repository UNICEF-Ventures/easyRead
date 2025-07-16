import { useState, useEffect, useCallback, useRef } from 'react';
import { findSimilarImages, generateNewImage, updateSavedContentImage } from '../apiClient';

// Debounce utility function
const debounce = (func, delay) => {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    return new Promise((resolve, reject) => {
      timeoutId = setTimeout(async () => {
        try {
          const result = await func(...args);
          resolve(result);
        } catch (error) {
          reject(error);
        }
      }, delay);
    });
  };
};

// Create debounced version of findSimilarImages
const debouncedFindSimilarImages = debounce(findSimilarImages, 300);

// Cache for preventing duplicate concurrent requests
const requestCache = new Map();

// Enhanced findSimilarImages with caching and deduplication
const cachedFindSimilarImages = (query, n_results, excludeList = [], signal, imageSets = null) => {
  const cacheKey = JSON.stringify({ query, n_results, excludeList, imageSets });
  
  // Return existing promise if request is already in flight
  if (requestCache.has(cacheKey)) {
    return requestCache.get(cacheKey);
  }
  
  // Create new request and cache it
  const requestPromise = debouncedFindSimilarImages(query, n_results, excludeList, signal, imageSets)
    .finally(() => {
      // Remove from cache when request completes
      requestCache.delete(cacheKey);
    });
  
  requestCache.set(cacheKey, requestPromise);
  return requestPromise;
};

// Custom hook to manage image state and actions for EasyRead content
function useEasyReadImageManager(initialContent = [], contentId = null, selectedSets = [], preventDuplicateImages = true) {
  const [imageState, setImageState] = useState({});
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'success' });
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState(0);
  // Use ref to track fetch status for each index to prevent duplicate fetches
  const fetchingRef = useRef({});
  // Use ref to track content identity to avoid unnecessary refetches
  const contentRef = useRef(null);
  // AbortController for cancelling in-flight requests
  const abortControllerRef = useRef(null);
  // Track used images for duplicate prevention
  const usedImagesRef = useRef(new Set());
  // Track whether sequential attribution has been applied
  const sequentialAttributionAppliedRef = useRef(false);
  // Track current image selections for immediate access
  const currentImageSelectionsRef = useRef({});

  // Initialize or update image state when content changes
  useEffect(() => {
    // Cancel any existing requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    // Create new AbortController for this effect
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;
    if (!initialContent || initialContent.length === 0) {
      setImageState({});
      contentRef.current = null;
      return;
    }

    // Check if this is the same content reference we've already processed
    const isSameContentRef = initialContent === contentRef.current;
    if (isSameContentRef) {
      return;
    }

    // Update our content reference
    contentRef.current = initialContent;
    
    // Reset sequential attribution flag for new content
    sequentialAttributionAppliedRef.current = false;
    
    
    const initialImageState = {};
    const needsFetching = [];

    initialContent.forEach((item, index) => {
      // For saved content with existing selections, always update the state
      const hasSavedSelection = item.selected_image_path || (item.alternative_images && item.alternative_images.length > 0);
      const currentState = imageState[index];
      
      
      // Update if: no current state, or if we have saved data that differs from current state
      if (!currentState || (hasSavedSelection && currentState.selectedPath !== item.selected_image_path)) {
        const shouldFetch = !item.selected_image_path && item.image_retrieval && item.image_retrieval !== 'error';
        
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
       
       // Initialize currentImageSelectionsRef with initial selections
       Object.keys(initialImageState).forEach(index => {
         const indexNum = parseInt(index);
         if (initialImageState[index].selectedPath !== undefined) {
           currentImageSelectionsRef.current[indexNum] = initialImageState[index].selectedPath;
         }
       });
    }

    // Fetch initial images if any were marked
    const fetchMissingImages = async () => {
        if (needsFetching.length === 0) {
          // Ensure fetchingRef is cleared even if no fetch happens
          needsFetching.forEach(index => { fetchingRef.current[index] = false; }); 
          return;
        }

        // Ensure isLoading is true for items we are about to fetch
        setImageState(prev => {
            const loadingUpdates = { ...prev }; 
            needsFetching.forEach(index => {
                if(!loadingUpdates[index]) {
                    loadingUpdates[index] = { 
                        images: [], 
                        selectedPath: null, 
                        isLoading: true, 
                        error: null 
                    };
                } else {
                    loadingUpdates[index] = {
                        ...loadingUpdates[index],
                        isLoading: true
                    };
                }
            });
            return loadingUpdates;
        });

        // Array to hold results from each promise
        let fetchResults = []; 
        try {
            // Process in smaller batches to avoid overwhelming the backend
            const BATCH_SIZE = 1; // Reduce to 1 to avoid overwhelming the backend during model loading
            const batches = [];
            for (let i = 0; i < needsFetching.length; i += BATCH_SIZE) {
                batches.push(needsFetching.slice(i, i + BATCH_SIZE));
            }

            fetchResults = [];
            
            // Process batches sequentially with delay between them
            for (const batch of batches) {
                const batchResults = await Promise.all(batch.map(async (index) => {
                    const item = initialContent[index];
                    // No need to read current state here, we build the update from scratch

                    if (item.image_retrieval && item.image_retrieval !== 'error') {
                        try {
                            const response = await Promise.race([
                                cachedFindSimilarImages(item.image_retrieval, 10, [], signal, selectedSets),
                                new Promise((_, reject) => 
                                    setTimeout(() => reject(new Error('Request timeout')), 50000) // 50 seconds to allow for backend timeout
                                )
                            ]);
                        
                        // Check if request was aborted
                        if (signal.aborted) {
                            return { index: index, update: { isLoading: false, error: 'Request cancelled' } };
                        }
                        
                        let images = response.data.results || [];
                        
                        
                        // Return the update object for this index
                        const result = {
                            index: index,
                            update: {
                                images: images,
                                selectedPath: preventDuplicateImages ? null : (images.length > 0 ? images[0].url : null),
                                isLoading: preventDuplicateImages && images.length > 0, // Keep loading if duplicate prevention is enabled and we have images
                                error: images.length === 0 ? 'No images found' : null
                            }
                        };
                        
                        // Explicit cleanup to help GC
                        images = null;
                        return result;
                    } catch {
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
                     return {
                        index: index,
                        update: { isLoading: false, error: 'Fetch cancelled or invalid keyword' }
                    };                   
                }
            }));
            
            // Add results from this batch to the overall results
            fetchResults.push(...batchResults);
            
            // Add delay between batches to prevent overwhelming the backend
            if (batches.indexOf(batch) < batches.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 100)); // Minimal delay for sequential processing
            }
        }
        } catch {
              // If Promise.all fails catastrophically, we might not have individual results
              // Create error updates for all initially requested indices
              fetchResults = needsFetching.map(index => ({
                index: index,
                update: { isLoading: false, error: 'Batch fetch failed' }
              }));
        }
        
        // Don't process if aborted
        if (signal.aborted) {
            // Reset fetching status before returning
            needsFetching.forEach(index => {
              fetchingRef.current[index] = false;
            });
            return;
        }
              
              // Process results in batches to avoid memory spikes
              const batchSize = 10;
              const processBatch = (startIndex) => {
                  if (!fetchResults || fetchResults.length === 0) {
                      return;
                  }
                  const endIndex = Math.min(startIndex + batchSize, fetchResults.length);
                  const batchUpdates = {};
                  
                  for (let i = startIndex; i < endIndex; i++) {
                      const result = fetchResults[i];
                      if (result) {
                          batchUpdates[result.index] = result.update;
                          // Don't clear result yet - wait until all batches are done
                      }
                  }
                  
                  // Apply batch updates
                  // Build the new state outside of setState
                  const newState = {};
                  
                  // Get current state
                  const currentState = imageState;
                  
                  // Copy existing state
                  Object.keys(currentState).forEach(key => {
                      newState[key] = currentState[key];
                  });
                  
                  // Apply batch updates
                  Object.keys(batchUpdates).forEach(idx => {
                      const oldState = currentState[idx];
                      const updateData = batchUpdates[idx];
                      
                      newState[idx] = {
                          ...(oldState || {}),
                          ...updateData
                      };
                  });
                  
                  setImageState(newState);
                  
                  // Explicit cleanup to help GC
                  Object.keys(batchUpdates).forEach(key => {
                      delete batchUpdates[key];
                  });
                  
                  // Process next batch if there are more results
                  if (endIndex < fetchResults.length) {
                      setTimeout(() => processBatch(endIndex), 0);
                  } else {
                      // All batches processed - clean up
                      if (fetchResults) {
                          fetchResults.length = 0;
                          fetchResults = null;
                      }
                  }
              };
              
              // Start batch processing
              if (fetchResults.length > 0) {
                  processBatch(0);
              }
              
        // Reset fetching status for all initially targeted indices
        // NOTE: Cleanup will happen after all batches are processed
        needsFetching.forEach(index => {
          fetchingRef.current[index] = false;
        });
    };

    fetchMissingImages();
    
  // IMPORTANT: Only run this effect when initialContent reference changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialContent]);
  
  // Sequential attribution effect for duplicate prevention
  useEffect(() => {
    if (!preventDuplicateImages || !initialContent || initialContent.length === 0) {
      sequentialAttributionAppliedRef.current = false;
      return;
    }
    
    // Don't apply sequential attribution if we're viewing saved content (contentId is provided)
    // Saved content should preserve user's manual selections
    if (contentId !== null) {
      sequentialAttributionAppliedRef.current = true; // Mark as applied to prevent future runs
      return;
    }
    
    // Only apply once per content load
    if (sequentialAttributionAppliedRef.current) {
      return;
    }
    
    // Check if we have enough loaded images to start attribution
    const loadedStates = Object.keys(imageState).filter(index => {
      const state = imageState[index];
      return state && state.images && state.images.length > 0;
    });
    
    const hasLoadedImages = loadedStates.length > 0;
    
    if (!hasLoadedImages) {
      return; // Wait for images to load
    }
    
    // Apply sequential attribution immediately when images are available
    setImageState(currentState => {
      // Double check we have loaded images in current state
      const currentLoadedStates = Object.keys(currentState).filter(index => {
        const state = currentState[index];
        return state && state.images && state.images.length > 0;
      });
      
      if (currentLoadedStates.length === 0) {
        return currentState;
      }
      
      // Apply sequential attribution
      const usedImageIds = new Set();
      const updates = {};
      
      // Process sentences in order
      for (let i = 0; i < initialContent.length; i++) {
        const state = currentState[i];
        if (state) {
          if (state.images && state.images.length > 0) {
            // Find the first image that hasn't been used yet
            let selectedPath = null;
            
            for (const img of state.images) {
              const imageId = img.id || img.url;
              if (!usedImageIds.has(imageId)) {
                selectedPath = img.url;
                usedImageIds.add(imageId);
                break;
              }
            }
            
            // Always update when duplicate prevention is enabled to ensure proper assignment
            updates[i] = {
              ...state,
              selectedPath: selectedPath,
              isLoading: false, // Turn off loading when sequential attribution is applied
              error: selectedPath ? null : 'No unique images available'
            };
            
          } else if (state.isLoading) {
            // If this sentence is still loading or has no images, turn off loading
            updates[i] = {
              ...state,
              isLoading: false
            };
          }
        }
      }
      
      // Apply updates if there are any
      if (Object.keys(updates).length > 0) {
        const newState = { ...currentState };
        Object.keys(updates).forEach(index => {
          newState[index] = updates[index];
        });
        
        // Update the used images ref
        usedImagesRef.current = usedImageIds;
        sequentialAttributionAppliedRef.current = true;
        
        // Sync the current selections ref with the new state
        Object.keys(newState).forEach(index => {
          const indexNum = parseInt(index);
          if (newState[index].selectedPath !== undefined) {
            currentImageSelectionsRef.current[indexNum] = newState[index].selectedPath;
          }
        });
        
        return newState;
      } else {
        // Still mark as applied to prevent repeated checks
        sequentialAttributionAppliedRef.current = true;
        usedImagesRef.current = usedImageIds;
      }
      
      return currentState;
    });
  }, [preventDuplicateImages, initialContent, imageState]);
  
  // Cleanup effect for AbortController and request cache
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      // Clear any pending requests from cache
      requestCache.clear();
    };
  }, []); 

  // Memoize the image selection change handler to prevent unnecessary re-renders
  const handleImageSelectionChange = useCallback(async (sentenceIndex, newPath) => {
    
    // Update the state directly - always respect user choice, no deduplication enforcement
    setImageState(prev => {
      const currentState = prev[sentenceIndex];
      
      if (!currentState) {
        return prev;
      }
      
      // Always honor user selection without deduplication enforcement
      const newState = {
        ...prev,
        [sentenceIndex]: {
          ...currentState,
          selectedPath: newPath,
          isGenerating: false,
          error: null
        }
      };
      
      
      // Update the current selections ref immediately for synchronous access
      currentImageSelectionsRef.current[sentenceIndex] = newPath;
      
      
      // Update used images tracking for reference (but don't enforce conflicts)
      if (preventDuplicateImages) {
        const currentImageId = currentState.selectedPath;
        const newImageId = newPath;
        
        if (currentImageId) usedImagesRef.current.delete(currentImageId);
        if (newImageId) usedImagesRef.current.add(newImageId);
      }
      
      return newState;
    });

    // If it's saved content, update the backend
    if (contentId !== null) {
      
      try {
        // Get the current state to extract image URLs
        const currentState = imageState[sentenceIndex];
        if (currentState) {
          const allImageUrls = currentState.images.map(img => img.url);
          // Ensure the newly selected path is included if it wasn't already an option
          if (newPath && !allImageUrls.includes(newPath)) {
             allImageUrls.push(newPath);
          }
          
          
          await updateSavedContentImage(contentId, sentenceIndex, newPath, allImageUrls);
          setNotification({ open: true, message: 'Image selection saved', severity: 'success' });
          
        }
      } catch (err) {
        console.error(`useEasyReadImageManager: Error updating saved image for sentence ${sentenceIndex}:`, err);
        setNotification({ open: true, message: 'Failed to save image selection', severity: 'error' });
        // Revert optimistic update on error
        setImageState(prev => {
          const currentState = prev[sentenceIndex];
          if (currentState) {
            return {
              ...prev,
              [sentenceIndex]: { ...currentState, selectedPath: currentState.selectedPath }
            };
          }
          return prev;
        });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contentId, preventDuplicateImages]); // Remove imageState dependency to prevent infinite loops

  // Memoize the generate image handler to prevent unnecessary re-renders
  const handleGenerateImage = useCallback(async (sentenceIndex, prompt) => {
    if (!prompt) {
      setNotification({ open: true, message: 'Cannot generate image without a prompt.', severity: 'warning' });
      return;
    }

    // Store original state for potential revert
    let originalState;
    setImageState(prev => {
      originalState = prev[sentenceIndex] || { images: [], selectedPath: null, error: null, isLoading: false };
      return {
        ...prev,
        [sentenceIndex]: {
          ...originalState,
          isLoading: false,
          isGenerating: true,
          error: null
        }
      };
    });

    try {
      const response = await generateNewImage(prompt);
      
      let newImages = [];
      let newSelectedPath = null;

      if (response && response.all_generated_images && response.all_generated_images.length > 0) {
        console.log("useEasyReadImageManager: Processing all_generated_images from backend:", response.all_generated_images);
        newImages = response.all_generated_images.map(img => ({ url: img.url, id: img.id }));
        newSelectedPath = newImages[0].url;
        setNotification({ open: true, message: `Generated ${newImages.length} images. First one selected.`, severity: 'success' });
      } else if (response && response.new_image_url && response.new_image_id) {
        console.warn("useEasyReadImageManager: Using single image from backend (new_image_url).");
        newImages = [{ url: response.new_image_url, id: response.new_image_id }];
        newSelectedPath = response.new_image_url;
        setNotification({ open: true, message: 'Image generated successfully', severity: 'success' });
      } else {
        console.error("useEasyReadImageManager: Backend did not return valid image data.");
        throw new Error("Backend did not return a valid new image ID and URL.");
      }
      
      // Combine existing images with new images, ensuring uniqueness
      const existingImages = originalState.images || [];
      const combinedImagesMap = new Map();

      // Add existing images to the map first
      existingImages.forEach(img => {
        const key = img.id || img.url;
        if (key) combinedImagesMap.set(key, img);
      });

      // Add new images
      newImages.forEach(img => {
        const key = img.id || img.url;
        if (key) combinedImagesMap.set(key, img);
      });
      
      const finalCombinedImages = Array.from(combinedImagesMap.values());
      
      // Explicit cleanup to help with garbage collection
      combinedImagesMap.clear();
      
      // Clear references to help GC
      existingImages.length = 0;
      newImages.length = 0;
      
      setImageState(prev => ({
        ...prev,
        [sentenceIndex]: {
          ...originalState,
          images: finalCombinedImages,
          selectedPath: newSelectedPath,
          isLoading: false,
          isGenerating: false,
          error: null
        }
      }));

      // If it's saved content, update the backend
      if (contentId !== null) {
        try {
          const allAlternativeUrls = finalCombinedImages.map(img => img.url);
          await updateSavedContentImage(contentId, sentenceIndex, newSelectedPath, allAlternativeUrls);
        } catch (err) {
          console.error(`useEasyReadImageManager: Error updating saved image after generation for sentence ${sentenceIndex}:`, err);
          setNotification({ open: true, message: 'Failed to save newly generated image selection', severity: 'error' });
        }
      }
    } catch (err) {
      console.error(`useEasyReadImageManager: Error generating image for sentence ${sentenceIndex}:`, err);
      setImageState(prev => ({
        ...prev,
        [sentenceIndex]: { ...originalState, isGenerating: false, error: 'Image generation failed' }
      }));
      setNotification({ open: true, message: 'Image generation failed. Please try again.', severity: 'error' });
    }
  }, [contentId]); // Remove imageState dependency to prevent infinite loops


  // Function to refresh all images
  const handleRefreshAllImages = useCallback(async () => {
    if (!initialContent || initialContent.length === 0) {
      setNotification({ open: true, message: 'No content available to refresh images', severity: 'warning' });
      return;
    }

    // Cancel any existing requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    // Create new AbortController for this refresh
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;

    setRefreshingAll(true);
    setRefreshProgress(0);

    // Set all items to loading state
    setImageState(prev => {
      const newState = {};
      initialContent.forEach((item, index) => {
        newState[index] = {
          ...prev[index] || { images: [], selectedPath: null },
          isLoading: true,
          isGenerating: false,
          error: null
        };
      });
      return newState;
    });

    let successCount = 0;
    let failureCount = 0;
    const usedImageIds = preventDuplicateImages ? new Set() : null;

    try {
      if (preventDuplicateImages) {
        // Sequential processing for duplicate prevention
        // Step 1: Fetch 10 images for each sentence
        const allImageResults = [];
        
        for (let i = 0; i < initialContent.length; i++) {
          const item = initialContent[i];
          if (item.image_retrieval && item.image_retrieval !== 'error') {
            try {
              const response = await cachedFindSimilarImages(item.image_retrieval, 10, [], signal, selectedSets);
              if (signal.aborted) break;
              
              const images = response.data.results || [];
              allImageResults[i] = { images, success: images.length > 0 };
            } catch {
              allImageResults[i] = { images: [], success: false, error: 'Failed to fetch' };
            }
          } else {
            allImageResults[i] = { images: [], success: false, error: 'No valid keyword' };
          }
          
          // Update progress
          setRefreshProgress(Math.round(((i + 1) / initialContent.length) * 50)); // 50% for fetching
        }

        if (signal.aborted) return;

        // Step 2: Sequential attribution - assign first available image to each sentence
        const finalUpdates = {};
        for (let i = 0; i < initialContent.length; i++) {
          const result = allImageResults[i];
          if (result && result.success) {
            // Find the first image that hasn't been used yet
            let selectedPath = null;
            
            for (const img of result.images) {
              const imageId = img.id || img.url;
              if (!usedImageIds.has(imageId)) {
                selectedPath = img.url;
                usedImageIds.add(imageId);
                break;
              }
            }
            
            finalUpdates[i] = {
              images: result.images,
              selectedPath: selectedPath,
              isLoading: false,
              error: selectedPath ? null : 'No unique images available'
            };
            
            if (selectedPath) successCount++;
            else failureCount++;
          } else {
            finalUpdates[i] = {
              images: [],
              selectedPath: null,
              isLoading: false,
              error: result?.error || 'No images found'
            };
            failureCount++;
          }
        }

        // Apply all updates at once
        setImageState(prev => {
          const newState = { ...prev };
          Object.keys(finalUpdates).forEach(index => {
            newState[index] = { ...prev[index], ...finalUpdates[index] };
          });
          return newState;
        });
        
        // Update the used images ref with the current selection
        usedImagesRef.current = new Set(usedImageIds);
        
        // Set progress to 100% when complete
        setRefreshProgress(100);
        
      } else {
        // Parallel processing when duplicate prevention is disabled
        // Clear used images ref since duplicate prevention is disabled
        usedImagesRef.current = new Set();
        
        const BATCH_SIZE = 3;
        const DELAY_BETWEEN_BATCHES = 1000;

        for (let i = 0; i < initialContent.length; i += BATCH_SIZE) {
          const endIndex = Math.min(i + BATCH_SIZE, initialContent.length);
          const batchPromises = [];

          for (let j = i; j < endIndex; j++) {
            const item = initialContent[j];
            if (item.image_retrieval && item.image_retrieval !== 'error') {
              batchPromises.push(
                cachedFindSimilarImages(item.image_retrieval, 10, [], signal, selectedSets)
                  .then(response => {
                    if (signal.aborted) return null;
                    const images = response.data.results || [];
                    
                    return {
                      index: j,
                      update: {
                        images: images,
                        selectedPath: images.length > 0 ? images[0].url : null,
                        isLoading: false,
                        error: images.length === 0 ? 'No images found' : null
                      },
                      success: images.length > 0
                    };
                  })
                  .catch(() => ({
                    index: j,
                    update: { isLoading: false, error: 'Failed to fetch' },
                    success: false
                  }))
              );
            } else {
              batchPromises.push(Promise.resolve({
                index: j,
                update: { isLoading: false, error: 'No valid keyword' },
                success: false
              }));
            }
          }

          const batchResults = await Promise.all(batchPromises);
          
          if (signal.aborted) break;

          // Update state with batch results
          const batchUpdates = {};
          batchResults.forEach(result => {
            if (result) {
              batchUpdates[result.index] = result.update;
              if (result.success) successCount++;
              else failureCount++;
            }
          });

          setImageState(prev => {
            const newState = { ...prev };
            Object.keys(batchUpdates).forEach(index => {
              newState[index] = { ...prev[index], ...batchUpdates[index] };
            });
            return newState;
          });

          // Update progress
          setRefreshProgress(Math.round((endIndex / initialContent.length) * 100));

          // Delay between batches to avoid overwhelming the server
          if (endIndex < initialContent.length && !signal.aborted) {
            await new Promise(resolve => setTimeout(resolve, DELAY_BETWEEN_BATCHES));
          }
        }
      }
    } catch (error) {
      console.error('Error during batch refresh:', error);
    }

    if (!signal.aborted) {
      setRefreshingAll(false);
      setNotification({
        open: true,
        message: `Image refresh complete: ${successCount} success, ${failureCount} failed`,
        severity: successCount > 0 ? (failureCount > 0 ? 'warning' : 'success') : 'error'
      });
    }
  }, [initialContent, preventDuplicateImages, selectedSets]);

  // Function to close the notification snackbar
  const handleCloseNotification = useCallback((event, reason) => {
    if (reason === 'clickaway') return;
    setNotification(prev => ({ ...prev, open: false }));
  }, []);

  // Function to get current image selections (synchronous access)
  const getCurrentImageSelections = useCallback(() => {
    const currentSelections = {};
    
    // Combine keys from both imageState and the ref to ensure we don't miss any selections
    const allIndices = new Set([
      ...Object.keys(imageState).map(k => parseInt(k)),
      ...Object.keys(currentImageSelectionsRef.current).map(k => parseInt(k))
    ]);
    
    allIndices.forEach(indexNum => {
      // Prefer the ref value if available (most recent), otherwise use state
      const refValue = currentImageSelectionsRef.current[indexNum];
      const stateValue = imageState[indexNum]?.selectedPath;
      currentSelections[indexNum] = refValue || stateValue || null;
    });
    
    
    return currentSelections;
  }, [imageState]);

  return {
    imageState,
    setImageState, // Expose if direct manipulation is needed outside
    preventDuplicateImages,
    refreshingAll,
    refreshProgress,
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleRefreshAllImages,
    handleCloseNotification,
    getCurrentImageSelections // Expose function to get current selections
  };
}

export default useEasyReadImageManager; 