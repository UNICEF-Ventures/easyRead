"""
Image allocation optimization for EasyRead.
Implements fast approximate algorithms that scale well with any number of sentences or images.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import heapq
import time

logger = logging.getLogger(__name__)


class ImageAllocationOptimizer:
    """
    Fast approximate image allocation optimizer.
    Uses hybrid greedy + local search for optimal scalability.
    """
    
    def __init__(self, prevent_duplicates: bool = True):
        self.prevent_duplicates = prevent_duplicates
        self.metrics = {}
    
    def optimize_allocation(self, batch_results: Dict[str, List[Dict]], options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main optimization function that selects the best algorithm based on problem size.
        
        Args:
            batch_results: {"0": [{"id": 123, "url": "...", "similarity": 0.85}, ...], ...}
            options: Configuration options
            
        Returns:
            {
                "allocation": {"0": {"image_id": 123, "image_url": "...", "similarity": 0.85}, ...},
                "metrics": {"algorithm": "...", "total_similarity": 0.0, "processing_time_ms": 0}
            }
        """
        start_time = time.time()
        
        # Default options
        default_options = {
            'similarity_threshold': 0.1,  # Ignore very low similarities
            'uniqueness_bonus': 0.15,     # Bonus for images that appear in fewer sentences
            'high_similarity_threshold': 0.8,  # Threshold for "obviously good" matches
            'local_search_iterations': 2,  # Number of local search improvement rounds
            'enable_local_search': True    # Enable local search optimization
        }
        
        if options:
            default_options.update(options)
        options = default_options
        
        try:
            # Convert batch results to internal format
            sentences = self._prepare_sentence_data(batch_results, options['similarity_threshold'])
            
            if not sentences:
                return {
                    "allocation": {},
                    "metrics": {
                        "algorithm": "none",
                        "total_similarity": 0.0,
                        "processing_time_ms": 0,
                        "sentences_processed": 0
                    }
                }
            
            # Apply fast approximate algorithm
            allocation = self._fast_approximate_allocation(sentences, options)
            
            # Optional local search improvement
            if options['enable_local_search'] and len(sentences) <= 50:  # Skip for very large documents
                allocation = self._local_search_optimization(sentences, allocation, options)
            
            # Calculate metrics
            processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            metrics = self._calculate_metrics(allocation, processing_time, len(sentences))
            
            # Format results for API response
            formatted_allocation = self._format_allocation_for_response(allocation)
            
            logger.info(f"Image allocation completed: {metrics}")
            
            return {
                "allocation": formatted_allocation,
                "metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Error in optimize_allocation: {e}")
            processing_time = (time.time() - start_time) * 1000
            return {
                "allocation": {},
                "metrics": {
                    "algorithm": "error",
                    "total_similarity": 0.0,
                    "processing_time_ms": processing_time,
                    "error": str(e)
                }
            }
    
    def _prepare_sentence_data(self, batch_results: Dict[str, List[Dict]], similarity_threshold: float) -> List[Dict]:
        """Convert batch results to internal sentence format with filtering."""
        sentences = []
        
        for sentence_idx_str, images in batch_results.items():
            try:
                sentence_idx = int(sentence_idx_str)
                
                # Filter images by similarity threshold
                filtered_images = [
                    img for img in images 
                    if isinstance(img.get('similarity'), (int, float)) and img.get('similarity', 0) >= similarity_threshold
                ]
                
                if filtered_images:
                    sentences.append({
                        'index': sentence_idx,
                        'images': filtered_images,
                        'original_count': len(images),
                        'filtered_count': len(filtered_images)
                    })
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid sentence index {sentence_idx_str}: {e}")
        
        # Sort sentences by number of available images (ascending)
        # Sentences with fewer options should be processed first
        sentences.sort(key=lambda s: s['filtered_count'])
        
        return sentences
    
    def _fast_approximate_allocation(self, sentences: List[Dict], options: Dict) -> Dict[int, Dict]:
        """
        Fast approximate allocation using multi-phase greedy approach.
        
        Phase 1: Handle obvious high-similarity matches
        Phase 2: Smart greedy allocation with uniqueness bonus
        Phase 3: Fill remaining with best available
        """
        allocation = {}
        used_images = set()
        
        # Phase 1: Assign obvious high-similarity matches first
        obvious_matches = []
        for sentence in sentences:
            best_img = None
            best_score = 0
            
            for img in sentence['images']:
                similarity = img.get('similarity', 0)
                if similarity >= options['high_similarity_threshold']:
                    if similarity > best_score:
                        best_score = similarity
                        best_img = img
            
            if best_img:
                image_id = str(best_img.get('id', best_img.get('url', '')))
                if self.prevent_duplicates and image_id not in used_images:
                    obvious_matches.append((sentence['index'], best_img, best_score))
                    used_images.add(image_id)
                elif not self.prevent_duplicates:
                    obvious_matches.append((sentence['index'], best_img, best_score))
        
        # Sort obvious matches by similarity and assign
        obvious_matches.sort(key=lambda x: x[2], reverse=True)
        for sentence_idx, img, similarity in obvious_matches:
            allocation[sentence_idx] = {
                'image': img,
                'similarity': similarity,
                'phase': 'obvious'
            }
        
        # Phase 2: Smart greedy for remaining sentences
        remaining_sentences = [s for s in sentences if s['index'] not in allocation]
        
        if remaining_sentences:
            # Calculate image uniqueness scores
            image_usage_count = defaultdict(int)
            for sentence in remaining_sentences:
                for img in sentence['images']:
                    image_id = str(img.get('id', img.get('url', '')))
                    image_usage_count[image_id] += 1
            
            # Create candidate pairs with enhanced scoring
            candidates = []
            for sentence in remaining_sentences:
                for img in sentence['images']:
                    image_id = str(img.get('id', img.get('url', '')))
                    
                    # Skip if already used (duplicate prevention)
                    if self.prevent_duplicates and image_id in used_images:
                        continue
                    
                    similarity = img.get('similarity', 0)
                    uniqueness_bonus = options['uniqueness_bonus'] / max(1, image_usage_count[image_id])
                    combined_score = similarity + uniqueness_bonus
                    
                    candidates.append({
                        'sentence_idx': sentence['index'],
                        'image': img,
                        'similarity': similarity,
                        'combined_score': combined_score,
                        'image_id': image_id
                    })
            
            # Sort by combined score and assign greedily
            candidates.sort(key=lambda x: x['combined_score'], reverse=True)
            assigned_sentences = set(allocation.keys())
            
            for candidate in candidates:
                sentence_idx = candidate['sentence_idx']
                image_id = candidate['image_id']
                
                # Skip if sentence already assigned or image already used
                if sentence_idx in assigned_sentences:
                    continue
                if self.prevent_duplicates and image_id in used_images:
                    continue
                
                allocation[sentence_idx] = {
                    'image': candidate['image'],
                    'similarity': candidate['similarity'],
                    'phase': 'smart_greedy'
                }
                
                assigned_sentences.add(sentence_idx)
                used_images.add(image_id)
        
        # Phase 3: Fill any remaining sentences with best available
        unassigned_sentences = [s for s in sentences if s['index'] not in allocation]
        
        for sentence in unassigned_sentences:
            best_img = None
            best_similarity = -1
            
            for img in sentence['images']:
                image_id = str(img.get('id', img.get('url', '')))
                similarity = img.get('similarity', 0)
                
                # For duplicate prevention, only consider unused images
                if self.prevent_duplicates and image_id in used_images:
                    continue
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_img = img
            
            if best_img:
                allocation[sentence['index']] = {
                    'image': best_img,
                    'similarity': best_similarity,
                    'phase': 'fallback'
                }
                
                if self.prevent_duplicates:
                    image_id = str(best_img.get('id', best_img.get('url', '')))
                    used_images.add(image_id)
        
        return allocation
    
    def _local_search_optimization(self, sentences: List[Dict], initial_allocation: Dict[int, Dict], options: Dict) -> Dict[int, Dict]:
        """
        Local search optimization to improve allocation by trying beneficial swaps.
        """
        allocation = initial_allocation.copy()
        iterations = options.get('local_search_iterations', 2)
        
        for iteration in range(iterations):
            improved = False
            sentence_indices = list(allocation.keys())
            
            # Try pairwise swaps
            for i in range(len(sentence_indices)):
                for j in range(i + 1, len(sentence_indices)):
                    idx1, idx2 = sentence_indices[i], sentence_indices[j]
                    
                    # Get current images
                    current_img1 = allocation[idx1]['image']
                    current_img2 = allocation[idx2]['image']
                    current_total = allocation[idx1]['similarity'] + allocation[idx2]['similarity']
                    
                    # Find sentences data
                    sentence1 = next(s for s in sentences if s['index'] == idx1)
                    sentence2 = next(s for s in sentences if s['index'] == idx2)
                    
                    # Check if swap would improve total similarity
                    img1_in_s2 = next((img for img in sentence2['images'] 
                                     if str(img.get('id', img.get('url', ''))) == str(current_img1.get('id', current_img1.get('url', '')))), None)
                    img2_in_s1 = next((img for img in sentence1['images'] 
                                     if str(img.get('id', img.get('url', ''))) == str(current_img2.get('id', current_img2.get('url', '')))), None)
                    
                    if img1_in_s2 and img2_in_s1:
                        new_total = img1_in_s2.get('similarity', 0) + img2_in_s1.get('similarity', 0)
                        
                        if new_total > current_total:
                            # Beneficial swap found
                            allocation[idx1]['image'] = current_img2
                            allocation[idx1]['similarity'] = img2_in_s1.get('similarity', 0)
                            allocation[idx1]['phase'] = 'local_search'
                            
                            allocation[idx2]['image'] = current_img1
                            allocation[idx2]['similarity'] = img1_in_s2.get('similarity', 0)
                            allocation[idx2]['phase'] = 'local_search'
                            
                            improved = True
            
            if not improved:
                break  # No more improvements found
        
        return allocation
    
    def _calculate_metrics(self, allocation: Dict[int, Dict], processing_time_ms: float, sentences_count: int) -> Dict[str, Any]:
        """Calculate allocation quality metrics."""
        if not allocation:
            return {
                "algorithm": "approximate_greedy",
                "total_similarity": 0.0,
                "average_similarity": 0.0,
                "processing_time_ms": processing_time_ms,
                "sentences_processed": sentences_count,
                "sentences_assigned": 0,
                "assignment_rate": 0.0
            }
        
        similarities = [item['similarity'] for item in allocation.values()]
        phases = defaultdict(int)
        for item in allocation.values():
            phases[item.get('phase', 'unknown')] += 1
        
        return {
            "algorithm": "approximate_greedy",
            "total_similarity": sum(similarities),
            "average_similarity": sum(similarities) / len(similarities),
            "processing_time_ms": processing_time_ms,
            "sentences_processed": sentences_count,
            "sentences_assigned": len(allocation),
            "assignment_rate": len(allocation) / max(1, sentences_count),
            "phase_breakdown": dict(phases)
        }
    
    def _format_allocation_for_response(self, allocation: Dict[int, Dict]) -> Dict[str, Dict[str, Any]]:
        """Format allocation for API response."""
        formatted = {}
        
        for sentence_idx, assignment in allocation.items():
            image = assignment['image']
            
            formatted[str(sentence_idx)] = {
                "image_id": image.get('id'),
                "image_url": image.get('url'),
                "similarity": assignment['similarity'],
                "algorithm_phase": assignment.get('phase', 'unknown'),
                "filename": image.get('filename', ''),
                "set_name": image.get('set_name', ''),
                "description": image.get('description', ''),
                "file_format": image.get('file_format', '')
            }
        
        return formatted


def optimize_image_allocation(batch_results: Dict[str, List[Dict]], prevent_duplicates: bool = True, options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Convenience function for image allocation optimization.
    
    Args:
        batch_results: Batch image search results from find_similar_images_batch
        prevent_duplicates: Whether to prevent duplicate image assignments
        options: Additional configuration options
        
    Returns:
        Allocation results with metrics
    """
    optimizer = ImageAllocationOptimizer(prevent_duplicates=prevent_duplicates)
    return optimizer.optimize_allocation(batch_results, options)


def analyze_allocation_problem(batch_results: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """
    Analyze the allocation problem characteristics for debugging and optimization.
    
    Args:
        batch_results: Batch image search results
        
    Returns:
        Problem analysis metrics
    """
    if not batch_results:
        return {"error": "No batch results provided"}
    
    sentences_count = len(batch_results)
    total_images = sum(len(images) for images in batch_results.values())
    
    # Count unique images
    unique_images = set()
    image_usage_count = defaultdict(int)
    similarity_distribution = []
    
    for images in batch_results.values():
        for img in images:
            image_id = str(img.get('id', img.get('url', '')))
            unique_images.add(image_id)
            image_usage_count[image_id] += 1
            
            similarity = img.get('similarity', 0)
            if isinstance(similarity, (int, float)):
                similarity_distribution.append(similarity)
    
    avg_images_per_sentence = total_images / sentences_count if sentences_count > 0 else 0
    avg_sentences_per_image = sum(image_usage_count.values()) / len(unique_images) if unique_images else 0
    avg_similarity = sum(similarity_distribution) / len(similarity_distribution) if similarity_distribution else 0
    
    return {
        "sentences_count": sentences_count,
        "total_image_options": total_images,
        "unique_images": len(unique_images),
        "avg_images_per_sentence": round(avg_images_per_sentence, 2),
        "avg_sentences_per_image": round(avg_sentences_per_image, 2),
        "avg_similarity": round(avg_similarity, 3),
        "similarity_range": {
            "min": min(similarity_distribution) if similarity_distribution else 0,
            "max": max(similarity_distribution) if similarity_distribution else 0
        },
        "complexity": "low" if sentences_count <= 10 else ("medium" if sentences_count <= 30 else "high"),
        "sparsity": "high" if avg_sentences_per_image < 2 else ("medium" if avg_sentences_per_image < 4 else "low")
    }