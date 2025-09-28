import { useState, useEffect, useCallback, useMemo } from 'react';
import useEasyReadImageManager from './useEasyReadImageManager';

/**
 * Unified content management hook for both saved and new content
 * Handles content state, editing, and image management consistently
 */
const useContentManager = (initialContent, contentId = null, selectedSets = [], preventDuplicateImages = true) => {
  // Unified content state
  const [content, setContent] = useState(initialContent);
  
  // Update content when initial content changes
  useEffect(() => {
    setContent(initialContent);
  }, [initialContent]);

  // Memoize the easy read content for the image manager
  const memoizedEasyReadContent = useMemo(() => 
    content?.easy_read_content || [], 
    [content?.easy_read_content]
  );

  // Use the image management hook
  const imageManagerResult = useEasyReadImageManager(
    memoizedEasyReadContent, 
    contentId, 
    selectedSets, 
    preventDuplicateImages
  );

  // Handle sentence changes from inline editing (same pattern as SavedContentDetailPage)
  const handleSentenceChange = useCallback((index, newSentence) => {
    setContent(prevContent => {
      if (!prevContent?.easy_read_content) return prevContent;
      
      const updatedEasyReadContent = [...prevContent.easy_read_content];
      updatedEasyReadContent[index] = {
        ...updatedEasyReadContent[index],
        sentence: newSentence
      };
      
      return {
        ...prevContent,
        easy_read_content: updatedEasyReadContent
      };
    });
    
    console.log(`Sentence at index ${index} changed to: "${newSentence}"`);
  }, []);

  // Handle highlight changes for sentences (same pattern as SavedContentDetailPage)
  const handleHighlightChange = useCallback((index, highlighted) => {
    setContent(prevContent => {
      if (!prevContent?.easy_read_content) return prevContent;
      
      const updatedEasyReadContent = [...prevContent.easy_read_content];
      updatedEasyReadContent[index] = {
        ...updatedEasyReadContent[index],
        highlighted: highlighted
      };
      
      return {
        ...prevContent,
        easy_read_content: updatedEasyReadContent
      };
    });
    
    console.log(`Sentence at index ${index} highlight changed to: ${highlighted}`);
  }, []);

  // Handle sentence reordering from drag and drop
  const handleReorderSentences = useCallback((newOrder) => {
    console.log('Sentences reordered:', newOrder);
    
    // Find which item was moved by comparing with current content
    const currentContent = content?.easy_read_content || [];
    let oldIndex = -1;
    let newIndex = -1;
    
    // Find the item that changed position
    for (let i = 0; i < newOrder.length; i++) {
      if (i < currentContent.length && newOrder[i] !== currentContent[i]) {
        // Found a difference, now find where this item came from
        const movedItem = newOrder[i];
        oldIndex = currentContent.findIndex(item => item === movedItem);
        newIndex = i;
        break;
      }
    }
    
    // If we found valid indices, reorder content and notify image manager
    if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
      imageManagerResult.handleReorderContent?.(oldIndex, newIndex, newOrder.length);
    }
    
    // Update content state
    setContent(prevContent => ({
      ...prevContent,
      easy_read_content: newOrder
    }));
  }, [content?.easy_read_content, imageManagerResult.handleReorderContent]);

  // Update content with new easy read content (for revisions)
  const updateEasyReadContent = useCallback((newEasyReadContent) => {
    setContent(prevContent => ({
      ...prevContent,
      easy_read_content: newEasyReadContent
    }));
  }, []);

  return {
    // Content state
    content,
    setContent,
    updateEasyReadContent,
    
    // Editing handlers
    handleSentenceChange,
    handleHighlightChange,
    handleReorderSentences,
    
    // Image manager integration
    ...imageManagerResult,
    
    // Computed values
    isEmpty: !content?.easy_read_content || content.easy_read_content.length === 0,
    easyReadContent: content?.easy_read_content || []
  };
};

export default useContentManager;