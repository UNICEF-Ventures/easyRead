import { useState, useEffect, useCallback, useRef } from 'react';
import { findSimilarImages, findSimilarImagesBatch, generateNewImage, updateSavedContentImage } from '../apiClient';

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
  const [userKeywords, setUserKeywords] = useState({}); // Store user-input keywords per sentence
  const [imageSearchSource, setImageSearchSource] = useState({}); // Track search source: 'original' | 'custom'
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
  // Flag to prevent useEffect reinitialization during reordering
  const isReorderingRef = useRef(false);

  // Initialize or update image state when content changes
  useEffect(() => {
    // Skip if we're in the middle of reordering
    if (isReorderingRef.current) {
      return;
    }

    if (!initialContent || initialContent.length === 0) {
      setImageState({});
      setUserKeywords({});
      contentRef.current = null;
      // Clear any used images tracking
      usedImagesRef.current.clear();
      return;
    }

    // Check if this is the same content we've already processed
    // Compare by serialized structure instead of object reference to handle recreated objects
    const contentSignature = JSON.stringify(initialContent?.map(item => ({ 
      sentence: item.sentence, 
      image_retrieval: item.image_retrieval 
    })));
    
    if (contentSignature === contentRef.current) {
      if (import.meta.env.DEV) {
        console.log('🔄 Content signature unchanged, skipping image fetch');
      }
      return;
    }

    // Check if this is just a reordering of the same content
    const currentContentItems = initialContent?.map(item => ({ 
      sentence: item.sentence, 
      image_retrieval: item.image_retrieval 
    })) || [];
    
    const sortedContentSignature = JSON.stringify([...currentContentItems].sort((a, b) => a.sentence.localeCompare(b.sentence)));
    
    let previousSortedSignature = null;
    if (contentRef.current) {
      try {
        const previousContentItems = JSON.parse(contentRef.current);
        previousSortedSignature = JSON.stringify([...previousContentItems].sort((a, b) => a.sentence.localeCompare(b.sentence)));
      } catch (e) {
        // If parsing fails, treat as not reordering
        previousSortedSignature = null;
      }
    }
    
    const isReordering = previousSortedSignature === sortedContentSignature && contentRef.current !== null;

    // Update our content signature BEFORE starting operations to prevent StrictMode double-execution
    contentRef.current = contentSignature;

    if (import.meta.env.DEV) {
      console.log('🔄 Content signature changed. Previous:', previousSortedSignature?.substring(0, 100) + '...');
      console.log('🔄 Current sorted:', sortedContentSignature?.substring(0, 100) + '...');
      console.log('🔄 Is reordering:', isReordering);
    }

    if (isReordering) {
      if (import.meta.env.DEV) {
        console.log('🔄 Content reordering detected, skipping reinitialization');
      }
      return; // Skip reinitialization for reordering
    }

    if (import.meta.env.DEV) {
      console.log('🔄 Content signature changed, starting new image fetch');
    }
    
    // Clean up old keywords that are no longer relevant when content changes
    setUserKeywords(prev => {
      const relevantKeywords = {};
      Object.keys(prev).forEach(index => {
        const numIndex = parseInt(index);
        if (numIndex < initialContent.length) {
          relevantKeywords[index] = prev[index];
        }
      });
      return relevantKeywords;
    });

    // Cancel any existing requests ONLY when content actually changes
    if (abortControllerRef.current) {
      if (import.meta.env.DEV) {
        console.log('🚫 Aborting existing image fetch requests due to content change');
      }
      abortControllerRef.current.abort();
    }
    
    // Create new AbortController for this effect
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;
    
    // Reset sequential attribution flag for new content
    sequentialAttributionAppliedRef.current = false;
    
    
    const initialImageState = {};
    const initialUserKeywords = {};
    const needsFetching = [];

    initialContent.forEach((item, index) => {
      // For saved content with existing selections, always update the state
      const hasSavedSelection = item.selected_image_path || (item.alternative_images && item.alternative_images.length > 0);
      const currentState = imageState[index];
      
      
      // Update if: no current state, or if we have saved data that differs from current state
      if (!currentState || (hasSavedSelection && currentState.selectedPath !== item.selected_image_path)) {
        const shouldFetch = !item.selected_image_path && item.image_retrieval && item.image_retrieval !== 'error';
        
        // Build the complete images array including both selected and alternatives
        let allImages = [];
        
        // Start with alternative images if they exist
        if (item.alternative_images && item.alternative_images.length > 0) {
          if (import.meta.env.DEV) {
            console.log('🖼️ Processing alternative_images:', item.alternative_images);
          }
          
          allImages = item.alternative_images.map(imageItem => {
            // Handle both old format (URL strings) and new format (enhanced objects)
            if (typeof imageItem === 'string') {
              if (import.meta.env.DEV) {
                console.log('📝 Found string URL:', imageItem);
              }
              return { url: imageItem };
            } else if (imageItem && typeof imageItem === 'object') {
              // Preserve the enhanced object with all metadata
              if (import.meta.env.DEV) {
                console.log('📝 Found enhanced object:', imageItem);
              }
              return imageItem;
            } else {
              if (import.meta.env.DEV) {
                console.log('📝 Found unknown format:', imageItem);
              }
              return { url: imageItem };
            }
          });
        }
        
        // Ensure selected image is included (might not be in alternatives)
        if (item.selected_image_path) {
          const selectedExists = allImages.some(img => img.url === item.selected_image_path);
          if (!selectedExists) {
            // Try to find enhanced data for selected image, fallback to simple format
            const selectedImageData = { url: item.selected_image_path };
            allImages.unshift(selectedImageData); // Add to beginning
          }
        }
        
        // If no images at all, use selected as the only image
        if (allImages.length === 0 && item.selected_image_path) {
          allImages = [{ url: item.selected_image_path }];
        }

        initialImageState[index] = {
          images: allImages,
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
      
      // Initialize user keywords from saved content
      if (item.user_keywords) {
        initialUserKeywords[index] = item.user_keywords;
      }
    });
    
    if (Object.keys(initialImageState).length > 0) {
       setImageState(prev => ({ ...prev, ...initialImageState }));
    }
    
    if (Object.keys(initialUserKeywords).length > 0) {
       setUserKeywords(prev => ({ ...prev, ...initialUserKeywords }));
       
       // Initialize currentImageSelectionsRef with initial selections
       Object.keys(initialImageState).forEach(index => {
         const indexNum = parseInt(index);
         if (initialImageState[index].selectedPath !== undefined) {
           currentImageSelectionsRef.current[indexNum] = initialImageState[index].selectedPath;
         }
       });
    }

    // Fetch initial images using batch processing
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

        try {
            // Prepare batch queries - collect all valid queries
            const batchQueries = [];
            const queryIndexMap = {}; // Map to track which query corresponds to which sentence index
            
            needsFetching.forEach(index => {
                const item = initialContent[index];
                if (item.image_retrieval && item.image_retrieval !== 'error') {
                    const queryIndex = batchQueries.length;
                    batchQueries.push({
                        index: queryIndex,
                        query: item.image_retrieval,
                        n_results: 10
                    });
                    queryIndexMap[queryIndex] = index;
                }
            });

            if (batchQueries.length === 0) {
                // No valid queries to process - set all to "No image"
                const noImageUpdates = {};
                needsFetching.forEach(index => {
                    fetchingRef.current[index] = false;
                    noImageUpdates[index] = {
                        isLoading: false,
                        error: 'No image'
                    };
                });
                
                setImageState(prev => ({
                    ...prev,
                    ...noImageUpdates
                }));
                return;
            }

            // Make single batch API call (includes image allocation optimization)
            if (import.meta.env.DEV) {
                console.log('🔍 Fetching images and optimizing allocation for', batchQueries.length, 'sentences...');
            }
            
            const response = await Promise.race([
                findSimilarImagesBatch(batchQueries, [], signal, selectedSets),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Batch request timeout')), 300000) // 5 minutes timeout for large batches
                )
            ]);

            // Check if request was aborted
            if (signal.aborted) {
                if (import.meta.env.DEV) {
                    console.log('🚫 Batch image request was aborted after completion');
                }
                needsFetching.forEach(index => {
                    fetchingRef.current[index] = false;
                });
                return;
            }

            const batchResults = response.data.results || {};
            const optimalAllocation = response.data.optimal_allocation || {};
            const allocationMetrics = response.data.allocation_metrics || {};
            const stateUpdates = {};

            // Log allocation metrics in development
            if (import.meta.env.DEV && Object.keys(allocationMetrics).length > 0) {
                console.log('🎯 Backend image allocation metrics:', allocationMetrics);
            }

            // Process batch results with optimal allocation
            Object.keys(batchResults).forEach(queryIndexStr => {
                const queryIndex = parseInt(queryIndexStr);
                const sentenceIndex = queryIndexMap[queryIndex];
                const images = batchResults[queryIndexStr] || [];

                if (sentenceIndex !== undefined) {
                    // Check if backend provided optimal allocation for this sentence
                    const backendAllocation = optimalAllocation[sentenceIndex];
                    let selectedPath = null;
                    let isLoading = false;

                    if (backendAllocation && backendAllocation.image_url) {
                        // Use backend's optimal selection
                        selectedPath = backendAllocation.image_url;
                        if (import.meta.env.DEV) {
                            console.log(`📍 Sentence ${sentenceIndex}: Using backend allocation (similarity: ${backendAllocation.similarity?.toFixed(3)})`);
                        }
                    } else if (preventDuplicateImages && images.length > 0) {
                        // No backend allocation - will be handled by frontend allocation effect
                        selectedPath = null;
                        isLoading = true;
                    } else if (images.length > 0) {
                        // No duplicate prevention - use first image
                        selectedPath = images[0].url;
                    }

                    stateUpdates[sentenceIndex] = {
                        images: images,
                        selectedPath: selectedPath,
                        isLoading: isLoading,
                        error: images.length === 0 ? 'No images found' : null,
                        backendAllocated: !!backendAllocation
                    };
                }
            });

            // Handle queries that didn't return results (failed on backend)
            needsFetching.forEach(index => {
                const item = initialContent[index];
                if (item.image_retrieval && item.image_retrieval !== 'error' && !stateUpdates[index]) {
                    stateUpdates[index] = {
                        isLoading: false,
                        error: 'Failed to fetch'
                    };
                } else if (!item.image_retrieval || item.image_retrieval === 'error') {
                    stateUpdates[index] = {
                        isLoading: false,
                        error: 'Invalid keyword'
                    };
                }
            });

            // Apply all updates at once
            setImageState(prev => ({
                ...prev,
                ...stateUpdates
            }));

        } catch (error) {
            // Handle batch request failure
            if (import.meta.env.DEV) {
                if (error.name === 'CanceledError' || error.code === 'ERR_CANCELED') {
                    console.log('🚫 Batch image fetch was cancelled:', error.message);
                } else {
                    console.error('❌ Batch image fetch failed with error:', error);
                }
            }
            
            const errorUpdates = {};
            needsFetching.forEach(index => {
                // If request was cancelled, it might be due to no images being available
                // Show a more user-friendly message
                let errorMessage = 'No image';
                
                // Only show technical error messages for non-cancellation errors
                if (!signal.aborted && error.name !== 'CanceledError') {
                    errorMessage = 'Failed to fetch';
                }
                
                errorUpdates[index] = {
                    isLoading: false,
                    error: errorMessage
                };
            });

            setImageState(prev => ({
                ...prev,
                ...errorUpdates
            }));
        }
        
        // Reset fetching status for all initially targeted indices
        needsFetching.forEach(index => {
          fetchingRef.current[index] = false;
        });
    };

    fetchMissingImages();
    
  // IMPORTANT: Only run this effect when initialContent reference changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialContent]);
  
  // Fallback allocation effect for sentences without backend allocation
  useEffect(() => {
    if (!preventDuplicateImages || !initialContent || initialContent.length === 0) {
      sequentialAttributionAppliedRef.current = false;
      return;
    }
    
    // Don't apply allocation if we're viewing saved content (contentId is provided)
    // Saved content should preserve user's manual selections
    if (contentId !== null) {
      sequentialAttributionAppliedRef.current = true; // Mark as applied to prevent future runs
      return;
    }
    
    // Only apply once per content load
    if (sequentialAttributionAppliedRef.current) {
      return;
    }
    
    // Check if we have loaded images that need frontend allocation
    const needsFrontendAllocation = Object.keys(imageState).filter(index => {
      const state = imageState[index];
      return state && 
             state.images && 
             state.images.length > 0 && 
             !state.backendAllocated && 
             state.isLoading; // Still loading means no selection made
    });
    
    if (needsFrontendAllocation.length === 0) {
      // No sentences need frontend allocation - either backend handled them or no images
      sequentialAttributionAppliedRef.current = true;
      return;
    }
    
    // Apply simple sequential allocation for remaining sentences
    setImageState(currentState => {
      const updates = {};
      const usedImageIds = new Set();
      
      // First, collect already used images from backend allocation
      Object.keys(currentState).forEach(index => {
        const state = currentState[index];
        if (state && state.backendAllocated && state.selectedPath) {
          // Extract image ID from URL for duplicate tracking
          const images = state.images || [];
          const selectedImg = images.find(img => img.url === state.selectedPath);
          if (selectedImg) {
            const imageId = selectedImg.id || selectedImg.url;
            usedImageIds.add(imageId);
          }
        }
      });
      
      // Apply sequential allocation to remaining sentences
      needsFrontendAllocation.forEach(indexStr => {
        const index = parseInt(indexStr);
        const state = currentState[index];
        
        if (state && state.images && state.images.length > 0) {
          // Find first unused image
          let selectedImage = null;
          
          for (const img of state.images) {
            const imageId = img.id || img.url;
            if (!usedImageIds.has(imageId)) {
              selectedImage = img;
              usedImageIds.add(imageId);
              break;
            }
          }
          
          updates[index] = {
            ...state,
            selectedPath: selectedImage ? selectedImage.url : null,
            isLoading: false,
            error: selectedImage ? null : 'No unique images available'
          };
        }
      });
      
      if (Object.keys(updates).length > 0) {
        const newState = { ...currentState };
        Object.keys(updates).forEach(index => {
          newState[index] = updates[index];
        });
        
        // Update refs
        usedImagesRef.current = usedImageIds;
        sequentialAttributionAppliedRef.current = true;
        
        // Sync current selections
        Object.keys(newState).forEach(index => {
          const indexNum = parseInt(index);
          if (newState[index].selectedPath !== undefined) {
            currentImageSelectionsRef.current[indexNum] = newState[index].selectedPath;
          }
        });
        
        if (import.meta.env.DEV) {
          console.log('🔄 Applied frontend fallback allocation for', Object.keys(updates).length, 'sentences');
        }
        
        return newState;
      } else {
        sequentialAttributionAppliedRef.current = true;
      }
      
      return currentState;
    });
  }, [preventDuplicateImages, initialContent]); // Removed imageState to prevent infinite loop
  
  // Cleanup effect for request cache only (no abort to prevent StrictMode conflicts)
  useEffect(() => {
    return () => {
      // Clear any pending requests from cache on unmount
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

  // Validation function for user keywords
  const validateKeywords = useCallback((keywords) => {
    if (!keywords || typeof keywords !== 'string') {
      return { valid: false, message: 'Keywords must be a non-empty text.' };
    }
    
    const trimmed = keywords.trim();
    if (trimmed.length === 0) {
      return { valid: false, message: 'Keywords cannot be empty.' };
    }
    
    if (trimmed.length > 500) {
      return { valid: false, message: 'Keywords cannot exceed 500 characters.' };
    }
    
    // Check for potentially problematic content
    if (trimmed.length < 2) {
      return { valid: false, message: 'Keywords must be at least 2 characters long.' };
    }
    
    return { valid: true, trimmed };
  }, []);

  // Memoize the generate image handler to prevent unnecessary re-renders
  const handleGenerateImage = useCallback(async (sentenceIndex, prompt, style = 'Mulberry') => {
    // Validate the input keywords
    const validation = validateKeywords(prompt);
    if (!validation.valid) {
      setNotification({ open: true, message: validation.message, severity: 'warning' });
      return;
    }

    const validatedPrompt = validation.trimmed;
    
    // Store the user keywords for this sentence
    setUserKeywords(prev => ({ ...prev, [sentenceIndex]: validatedPrompt }));

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
      const response = await generateNewImage(validatedPrompt, style);
      
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
      
      // Provide more specific error messages
      let errorMessage = 'Image generation failed. Please try again.';
      if (err.response) {
        // Server responded with error status
        if (err.response.status === 429) {
          errorMessage = 'Too many requests. Please wait a moment and try again.';
        } else if (err.response.status === 400) {
          errorMessage = 'Invalid keywords provided. Please check your input.';
        } else if (err.response.data?.error) {
          errorMessage = err.response.data.error;
        }
      } else if (err.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. The image generation service may be busy.';
      } else if (!navigator.onLine) {
        errorMessage = 'No internet connection. Please check your connection and try again.';
      }
      
      setImageState(prev => ({
        ...prev,
        [sentenceIndex]: { ...originalState, isGenerating: false, error: 'Image generation failed' }
      }));
      setNotification({ open: true, message: errorMessage, severity: 'error' });
    }
  }, [contentId, validateKeywords]); // Remove imageState dependency to prevent infinite loops

  // Function to search with custom keywords
  const handleSearchWithCustomKeywords = useCallback(async (sentenceIndex, keywords) => {
    // Validate the input keywords
    const validation = validateKeywords(keywords);
    if (!validation.valid) {
      setNotification({ open: true, message: validation.message, severity: 'warning' });
      return;
    }

    const validatedKeywords = validation.trimmed;
    
    // Store the user keywords for this sentence
    setUserKeywords(prev => ({ ...prev, [sentenceIndex]: validatedKeywords }));

    // Store original state for potential revert
    let originalState;
    setImageState(prev => {
      originalState = prev[sentenceIndex] || { images: [], selectedPath: null, error: null, isLoading: false };
      return {
        ...prev,
        [sentenceIndex]: {
          ...originalState,
          isLoading: true,
          error: null
        }
      };
    });

    try {
      // Debug logging for custom keyword search
      if (import.meta.env.DEV) {
        console.log(`🔍 Starting custom keyword search for: "${validatedKeywords}" in sets:`, selectedSets);
      }
      
      // Search for images using custom keywords
      const response = await cachedFindSimilarImages(validatedKeywords, 10, [], null, selectedSets);
      
      // Extract results from API response
      const images = response.data.results || [];
      
      if (images && images.length > 0) {
        const newImages = images.map(img => ({ 
          url: img.url, 
          id: img.id || img.url,
          description: img.description || 'No description'
        }));
        
        setImageState(prev => ({
          ...prev,
          [sentenceIndex]: {
            ...originalState,
            images: newImages,
            selectedPath: newImages[0].url, // Auto-select first result
            isLoading: false,
            error: null
          }
        }));
        
        // Track that this sentence is using custom search results
        setImageSearchSource(prev => ({ ...prev, [sentenceIndex]: 'custom' }));
        
        setNotification({ 
          open: true, 
          message: `Found ${newImages.length} images for "${validatedKeywords}"`, 
          severity: 'success' 
        });
        
        // Log success for debugging
        if (import.meta.env.DEV) {
          console.log(`🔍 Custom keyword search found ${newImages.length} images for: "${validatedKeywords}"`);
        }
        
        // Update current selections ref
        currentImageSelectionsRef.current[sentenceIndex] = newImages[0].url;
        
        // If it's saved content, update the backend
        if (contentId !== null) {
          try {
            const allAlternativeUrls = newImages.map(img => img.url);
            await updateSavedContentImage(contentId, sentenceIndex, newImages[0].url, allAlternativeUrls);
          } catch (err) {
            console.error(`useEasyReadImageManager: Error updating saved image after custom search for sentence ${sentenceIndex}:`, err);
            setNotification({ open: true, message: 'Found images but failed to save selection', severity: 'warning' });
          }
        }
      } else {
        // No results found
        setImageState(prev => ({
          ...prev,
          [sentenceIndex]: {
            ...originalState,
            isLoading: false,
            error: 'No images found'
          }
        }));
        
        setNotification({ 
          open: true, 
          message: `No images found for "${validatedKeywords}". Try different keywords or generate a new image.`, 
          severity: 'info' 
        });
      }
    } catch (err) {
      console.error(`useEasyReadImageManager: Error searching images with custom keywords for sentence ${sentenceIndex}:`, err);
      
      // Provide more specific error messages
      let errorMessage = 'Image search failed. Please try again.';
      if (err.response) {
        if (err.response.status === 429) {
          errorMessage = 'Too many requests. Please wait a moment and try again.';
        } else if (err.response.data?.error) {
          errorMessage = err.response.data.error;
        }
      } else if (!navigator.onLine) {
        errorMessage = 'No internet connection. Please check your connection and try again.';
      }
      
      setImageState(prev => ({
        ...prev,
        [sentenceIndex]: { ...originalState, isLoading: false, error: 'Search failed' }
      }));
      setNotification({ open: true, message: errorMessage, severity: 'error' });
    }
  }, [validateKeywords, selectedSets, contentId]);

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

  // Function to reorder both userKeywords and imageState when sentences are reordered
  const handleReorderContent = useCallback((oldIndex, newIndex, contentLength) => {
    // Prevent double execution with a more aggressive approach
    if (isReorderingRef.current) {
      return;
    }
    
    // Set flag immediately to prevent any race conditions
    isReorderingRef.current = true;
    
    // Reorder userKeywords
    setUserKeywords(prev => {
      // If there are no keywords to reorder, return current state
      if (Object.keys(prev).length === 0) {
        return prev;
      }
      
      // Create a completely new keywords object based on the full content length
      // We need to rebuild the entire mapping, not just reorder existing ones
      const newKeywords = {};
      
      // Use the passed contentLength parameter instead of initialContent length
      
      // Create an array representing all keyword positions
      const allKeywords = Array(contentLength).fill(null);
      
      // Fill in existing keywords at their current positions
      for (let i = 0; i < contentLength; i++) {
        if (prev[i]) {
          allKeywords[i] = prev[i];
        }
      }
      
      // Move the keyword from oldIndex to newIndex
      if (oldIndex < allKeywords.length && newIndex < allKeywords.length) {
        const [movedKeyword] = allKeywords.splice(oldIndex, 1);
        allKeywords.splice(newIndex, 0, movedKeyword);
      }
      
      // Rebuild the keywords object
      allKeywords.forEach((keyword, index) => {
        if (keyword) {
          newKeywords[index] = keyword;
        }
      });
      
      return newKeywords;
    });

    // Reorder imageState
    setImageState(prev => {
      // If there's no image state to reorder, return current state
      if (Object.keys(prev).length === 0) return prev;
      
      const newImageState = { ...prev };
      
      // Get the arrays of indices and their corresponding image states
      const indices = Object.keys(newImageState).map(k => parseInt(k)).sort((a, b) => a - b);
      const imageStateValues = indices.map(i => newImageState[i]);
      
      // Remove the old image states
      indices.forEach(i => delete newImageState[i]);
      
      // Create the reordered array by moving the item from oldIndex to newIndex
      const reorderedValues = [...imageStateValues];
      const [movedImageState] = reorderedValues.splice(oldIndex, 1);
      reorderedValues.splice(newIndex, 0, movedImageState);
      
      // Reassign image states to new indices
      reorderedValues.forEach((imageStateItem, index) => {
        if (imageStateItem) { // Only set if image state exists
          newImageState[index] = imageStateItem;
        }
      });
      
      return newImageState;
    });

    // Also update the current image selections ref
    const currentSelections = { ...currentImageSelectionsRef.current };
    const indices = Object.keys(currentSelections).map(k => parseInt(k)).sort((a, b) => a - b);
    const selectionValues = indices.map(i => currentSelections[i]);
    
    // Clear old selections
    indices.forEach(i => delete currentSelections[i]);
    
    // Reorder selections
    const reorderedSelections = [...selectionValues];
    const [movedSelection] = reorderedSelections.splice(oldIndex, 1);
    reorderedSelections.splice(newIndex, 0, movedSelection);
    
    // Reassign selections to new indices
    reorderedSelections.forEach((selection, index) => {
      if (selection) {
        currentSelections[index] = selection;
      }
    });
    
    currentImageSelectionsRef.current = currentSelections;
    
    // Reset flag after reordering is complete with a slightly longer delay
    setTimeout(() => {
      isReorderingRef.current = false;
    }, 100); // 100ms delay to ensure all React updates are processed
  }, []);

  return {
    imageState,
    userKeywords,
    imageSearchSource,
    setImageState, // Expose if direct manipulation is needed outside
    preventDuplicateImages,
    refreshingAll,
    refreshProgress,
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleSearchWithCustomKeywords,
    handleRefreshAllImages,
    handleCloseNotification,
    getCurrentImageSelections, // Expose function to get current selections
    handleReorderContent // Expose function to reorder both keywords and image state when sentences are reordered
  };
}

export default useEasyReadImageManager; 