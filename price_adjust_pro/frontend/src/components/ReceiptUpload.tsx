import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Typography,
  Paper,
  CircularProgress,
  Alert,
  Button,
  Fade,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  useTheme,
  alpha,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  CheckCircleOutline as CheckIcon,
  Description as FileIcon,
  ArrowBack as BackIcon,
} from '@mui/icons-material';
import axios from 'axios';

const ReceiptUpload: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF file');
      return;
    }

    setSelectedFile(file);
    setError(null);
  }, []);

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('receipt_file', selectedFile);

    try {
      const response = await axios.post('/api/receipts/upload/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      navigate(`/receipt/${response.data.id}`);
    } catch (err: any) {
      setError(
        err.response?.data?.message ||
        'Failed to upload receipt. Please try again.'
      );
      setUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <Fade in>
      <Box sx={{ maxWidth: 800, mx: 'auto', p: 3 }}>
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h4" gutterBottom>
            Upload Receipt
          </Typography>
          <Button
            startIcon={<BackIcon />}
            onClick={() => navigate('/')}
            variant="outlined"
            sx={{
              '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.04),
              },
            }}
          >
            Back to Receipts
          </Button>
        </Box>

        {error && (
          <Alert 
            severity="error" 
            sx={{ mb: 3 }}
            onClose={() => setError(null)}
          >
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', md: 'row' } }}>
          <Box sx={{ flex: 1 }}>
            <Paper
              {...getRootProps()}
              sx={{
                p: 4,
                textAlign: 'center',
                cursor: uploading ? 'not-allowed' : 'pointer',
                backgroundColor: isDragActive ? alpha(theme.palette.primary.main, 0.04) : 'background.paper',
                border: '2px dashed',
                borderColor: isDragActive ? 'primary.main' : 'divider',
                borderRadius: 2,
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  backgroundColor: alpha(theme.palette.primary.main, 0.04),
                  borderColor: 'primary.main',
                },
              }}
            >
              <input {...getInputProps()} />
              
              {uploading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <CircularProgress size={48} sx={{ mb: 2 }} />
                  <Typography variant="h6" color="primary">Processing receipt...</Typography>
                  <Typography color="text.secondary" sx={{ mt: 1 }}>
                    This may take a few moments
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  {selectedFile ? (
                    <>
                      <CheckIcon sx={{ fontSize: 48, mb: 2, color: 'success.main' }} />
                      <Typography variant="h6" gutterBottom color="success.main">
                        File Selected
                      </Typography>
                      <Typography color="text.secondary" gutterBottom>
                        {selectedFile.name}
                      </Typography>
                      <Button
                        variant="contained"
                        color="primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleUpload();
                        }}
                        sx={{ mt: 2 }}
                      >
                        Upload Now
                      </Button>
                    </>
                  ) : (
                    <>
                      <UploadIcon sx={{ fontSize: 48, mb: 2, color: 'primary.main' }} />
                      <Typography variant="h6" gutterBottom>
                        {isDragActive
                          ? 'Drop the PDF here'
                          : 'Drag and drop a receipt PDF here'}
                      </Typography>
                      <Typography color="text.secondary" gutterBottom>
                        or
                      </Typography>
                      <Button 
                        variant="contained" 
                        component="span" 
                        disabled={uploading}
                        sx={{
                          mt: 1,
                          '&:hover': {
                            backgroundColor: theme.palette.primary.dark,
                          },
                        }}
                      >
                        Browse Files
                      </Button>
                    </>
                  )}
                </Box>
              )}
            </Paper>
          </Box>

          <Card sx={{ flex: 1, height: 'fit-content' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <FileIcon color="primary" />
                Instructions
              </Typography>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <CheckIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Upload a PDF file of your receipt"
                    secondary="Make sure the text in the PDF is clear and readable"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="File size limit"
                    secondary="Maximum file size is 10MB"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Supported receipts"
                    secondary="Currently supporting Costco receipts"
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Fade>
  );
};

export default ReceiptUpload; 