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
  Container,
  IconButton,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  CheckCircleOutline as CheckIcon,
  Description as FileIcon,
  ArrowBack as BackIcon,
  Delete as DeleteIcon,
  PictureAsPdf as PictureAsPdfIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import api from '../api/axios';

interface UploadError {
  file: string;
  error: string;
}

const ReceiptUpload: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [uploading, setUploading] = useState(false);
  const [errors, setErrors] = useState<UploadError[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{[key: string]: number}>({});
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const pdfFiles = acceptedFiles.filter(file => file.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) {
      setErrors(prev => [...prev, { file: 'Upload', error: 'Please upload PDF files only' }]);
      return;
    }

    setSelectedFiles(current => [...current, ...pdfFiles]);
    setErrors([]);
  }, []);

  const removeFile = (fileName: string) => {
    setSelectedFiles(current => current.filter(file => file.name !== fileName));
    setUploadProgress(current => {
      const newProgress = { ...current };
      delete newProgress[fileName];
      return newProgress;
    });
    setErrors(current => current.filter(error => error.file !== fileName));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    
    setUploading(true);
    setErrors([]);
    
    for (const file of selectedFiles) {
      const formData = new FormData();
      formData.append('receipt_file', file);

      try {
        const response = await api.post('/api/receipts/upload/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
              setUploadProgress(current => ({
                ...current,
                [file.name]: progress
              }));
            }
          }
        });

        if (response.data.parse_error) {
          setErrors(prev => [...prev, { file: file.name, error: response.data.parse_error }]);
        }
      } catch (err: any) {
        handleUploadError(err);
      }
    }

    setUploading(false);
    
    // Only navigate if there were no errors
    if (errors.length === 0 && !duplicateDialogOpen) {
      navigate('/receipts');
    }
  };

  const handleDuplicateConfirm = async () => {
    setDuplicateDialogOpen(false);
    if (!currentFile) return;

    const formData = new FormData();
    formData.append('receipt_file', currentFile);
    formData.append('force_update', 'true');

    try {
      await api.post('/api/receipts/upload/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });
      removeFile(currentFile.name);
    } catch (err: any) {
      handleUploadError(err);
    }
    setCurrentFile(null);
  };

  const handleUploadError = (error: any) => {
    if (error.response?.data?.error?.includes('UNIQUE constraint failed')) {
      setError('This receipt has already been uploaded');
    } else if (error.response?.data?.error?.includes('NOT NULL constraint failed')) {
      setError('Authentication error - please login again');
    } else {
      setError(error.response?.data?.error || 'Upload failed');
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: true,
    disabled: uploading,
  });

  return (
    <Container maxWidth="sm" sx={{ py: 4 }}>
      <Card elevation={3}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <UploadIcon sx={{ fontSize: 40, color: 'primary.main', mb: 2 }} />
            <Typography variant="h4" component="h1" gutterBottom>
              Upload Receipts
            </Typography>
            <Typography color="text.secondary">
              Upload one or more Costco receipt PDFs
            </Typography>
          </Box>

          {errors.length > 0 && (
            <Box sx={{ mb: 3 }}>
              {errors.map((error, index) => (
                <Alert key={index} severity="error" sx={{ mb: 1 }}>
                  {error.file}: {error.error}
                </Alert>
              ))}
            </Box>
          )}

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
              mb: 3,
            }}
          >
            <input {...getInputProps()} />
            
            {uploading ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <CircularProgress size={48} sx={{ mb: 2 }} />
                <Typography variant="h6" color="primary">Processing receipts...</Typography>
                <Typography color="text.secondary" sx={{ mt: 1 }}>
                  This may take a few moments
                </Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <UploadIcon sx={{ fontSize: 48, mb: 2, color: 'primary.main' }} />
                <Typography variant="h6" gutterBottom>
                  {isDragActive ? 'Drop the PDFs here' : 'Drag and drop receipt PDFs here'}
                </Typography>
                <Typography color="text.secondary" gutterBottom>
                  or
                </Typography>
                <Button 
                  variant="contained" 
                  component="span" 
                  disabled={uploading}
                  sx={{ mt: 1 }}
                >
                  Browse Files
                </Button>
              </Box>
            )}
          </Paper>

          {selectedFiles.length > 0 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Selected Files ({selectedFiles.length})
              </Typography>
              <List>
                {selectedFiles.map((file) => (
                  <ListItem
                    key={file.name}
                    secondaryAction={
                      !uploading && (
                        <IconButton edge="end" onClick={() => removeFile(file.name)}>
                          <DeleteIcon />
                        </IconButton>
                      )
                    }
                  >
                    <ListItemIcon>
                      <PictureAsPdfIcon />
                    </ListItemIcon>
                    <ListItemText 
                      primary={file.name}
                      secondary={
                        uploading && uploadProgress[file.name] !== undefined && (
                          <LinearProgress 
                            variant="determinate" 
                            value={uploadProgress[file.name]} 
                            sx={{ mt: 1 }}
                          />
                        )
                      }
                    />
                  </ListItem>
                ))}
              </List>

              <Button
                variant="contained"
                fullWidth
                size="large"
                onClick={handleUpload}
                disabled={uploading}
                startIcon={uploading ? <CircularProgress size={20} /> : <UploadIcon />}
                sx={{ mt: 2 }}
              >
                {uploading ? 'Uploading...' : 'Upload Selected Files'}
              </Button>
            </Box>
          )}

          <Box sx={{ mt: 4 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Instructions:
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="primary" />
                </ListItemIcon>
                <ListItemText primary="Upload multiple PDF files at once" />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="primary" />
                </ListItemIcon>
                <ListItemText primary="Files must be in PDF format" />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="primary" />
                </ListItemIcon>
                <ListItemText primary="Each receipt will be processed individually" />
              </ListItem>
            </List>
          </Box>
        </CardContent>
      </Card>

      <Dialog
        open={duplicateDialogOpen}
        onClose={() => {
          setDuplicateDialogOpen(false);
          setCurrentFile(null);
        }}
      >
        <DialogTitle>Duplicate Receipt</DialogTitle>
        <DialogContent>
          <Typography>
            This receipt has already been uploaded. Would you like to update the existing receipt?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => {
              setDuplicateDialogOpen(false);
              setCurrentFile(null);
              if (currentFile) {
                removeFile(currentFile.name);
              }
            }}
          >
            Skip
          </Button>
          <Button onClick={handleDuplicateConfirm} variant="contained" color="primary">
            Update Existing
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default ReceiptUpload; 