import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardMedia,
  CardContent,
  Chip,
  IconButton,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  Grid,
  List,
  ListItem,
  ListItemAvatar,
  Avatar,
  ListItemText,
  Tooltip,
  ButtonGroup,
  Button,
  Menu,
  Divider,
  Stack,
  InputAdornment,
  ToggleButtonGroup,
  ToggleButton,
  Checkbox,
  Fab,
  Dialog,
  DialogContent,
  DialogActions,
  Skeleton,
  Alert
} from '@mui/material';
import { styled } from '@mui/material/styles';

// Icons
import SearchIcon from '@mui/icons-material/Search';
import SearchOffIcon from '@mui/icons-material/SearchOff';
import WarningIcon from '@mui/icons-material/Warning';
import GridViewIcon from '@mui/icons-material/GridView';
import ViewListIcon from '@mui/icons-material/ViewList';
import ViewComfyIcon from '@mui/icons-material/ViewComfy';
import PhotoLibraryIcon from '@mui/icons-material/PhotoLibrary';
import FilterListIcon from '@mui/icons-material/FilterList';
import SortIcon from '@mui/icons-material/Sort';
import CloseIcon from '@mui/icons-material/Close';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

// Styled components
const ViewModeButton = styled(ToggleButton)(({ theme }) => ({
  padding: theme.spacing(1),
  border: `1px solid ${theme.palette.divider}`,
  '&.Mui-selected': {
    backgroundColor: theme.palette.primary.main,
    color: theme.palette.primary.contrastText,
    '&:hover': {
      backgroundColor: theme.palette.primary.dark,
    }
  }
}));

const ImageCard = styled(Card)(({ theme, density = 'comfortable' }) => {
  const heightMap = {
    compact: 120,
    comfortable: 160,
    spacious: 200
  };
  
  return {
    height: '100%',
    position: 'relative',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    '&:hover': {
      transform: 'translateY(-2px)',
      boxShadow: theme.shadows[4],
    },
    '& .MuiCardMedia-root': {
      height: heightMap[density]
    }
  };
});


const LazyImage = ({ src, alt, onLoad, style, ...props }) => {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const imgRef = useRef();

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !loaded && !error) {
            const image = new Image();
            image.onload = () => {
              setLoaded(true);
              if (onLoad) onLoad();
            };
            image.onerror = () => setError(true);
            image.src = src;
          }
        });
      },
      { threshold: 0.1, rootMargin: '50px' }
    );

    observer.observe(img);
    return () => observer.disconnect();
  }, [src, loaded, error, onLoad]);

  if (error) {
    return (
      <Box
        ref={imgRef}
        sx={{
          ...style,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#f5f5f5',
          color: 'text.secondary'
        }}
        {...props}
      >
        <Typography variant="caption">Image unavailable</Typography>
      </Box>
    );
  }

  return (
    <Box ref={imgRef} sx={style} {...props}>
      {!loaded ? (
        <Skeleton variant="rectangular" width="100%" height="100%" />
      ) : (
        <img
          src={src}
          alt={alt}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'contain',
            display: 'block'
          }}
        />
      )}
    </Box>
  );
};

const ImageGallery = ({
  imagesBySet = {},
  loading = false,
  embeddingStats = null,
  onImageSelect,
  selectionMode = false,
  selectedImages = new Set(),
  onSelectionChange
}) => {
  // View and layout state
  const [viewMode, setViewMode] = useState('grid'); // 'grid', 'list', 'thumbnails', 'sets'
  const [density, setDensity] = useState('comfortable'); // 'compact', 'comfortable', 'spacious'
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  
  // Search and filtering state
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSet, setSelectedSet] = useState('all');
  const [sortBy, setSortBy] = useState('newest'); // 'newest', 'oldest', 'name', 'set'
  const [embeddingFilter, setEmbeddingFilter] = useState('all'); // 'all', 'searchable', 'missing'
  const [collapsedSets, setCollapsedSets] = useState(new Set());
  
  // UI state
  const [previewImage, setPreviewImage] = useState(null);
  const [filterMenuAnchor, setFilterMenuAnchor] = useState(null);
  const [sortMenuAnchor, setSortMenuAnchor] = useState(null);

  // Debounced search term
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearchTerm, selectedSet, sortBy, embeddingFilter]);

  // Flatten and filter images
  const allImages = useMemo(() => {
    const images = [];
    Object.entries(imagesBySet).forEach(([setName, setImages]) => {
      setImages.forEach(image => {
        images.push({
          ...image,
          setName,
          searchableText: `${image.description || ''} ${setName}`.toLowerCase()
        });
      });
    });
    return images;
  }, [imagesBySet]);

  const filteredImages = useMemo(() => {
    let filtered = [...allImages];

    // Text search
    if (debouncedSearchTerm) {
      const term = debouncedSearchTerm.toLowerCase();
      filtered = filtered.filter(image =>
        image.searchableText.includes(term) || 
        image.description?.toLowerCase().includes(term) ||
        image.setName.toLowerCase().includes(term)
      );
    }

    // Set filter
    if (selectedSet !== 'all') {
      filtered = filtered.filter(image => image.setName === selectedSet);
    }

    // Embedding filter
    if (embeddingFilter === 'searchable') {
      filtered = filtered.filter(image => image.has_embeddings !== false);
    } else if (embeddingFilter === 'missing') {
      filtered = filtered.filter(image => image.has_embeddings === false);
    }

    // Sort
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'newest':
          return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        case 'oldest':
          return new Date(a.created_at || 0) - new Date(b.created_at || 0);
        case 'name':
          return (a.description || '').localeCompare(b.description || '');
        case 'set':
          return a.setName.localeCompare(b.setName);
        default:
          return 0;
      }
    });

    return filtered;
  }, [allImages, debouncedSearchTerm, selectedSet, sortBy, embeddingFilter]);

  // Paginated images
  const paginatedImages = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return filteredImages.slice(startIndex, startIndex + pageSize);
  }, [filteredImages, currentPage, pageSize]);

  const totalPages = Math.ceil(filteredImages.length / pageSize);
  const setNames = Object.keys(imagesBySet);

  // Event handlers
  const handleImageClick = useCallback((image) => {
    if (selectionMode) {
      const newSelected = new Set(selectedImages);
      if (newSelected.has(image.id)) {
        newSelected.delete(image.id);
      } else {
        newSelected.add(image.id);
      }
      onSelectionChange?.(newSelected);
    } else {
      setPreviewImage(image);
      onImageSelect?.(image);
    }
  }, [selectionMode, selectedImages, onSelectionChange, onImageSelect]);

  const toggleSetCollapse = useCallback((setName) => {
    const newCollapsed = new Set(collapsedSets);
    if (newCollapsed.has(setName)) {
      newCollapsed.delete(setName);
    } else {
      newCollapsed.add(setName);
    }
    setCollapsedSets(newCollapsed);
  }, [collapsedSets]);

  const selectAll = useCallback(() => {
    const newSelected = new Set(selectedImages);
    paginatedImages.forEach(image => newSelected.add(image.id));
    onSelectionChange?.(newSelected);
  }, [selectedImages, paginatedImages, onSelectionChange]);

  const clearSelection = useCallback(() => {
    onSelectionChange?.(new Set());
  }, [onSelectionChange]);

  // Render methods
  const renderGridView = () => (
    <Grid container spacing={density === 'compact' ? 1 : 2}>
      {paginatedImages.map((image) => (
        <Grid item xs={12} sm={6} md={4} lg={3} xl={2} key={image.id || image.db_id}>
          <ImageCard 
            density={density}
            onClick={() => handleImageClick(image)}
            sx={{
              border: selectedImages.has(image.id) ? '3px solid' : 
                     image.has_embeddings === false ? '2px solid' : 'none',
              borderColor: selectedImages.has(image.id) ? 'primary.main' : 
                          image.has_embeddings === false ? 'warning.main' : 'transparent',
              backgroundColor: image.has_embeddings === false ? '#fff3e0' : 'inherit'
            }}
          >
            {/* Selection checkbox */}
            {selectionMode && (
              <Checkbox
                checked={selectedImages.has(image.id)}
                sx={{
                  position: 'absolute',
                  top: 8,
                  left: 8,
                  zIndex: 2,
                  backgroundColor: 'rgba(255,255,255,0.9)',
                  '&:hover': { backgroundColor: 'rgba(255,255,255,0.8)' }
                }}
              />
            )}

            {/* Status badges */}
            <Box sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1 }}>
              {image.has_embeddings === false && (
                <Tooltip title="Missing embeddings - image search won't work">
                  <Chip
                    icon={<SearchOffIcon />}
                    label="No Search"
                    size="small"
                    color="warning"
                    variant="filled"
                  />
                </Tooltip>
              )}
            </Box>

            <LazyImage
              src={image.image_url}
              alt={image.description || 'Image'}
              style={{ height: density === 'compact' ? 120 : density === 'comfortable' ? 160 : 200 }}
            />
            
            <CardContent sx={{ p: density === 'compact' ? 1 : 2 }}>
              <Typography variant="body2" color="text.secondary" noWrap>
                {image.description || 'No description'}
              </Typography>
              {density !== 'compact' && (
                <>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Set: {image.setName}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Uploaded: {image.created_at ? new Date(image.created_at).toLocaleDateString() : 'N/A'}
                  </Typography>
                </>
              )}
            </CardContent>
          </ImageCard>
        </Grid>
      ))}
    </Grid>
  );

  const renderListView = () => (
    <List>
      {paginatedImages.map((image) => (
        <ListItem
          key={image.id || image.db_id}
          onClick={() => handleImageClick(image)}
          sx={{
            cursor: 'pointer',
            borderRadius: 1,
            mb: 1,
            border: selectedImages.has(image.id) ? '2px solid' : '1px solid transparent',
            borderColor: selectedImages.has(image.id) ? 'primary.main' : 'transparent',
            backgroundColor: image.has_embeddings === false ? '#fff3e0' : 
                            selectedImages.has(image.id) ? 'rgba(25, 118, 210, 0.04)' : 'transparent',
            '&:hover': {
              backgroundColor: 'action.hover'
            }
          }}
        >
          {selectionMode && (
            <Checkbox
              checked={selectedImages.has(image.id)}
              sx={{ mr: 2 }}
            />
          )}
          
          <ListItemAvatar>
            <Avatar
              variant="rounded"
              sx={{ width: 60, height: 60 }}
            >
              <LazyImage
                src={image.image_url}
                alt={image.description || 'Image'}
                style={{ width: '100%', height: '100%' }}
              />
            </Avatar>
          </ListItemAvatar>
          
          <ListItemText
            primary={image.description || 'No description'}
            secondary={
              <Stack direction="row" spacing={2} alignItems="center">
                <Typography variant="caption" color="text.secondary">
                  Set: {image.setName}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {image.created_at ? new Date(image.created_at).toLocaleDateString() : 'N/A'}
                </Typography>
                {image.has_embeddings === false && (
                  <Chip
                    icon={<WarningIcon />}
                    label="No Search"
                    size="small"
                    color="warning"
                    variant="outlined"
                  />
                )}
              </Stack>
            }
          />
          
          <IconButton onClick={(e) => { e.stopPropagation(); setPreviewImage(image); }}>
            <FullscreenIcon />
          </IconButton>
        </ListItem>
      ))}
    </List>
  );

  const renderThumbnailView = () => (
    <Grid container spacing={0.5}>
      {paginatedImages.map((image) => (
        <Grid item key={image.id || image.db_id}>
          <Tooltip
            title={
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {image.description || 'No description'}
                </Typography>
                <Typography variant="caption" color="inherit">
                  Set: {image.setName}
                </Typography>
              </Box>
            }
            placement="top"
            arrow
          >
            <Box
              onClick={() => handleImageClick(image)}
              sx={{
                position: 'relative',
                width: 80,
                height: 80,
                cursor: 'pointer',
                border: selectedImages.has(image.id) ? '2px solid' : '1px solid',
                borderColor: selectedImages.has(image.id) ? 'primary.main' : 'divider',
                borderRadius: 1,
                overflow: 'hidden',
                transition: 'all 0.2s ease',
                '&:hover': {
                  transform: 'scale(1.1)',
                  zIndex: 1,
                  boxShadow: 2
                }
              }}
            >
              {selectionMode && (
                <Checkbox
                  checked={selectedImages.has(image.id)}
                  size="small"
                  sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    zIndex: 2,
                    padding: 0.25,
                    backgroundColor: 'rgba(255,255,255,0.9)'
                  }}
                />
              )}
              <LazyImage
                src={image.image_url}
                alt={image.description || 'Image'}
                style={{ width: '100%', height: '100%' }}
              />
              {image.has_embeddings === false && (
                <Box
                  sx={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    width: 16,
                    height: 16,
                    backgroundColor: 'warning.main',
                    borderRadius: '4px 0 0 0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  <WarningIcon sx={{ fontSize: 12, color: 'white' }} />
                </Box>
              )}
            </Box>
          </Tooltip>
        </Grid>
      ))}
    </Grid>
  );

  const renderSetGroupedView = () => {
    const imagesBySetFiltered = {};
    paginatedImages.forEach(image => {
      if (!imagesBySetFiltered[image.setName]) {
        imagesBySetFiltered[image.setName] = [];
      }
      imagesBySetFiltered[image.setName].push(image);
    });

    return Object.entries(imagesBySetFiltered).map(([setName, images]) => (
      <Box key={setName} sx={{ mb: 4 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 2,
            cursor: 'pointer'
          }}
          onClick={() => toggleSetCollapse(setName)}
        >
          <Typography variant="h6" color="primary" sx={{ fontWeight: 'bold' }}>
            📁 {setName} ({images.length} images)
          </Typography>
          <IconButton>
            {collapsedSets.has(setName) ? <ExpandMoreIcon /> : <ExpandLessIcon />}
          </IconButton>
        </Box>
        
        {!collapsedSets.has(setName) && (
          <Grid container spacing={2}>
            {images.map((image) => (
              <Grid item xs={12} sm={6} md={4} lg={3} key={image.id || image.db_id}>
                <ImageCard 
                  density={density}
                  onClick={() => handleImageClick(image)}
                  sx={{
                    border: selectedImages.has(image.id) ? '3px solid' : 
                           image.has_embeddings === false ? '2px solid' : 'none',
                    borderColor: selectedImages.has(image.id) ? 'primary.main' : 
                                image.has_embeddings === false ? 'warning.main' : 'transparent',
                    backgroundColor: image.has_embeddings === false ? '#fff3e0' : 'inherit'
                  }}
                >
                  {selectionMode && (
                    <Checkbox
                      checked={selectedImages.has(image.id)}
                      sx={{
                        position: 'absolute',
                        top: 8,
                        left: 8,
                        zIndex: 2,
                        backgroundColor: 'rgba(255,255,255,0.9)'
                      }}
                    />
                  )}

                  <Box sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1 }}>
                    {image.has_embeddings === false && (
                      <Chip
                        icon={<SearchOffIcon />}
                        label="No Search"
                        size="small"
                        color="warning"
                        variant="filled"
                      />
                    )}
                  </Box>

                  <LazyImage
                    src={image.image_url}
                    alt={image.description || 'Image'}
                    style={{ height: density === 'compact' ? 120 : density === 'comfortable' ? 160 : 200 }}
                  />
                  
                  <CardContent sx={{ p: density === 'compact' ? 1 : 2 }}>
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {image.description || 'No description'}
                    </Typography>
                    {density !== 'compact' && (
                      <Typography variant="caption" color="text.secondary">
                        {image.created_at ? new Date(image.created_at).toLocaleDateString() : 'N/A'}
                      </Typography>
                    )}
                  </CardContent>
                </ImageCard>
              </Grid>
            ))}
          </Grid>
        )}
      </Box>
    ));
  };

  if (loading) {
    return (
      <Box>
        <Grid container spacing={2}>
          {[...Array(8)].map((_, i) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={i}>
              <Skeleton variant="rectangular" height={160} />
              <Skeleton variant="text" />
              <Skeleton variant="text" width="60%" />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (filteredImages.length === 0) {
    return (
      <Alert severity="info">
        {debouncedSearchTerm || selectedSet !== 'all' || embeddingFilter !== 'all'
          ? 'No images match the current filters.'
          : 'No images found.'}
      </Alert>
    );
  }

  return (
    <Box>
      {/* Controls Header */}
      <Box sx={{ mb: 3 }}>
        {/* Search and Filters Row */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            placeholder="Search images..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              )
            }}
            sx={{ minWidth: 250, flexGrow: 1 }}
            size="small"
          />

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Set</InputLabel>
            <Select
              value={selectedSet}
              onChange={(e) => setSelectedSet(e.target.value)}
              label="Set"
            >
              <MenuItem value="all">All Sets</MenuItem>
              {setNames.map((setName) => (
                <MenuItem key={setName} value={setName}>
                  {setName} ({imagesBySet[setName].length})
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Button
            variant="outlined"
            startIcon={<FilterListIcon />}
            onClick={(e) => setFilterMenuAnchor(e.currentTarget)}
            size="small"
          >
            Filters
          </Button>

          <Button
            variant="outlined"
            startIcon={<SortIcon />}
            onClick={(e) => setSortMenuAnchor(e.currentTarget)}
            size="small"
          >
            Sort
          </Button>

          {selectionMode && (
            <Stack direction="row" spacing={1}>
              <Button
                size="small"
                variant="outlined"
                startIcon={<SelectAllIcon />}
                onClick={selectAll}
              >
                Select All
              </Button>
              {selectedImages.size > 0 && (
                <Button
                  size="small"
                  variant="outlined"
                  color="error"
                  startIcon={<DeleteIcon />}
                  onClick={clearSelection}
                >
                  Clear ({selectedImages.size})
                </Button>
              )}
            </Stack>
          )}
        </Box>

        {/* View Controls Row */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              {filteredImages.length} images • Page {currentPage} of {totalPages}
            </Typography>
            
            <FormControl size="small" sx={{ minWidth: 80 }}>
              <InputLabel>Show</InputLabel>
              <Select
                value={pageSize}
                onChange={(e) => setPageSize(e.target.value)}
                label="Show"
              >
                <MenuItem value={25}>25</MenuItem>
                <MenuItem value={50}>50</MenuItem>
                <MenuItem value={100}>100</MenuItem>
                <MenuItem value={200}>200</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(e, newMode) => newMode && setViewMode(newMode)}
              size="small"
            >
              <ViewModeButton value="grid" title="Grid View">
                <GridViewIcon />
              </ViewModeButton>
              <ViewModeButton value="list" title="List View">
                <ViewListIcon />
              </ViewModeButton>
              <ViewModeButton value="thumbnails" title="Thumbnail View">
                <PhotoLibraryIcon />
              </ViewModeButton>
              <ViewModeButton value="sets" title="Group by Sets">
                <ViewComfyIcon />
              </ViewModeButton>
            </ToggleButtonGroup>

            {(viewMode === 'grid' || viewMode === 'sets') && (
              <ToggleButtonGroup
                value={density}
                exclusive
                onChange={(e, newDensity) => newDensity && setDensity(newDensity)}
                size="small"
              >
                <ToggleButton value="compact" title="Compact">
                  C
                </ToggleButton>
                <ToggleButton value="comfortable" title="Comfortable">
                  M
                </ToggleButton>
                <ToggleButton value="spacious" title="Spacious">
                  S
                </ToggleButton>
              </ToggleButtonGroup>
            )}
          </Box>
        </Box>

        {/* Statistics */}
        {embeddingStats && (
          <Box sx={{ mt: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip 
              icon={<SearchIcon />}
              label={`${embeddingStats.with_embeddings} searchable`}
              color="success"
              size="small"
            />
            {embeddingStats.without_embeddings > 0 && (
              <Chip 
                icon={<WarningIcon />}
                label={`${embeddingStats.without_embeddings} missing embeddings`}
                color="warning"
                size="small"
              />
            )}
            <Typography variant="caption" color="text.secondary">
              {embeddingStats.embedding_coverage_percent}% search coverage
            </Typography>
          </Box>
        )}
      </Box>

      {/* Main Gallery */}
      <Box sx={{ mb: 3 }}>
        {viewMode === 'grid' && renderGridView()}
        {viewMode === 'list' && renderListView()}
        {viewMode === 'thumbnails' && renderThumbnailView()}
        {viewMode === 'sets' && renderSetGroupedView()}
      </Box>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <Pagination
            count={totalPages}
            page={currentPage}
            onChange={(e, page) => setCurrentPage(page)}
            color="primary"
            size="large"
            showFirstButton
            showLastButton
          />
        </Box>
      )}

      {/* Filter Menu */}
      <Menu
        anchorEl={filterMenuAnchor}
        open={Boolean(filterMenuAnchor)}
        onClose={() => setFilterMenuAnchor(null)}
      >
        <MenuItem onClick={() => { setEmbeddingFilter('all'); setFilterMenuAnchor(null); }}>
          <Typography color={embeddingFilter === 'all' ? 'primary' : 'inherit'}>
            All Images
          </Typography>
        </MenuItem>
        <MenuItem onClick={() => { setEmbeddingFilter('searchable'); setFilterMenuAnchor(null); }}>
          <Typography color={embeddingFilter === 'searchable' ? 'primary' : 'inherit'}>
            Searchable Only
          </Typography>
        </MenuItem>
        <MenuItem onClick={() => { setEmbeddingFilter('missing'); setFilterMenuAnchor(null); }}>
          <Typography color={embeddingFilter === 'missing' ? 'primary' : 'inherit'}>
            Missing Embeddings
          </Typography>
        </MenuItem>
      </Menu>

      {/* Sort Menu */}
      <Menu
        anchorEl={sortMenuAnchor}
        open={Boolean(sortMenuAnchor)}
        onClose={() => setSortMenuAnchor(null)}
      >
        <MenuItem onClick={() => { setSortBy('newest'); setSortMenuAnchor(null); }}>
          <Typography color={sortBy === 'newest' ? 'primary' : 'inherit'}>
            Newest First
          </Typography>
        </MenuItem>
        <MenuItem onClick={() => { setSortBy('oldest'); setSortMenuAnchor(null); }}>
          <Typography color={sortBy === 'oldest' ? 'primary' : 'inherit'}>
            Oldest First
          </Typography>
        </MenuItem>
        <MenuItem onClick={() => { setSortBy('name'); setSortMenuAnchor(null); }}>
          <Typography color={sortBy === 'name' ? 'primary' : 'inherit'}>
            By Name
          </Typography>
        </MenuItem>
        <MenuItem onClick={() => { setSortBy('set'); setSortMenuAnchor(null); }}>
          <Typography color={sortBy === 'set' ? 'primary' : 'inherit'}>
            By Set
          </Typography>
        </MenuItem>
      </Menu>

      {/* Image Preview Dialog */}
      <Dialog
        open={Boolean(previewImage)}
        onClose={() => setPreviewImage(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogContent sx={{ p: 0 }}>
          {previewImage && (
            <Box sx={{ position: 'relative' }}>
              <img
                src={previewImage.image_url}
                alt={previewImage.description || 'Image'}
                style={{
                  width: '100%',
                  height: 'auto',
                  maxHeight: '80vh',
                  objectFit: 'contain'
                }}
              />
              <IconButton
                sx={{
                  position: 'absolute',
                  top: 8,
                  right: 8,
                  backgroundColor: 'rgba(0,0,0,0.5)',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: 'rgba(0,0,0,0.7)'
                  }
                }}
                onClick={() => setPreviewImage(null)}
              >
                <CloseIcon />
              </IconButton>
            </Box>
          )}
        </DialogContent>
        
        {previewImage && (
          <DialogActions sx={{ flexDirection: 'column', alignItems: 'stretch', p: 2 }}>
            <Typography variant="h6" gutterBottom>
              {previewImage.description || 'No description'}
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                Set: {previewImage.setName}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {previewImage.created_at ? new Date(previewImage.created_at).toLocaleDateString() : 'N/A'}
              </Typography>
            </Box>
            {previewImage.has_embeddings === false && (
              <Alert severity="warning" sx={{ mt: 1 }}>
                This image is missing embeddings and won't appear in similarity searches.
              </Alert>
            )}
          </DialogActions>
        )}
      </Dialog>
    </Box>
  );
};

export default ImageGallery;