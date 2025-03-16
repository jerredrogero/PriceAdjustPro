import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { Receipt, LineItem } from '../types';

interface Props {
  receipt: Partial<Receipt> & {
    items: LineItem[];
    total_items_sold: number;
    review_reason?: string;
  };
  open: boolean;
  onClose: () => void;
  onSave: (updatedReceipt: Partial<Receipt>) => void;
}

interface EditableItem extends Omit<LineItem, 'original_description' | 'original_quantity'> {
  original_description: string;
  original_quantity: number;
}

const ReceiptReview: React.FC<Props> = ({ receipt, open, onClose, onSave }) => {
  const [items, setItems] = useState<EditableItem[]>(
    receipt.items.map(item => ({
      ...item,
      original_description: item.original_description || item.description,
      original_quantity: item.original_quantity || item.quantity,
    }))
  );
  const [error, setError] = useState<string>('');

  const handleQuantityChange = (index: number, newQuantity: number) => {
    const newItems = [...items];
    newItems[index] = {
      ...newItems[index],
      quantity: newQuantity,
    };
    setItems(newItems);
  };

  const handleDescriptionChange = (index: number, newDescription: string) => {
    const newItems = [...items];
    newItems[index] = {
      ...newItems[index],
      description: newDescription,
    };
    setItems(newItems);
  };

  const handleSave = () => {
    // Validate total quantity matches expected count
    const totalQuantity = items.reduce((sum, item) => sum + item.quantity, 0);
    if (totalQuantity !== receipt.total_items_sold) {
      setError(`Total quantity (${totalQuantity}) must match receipt total (${receipt.total_items_sold})`);
      return;
    }

    // Create updated receipt
    const updatedReceipt: Partial<Receipt> = {
      ...receipt,
      items: items.map(item => ({
        ...item,
        needs_quantity_review: false,  // Clear review flag
      })),
      needs_review: false,  // Clear review flag
    };

    onSave(updatedReceipt);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Review Receipt Items</DialogTitle>
      <DialogContent>
        {receipt.review_reason && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {receipt.review_reason}
          </Alert>
        )}
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        <Typography variant="body2" color="text.secondary" gutterBottom>
          Total items on receipt: {receipt.total_items_sold}
        </Typography>

        <TableContainer component={Paper} sx={{ mt: 2 }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Item Code</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="right">Unit Price</TableCell>
                <TableCell align="right">Quantity</TableCell>
                <TableCell align="right">Total</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item, index) => (
                <TableRow key={item.item_code}>
                  <TableCell>{item.item_code}</TableCell>
                  <TableCell>
                    <TextField
                      fullWidth
                      value={item.description}
                      onChange={(e) => handleDescriptionChange(index, e.target.value)}
                      variant="standard"
                      helperText={
                        item.description !== item.original_description
                          ? `Original: ${item.original_description}`
                          : undefined
                      }
                    />
                  </TableCell>
                  <TableCell align="right">${item.price}</TableCell>
                  <TableCell align="right">
                    <TextField
                      type="number"
                      value={item.quantity}
                      onChange={(e) => handleQuantityChange(index, parseInt(e.target.value) || 0)}
                      variant="standard"
                      error={item.needs_quantity_review}
                      helperText={
                        item.quantity !== item.original_quantity
                          ? `Original: ${item.original_quantity}`
                          : undefined
                      }
                      inputProps={{ min: 1, style: { textAlign: 'right' } }}
                      sx={{ width: 80 }}
                    />
                  </TableCell>
                  <TableCell align="right">
                    ${(parseFloat(item.price) * item.quantity).toFixed(2)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" color="primary">
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ReceiptReview; 