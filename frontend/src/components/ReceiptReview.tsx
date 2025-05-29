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

const ReceiptReview: React.FC<Props> = ({ receipt, open, onClose, onSave }) => {
  const [items, setItems] = useState<LineItem[]>(
    receipt.items.map(item => ({
      ...item,
      original_description: item.original_description || item.description,
      original_quantity: item.original_quantity || item.quantity,
      original_item_code: item.original_item_code || item.item_code,
      original_total_price: item.total_price || (parseFloat(item.price) * item.quantity).toFixed(2)
    }))
  );
  const [error, setError] = useState<string>('');

  const handleQuantityChange = (index: number, newQuantity: number) => {
    const newItems = [...items];
    const item = newItems[index];
    
    // Calculate per-unit price from the original total price from receipt
    const originalTotalPrice = parseFloat(item.original_total_price || item.total_price || (parseFloat(item.price) * item.quantity).toString());
    const perUnitPrice = originalTotalPrice / newQuantity;
    
    newItems[index] = {
      ...newItems[index],
      quantity: newQuantity,
      price: perUnitPrice.toFixed(2), // Store per-unit price for comparisons
      total_price: originalTotalPrice.toFixed(2) // Keep original total from receipt
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

  const handleItemCodeChange = (index: number, newItemCode: string) => {
    const newItems = [...items];
    newItems[index] = {
      ...newItems[index],
      item_code: newItemCode,
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

        <Alert severity="info" sx={{ mt: 1, mb: 2 }}>
          <Typography variant="body2">
            <strong>Beta Feature:</strong> Item codes can be edited for accuracy. 
            These are used to match products across users for price adjustment alerts.
          </Typography>
        </Alert>

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
                  <TableCell>
                    <TextField
                      fullWidth
                      value={item.item_code}
                      onChange={(e) => handleItemCodeChange(index, e.target.value)}
                      variant="standard"
                      helperText={
                        item.item_code !== (item.original_item_code || item.item_code)
                          ? `Original: ${item.original_item_code || item.item_code}`
                          : undefined
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <TextField
                      fullWidth
                      value={item.description}
                      onChange={(e) => handleDescriptionChange(index, e.target.value)}
                      variant="standard"
                      helperText={
                        item.description !== (item.original_description || item.description)
                          ? `Original: ${item.original_description || item.description}`
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
                        item.quantity !== (item.original_quantity || item.quantity)
                          ? `Original: ${item.original_quantity || item.quantity}`
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