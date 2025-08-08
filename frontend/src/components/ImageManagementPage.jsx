import React, { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { 
  Box, 
  Typography, 
  Button, 
  TextField, 
  Grid, 
  Card, 
  CardMedia, 
  CardContent, 
  Chip,
  CircularProgress, 
  Snackbar, 
  Alert,
  Paper,
  Container,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
  Stack,
  Badge,
  LinearProgress
} from '@mui/material';
import { styled } from '@mui/material/styles';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import SearchOffIcon from '@mui/icons-material/SearchOff';
import WarningIcon from '@mui/icons-material/Warning';
import { listImages, uploadImage, batchUploadImages, optimizedBatchUpload, uploadFolder, getImageSets } from '../apiClient';
import UploadProgressDialog from './UploadProgressDialog';
import ImageGallery from './ImageGallery';

// Maximum file size in bytes (5MB)
const MAX_FILE_SIZE = 5 * 1024 * 1024;

// Styled component for file input
const VisuallyHiddenInput = styled('input')({
  clip: 'rect(0 0 0 0)',
  clipPath: 'inset(50%)',
  height: 1,
  overflow: 'hidden',
  position: 'absolute',
  bottom: 0,
  left: 0,
  whiteSpace: 'nowrap',
  width: 1,
});

// Styled component for drop zone
const DropZone = styled(Box)(({ theme, isDragging }) => ({
  border: `2px dashed ${isDragging ? theme.palette.primary.main : theme.palette.divider}`,
  borderRadius: theme.shape.borderRadius,
  padding: theme.spacing(4),
  backgroundColor: isDragging ? theme.palette.action.hover : 'transparent',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'all 0.2s',
  cursor: 'pointer',
  minHeight: 150,
}));

const ImageManagementPage = () => {
  // Separate state for uploaded and generated images
  const [uploadedImages, setUploadedImages] = useState({}); // Now stores images by set
  // const [generatedImages, setGeneratedImages] = useState([]); // Removed - no longer used with new ImageGallery
  const [embeddingStats, setEmbeddingStats] = useState(null);
  
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingStage, setProcessingStage] = useState('uploading'); // 'uploading', 'processing', 'complete'
  const [isChunkedUpload, setIsChunkedUpload] = useState(false);
  const [currentChunk, setCurrentChunk] = useState(0);
  const [totalChunks, setTotalChunks] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [imageLabels, setImageLabels] = useState({}); // Track individual image labels
  const [imageSets, setImageSets] = useState([]);
  const [selectedSet, setSelectedSet] = useState('');
  const [newSetName, setNewSetName] = useState('');
  const [showNewSetDialog, setShowNewSetDialog] = useState(false);
  const [alert, setAlert] = useState({ open: false, message: '', severity: 'success' });
  
  // Folder upload mode state
  const [uploadMode, setUploadMode] = useState('folders'); // 'files' or 'folders'
  const [folderPreview, setFolderPreview] = useState({}); // Preview folder structure
  const [manualFolderName, setManualFolderName] = useState(''); // Manual folder name input
  const [showManualFolderName, setShowManualFolderName] = useState(false); // Show manual input
  const [editingFolder, setEditingFolder] = useState(null); // Which folder is being edited
  const [editFolderName, setEditFolderName] = useState(''); // Temp name while editing
  const [validationErrors, setValidationErrors] = useState([]); // File validation errors
  
  // Progress dialog state
  const [showProgressDialog, setShowProgressDialog] = useState(false);
  const [uploadSessionId, setUploadSessionId] = useState(null);

  // Clean up object URLs when component unmounts
  useEffect(() => {
    return () => {
      // Revoke any object URLs to avoid memory leaks
      selectedFiles.forEach(file => {
        if (file.preview) {
          URL.revokeObjectURL(file.preview);
        }
      });
    };
  }, [selectedFiles]);

  const fetchImages = useCallback(async () => {
    setLoading(true);
    try {
      const response = await listImages();
      console.log('API Response:', response.data);
      
      // Process the new API response structure - images_by_set
      const imagesBySet = response.data.images_by_set || {};
      
      // Store images grouped by set
      setUploadedImages(imagesBySet);
      
      // Store embedding statistics
      setEmbeddingStats(response.data.embedding_stats);
      
      // Generated images are now handled as part of imagesBySet 
    } catch (error) {
      console.error('Error fetching images:', error);
      showAlert('Error loading images', 'error');
      setUploadedImages({}); // Clear on error
      // Generated images cleared as part of imagesBySet
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchImageSets = useCallback(async () => {
    try {
      const response = await getImageSets();
      setImageSets(response.data.sets);
    } catch (error) {
      console.error('Error fetching image sets:', error);
    }
  }, []);

  // Fetch all images and sets on component mount
  useEffect(() => {
    fetchImages();
    fetchImageSets();
  }, [fetchImages, fetchImageSets]);

  // Generate default label from filename (consistent with backend)
  const generateDefaultLabel = (filename) => {
    return filename.replace(/\.[^/.]+$/, '') // Remove extension
                  .replace(/_/g, ' ')        // Replace underscores with spaces
                  .replace(/-/g, ' ')        // Replace hyphens with spaces
                  .trim();                   // Clean up whitespace
  };

  // File validation function
  const validateFiles = (files) => {
    const errors = [];
    const validFiles = [];
    const ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'];
    const ALLOWED_MIME_TYPES = [
      'image/png',
      'image/jpeg', 
      'image/gif',
      'image/webp',
      'image/svg+xml'
    ];
    
    files.forEach(file => {
      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`${file.name}: File too large (${(file.size / 1024 / 1024).toFixed(2)}MB, max: 5MB)`);
        return;
      }
      
      // Check file extension
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        errors.push(`${file.name}: Invalid file type (${ext})`);
        return;
      }
      
      // Check MIME type if available
      if (file.type && !ALLOWED_MIME_TYPES.includes(file.type) && file.type !== '') {
        errors.push(`${file.name}: Invalid MIME type (${file.type})`);
        return;
      }
      
      validFiles.push(file);
    });
    
    return { validFiles, errors };
  };

  const onDrop = (acceptedFiles) => {
    // Debug logging (can be removed in production)
    if (import.meta.env.DEV) {
      console.log('Files dropped:', acceptedFiles);
      console.log('Upload mode:', uploadMode);
      console.log('Files with webkitRelativePath:', acceptedFiles.filter(file => file.webkitRelativePath));
      
      // Detailed debugging for each file
      acceptedFiles.forEach((file, index) => {
        console.log(`File ${index}:`, {
          name: file.name,
          webkitRelativePath: file.webkitRelativePath,
          path: file.path,
          fullPath: file.fullPath,
          type: file.type,
          size: file.size
        });
      });
    }
    
    if (uploadMode === 'folders') {
      // Handle as incremental if there are already files selected
      const isIncremental = selectedFiles.length > 0;
      handleFolderDrop(acceptedFiles, isIncremental);
    } else {
      // Handle individual file upload (existing logic)
      handleFilesDrop(acceptedFiles);
    }
  };

  const handleFilesDrop = (acceptedFiles) => {
    // Comprehensive file validation
    const { validFiles, errors } = validateFiles(acceptedFiles);
    
    // Display validation errors
    if (errors.length > 0) {
      setValidationErrors(errors);
      showAlert(`Validation errors: ${errors.length} file(s) rejected`, 'error');
    } else {
      setValidationErrors([]);
    }
    
    // Stop if no valid files
    if (validFiles.length === 0) {
      return;
    }

    // Create preview URLs and default labels for valid files
    const filesWithPreviews = validFiles.map((file, index) => {
      const fileWithPreview = Object.assign(file, {
        preview: URL.createObjectURL(file),
        id: Date.now() + index // Unique ID for tracking
      });
      
      // Set default label
      setImageLabels(prev => ({
        ...prev,
        [fileWithPreview.id]: generateDefaultLabel(file.name)
      }));
      
      return fileWithPreview;
    });

    setSelectedFiles(prev => [...prev, ...filesWithPreviews]);
  };

  const handleFolderDrop = (acceptedFiles, isIncremental = false) => {
    // Comprehensive file validation
    const { validFiles, errors } = validateFiles(acceptedFiles);
    
    // Display validation errors
    if (errors.length > 0) {
      setValidationErrors(errors);
      showAlert(`Validation errors: ${errors.length} file(s) rejected`, 'error');
    } else {
      setValidationErrors([]);
    }
    
    // Stop if no valid files
    if (validFiles.length === 0) {
      return;
    }

    // Start with existing structure if incremental, otherwise start fresh
    const existingFolderStructure = isIncremental ? { ...folderPreview } : {};
    const existingFiles = isIncremental ? [...selectedFiles] : [];
    
    // Create a set of existing file paths for duplicate detection
    const existingFilePaths = new Set(
      existingFiles.map(file => `${file.webkitRelativePath || file.name}_${file.size}_${file.lastModified}`)
    );

    // Group files by folder structure and create preview URLs
    const newFolderStructure = { ...existingFolderStructure };
    const newFilesWithPreviews = [];
    let duplicatesFound = 0;
    
    validFiles.forEach((file, index) => {
      // Check for duplicates
      const fileSignature = `${file.webkitRelativePath || file.name}_${file.size}_${file.lastModified}`;
      if (existingFilePaths.has(fileSignature)) {
        duplicatesFound++;
        return; // Skip this file
      }

      // Generate label from filename (same logic as backend)
      const filename = file.name;
      const label = filename.replace(/\.[^/.]+$/, '') // Remove extension
                           .replace(/_/g, ' ')        // Replace underscores with spaces
                           .replace(/-/g, ' ')        // Replace hyphens with spaces
                           .trim();                   // Clean up whitespace

      // Create preview URL for each file
      const fileWithPreview = Object.assign(file, {
        preview: URL.createObjectURL(file),
        id: Date.now() + index + Math.random(), // More unique ID
        label: label // Add the generated label
      });

      // Try multiple ways to extract folder name
      let folderName = null; // Start with null to track if we found a name
      
      // Method 1: webkitRelativePath (most reliable)
      if (file.webkitRelativePath && file.webkitRelativePath.trim()) {
        if (file.webkitRelativePath.includes('/')) {
          const parts = file.webkitRelativePath.split('/').filter(part => part.trim());
          folderName = parts[0];
        } else {
          // If webkitRelativePath doesn't contain '/', it might be just the filename
          // In this case, we'll try other methods
        }
      }
      
      // Method 2: Check if file has path property
      if (!folderName && file.path && file.path.trim()) {
        if (file.path.includes('/')) {
          const parts = file.path.split('/').filter(part => part.trim());
          folderName = parts[0];
        }
      }
      
      // Method 3: Check fullPath property
      if (!folderName && file.fullPath && file.fullPath.trim()) {
        if (file.fullPath.includes('/')) {
          const parts = file.fullPath.split('/').filter(part => part.trim());
          folderName = parts.length > 1 ? parts[0] : null;
        }
      }
      
      // Method 4: Try to extract from any available path-like properties
      if (!folderName) {
        // Check for any property that might contain path information
        const pathProperties = ['webkitRelativePath', 'path', 'fullPath', 'mozFullPath'];
        for (const prop of pathProperties) {
          if (file[prop] && typeof file[prop] === 'string' && file[prop].includes('/')) {
            const parts = file[prop].split('/').filter(part => part.trim());
            if (parts.length > 1) {
              folderName = parts[0];
              break;
            }
          }
        }
      }
      
      // Method 5: Use manual folder name if provided
      if (!folderName && manualFolderName && manualFolderName.trim()) {
        folderName = manualFolderName.trim();
      }
      
      // Method 6: If we're in folder mode but no folder structure detected, 
      // try to create a meaningful name from the file context
      if (!folderName && uploadMode === 'folders') {
        // Check if all files share a common prefix (indicating they're from the same folder)
        const commonPrefixMatch = file.name.match(/^([^.]+?)(_|\-|\.)/);
        if (commonPrefixMatch) {
          folderName = commonPrefixMatch[1];
        } else {
          // Use the filename without extension as folder name
          const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '');
          const parts = nameWithoutExt.split(/[_\-\s]+/);
          folderName = parts[0] || nameWithoutExt;
        }
      }
      
      // Final fallback - but also trigger manual input option
      if (!folderName || folderName.trim() === '') {
        folderName = `Folder_${Math.floor(Date.now() / 1000)}`; // Use timestamp to avoid duplicates
        setShowManualFolderName(true); // Show manual input option
      }
      
      // Clean the folder name (replace underscores/hyphens with spaces, remove invalid characters)
      folderName = folderName.trim()
                             .replace(/_/g, ' ')           // Replace underscores with spaces
                             .replace(/-/g, ' ')           // Replace hyphens with spaces
                             .replace(/[<>:"/\\|?*]/g, ' ') // Replace invalid chars with spaces
                             .replace(/\s+/g, ' ')         // Replace multiple spaces with single space
                             .trim();                      // Clean up whitespace

      // Debug logging for folder detection (reduced)
      if (import.meta.env.DEV && index === 0) {
        console.log(`📁 Folder detection for ${validFiles.length} files:`, {
          sampleFile: file.name,
          webkitRelativePath: file.webkitRelativePath,
          extractedFolderName: folderName
        });
      }
      
      // Add folder name to the file object for upload use
      fileWithPreview.folderName = folderName;
      
      if (!newFolderStructure[folderName]) {
        newFolderStructure[folderName] = [];
      }
      newFolderStructure[folderName].push(fileWithPreview);
      newFilesWithPreviews.push(fileWithPreview);
    });

    // Combine existing and new files
    const allFiles = [...existingFiles, ...newFilesWithPreviews];

    // Debug logging (can be removed in production)
    if (import.meta.env.DEV) {
      console.log('Final folder structure:', newFolderStructure);
      console.log('Total files processed:', allFiles.length);
      if (duplicatesFound > 0) {
        console.log(`Skipped ${duplicatesFound} duplicate file(s)`);
      }
    }

    // Show notification about duplicates
    if (duplicatesFound > 0) {
      showAlert(`Added ${newFilesWithPreviews.length} new images. Skipped ${duplicatesFound} duplicate(s).`, 'info');
    } else if (isIncremental && newFilesWithPreviews.length > 0) {
      showAlert(`Added ${newFilesWithPreviews.length} new images.`, 'success');
    }

    setSelectedFiles(allFiles);
    setFolderPreview(newFolderStructure);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': [],
      'image/png': [],
      'image/gif': [],
      'image/webp': []
    },
    maxSize: MAX_FILE_SIZE
  });

  // Custom input props for folder mode
  const getFolderInputProps = () => {
    const inputProps = getInputProps();
    if (uploadMode === 'folders') {
      return {
        ...inputProps,
        webkitdirectory: '',
        directory: '',
        multiple: true,
        accept: 'image/*',
        onChange: handleDirectFolderSelect,
      };
    }
    return inputProps;
  };

  // Direct folder selection handler (bypasses react-dropzone for folder mode)
  const handleDirectFolderSelect = (event) => {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
      console.log('Direct folder selection:', files);
      const isIncremental = selectedFiles.length > 0;
      handleFolderDrop(files, isIncremental);
    }
  };

  // Remove an entire folder
  const handleRemoveFolder = (folderNameToRemove) => {
    // Filter out all files that belong to this folder
    const newSelectedFiles = selectedFiles.filter(file => {
      const relativePath = file.webkitRelativePath || file.name;
      let folderName;
      if (relativePath.includes('/')) {
        folderName = relativePath.split('/')[0];
      } else {
        folderName = 'Uploaded Files';
      }
      
      // Clean the folder name to match what was stored (same logic as folder creation)
      folderName = folderName.trim()
                             .replace(/_/g, ' ')           // Replace underscores with spaces
                             .replace(/-/g, ' ')           // Replace hyphens with spaces
                             .replace(/[<>:"/\\|?*]/g, ' ') // Replace invalid chars with spaces
                             .replace(/\s+/g, ' ')         // Replace multiple spaces with single space
                             .trim();                      // Clean up whitespace
      
      const shouldKeep = folderName !== folderNameToRemove;
      
      // Revoke preview URL for removed files
      if (!shouldKeep && file.preview) {
        URL.revokeObjectURL(file.preview);
      }
      
      return shouldKeep;
    });

    // Rebuild folder preview without the removed folder
    const newFolderPreview = { ...folderPreview };
    delete newFolderPreview[folderNameToRemove];

    setSelectedFiles(newSelectedFiles);
    setFolderPreview(newFolderPreview);
    
    const removedCount = selectedFiles.length - newSelectedFiles.length;
    showAlert(`Removed folder "${folderNameToRemove}" (${removedCount} images)`, 'info');
  };

  // Start editing a folder name
  const handleStartEditFolder = (folderName) => {
    setEditingFolder(folderName);
    setEditFolderName(folderName);
  };

  // Cancel editing
  const handleCancelEditFolder = () => {
    setEditingFolder(null);
    setEditFolderName('');
  };

  // Save the edited folder name
  const handleSaveEditFolder = () => {
    if (!editFolderName.trim() || editFolderName.trim() === editingFolder) {
      handleCancelEditFolder();
      return;
    }

    const cleanedNewName = editFolderName.trim()
                                        .replace(/[<>:"/\\|?*]/g, ' ') // Replace invalid chars with spaces
                                        .replace(/\s+/g, ' ')         // Replace multiple spaces with single space
                                        .trim();                      // Clean up whitespace

    if (!cleanedNewName) {
      showAlert('Set name cannot be empty', 'warning');
      return;
    }

    // Check if the new name already exists
    if (folderPreview[cleanedNewName] && cleanedNewName !== editingFolder) {
      showAlert('A set with this name already exists', 'warning');
      return;
    }

    // Update folder preview
    const newFolderPreview = { ...folderPreview };
    newFolderPreview[cleanedNewName] = newFolderPreview[editingFolder];
    delete newFolderPreview[editingFolder];

    setFolderPreview(newFolderPreview);
    showAlert(`Renamed "${editingFolder}" to "${cleanedNewName}"`, 'success');
    handleCancelEditFolder();
  };

  const handleRemoveFile = (index) => {
    setSelectedFiles(prev => {
      const newFiles = [...prev];
      const fileToRemove = newFiles[index];
      
      // Revoke the URL to prevent memory leaks
      if (fileToRemove.preview) {
        URL.revokeObjectURL(fileToRemove.preview);
      }
      
      // Remove the label for this file
      setImageLabels(prevLabels => {
        const newLabels = { ...prevLabels };
        delete newLabels[fileToRemove.id];
        return newLabels;
      });
      
      newFiles.splice(index, 1);
      return newFiles;
    });
  };

  const handleLabelChange = (fileId, newLabel) => {
    setImageLabels(prev => ({
      ...prev,
      [fileId]: newLabel
    }));
  };

  const handleSetChange = (event) => {
    const value = event.target.value;
    if (value === 'CREATE_NEW') {
      setShowNewSetDialog(true);
    } else {
      setSelectedSet(value);
    }
  };

  const handleCreateNewSet = () => {
    if (newSetName.trim()) {
      setSelectedSet(newSetName.trim());
      setImageSets(prev => [...prev, { name: newSetName.trim(), imageCount: 0 }]);
      setNewSetName('');
      setShowNewSetDialog(false);
    }
  };

  const handleCancelNewSet = () => {
    setNewSetName('');
    setShowNewSetDialog(false);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      showAlert('Please select at least one file', 'warning');
      return;
    }

    if (!selectedSet) {
      showAlert('Please select an image set', 'warning');
      return;
    }

    setUploading(true);
    setUploadingCount(0);
    
    try {
      const fileCount = selectedFiles.length;
      
      // Use optimized upload for large batches (100+ images)
      if (fileCount >= 100) {
        console.log(`🚀 Starting optimized batch upload for ${fileCount} images`);
        
        // Generate session ID
        const sessionId = Date.now().toString() + Math.random().toString(36).substr(2, 9);
        setUploadSessionId(sessionId);
        setShowProgressDialog(true);
        
        // Create clean files for upload
        const cleanFiles = selectedFiles.map(file => 
          new File([file], file.name, { type: file.type })
        );
        
        // Start optimized batch upload
        const response = await optimizedBatchUpload(
          cleanFiles, 
          '', // No individual descriptions for batch upload
          selectedSet, 
          50, // batch size
          sessionId
        );
        
        if (response.data.success) {
          showAlert(`Optimized batch upload started! Processing ${fileCount} images in batches.`, 'info');
        } else {
          throw new Error(response.data.error || 'Upload failed');
        }
        
      } else {
        // Use regular upload for smaller batches
        console.log(`📤 Starting regular upload for ${fileCount} images`);
        
        if (fileCount > 1) {
          // Use batch upload for multiple files
          const cleanFiles = selectedFiles.map(file => 
            new File([file], file.name, { type: file.type })
          );
          
          const response = await batchUploadImages(cleanFiles, '', selectedSet);
          
          if (response.data.success) {
            showAlert(`Successfully uploaded ${fileCount} images`, 'success');
          } else {
            throw new Error('Batch upload failed');
          }
        } else {
          // Single file upload with individual labels
          const file = selectedFiles[0];
          const label = imageLabels[file.id] || generateDefaultLabel(file.name);
          const cleanFile = new File([file], file.name, { type: file.type });
          
          await uploadImage(cleanFile, label, selectedSet);
          setUploadingCount(1);
          showAlert('Successfully uploaded 1 image', 'success');
        }
        
        // Reset form immediately for small uploads
        selectedFiles.forEach(file => {
          if (file.preview) URL.revokeObjectURL(file.preview);
        });
        setSelectedFiles([]);
        setImageLabels({});
        setSelectedSet('');
        
        // Refresh image list and sets
        fetchImages();
        fetchImageSets();
      }
      
    } catch (error) {
      console.error('Error uploading images:', error);
      showAlert(`Error uploading images: ${error.message}`, 'error');
    } finally {
      setUploading(false);
      setUploadingCount(0);
    }
  };

  const handleProgressDialogClose = () => {
    setShowProgressDialog(false);
    setUploadSessionId(null);
  };

  const handleUploadComplete = (progressData) => {
    if (progressData.status === 'completed') {
      showAlert(`Upload completed! ${progressData.successful}/${progressData.total_images} images processed successfully.`, 'success');
      
      // Reset form after completion
      selectedFiles.forEach(file => {
        if (file.preview) URL.revokeObjectURL(file.preview);
      });
      setSelectedFiles([]);
      setImageLabels({});
      setSelectedSet('');
      
      // Refresh image list and sets
      fetchImages();
      fetchImageSets();
    } else if (progressData.status === 'failed') {
      showAlert(`Upload failed. ${progressData.successful || 0}/${progressData.total_images} images were processed before the error.`, 'error');
    }
  };

  const handleFolderUpload = async () => {
    if (selectedFiles.length === 0) {
      showAlert('Please select a folder with images', 'warning');
      return;
    }

    setUploading(true);
    setUploadingCount(0);
    setUploadProgress(0);
    setProcessingStage('uploading');
    setIsChunkedUpload(false);
    setCurrentChunk(0);
    setTotalChunks(0);
    
    try {
      console.log('🚀 Starting folder upload:', {
        fileCount: selectedFiles.length,
        isLargeUpload: selectedFiles.length >= 100
      });
      
      // Upload folder structure with progress tracking
      const result = await uploadFolder(selectedFiles, (progress) => {
        console.log('📊 Upload Progress:', progress); // Debug log
        
        // Batch state updates to prevent race conditions
        if (progress.isChunked && !isChunkedUpload) {
          // First time chunked upload detected - batch initial state
          console.log('🔄 Switching to chunked upload mode');
          setIsChunkedUpload(true);
          setTotalChunks(progress.totalChunks);
        }
        
        // Update progress state - differentiate between upload and processing
        if (progress.percentage >= 100 && processingStage === 'uploading') {
          // Upload complete, now processing
          setProcessingStage('processing');
          setUploadProgress(0); // Reset progress for processing stage
          setUploadingCount(0);
          console.log('🔄 Upload complete, switching to processing stage');
        } else if (processingStage === 'uploading') {
          // Still uploading
          setUploadProgress(progress.percentage);
          const filesProcessed = progress.files || 0;
          setUploadingCount(filesProcessed);
        }
        
        // Update chunk information if chunked
        if (progress.isChunked) {
          setCurrentChunk(progress.currentChunk);
          console.log(`🔢 Processing chunk ${progress.currentChunk}/${progress.totalChunks}`);
        }
        
        // Show error alerts for failed chunks
        if (progress.error) {
          console.error('❌ Upload error:', progress.error);
          showAlert(progress.error, 'warning');
        }
      });
      
      console.log('📋 Upload result:', result);
      console.log('📋 Upload result.data:', result.data);
      
      // Fix: Access the nested data object
      const uploadData = result.data.data || result.data;
      console.log('📋 uploadData:', uploadData);
      console.log('📋 total_successful:', uploadData.total_successful);
      console.log('📋 total_uploads:', uploadData.total_uploads);
      
      if (uploadData.total_successful > 0) {
        let message = `Successfully uploaded ${uploadData.total_successful}/${uploadData.total_uploads} images to ${uploadData.sets_created} set(s)`;
        
        // Show warnings if some failed
        const failed = uploadData.total_uploads - uploadData.total_successful;
        if (failed > 0) {
          message += ` (${failed} failed)`;
          showAlert(message, 'warning');
          
          // Show detailed errors if available
          if (uploadData.errors && uploadData.errors.length > 0) {
            console.warn('Upload errors:', uploadData.errors);
            // Show first few errors to user
            const errorSummary = uploadData.errors.slice(0, 3).join('; ');
            showAlert(`Upload errors: ${errorSummary}`, 'error');
          }
        } else {
          showAlert(message, 'success');
        }
        
        // Mark processing as complete
        setProcessingStage('complete');
        console.log('✅ Processing complete, upload successful');
        
        // Reset form
        setSelectedFiles([]);
        setFolderPreview({});
        
        // Refresh image list and sets
        fetchImages();
        fetchImageSets();
      } else {
        showAlert('No images were uploaded successfully', 'error');
        
        // Show error details if available
        if (uploadData.errors && uploadData.errors.length > 0) {
          const errorSummary = uploadData.errors.slice(0, 3).join('; ');
          showAlert(`Upload failed: ${errorSummary}`, 'error');
        }
      }
    } catch (error) {
      console.error('❌ Error uploading folder:', error);
      console.error('❌ Error details:', {
        code: error.code,
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        stack: error.stack
      });
      
      // Provide more specific error messages
      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        console.error('❌ Upload timeout detected');
        showAlert('Upload timed out - try uploading fewer files at once', 'error');
      } else if (error.response?.status === 413) {
        console.error('❌ Upload too large');
        showAlert('Upload too large - try uploading fewer files at once', 'error');
      } else if (error.response?.status >= 500) {
        console.error('❌ Server error');
        showAlert('Server error - please try again later', 'error');
      } else if (error.response?.status >= 400) {
        console.error('❌ Client error');
        showAlert(`Upload failed: ${error.response?.data?.message || 'Client error'}`, 'error');
      } else {
        console.error('❌ Unexpected error');
        showAlert(`Error uploading folder: ${error.message || 'Unknown error'}`, 'error');
      }
    } finally {
      setUploading(false);
      setUploadingCount(0);
      setUploadProgress(0);
      setProcessingStage('uploading'); // Reset for next upload
      setIsChunkedUpload(false);
      setCurrentChunk(0);
      setTotalChunks(0);
    }
  };

  const showAlert = (message, severity) => {
    setAlert({
      open: true,
      message,
      severity
    });
  };

  const handleCloseAlert = () => {
    setAlert({ ...alert, open: false });
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Paper sx={{ p: 3, mb: 4 }}>
        
        {/* Upload Section */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h5" component="h2" gutterBottom>
            Add New Images
          </Typography>
          
          {/* Upload Mode Switcher */}
          <Box sx={{ mb: 3 }}>
            <Chip 
              label="Upload Files" 
              onClick={() => {
                setUploadMode('files');
                setSelectedFiles([]);
                setFolderPreview({});
                setManualFolderName('');
                setShowManualFolderName(false);
                setEditingFolder(null);
                setEditFolderName('');
                setValidationErrors([]);
              }}
              color={uploadMode === 'files' ? 'primary' : 'default'}
              variant={uploadMode === 'files' ? 'filled' : 'outlined'}
              sx={{ mr: 1 }}
            />
            <Chip 
              label="Upload Folders" 
              onClick={() => {
                setUploadMode('folders');
                setSelectedFiles([]);
                setFolderPreview({});
                setSelectedSet('');
                setManualFolderName('');
                setShowManualFolderName(false);
                setEditingFolder(null);
                setEditFolderName('');
                setValidationErrors([]);
              }}
              color={uploadMode === 'folders' ? 'primary' : 'default'}
              variant={uploadMode === 'folders' ? 'filled' : 'outlined'}
            />
          </Box>
          
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, height: 'fit-content' }}>
                {/* React Dropzone */}
                <Box 
                  {...getRootProps()} 
                  sx={{
                    border: '2px dashed',
                    borderColor: isDragActive ? 'primary.main' : 'divider',
                    borderRadius: 1,
                    p: 3,
                    bgcolor: isDragActive ? 'action.hover' : 'transparent',
                    textAlign: 'center',
                    cursor: 'pointer',
                    minHeight: 150,
                    width: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    transition: 'all 0.2s',
                    '&:hover': {
                      borderColor: 'primary.light',
                      bgcolor: 'rgba(0, 0, 0, 0.02)'
                    }
                  }}
                >
                  <input {...getFolderInputProps()} />
                  <CloudUploadIcon fontSize="large" color="primary" sx={{ mb: 1 }} />
                  <Typography variant="body1">
                    {isDragActive 
                      ? (uploadMode === 'folders' ? 'Drop your folder here...' : 'Drop your images here...')
                      : (uploadMode === 'folders' 
                          ? 'Drag and drop a folder here, or click to select folders'
                          : 'Drag and drop images here, or click to select files')}
                  </Typography>
                  <Typography variant="caption" color="textSecondary" sx={{ mt: 1 }}>
                    {uploadMode === 'folders' 
                      ? (selectedFiles.length > 0 
                          ? `Add more folders - duplicates will be automatically detected and skipped. ${selectedFiles.length >= 100 ? '🚀 Will use chunked upload to handle large batch efficiently.' : selectedFiles.length > 50 ? '⚠️ Large uploads may take several minutes.' : ''}`
                          : 'Click to select a folder containing images - sets will be created automatically from folder names. Note: Drag & drop may not preserve folder structure in all browsers.')
                      : 'Supported formats: JPG, PNG, GIF, WEBP (Max: 5MB per file)'}
                  </Typography>
                </Box>
                
                {/* Show set selector only in file mode */}
                {uploadMode === 'files' && (
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel>Select Image Set</InputLabel>
                    <Select
                      value={selectedSet}
                      onChange={handleSetChange}
                      disabled={uploading}
                      label="Select Image Set"
                    >
                      {imageSets.map((set) => (
                        <MenuItem key={set.name} value={set.name}>
                          {set.name} ({set.imageCount} images)
                        </MenuItem>
                      ))}
                      <MenuItem value="CREATE_NEW">
                        <em>Create New Set...</em>
                      </MenuItem>
                    </Select>
                  </FormControl>
                )}
                
                {/* Manual folder name input */}
                {uploadMode === 'folders' && showManualFolderName && (
                  <Box sx={{ mb: 2, p: 2, bgcolor: 'warning.light', borderRadius: 1, border: '1px solid', borderColor: 'warning.main' }}>
                    <Typography variant="body2" color="warning.dark" sx={{ mb: 1, fontWeight: 'bold' }}>
                      ⚠️ Folder name could not be detected
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
                      <TextField
                        label="Set Name"
                        value={manualFolderName}
                        onChange={(e) => setManualFolderName(e.target.value)}
                        size="small"
                        variant="outlined"
                        sx={{ flexGrow: 1 }}
                        helperText="Enter a name for the image set"
                      />
                      <Button 
                        variant="contained"
                        size="small"
                        onClick={() => {
                          if (manualFolderName.trim()) {
                            // Re-process with the manual folder name, but don't make it incremental
                            // since we're updating existing files
                            handleFolderDrop(selectedFiles, false);
                            setShowManualFolderName(false);
                          }
                        }}
                        disabled={!manualFolderName.trim()}
                      >
                        Update
                      </Button>
                    </Box>
                  </Box>
                )}

                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {/* Progress bar for folder uploads */}
                  {uploadMode === 'folders' && uploading && (
                    <Box sx={{ width: '100%' }}>
                      {processingStage === 'uploading' ? (
                        // Upload progress
                        <>
                          <LinearProgress 
                            variant="determinate" 
                            value={uploadProgress} 
                            sx={{ height: 8, borderRadius: 4 }}
                          />
                          <Box sx={{ mt: 0.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography variant="caption" color="text.secondary">
                              Uploading files... {uploadingCount}/{selectedFiles.length} files
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
                              {uploadProgress}%
                            </Typography>
                          </Box>
                        </>
                      ) : (
                        // Processing progress - indeterminate until we get actual progress
                        <>
                          <LinearProgress 
                            variant="indeterminate" 
                            sx={{ height: 8, borderRadius: 4 }}
                          />
                          <Box sx={{ mt: 0.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography variant="caption" color="text.secondary">
                              {isChunkedUpload 
                                ? `Processing chunk ${currentChunk} of ${totalChunks} • Generating embeddings...`
                                : `Processing images and generating embeddings... Please wait`}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
                              Processing...
                            </Typography>
                          </Box>
                        </>
                      )}
                      {isChunkedUpload && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, fontStyle: 'italic' }}>
                          Large upload detected - processing in chunks to prevent timeouts
                        </Typography>
                      )}
                    </Box>
                  )}
                  
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button 
                      variant="contained" 
                      color="primary" 
                      onClick={uploadMode === 'folders' ? handleFolderUpload : handleUpload}
                      disabled={selectedFiles.length === 0 || (uploadMode === 'files' && !selectedSet) || uploading}
                      startIcon={uploading ? <CircularProgress size={20} /> : null}
                      sx={{ flexGrow: 1 }}
                    >
                      {uploading 
                        ? (processingStage === 'uploading'
                            ? (isChunkedUpload
                                ? `Uploading Chunk ${currentChunk}/${totalChunks}`
                                : `Uploading ${uploadProgress}%`)
                            : (isChunkedUpload
                                ? `Processing Chunk ${currentChunk}/${totalChunks}`
                                : `Processing Images...`))
                        : (uploadMode === 'folders' 
                            ? `Upload ${selectedFiles.length} Images to Auto-Created Sets${selectedFiles.length >= 100 ? ' (Chunked)' : ''}`
                            : `Upload ${selectedFiles.length} Image${selectedFiles.length !== 1 ? 's' : ''} to ${selectedSet || 'Set'}`)}
                    </Button>
                  
                    {/* Clear All button for folders mode */}
                    {uploadMode === 'folders' && selectedFiles.length > 0 && (
                      <Button 
                        variant="outlined" 
                        color="error"
                        onClick={() => {
                          // Revoke all preview URLs
                          selectedFiles.forEach(file => {
                            if (file.preview) URL.revokeObjectURL(file.preview);
                          });
                          setSelectedFiles([]);
                          setFolderPreview({});
                          setManualFolderName('');
                          setShowManualFolderName(false);
                          setEditingFolder(null);
                          setEditFolderName('');
                          showAlert('Cleared all folders', 'info');
                        }}
                        disabled={uploading}
                      >
                        Clear All
                      </Button>
                    )}
                  </Box>
                </Box>
              </Box>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Box sx={{ 
                minHeight: 400, 
                maxHeight: 600, 
                overflowY: 'auto',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                p: 2,
                bgcolor: 'background.paper'
              }}>
                {selectedFiles.length > 0 ? (
                  <>
                    <Typography variant="subtitle1" gutterBottom>
                      {uploadMode === 'folders' 
                        ? `Selected Files from Folders (${selectedFiles.length}):`
                        : `Selected Files (${selectedFiles.length}):`}
                    </Typography>
                  
                  {uploadMode === 'folders' ? (
                    // Folder mode: Show files grouped by folder with clean image previews
                    Object.entries(folderPreview).map(([folderName, files]) => (
                      <Box key={folderName} sx={{ mb: 4 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                          {editingFolder === folderName ? (
                            // Editing mode
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 1, mr: 1 }}>
                              <Typography sx={{ fontSize: '1.25rem' }}>📁</Typography>
                              <TextField
                                value={editFolderName}
                                onChange={(e) => setEditFolderName(e.target.value)}
                                size="small"
                                variant="outlined"
                                sx={{ flexGrow: 1 }}
                                autoFocus
                                onKeyPress={(e) => {
                                  if (e.key === 'Enter') {
                                    handleSaveEditFolder();
                                  } else if (e.key === 'Escape') {
                                    handleCancelEditFolder();
                                  }
                                }}
                              />
                              <IconButton size="small" onClick={handleSaveEditFolder} color="primary">
                                <CheckIcon fontSize="small" />
                              </IconButton>
                              <IconButton size="small" onClick={handleCancelEditFolder}>
                                <CloseIcon fontSize="small" />
                              </IconButton>
                            </Box>
                          ) : (
                            // Display mode
                            <Typography variant="h6" color="primary" sx={{ fontWeight: 'bold' }}>
                              📁 {folderName}
                            </Typography>
                          )}
                          
                          {editingFolder !== folderName && (
                            <Box sx={{ display: 'flex', gap: 0.5 }}>
                              <IconButton 
                                size="small" 
                                onClick={() => handleStartEditFolder(folderName)}
                                sx={{ 
                                  color: 'primary.main',
                                  '&:hover': { 
                                    backgroundColor: 'primary.light',
                                    color: 'white'
                                  }
                                }}
                              >
                                <EditIcon fontSize="small" />
                              </IconButton>
                              <IconButton 
                                size="small" 
                                onClick={() => handleRemoveFolder(folderName)}
                                sx={{ 
                                  color: 'error.main',
                                  '&:hover': { 
                                    backgroundColor: 'error.light',
                                    color: 'white'
                                  }
                                }}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Box>
                          )}
                        </Box>
                        <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                          {files.length} image{files.length !== 1 ? 's' : ''} • Will create image set "{folderName}"
                        </Typography>
                        <Grid container spacing={2}>
                          {files.slice(0, 8).map((file, index) => (
                            <Grid item key={`${folderName}-${index}`}>
                              <Tooltip 
                                title={
                                  <Box>
                                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                      {file.label || file.name}
                                    </Typography>
                                    <Typography variant="caption" color="inherit">
                                      {file.name} • {(file.size / 1024).toFixed(1)} KB
                                    </Typography>
                                  </Box>
                                }
                                placement="top"
                                arrow
                              >
                                <Box sx={{ 
                                  width: 80, 
                                  height: 80, 
                                  backgroundImage: file.preview ? `url(${file.preview})` : 'none',
                                  backgroundColor: file.preview ? 'transparent' : '#f5f5f5',
                                  backgroundSize: 'cover',
                                  backgroundPosition: 'center',
                                  borderRadius: 2,
                                  border: '2px solid #e0e0e0',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  cursor: 'pointer',
                                  transition: 'all 0.2s ease',
                                  '&:hover': {
                                    borderColor: 'primary.main',
                                    transform: 'scale(1.05)',
                                    boxShadow: 2
                                  }
                                }}>
                                  {!file.preview && (
                                    <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold' }}>
                                      IMG
                                    </Typography>
                                  )}
                                </Box>
                              </Tooltip>
                            </Grid>
                          ))}
                          {files.length > 8 && (
                            <Grid item>
                              <Tooltip 
                                title={`And ${files.length - 8} more images`}
                                placement="top"
                                arrow
                              >
                                <Box sx={{ 
                                  width: 80, 
                                  height: 80, 
                                  backgroundColor: '#f5f5f5',
                                  borderRadius: 2,
                                  border: '2px dashed #c0c0c0',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  cursor: 'pointer',
                                  transition: 'all 0.2s ease',
                                  '&:hover': {
                                    borderColor: 'primary.main',
                                    backgroundColor: 'rgba(25, 118, 210, 0.04)'
                                  }
                                }}>
                                  <Typography variant="body2" color="primary" sx={{ fontWeight: 'bold' }}>
                                    +{files.length - 8}
                                  </Typography>
                                </Box>
                              </Tooltip>
                            </Grid>
                          )}
                        </Grid>
                      </Box>
                    ))
                  ) : (
                    // File mode: Show individual files with labels (existing logic)
                    <List dense>
                      {selectedFiles.map((file, index) => (
                        <ListItem 
                          key={file.id || index}
                          sx={{ 
                            display: 'flex', 
                            flexDirection: 'column', 
                            alignItems: 'stretch', 
                            py: 2 
                          }}
                        >
                          <Box sx={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            width: '100%', 
                            mb: 1
                          }}>
                            <Tooltip 
                              title={
                                <Box>
                                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                    {imageLabels[file.id] || generateDefaultLabel(file.name)}
                                  </Typography>
                                  <Typography variant="caption" color="inherit">
                                    {file.name} • {(file.size / 1024).toFixed(1)} KB
                                  </Typography>
                                </Box>
                              }
                              placement="top"
                              arrow
                            >
                              <Box sx={{ 
                                width: 60, 
                                height: 60, 
                                mr: 2, 
                                backgroundImage: `url(${file.preview})`,
                                backgroundSize: 'cover',
                                backgroundPosition: 'center',
                                borderRadius: 1,
                                border: '1px solid #ddd',
                                cursor: 'pointer',
                                '&:hover': {
                                  borderColor: 'primary.main',
                                  transform: 'scale(1.05)',
                                  transition: 'all 0.2s ease'
                                }
                              }} />
                            </Tooltip>
                            <Box sx={{ flexGrow: 1 }}>
                              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                {file.name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {`${(file.size / 1024).toFixed(1)} KB`}
                              </Typography>
                            </Box>
                            <IconButton 
                              edge="end" 
                              aria-label="delete" 
                              onClick={() => handleRemoveFile(index)}
                              disabled={uploading}
                              sx={{ ml: 1 }}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Box>
                          <TextField
                            label="Image Label"
                            value={imageLabels[file.id] || ''}
                            onChange={(e) => handleLabelChange(file.id, e.target.value)}
                            disabled={uploading}
                            size="small"
                            fullWidth
                            sx={{ mt: 1 }}
                            helperText="This will be used as the image description"
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}
                  </>
                ) : (
                  // Placeholder when no files selected
                  <Box sx={{ 
                    display: 'flex', 
                    flexDirection: 'column', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    height: '100%',
                    minHeight: 300,
                    color: 'text.secondary'
                  }}>
                    <Typography variant="h6" gutterBottom>
                      {uploadMode === 'folders' ? 'No folders selected' : 'No files selected'}
                    </Typography>
                    <Typography variant="body2" align="center">
                      {uploadMode === 'folders' 
                        ? 'Select folders to see preview of images and set names that will be created'
                        : 'Select images to see preview and edit their labels'}
                    </Typography>
                  </Box>
                )}
              </Box>
            </Grid>
          </Grid>
        </Box>
        
        <Divider sx={{ my: 4 }} />
        
        {/* Enhanced Image Gallery Section */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
            Image Gallery
          </Typography>
          
          {/* Show warning if there are images without embeddings */}
          {embeddingStats && embeddingStats.without_embeddings > 0 && (
            <Alert severity="warning" sx={{ mb: 3 }}>
              <Typography variant="body2">
                {embeddingStats.without_embeddings} images are missing embeddings and won't appear in similarity search. 
                You can regenerate embeddings using: <code>python manage.py regenerate_embeddings</code>
              </Typography>
            </Alert>
          )}
          
          <ImageGallery
            imagesBySet={uploadedImages}
            loading={loading}
            embeddingStats={embeddingStats}
            onImageSelect={(image) => {
              console.log('Image selected:', image);
              // Optional: Add image selection handling here if needed
            }}
          />
        </Paper>
      </Paper>
      
      {/* New Set Creation Dialog */}
      <Dialog open={showNewSetDialog} onClose={handleCancelNewSet}>
        <DialogTitle>Create New Image Set</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Set Name"
            fullWidth
            variant="outlined"
            value={newSetName}
            onChange={(e) => setNewSetName(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleCreateNewSet();
              }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelNewSet}>Cancel</Button>
          <Button 
            onClick={handleCreateNewSet} 
            variant="contained"
            disabled={!newSetName.trim()}
          >
            Create Set
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Validation Errors Display */}
      {validationErrors && validationErrors.length > 0 && (
        <Paper sx={{ 
          position: 'fixed', 
          bottom: 80, 
          right: 20, 
          p: 2, 
          maxWidth: 400,
          bgcolor: 'error.main',
          color: 'error.contrastText',
          zIndex: 1000
        }}>
          <Typography variant="subtitle2" gutterBottom>
            Validation Errors ({validationErrors.length})
          </Typography>
          {validationErrors.slice(0, 3).map((error, index) => (
            <Typography key={index} variant="caption" display="block">
              • {error}
            </Typography>
          ))}
          {validationErrors.length > 3 && (
            <Typography variant="caption" display="block" sx={{ fontStyle: 'italic' }}>
              ... and {validationErrors.length - 3} more
            </Typography>
          )}
          <Button 
            size="small" 
            variant="outlined"
            color="inherit"
            onClick={() => setValidationErrors([])}
            sx={{ mt: 1 }}
          >
            Dismiss
          </Button>
        </Paper>
      )}
      
      {/* Alert Snackbar */}
      <Snackbar 
        open={alert.open} 
        autoHideDuration={6000} 
        onClose={handleCloseAlert}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseAlert} severity={alert.severity}>
          {alert.message}
        </Alert>
      </Snackbar>

      {/* Upload Progress Dialog */}
      <UploadProgressDialog
        open={showProgressDialog}
        onClose={handleProgressDialogClose}
        sessionId={uploadSessionId}
        onComplete={handleUploadComplete}
      />
    </Container>
  );
};

export default ImageManagementPage; 