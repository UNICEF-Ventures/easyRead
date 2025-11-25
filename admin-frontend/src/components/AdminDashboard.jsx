import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Alert,
  Chip,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Divider,
  Stack
} from '@mui/material';
import { styled } from '@mui/material/styles';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import PeopleIcon from '@mui/icons-material/People';
import DescriptionIcon from '@mui/icons-material/Description';
import ImageIcon from '@mui/icons-material/Image';
import DownloadIcon from '@mui/icons-material/Download';
import SaveIcon from '@mui/icons-material/Save';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import BarChartIcon from '@mui/icons-material/BarChart';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import ComputerIcon from '@mui/icons-material/Computer';
import RefreshIcon from '@mui/icons-material/Refresh';
import apiClient from '../apiClient';

const StyledCard = styled(Card)(() => ({
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
}));

const MetricCard = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(3),
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(2),
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  color: 'white',
  height: '120px',
}));

const ChartContainer = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(3),
  height: '300px',
  display: 'flex',
  flexDirection: 'column',
}));

const AdminDashboard = () => {
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timePeriod, setTimePeriod] = useState(30);

  const fetchAnalytics = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get(`/admin/api/analytics/?days=${timePeriod}`);
      setAnalyticsData(response.data);
    } catch (err) {
      console.error('Analytics fetch error:', err);
      setError(err.response?.data?.error || 'Failed to fetch analytics data');
    } finally {
      setLoading(false);
    }
  }, [timePeriod]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getConversionRateColor = (rate) => {
    if (rate >= 70) return 'success';
    if (rate >= 40) return 'warning';
    return 'error';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error) {
    return (
      <Container>
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Typography variant="h4" component="h1" fontWeight="bold">
          EasyRead Analytics Dashboard
        </Typography>
        <Stack direction="row" spacing={2} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Period</InputLabel>
            <Select
              value={timePeriod}
              label="Period"
              onChange={(e) => setTimePeriod(e.target.value)}
            >
              <MenuItem value={7}>Last 7 days</MenuItem>
              <MenuItem value={30}>Last 30 days</MenuItem>
              <MenuItem value={90}>Last 90 days</MenuItem>
            </Select>
          </FormControl>
          <IconButton onClick={fetchAnalytics} color="primary">
            <RefreshIcon />
          </IconButton>
        </Stack>
      </Box>

      {/* Key Metrics */}
      <Grid container spacing={3} mb={4}>
        <Grid item xs={12} sm={6} md={2.4}>
          <MetricCard>
            <PeopleIcon fontSize="large" />
            <Box>
              <Typography variant="h4" component="div" fontWeight="bold">
                {analyticsData.summary.total_sessions}
              </Typography>
              <Typography variant="body2">Total Sessions</Typography>
            </Box>
          </MetricCard>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <Tooltip title="Sentences generated from document processing (PDF upload → Easy Read conversion)">
            <MetricCard>
              <DescriptionIcon fontSize="large" />
              <Box>
                <Typography variant="h4" component="div" fontWeight="bold">
                  {analyticsData.content.total_sentences}
                </Typography>
                <Typography variant="body2">Sentences Generated</Typography>
                <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.7rem' }}>
                  From document processing
                </Typography>
              </Box>
            </MetricCard>
          </Tooltip>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <MetricCard>
            <SaveIcon fontSize="large" />
            <Box>
              <Typography variant="h4" component="div" fontWeight="bold">
                {analyticsData.saved_content.total_saved}
              </Typography>
              <Typography variant="body2">Content Saved</Typography>
            </Box>
          </MetricCard>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <MetricCard>
            <DownloadIcon fontSize="large" />
            <Box>
              <Typography variant="h4" component="div" fontWeight="bold">
                {analyticsData.summary.sessions_with_export}
              </Typography>
              <Typography variant="body2">Exports Created</Typography>
            </Box>
          </MetricCard>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <MetricCard>
            <ImageIcon fontSize="large" />
            <Box>
              <Typography variant="h4" component="div" fontWeight="bold">
                {analyticsData.images.total_images.toLocaleString()}
              </Typography>
              <Typography variant="body2">Images Available</Typography>
            </Box>
          </MetricCard>
        </Grid>
      </Grid>

      {/* Conversion Funnel */}
      <Grid container spacing={3} mb={4}>
        <Grid item xs={12} md={6}>
          <StyledCard>
            <CardHeader 
              title="User Journey Conversion Rates"
              avatar={<TrendingUpIcon />}
            />
            <CardContent>
              <Box mb={2}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  PDF Upload → Processing: {analyticsData.summary.conversion_rates.pdf_to_processing}%
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={analyticsData.summary.conversion_rates.pdf_to_processing}
                  color={getConversionRateColor(analyticsData.summary.conversion_rates.pdf_to_processing)}
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
              <Box mb={2}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Processing → Export: {analyticsData.summary.conversion_rates.processing_to_export}%
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={analyticsData.summary.conversion_rates.processing_to_export}
                  color={getConversionRateColor(analyticsData.summary.conversion_rates.processing_to_export)}
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  PDF Upload → Export: {analyticsData.summary.conversion_rates.pdf_to_export}%
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={analyticsData.summary.conversion_rates.pdf_to_export}
                  color={getConversionRateColor(analyticsData.summary.conversion_rates.pdf_to_export)}
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
            </CardContent>
          </StyledCard>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <StyledCard>
            <CardHeader 
              title="Content Statistics"
              avatar={<BarChartIcon />}
            />
            <CardContent>
              <Stack spacing={2}>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">Avg Sentences per Session:</Typography>
                  <Chip 
                    label={analyticsData.content.avg_sentences_per_session} 
                    color={analyticsData.content.avg_sentences_per_session > 0 ? "primary" : "default"}
                    size="small"
                  />
                </Box>
                {analyticsData.content.avg_sentences_per_session === 0 && (
                  <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic', fontSize: '0.75rem' }}>
                    No document processing sessions yet - upload a PDF to generate sentences
                  </Typography>
                )}
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">Avg PDF Size:</Typography>
                  <Chip label={formatBytes(analyticsData.content.avg_pdf_size_bytes)} color="secondary" />
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">Avg Input Length:</Typography>
                  <Chip label={`${analyticsData.content.avg_input_content_chars} chars`} color="info" />
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2">Image Sets Available:</Typography>
                  <Chip label={analyticsData.images.total_image_sets} color="success" />
                </Box>
              </Stack>
            </CardContent>
          </StyledCard>
        </Grid>
      </Grid>

      {/* Activity Charts */}
      <Grid container spacing={3} mb={4}>
        <Grid item xs={12} md={8}>
          <ChartContainer>
            <Typography variant="h6" gutterBottom>
              <ShowChartIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              Daily Activity Trends
            </Typography>
            <Box flex={1} display="flex" alignItems="center" justifyContent="center">
              <Typography color="text.secondary">
                Chart visualization would be implemented here with a library like Chart.js or Recharts
              </Typography>
            </Box>
            {/* Simple activity list as alternative */}
            <Box mt={2} sx={{ maxHeight: 200, overflowY: 'auto' }}>
              <Typography variant="subtitle2" gutterBottom>Recent Activity Summary:</Typography>
              <Box sx={{ maxHeight: 150, overflowY: 'auto', pr: 1 }}>
                {analyticsData.daily_activity.slice(-7).map((day, index) => (
                  <Box key={index} display="flex" justifyContent="space-between" mb={1} sx={{ minHeight: 24 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
                      {formatDate(day.date)}:
                    </Typography>
                    <Typography variant="body2" sx={{ fontSize: '0.8rem', textAlign: 'right' }}>
                      {day.sessions}s, {day.events}e
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          </ChartContainer>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <StyledCard>
            <CardHeader 
              title="Popular Image Sets"
              avatar={<ImageIcon />}
            />
            <CardContent sx={{ maxHeight: 300, overflow: 'auto' }}>
              <List dense>
                {analyticsData.images.popular_sets.map((set, index) => (
                  <ListItem key={index}>
                    <ListItemText 
                      primary={set.image_set__name || 'Unknown Set'}
                      secondary={`${set.count} selections`}
                    />
                  </ListItem>
                ))}
                {analyticsData.images.popular_sets.length === 0 && (
                  <Typography color="text.secondary" align="center">
                    No image set data available
                  </Typography>
                )}
              </List>
            </CardContent>
          </StyledCard>
        </Grid>
      </Grid>

      {/* Recent Activity & User Agents */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <StyledCard>
            <CardHeader 
              title="Recent Sessions"
              avatar={<ShowChartIcon />}
            />
            <CardContent>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Session ID</TableCell>
                      <TableCell>Started</TableCell>
                      <TableCell>Last Active</TableCell>
                      <TableCell>PDF</TableCell>
                      <TableCell>Sentences</TableCell>
                      <TableCell>Exported</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {analyticsData.recent_sessions.map((session, index) => (
                      <TableRow key={index}>
                        <TableCell>
                          <Tooltip title={session.session_id}>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              {session.session_id.substring(0, 8)}...
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {formatDate(session.started_at)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {formatDate(session.last_activity)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip 
                            size="small"
                            label={session.pdf_uploaded ? "Yes" : "No"}
                            color={session.pdf_uploaded ? "success" : "default"}
                          />
                        </TableCell>
                        <TableCell>{session.sentences_generated}</TableCell>
                        <TableCell>
                          <Chip 
                            size="small"
                            label={session.exported_result ? "Yes" : "No"}
                            color={session.exported_result ? "success" : "default"}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </StyledCard>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <StyledCard>
            <CardHeader 
              title="Top User Agents"
              avatar={<ComputerIcon />}
            />
            <CardContent sx={{ maxHeight: 300, overflow: 'auto' }}>
              <List dense>
                {analyticsData.user_agents.map((agent, index) => (
                  <ListItem key={index}>
                    <ListItemText 
                      primary={agent.user_agent.substring(0, 40) + '...'}
                      secondary={`${agent.count} sessions`}
                    />
                  </ListItem>
                ))}
                {analyticsData.user_agents.length === 0 && (
                  <Typography color="text.secondary" align="center">
                    No user agent data available
                  </Typography>
                )}
              </List>
            </CardContent>
          </StyledCard>
        </Grid>
      </Grid>

      {/* Event Types Summary */}
      <Box mt={4}>
        <StyledCard>
          <CardHeader 
            title="Event Activity Summary"
            subheader={`Total Events: ${analyticsData.events.total}`}
            avatar={<CalendarTodayIcon />}
          />
          <CardContent>
            <Grid container spacing={2}>
              {analyticsData.events.by_type.map((event, index) => (
                <Grid item xs={6} sm={4} md={3} key={index}>
                  <Box textAlign="center" p={2}>
                    <Typography variant="h6" color="primary">
                      {event.count}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {event.event_type.replace('_', ' ').toUpperCase()}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </StyledCard>
      </Box>
    </Container>
  );
};

export default AdminDashboard;