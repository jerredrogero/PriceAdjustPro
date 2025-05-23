export interface ReceiptItem {
  id: number;
  item_code: string;
  description: string;
  price: string;
  quantity: number;
  total_price: string;
  instant_savings: string | null;
  original_price: string | null;
  // Optional fields for editing support
  original_item_code?: string;
  original_description?: string;
  original_quantity?: number;
  needs_quantity_review?: boolean;
}

export interface Receipt {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  total: string;
  items_count: number;
  parsed_successfully: boolean;
  items: ReceiptItem[];
  subtotal: string;
  tax: string;
  instant_savings: string | null;
}

export interface PriceAdjustment {
  id: number;
  receipt: Receipt;
  item: ReceiptItem;
  original_price: string;
  current_price: string;
  potential_savings: string;
  status: 'pending' | 'completed' | 'expired';
  created_at: string;
  expires_at: string;
}

export interface AnalyticsSummary {
  total_spent: string;
  instant_savings: string;
  total_receipts: number;
  total_items: number;
  average_receipt_total: string;
  spending_by_month: {
    [key: string]: {
      total: string;
      count: number;
    };
  };
} 