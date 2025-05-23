import React, { useCallback, useState, useRef } from 'react';
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
  Chip,
  Stack,
  Divider,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  CheckCircleOutline as CheckIcon,
  Description as FileIcon,
  ArrowBack as BackIcon,
  Delete as DeleteIcon,
  PictureAsPdf as PictureAsPdfIcon,
  Info as InfoIcon,
  CameraAlt as CameraIcon,
  Image as ImageIcon,
  PhotoCamera as PhotoCameraIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import api from '../api/axios';
import { LineItem } from '../types';

interface UploadError {
  file: string;
  error: string;
}

interface UploadResponse {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  subtotal: string;
  tax: string;
  total: string;
  items: LineItem[];
  needs_review: boolean;
  review_reason?: string;
  total_items_sold: number;
  parsed_successfully: boolean;
  parse_error?: string | null;
  instant_savings?: string | null;
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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    console.log('Files dropped:', acceptedFiles);
    console.log('File types:', acceptedFiles.map(f => ({ name: f.name, type: f.type })));
    
    // Accept both PDFs and images
    const validFiles = acceptedFiles.filter(file => {
      const name = file.name.toLowerCase();
      const isValid = name.endsWith('.pdf') || 
             name.endsWith('.jpg') || name.endsWith('.jpeg') || 
             name.endsWith('.png') || name.endsWith('.webp') ||
             name.endsWith('.gif') || name.endsWith('.bmp');
      console.log(`File ${file.name}: ${isValid ? 'valid' : 'invalid'}`);
      return isValid;
    });
    
    console.log('Valid files:', validFiles);
    
    if (validFiles.length === 0) {
      setErrors(prev => [...prev, { file: 'Upload', error: 'Please upload PDF files or images (JPG, PNG, etc.)' }]);
      return;
    }

    setSelectedFiles(current => [...current, ...validFiles]);
    setErrors([]);
  }, []);

  const handleCameraCapture = () => {
    if (cameraInputRef.current) {
      cameraInputRef.current.click();
    }
  };

  const handleFileSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleCameraChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      setSelectedFiles(current => [...current, ...Array.from(files)]);
      setErrors([]);
    }
  };

  const getFileIcon = (fileName: string) => {
    const name = fileName.toLowerCase();
    if (name.endsWith('.pdf')) {
      return <PictureAsPdfIcon color="error" />;
    } else {
      return <ImageIcon color="primary" />;
    }
  };

  const getFileTypeChip = (fileName: string) => {
    const name = fileName.toLowerCase();
    if (name.endsWith('.pdf')) {
      return <Chip label="PDF" size="small" color="secondary" />;
    } else {
      return <Chip label="Image" size="small" color="primary" />;
    }
  };

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
    
    const uploadPromises = selectedFiles.map(async (file) => {
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

        const data = response.data;
        
        if (data.parse_error) {
          setErrors(prev => [...prev, { file: file.name, error: data.parse_error }]);
        }
        
        if (data.error && !data.is_duplicate) {
          setErrors(prev => [...prev, { file: file.name, error: data.error }]);
        }
        
        // Remove file from list if:
        // 1. It was successfully processed (parsed_successfully)
        // 2. It's a duplicate (is_duplicate)
        // 3. It had a parse error but was still processed
        if (data.parsed_successfully || data.is_duplicate || data.parse_error) {
          removeFile(file.name);
        }
      } catch (err: any) {
        handleUploadError(err);
        removeFile(file.name);
      }
    });

    try {
      await Promise.all(uploadPromises);
      if (selectedFiles.length === 0) {  // Only navigate if all files were processed
        navigate('/receipts');
      }
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
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
    disabled: uploading,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
    }
  });

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Button
          startIcon={<BackIcon />}
          onClick={() => navigate('/receipts')}
          sx={{ mb: 2 }}
        >
          Back to Receipts
        </Button>
        <Typography variant="h4" component="h1" gutterBottom>
          Upload Receipt
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Snap a photo or upload a PDF/image of your Costco receipt
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card>
        <CardContent>
          {/* Quick Action Buttons */}
          <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
            <Button
              variant="contained"
              startIcon={<PhotoCameraIcon />}
              onClick={handleCameraCapture}
              disabled={uploading}
              sx={{ flex: 1 }}
            >
              Take Photo
            </Button>
            <Button
              variant="outlined"
              startIcon={<UploadIcon />}
              onClick={handleFileSelect}
              disabled={uploading}
              sx={{ flex: 1 }}
            >
              Choose File
            </Button>
          </Stack>

          <Divider sx={{ my: 3 }}>
            <Typography variant="body2" color="text.secondary">
              or drag and drop
            </Typography>
          </Divider>

          {/* Hidden file inputs */}
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: 'none' }}
            onChange={handleCameraChange}
          />
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.webp,.gif,.bmp,image/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              if (e.target.files) {
                console.log('Files selected from input:', Array.from(e.target.files));
                onDrop(Array.from(e.target.files));
              }
            }}
          />

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
                <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
                  <CameraIcon sx={{ fontSize: 48, color: 'primary.main' }} />
                  <UploadIcon sx={{ fontSize: 48, color: 'primary.main' }} />
                </Stack>
                <Typography variant="h6" gutterBottom>
                  {isDragActive ? 'Drop the files here' : 'Drag photos or PDFs here'}
                </Typography>
                <Typography color="text.secondary" gutterBottom>
                  Supports: PDF, JPG, PNG, and other image formats
                </Typography>
              </Box>
            )}
          </Paper>

          {/* File List */}
          {selectedFiles.length > 0 && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="subtitle2" gutterBottom>
                Selected Files ({selectedFiles.length})
              </Typography>
              <List dense>
                {selectedFiles.map((file, index) => (
                  <ListItem
                    key={index}
                    secondaryAction={
                      <IconButton
                        edge="end"
                        onClick={() => removeFile(file.name)}
                        disabled={uploading}
                        color="error"
                      >
                        <DeleteIcon />
                      </IconButton>
                    }
                  >
                    <ListItemIcon>{getFileIcon(file.name)}</ListItemIcon>
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="body2" sx={{ flex: 1 }}>
                            {file.name}
                          </Typography>
                          {getFileTypeChip(file.name)}
                        </Box>
                      }
                      secondary={`${(file.size / 1024 / 1024).toFixed(2)} MB`}
                    />
                    {uploadProgress[file.name] && (
                      <Box sx={{ width: '100%', ml: 2 }}>
                        <LinearProgress
                          variant="determinate"
                          value={uploadProgress[file.name]}
                        />
                      </Box>
                    )}
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {/* Upload Button */}
          {selectedFiles.length > 0 && !uploading && (
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Button
                variant="contained"
                size="large"
                onClick={handleUpload}
                startIcon={<UploadIcon />}
              >
                Process {selectedFiles.length} File{selectedFiles.length > 1 ? 's' : ''}
              </Button>
            </Box>
          )}

          {/* Error Messages */}
          {errors.length > 0 && (
            <Box sx={{ mt: 3 }}>
              {errors.map((error, index) => (
                <Alert key={index} severity="error" sx={{ mb: 1 }}>
                  <strong>{error.file}:</strong> {error.error}
                </Alert>
              ))}
            </Box>
          )}

          {/* Instructions */}
          <Box sx={{ mt: 4 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Tips for better results:
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="primary" />
                </ListItemIcon>
                <ListItemText primary="Take photos in good lighting with minimal shadows" />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="primary" />
                </ListItemIcon>
                <ListItemText primary="Keep the receipt flat and avoid creases when possible" />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="primary" />
                </ListItemIcon>
                <ListItemText primary="Don't worry about strikethrough marks - the system can read through them" />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <WarningIcon color="warning" />
                </ListItemIcon>
                <ListItemText primary="Photo uploads will require manual review for accuracy" />
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