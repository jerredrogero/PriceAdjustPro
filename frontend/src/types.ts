export interface LineItem {
  id?: number;
  item_code: string;
  description: string;
  price: string;
  quantity: number;
  discount?: string | null;
  total_price?: string;
  is_taxable: boolean;
  on_sale?: boolean;
  instant_savings?: string | null;
  original_price?: string | null;
  original_description?: string;
  original_quantity?: number;
  original_item_code?: string;
  original_total_price?: string;
  needs_quantity_review?: boolean;
  editable?: boolean;
}

export interface Receipt {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  subtotal: string;
  tax: string;
  total: string;
  items: LineItem[];
  parsed_successfully: boolean;
  parse_error?: string | null;
  file?: string | null;
  ebt_amount?: string | null;
  instant_savings?: string | null;
  needs_review?: boolean;
  review_reason?: string;
  total_items_sold?: number;
  source_type?: 'pdf' | 'image';
  confidence_note?: string;
}

export interface PriceAdjustment {
  item_code: string;
  description: string;
  current_price: number;
  lower_price: number;
  price_difference: number;
  store_location: string;
  store_number: string;
  purchase_date: string;
  days_remaining: number;
  claim_days_remaining?: number | null;
  original_store: string;
  original_store_number: string;
}

export interface AnalyticsData {
  total_spent: string;
  total_saved: string;
  total_receipts: number;
  total_items: number;
  average_receipt_total: string;
  most_purchased_items: Array<{
    item_code: string;
    description: string;
    count: number;
    total_spent: string;
  }>;
  spending_by_month: {
    [key: string]: {
      total: string;
      count: number;
    };
  };
  most_visited_stores: Array<{
    store: string;
    visits: number;
  }>;
  tax_paid: string;
  total_ebt_used: string;
  instant_savings: string;
} 