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
  Divider,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Description as FileIcon,
  Delete as DeleteIcon,
  PictureAsPdf as PictureAsPdfIcon,
  Info as InfoIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material';
import api from '../api/axios';
import { Receipt } from '../types';

interface UploadError {
  file: string;
  error: string;
}

interface UploadResponse {
  transaction_number: string;
  message: string;
  items: Array<{
    item_code: string;
    description: string;
    price: string;
    quantity: number;
    discount: string | null;
  }>;
  parse_error?: string | null;
  parsed_successfully: boolean;
  is_duplicate: boolean;
}

interface UploadedFile {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
  transactionNumber?: string;
}

const ReceiptUpload: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [errors, setErrors] = useState<UploadError[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{[key: string]: number}>({});
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      status: 'pending' as const
    }));
    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    setUploading(true);
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.status === 'success' || file.status === 'uploading') continue;

      setFiles(prev => prev.map((f, index) => 
        index === i ? { ...f, status: 'uploading' } : f
      ));

      const formData = new FormData();
      formData.append('receipt_file', file.file);

      try {
        const response = await api.post('/api/receipts/upload/', formData);
        setFiles(prev => prev.map((f, index) => 
          index === i ? { 
            ...f, 
            status: 'success',
            transactionNumber: response.data.transaction_number
          } : f
        ));
      } catch (error) {
        setFiles(prev => prev.map((f, index) => 
          index === i ? { ...f, status: 'error', error: 'Upload failed' } : f
        ));
      }
    }
    
    setUploading(false);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true
  });

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        Upload Receipts
      </Typography>

      {/* Instructions Section */}
      <Paper sx={{ p: 4, mb: 4 }}>
        <Typography variant="h5" gutterBottom>
          How to Find Your Costco Receipts
        </Typography>
        <List>
          <ListItem>
            <ListItemIcon>
              <Typography variant="h6" color="primary">1.</Typography>
            </ListItemIcon>
            <ListItemText 
              primary="Log in to Costco.com" 
              secondary="Visit Costco.com and sign in to your account"
            />
          </ListItem>
          <ListItem>
            <ListItemIcon>
              <Typography variant="h6" color="primary">2.</Typography>
            </ListItemIcon>
            <ListItemText 
              primary="Navigate to Orders & Returns" 
              secondary="Click on 'Orders & Returns' in the top navigation menu"
            />
          </ListItem>
          <ListItem>
            <ListItemIcon>
              <Typography variant="h6" color="primary">3.</Typography>
            </ListItemIcon>
            <ListItemText 
              primary="Find Your Order" 
              secondary="Locate the order you want to track"
            />
          </ListItem>
          <ListItem>
            <ListItemIcon>
              <Typography variant="h6" color="primary">4.</Typography>
            </ListItemIcon>
            <ListItemText 
              primary="Download Receipt" 
              secondary="Click 'View Receipt' and download the PDF"
            />
          </ListItem>
        </List>
        <Box sx={{ mt: 2 }}>
          <Button
            variant="contained"
            component="a"
            href="https://www.costco.com/OrderStatusCmd"
            target="_blank"
            rel="noopener noreferrer"
            endIcon={<ArrowForwardIcon />}
          >
            Go to Costco Orders
          </Button>
        </Box>
      </Paper>

      <Divider sx={{ my: 4 }} />

      {/* Upload Section */}
      <Paper
        {...getRootProps()}
        sx={{
          p: 4,
          border: `2px dashed ${theme.palette.primary.main}`,
          borderRadius: 2,
          cursor: 'pointer',
          bgcolor: isDragActive ? alpha(theme.palette.primary.main, 0.1) : 'background.paper',
          transition: 'background-color 0.3s ease',
          textAlign: 'center',
        }}
      >
        <input {...getInputProps()} />
        <UploadIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
        <Typography variant="h6" gutterBottom>
          {isDragActive ? 'Drop your receipt PDFs here' : 'Drag and drop receipt PDFs here'}
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          Save time by uploading multiple receipts at once
        </Typography>
        <Typography color="text.secondary">
          or click to select files
        </Typography>
      </Paper>

      {files.length > 0 && (
        <Paper sx={{ mt: 4, p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Selected Files
          </Typography>
          <List>
            {files.map((file, index) => (
              <ListItem
                key={index}
                secondaryAction={
                  <IconButton
                    edge="end"
                    onClick={() => removeFile(index)}
                    disabled={file.status === 'uploading'}
                  >
                    <DeleteIcon />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={file.file.name}
                  secondary={
                    file.status === 'uploading' ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CircularProgress size={16} />
                        <Typography variant="body2">Uploading...</Typography>
                      </Box>
                    ) : file.status === 'success' ? (
                      <Typography variant="body2" color="success.main">
                        Uploaded successfully
                      </Typography>
                    ) : file.status === 'error' ? (
                      <Typography variant="body2" color="error">
                        {file.error}
                      </Typography>
                    ) : null
                  }
                />
              </ListItem>
            ))}
          </List>
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              onClick={handleUpload}
              disabled={uploading || files.every(f => f.status === 'success')}
              startIcon={uploading ? <CircularProgress size={20} /> : null}
            >
              {uploading ? 'Uploading...' : 'Upload Selected Files'}
            </Button>
          </Box>
        </Paper>
      )}
    </Container>
  );
};

export default ReceiptUpload; 