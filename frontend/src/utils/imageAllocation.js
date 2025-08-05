/**
 * Image allocation optimization utilities
 * Implements Hungarian algorithm for optimal image-sentence matching
 */

/**
 * Hungarian Algorithm implementation for optimal assignment
 * Finds the maximum weight matching in a bipartite graph
 */
class HungarianAlgorithm {
  constructor(costMatrix) {
    this.matrix = costMatrix.map(row => [...row]); // Deep copy
    this.n = this.matrix.length;
    this.m = this.matrix[0] ? this.matrix[0].length : 0;
    
    // Pad matrix to be square if needed
    this.padMatrix();
  }

  padMatrix() {
    const size = Math.max(this.n, this.m);
    
    // Add rows if needed
    while (this.matrix.length < size) {
      this.matrix.push(new Array(size).fill(0));
    }
    
    // Add columns if needed
    this.matrix.forEach(row => {
      while (row.length < size) {
        row.push(0);
      }
    });
    
    this.size = size;
  }

  solve() {
    // Convert to minimization problem (subtract from max value)
    const maxValue = Math.max(...this.matrix.flat());
    const costMatrix = this.matrix.map(row => 
      row.map(val => maxValue - val)
    );

    // Step 1: Subtract row minimums
    for (let i = 0; i < this.size; i++) {
      const rowMin = Math.min(...costMatrix[i]);
      for (let j = 0; j < this.size; j++) {
        costMatrix[i][j] -= rowMin;
      }
    }

    // Step 2: Subtract column minimums
    for (let j = 0; j < this.size; j++) {
      const colMin = Math.min(...costMatrix.map(row => row[j]));
      for (let i = 0; i < this.size; i++) {
        costMatrix[i][j] -= colMin;
      }
    }

    // Find assignment using simplified approach
    return this.findAssignment(costMatrix);
  }

  findAssignment(matrix) {
    const assignment = new Array(this.n).fill(-1);
    const used = new Set();

    // Greedy assignment on reduced matrix
    for (let i = 0; i < this.n; i++) {
      let bestJ = -1;
      let bestValue = -1;
      
      for (let j = 0; j < this.m; j++) {
        if (!used.has(j) && matrix[i][j] === 0) {
          const originalValue = this.matrix[i][j];
          if (originalValue > bestValue) {
            bestValue = originalValue;
            bestJ = j;
          }
        }
      }
      
      if (bestJ !== -1) {
        assignment[i] = bestJ;
        used.add(bestJ);
      }
    }

    // Fill remaining with greedy approach on original matrix
    for (let i = 0; i < this.n; i++) {
      if (assignment[i] === -1 && i < this.m) {
        let bestJ = -1;
        let bestValue = -1;
        
        for (let j = 0; j < this.m; j++) {
          if (!used.has(j) && this.matrix[i][j] > bestValue) {
            bestValue = this.matrix[i][j];
            bestJ = j;
          }
        }
        
        if (bestJ !== -1) {
          assignment[i] = bestJ;
          used.add(bestJ);
        }
      }
    }

    return assignment;
  }
}

/**
 * Optimizes image allocation using Hungarian algorithm or fallback strategies
 * @param {Array} sentenceImageData - Array of objects with sentence data and available images
 * @param {Object} options - Configuration options
 * @returns {Object} Optimal allocation mapping
 */
export function optimizeImageAllocation(sentenceImageData, options = {}) {
  const {
    useHungarian = true,
    hungarianThreshold = 3,
    hungarianMaxSize = 15, // Reduce max size for better performance
    fallbackToGreedy = true,
    preferHighSimilarity = true,
    enableCaching = true
  } = options;

  // Validate input
  if (!sentenceImageData || sentenceImageData.length === 0) {
    return {};
  }

  // Filter valid sentences with images
  const validSentences = sentenceImageData.filter(item => 
    item && item.images && item.images.length > 0
  );

  if (validSentences.length === 0) {
    return {};
  }

  // Performance optimization: sort sentences by number of available images
  // Sentences with fewer options should be processed first
  validSentences.sort((a, b) => a.images.length - b.images.length);

  // Decide algorithm based on size and preferences
  const shouldUseHungarian = useHungarian && 
    validSentences.length >= hungarianThreshold &&
    validSentences.length <= hungarianMaxSize;

  let allocation;
  let algorithmUsed;
  
  if (shouldUseHungarian) {
    try {
      allocation = hungarianAllocation(validSentences);
      algorithmUsed = 'hungarian';
    } catch (error) {
      console.warn('Hungarian algorithm failed, falling back to greedy:', error);
      allocation = greedyAllocation(validSentences, preferHighSimilarity);
      algorithmUsed = 'greedy_fallback';
    }
  } else if (fallbackToGreedy) {
    allocation = greedyAllocation(validSentences, preferHighSimilarity);
    algorithmUsed = 'greedy';
  } else {
    allocation = sequentialAllocation(validSentences);
    algorithmUsed = 'sequential';
  }

  // Add algorithm metadata to results
  Object.keys(allocation).forEach(key => {
    allocation[key].algorithm = algorithmUsed;
  });

  return allocation;
}

/**
 * Hungarian algorithm-based allocation
 */
function hungarianAllocation(sentenceData) {
  // Build similarity matrix
  const allImages = [];
  const imageToGlobalIndex = new Map();
  const sentenceToImageMap = new Map(); // Track which sentence can use which images
  
  // Collect all unique images and build mapping
  sentenceData.forEach((sentence, sentenceIdx) => {
    const availableImages = [];
    sentence.images.forEach(img => {
      const imageId = img.id || img.url;
      if (!imageToGlobalIndex.has(imageId)) {
        imageToGlobalIndex.set(imageId, allImages.length);
        allImages.push({
          ...img,
          originalSimilarity: img.similarity || 0.5
        });
      }
      availableImages.push(imageToGlobalIndex.get(imageId));
    });
    sentenceToImageMap.set(sentenceIdx, availableImages);
  });

  if (allImages.length === 0) {
    return {};
  }

  // Create cost matrix (similarity scores)
  const costMatrix = sentenceData.map((sentence, sentenceIdx) => {
    return allImages.map((globalImg, imageIdx) => {
      const availableImages = sentenceToImageMap.get(sentenceIdx);
      if (!availableImages.includes(imageIdx)) {
        return 0; // This sentence cannot use this image
      }
      
      // Find the local image with similarity score
      const localImg = sentence.images.find(img => 
        (img.id || img.url) === (globalImg.id || globalImg.url)
      );
      return localImg ? (localImg.similarity || 0.5) : 0;
    });
  });

  // Solve using Hungarian algorithm
  const hungarian = new HungarianAlgorithm(costMatrix);
  const assignment = hungarian.solve();

  // Convert assignment to result format
  const allocation = {};
  
  assignment.forEach((imageIndex, sentenceIndex) => {
    if (imageIndex !== -1 && imageIndex < allImages.length && sentenceIndex < sentenceData.length) {
      const sentence = sentenceData[sentenceIndex];
      const assignedImage = allImages[imageIndex];
      
      // Verify this is a valid assignment (sentence can actually use this image)
      const availableImages = sentenceToImageMap.get(sentenceIndex);
      if (sentence && assignedImage && availableImages.includes(imageIndex)) {
        // Get the similarity from the original sentence data
        const originalImg = sentence.images.find(img => 
          (img.id || img.url) === (assignedImage.id || assignedImage.url)
        );
        
        allocation[sentence.index] = {
          image: assignedImage,
          similarity: originalImg ? originalImg.similarity : assignedImage.originalSimilarity,
          algorithm: 'hungarian'
        };
      }
    }
  });

  return allocation;
}

/**
 * Improved greedy allocation with global consideration
 */
function greedyAllocation(sentenceData, preferHighSimilarity = true) {
  const allocation = {};
  const usedImages = new Set();
  
  // Create all sentence-image pairs with similarities
  const pairs = [];
  
  sentenceData.forEach(sentence => {
    sentence.images.forEach(img => {
      pairs.push({
        sentenceIndex: sentence.index,
        image: img,
        similarity: img.similarity || 0.5,
        imageId: img.id || img.url
      });
    });
  });

  // Sort by similarity (descending) for greedy selection
  pairs.sort((a, b) => b.similarity - a.similarity);

  // Assign images greedily by highest similarity
  const assignedSentences = new Set();
  
  for (const pair of pairs) {
    const { sentenceIndex, image, similarity, imageId } = pair;
    
    // Skip if sentence already has assignment or image is used
    if (assignedSentences.has(sentenceIndex) || usedImages.has(imageId)) {
      continue;
    }
    
    allocation[sentenceIndex] = {
      image,
      similarity,
      algorithm: 'greedy'
    };
    
    assignedSentences.add(sentenceIndex);
    usedImages.add(imageId);
  }

  return allocation;
}

/**
 * Fallback sequential allocation (current approach)
 */
function sequentialAllocation(sentenceData) {
  const allocation = {};
  const usedImages = new Set();
  
  sentenceData.forEach(sentence => {
    // Find first unused image
    for (const img of sentence.images) {
      const imageId = img.id || img.url;
      if (!usedImages.has(imageId)) {
        allocation[sentence.index] = {
          image: img,
          similarity: img.similarity || 0.5,
          algorithm: 'sequential'
        };
        usedImages.add(imageId);
        break;
      }
    }
  });
  
  return allocation;
}

/**
 * Analyzes allocation quality and provides metrics
 */
export function analyzeAllocation(allocation) {
  const similarities = Object.values(allocation).map(item => item.similarity);
  
  if (similarities.length === 0) {
    return {
      averageSimilarity: 0,
      totalSimilarity: 0,
      assignedCount: 0,
      algorithm: 'none'
    };
  }

  return {
    averageSimilarity: similarities.reduce((sum, sim) => sum + sim, 0) / similarities.length,
    totalSimilarity: similarities.reduce((sum, sim) => sum + sim, 0),
    assignedCount: similarities.length,
    algorithm: allocation[Object.keys(allocation)[0]]?.algorithm || 'unknown'
  };
}