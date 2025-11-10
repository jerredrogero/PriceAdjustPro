import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional
import json
import os
from django.conf import settings
import logging
import uuid

# Try to import Google Generative AI, but provide a mock if not available
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    # Mock implementation for development
    class MockGenAI:
        def configure(self, *args, **kwargs):
            pass
        
        class GenerativeModel:
            def __init__(self, *args, **kwargs):
                pass
                
            def generate_content(self, *args, **kwargs):
                class MockResponse:
                    def __init__(self):
                        self.text = "Mock response for development"
                return MockResponse()
    
    genai = MockGenAI()

from django.utils import timezone
import base64
from django.urls import reverse
from .models import (
    CostcoItem, CostcoWarehouse,
    PriceAdjustmentAlert, Receipt, LineItem,
    CostcoPromotion, OfficialSaleItem
)

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file using Gemini Vision."""
    try:
        # If GenAI is not available, return a mock response for development
        if not GENAI_AVAILABLE:
            return """MOCK COSTCO RECEIPT FOR DEVELOPMENT
WAREHOUSE #123 - ANYTOWN, USA
DATE: 2023-05-15 12:34:56
MEMBER: 12345678

E 1347776 KS WD FL HNY 12.99 3
346014 /1347776 3.00-
E 1234567 BANANAS 4.99 1
E 7654321 MILK 3.49 2
E 9876543 EGGS 5.99 1

SUBTOTAL 45.94
TAX 3.67
TOTAL 49.61

TOTAL INSTANT SAVINGS 3.00
"""
            
        # Read the PDF file as binary
        with open(pdf_path, 'rb') as file:
            pdf_content = file.read()
        
        # Configure Gemini
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise Exception("Gemini API key not configured")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Create the prompt for text extraction
        prompt = """This is a Costco receipt. Please extract all the text from this receipt, preserving the exact format and numbers. Pay special attention to:

1. Item lines starting with 'E' followed by an item code and description
2. Discount lines that follow items, which:
   - End with a minus sign (e.g. "3.00-")
   - Contain a forward slash followed by the item code (e.g. "/1726362")
   - Show the instant savings amount
3. Store location and number
4. Transaction date and number
5. Subtotal, tax, and total amounts
6. Total instant savings amount

Example format to look for:
E 1347776 KS WD FL HNY 12.99 3
346014 /1347776 3.00-
E 1726362 POUCH 13.89 3

Output the text exactly as it appears, maintaining line breaks and spacing."""
        
        # Create the image data
        image_data = {
            "mime_type": "application/pdf",
            "data": base64.b64encode(pdf_content).decode('utf-8')
        }
        
        # Generate response
        response = model.generate_content([prompt, image_data], stream=False)
        
        # Return the extracted text
        return response.text
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        raise

def parse_receipt(text: str) -> Dict:
    """
    Parse receipt text using Google's Gemini API.
    """
    try:
        prompt = """You are a specialized Costco receipt parser. Extract and return these fields from the receipt:

store_location: Store name and location (e.g. "Costco Athens #1621")
store_number: Store number only (e.g. "1621")
transaction_date: Date and time (format EXACTLY as MM/DD/YYYY HH:MM, e.g. 12/27/2024 16:54)
transaction_number: The 13-digit number after the date/time (e.g. 1621206176706)
items: List each item with:
- item_code: The first number on the line
- description: The item description
- price: The final price shown
- is_taxable: Y/N (look for Y after the price)
- instant_savings: The amount from the discount line that follows (e.g. "346014 /1726362 3.00-"), null if no discount line
- original_price: Calculate by adding price + instant_savings, null if no instant savings

IMPORTANT: Look for discount lines that follow item lines. These lines:
1. End with a minus sign (e.g. "3.00-")
2. Contain a forward slash followed by the item code (e.g. "/1726362")
3. The amount is the instant savings for the previous item

CRITICAL: Only count discount lines that IMMEDIATELY follow an item line and contain a forward slash with an item code.
DO NOT count lines like "TOTAL INSTANT SAVINGS" or summary lines as discount lines.
DO NOT extract instant_savings from summary text at the bottom of the receipt.

Example receipt text:
E 1347776 KS WD FL HNY 12.99 3
346014 /1347776 3.00-
E 1726362 POUCH 13.89 3

For each item:
1. Look for a discount line immediately following it
2. If found, extract the amount before the minus sign as instant_savings
3. Add instant_savings to the price to get original_price

Format each item line as: "item_code, description, price, is_taxable, instant_savings, original_price"

subtotal: Total before tax
tax: Tax amount
total: Final total
instant_savings: ONLY sum the discount lines that have a forward slash with item code (e.g. "346014 /1726362 3.00-"). If no such discount lines exist, this should be 0.00 or null, NOT any "TOTAL INSTANT SAVINGS" text from the receipt.
total_items_sold: The number from "Items Sold: X" line

Format each field on a new line with a colon separator like this:
store_location: Costco Athens #1621
store_number: 1621
transaction_date: 12/27/2024 16:54
transaction_number: 1621206176706
items:
- 1347776, KS WD FL HNY, 12.99, N, 3.00, 15.99
- 1726362, POUCH, 13.89, N, null, null
subtotal: 59.15
tax: 1.28
total: 60.43
instant_savings: 3.00
total_items_sold: 8

IMPORTANT: If there are NO discount lines with forward slashes (e.g. "/item_code"), then instant_savings should be 0.00 or null, even if the receipt mentions "instant savings" in text somewhere. Only actual discount lines count.

Parse this receipt:
{text}"""

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise Exception("Gemini API key not configured")

        # Configure Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Generate response
        response = model.generate_content(prompt.format(text=text), stream=False)
        
        # Print raw response for debugging
        print("Raw Gemini Response:", response.text)
        
        # Parse the response line by line
        lines = response.text.strip().split('\n')
        parsed_data = {
            'store_location': 'Costco Warehouse',
            'store_number': '0000',
            'transaction_date': timezone.now(),
            'transaction_number': None,
            'items': [],
            'subtotal': Decimal('0.00'),
            'tax': Decimal('0.00'),
            'total': Decimal('0.00'),
            'instant_savings': None,
            'total_items_sold': 0,
            'parse_error': None,
            'parsed_successfully': True
        }
        
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('items:'):
                current_section = 'items'
                continue
                
            if current_section == 'items':
                if line.startswith('-'):
                    # Parse item line
                    item_parts = line.replace('-', '').strip().split(',')
                    if len(item_parts) >= 6:
                        try:
                            line_price = Decimal(item_parts[2].strip())
                            instant_savings_str = item_parts[4].strip()
                            # The 6th field from the parser is expected to be original price, but we will compute it to be safe
                            
                            has_instant_savings = instant_savings_str != 'null' and instant_savings_str != ''
                            instant_savings_val = None
                            if has_instant_savings:
                                instant_savings_val = Decimal(instant_savings_str)
                            
                            original_price_val = None
                            if instant_savings_val is not None:
                                original_price_val = line_price + instant_savings_val
                            
                            # Each line is one item
                            item = {
                                'item_code': item_parts[0].strip(),
                                'description': item_parts[1].strip(),
                                'original_price': original_price_val,  # Original price before instant savings
                                'quantity': 1,  # Each line represents one item
                                'is_taxable': item_parts[3].strip().upper() == 'Y',
                                'instant_savings': instant_savings_val,
                                'price': line_price,  # Final price shown on receipt after discount
                                'total_price': str(line_price)
                            }
                            parsed_data['items'].append(item)
                        except (ValueError, IndexError, InvalidOperation) as e:
                            print(f"Error parsing item line: {str(e)}")
                            continue
                else:
                    current_section = None
                    
            if ':' in line and current_section != 'items':
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ['subtotal', 'tax', 'total', 'instant_savings']:
                    try:
                        if value.lower() == 'null':
                            parsed_data[key] = None
                        else:
                            parsed_data[key] = Decimal(value)
                    except InvalidOperation:
                        if key in ['subtotal', 'tax', 'total']:
                            parsed_data[key] = Decimal('0.00')
                        else:
                            parsed_data[key] = None
                elif key == 'transaction_date':
                    try:
                        parsed_data[key] = timezone.make_aware(
                            datetime.strptime(value, "%m/%d/%Y %H:%M")
                        )
                    except ValueError as e:
                        print(f"Date parsing error: {str(e)}")
                        parsed_data['parse_error'] = "Failed to parse transaction date"
                        parsed_data['parsed_successfully'] = False
                elif key == 'total_items_sold':
                    try:
                        parsed_data[key] = int(value)
                    except ValueError:
                        parsed_data[key] = 0
                else:
                    parsed_data[key] = value

        # Normalize store location format and handle null store numbers
        store_number = parsed_data.get('store_number', '')
        if not store_number or store_number.lower() in ['null', 'n/a', '', 'none']:
            store_number = '0000'  # Default fallback
            parsed_data['store_number'] = store_number
            
        # Handle null store locations
        store_location = parsed_data.get('store_location', '')
        if not store_location or store_location.lower() in ['null', 'n/a', '', 'none']:
            store_location = f'Costco Warehouse #{store_number}'
            parsed_data['store_location'] = store_location
        elif store_number != '0000' and store_number not in store_location:
            # If we have a valid store number but it's not in the location, add it
            if not store_location.endswith(f'#{store_number}'):
                store_location = f'{store_location} #{store_number}'
                parsed_data['store_location'] = store_location
            
        # Special case for known stores
        if store_number == '1621':
            parsed_data['store_location'] = 'Costco Athens #1621'

        # Ensure transaction number is present and clean
        transaction_number = parsed_data.get('transaction_number', '')
        if not transaction_number or transaction_number.lower() in ['null', 'n/a', '', 'none']:
            # Try to extract from text directly as fallback
            matches = re.findall(r'Whse:\s*\d+\s*Trm:\s*(\d+)\s*Trn:\s*(\d+)', text)
            if matches:
                trm, trn = matches[0]
                transaction_number = f"{store_number}{trm}{trn}"
                logger.info(f"Extracted transaction number from text: {transaction_number}")
            else:
                # Generate a unique fallback transaction number using timestamp and store info
                timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
                # Add a short random component to ensure uniqueness
                random_suffix = str(uuid.uuid4().hex)[:4].upper()
                transaction_number = f"{store_number}{timestamp}{random_suffix}"
                parsed_data['parse_error'] = "Transaction number not found - generated unique fallback ID"
                logger.warning(f"Generated fallback transaction number: {transaction_number}")
                # Don't mark as failed since we have a valid fallback
            
            parsed_data['transaction_number'] = transaction_number
        else:
            # Clean existing transaction number if it contains "null"
            if 'null' in transaction_number.lower():
                # Extract the meaningful part and regenerate
                timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
                random_suffix = str(uuid.uuid4().hex)[:4].upper()
                transaction_number = f"{store_number}{timestamp}{random_suffix}"
                parsed_data['transaction_number'] = transaction_number
                logger.warning(f"Cleaned malformed transaction number, generated: {transaction_number}")

        # Validate item count against total_items_sold
        actual_item_count = len(parsed_data['items'])
        expected_item_count = parsed_data.get('total_items_sold', 0)
        
        if expected_item_count > 0 and actual_item_count != expected_item_count:
            parsed_data['parse_error'] = f"Item count mismatch: found {actual_item_count} items but receipt shows {expected_item_count} items sold"
            parsed_data['parsed_successfully'] = False

        # Try to extract transaction date from text
        if not parsed_data.get('transaction_date'):
            # Look for date patterns in the text
            date_patterns = [
                r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})',  # MM/DD/YYYY HH:MM
                r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2})',  # M/D/YYYY H:MM
                r'P7\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})',  # P7 MM/DD/YYYY HH:MM
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    date_str, time_str = matches[0]
                    try:
                        # Parse date and time
                        parsed_date = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M")
                        parsed_data['transaction_date'] = timezone.make_aware(parsed_date)
                        break
                    except ValueError:
                        continue

            if not parsed_data.get('transaction_date'):
                parsed_data['transaction_date'] = timezone.now()
                parsed_data['parse_error'] = "Could not extract transaction date"
                parsed_data['parsed_successfully'] = False

        return parsed_data

    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        return {
            'store_location': 'Costco Warehouse',
            'store_number': '0000',
            'transaction_date': timezone.now(),
            'transaction_number': None,
            'items': [],
            'subtotal': Decimal('0.00'),
            'tax': Decimal('0.00'),
            'total': Decimal('0.00'),
            'instant_savings': None,
            'total_items_sold': 0,
            'parse_error': f"Failed to parse receipt: {str(e)}",
            'parsed_successfully': False
        }

def check_for_price_adjustments(item: LineItem, receipt: Receipt, is_user_edited: bool = False) -> None:
    """
    Check if the current user can benefit from official Costco promotions.
    This replaces the old user-to-user comparison with official sales only.
    
    Args:
        item: The line item to check
        receipt: The receipt containing the item
        is_user_edited: Whether this data comes from user edits (less trusted)
    """
    try:
        # Only check items that have a valid item code
        if not item.item_code:
            logger.info(f"Skipping price adjustment check - no item code for {item.description}")
            return

        logger.info(f"=== OFFICIAL SALES PRICE CHECK for {item.description} (${item.price}) ===")
        logger.info(f"Item code: {item.item_code}, Receipt date: {receipt.transaction_date}, User: {receipt.user.username}")

        # Skip if this item was bought on sale - user already got the discount
        if item.on_sale or (item.instant_savings and item.instant_savings > 0):
            logger.info(f"Skipping price adjustment check for {item.description} - item was bought on sale")
            return

        # Check against official Costco promotions only
        from .models import OfficialSaleItem, PriceAdjustmentAlert
        
        # Use current date to check what's currently active
        current_date = timezone.now().date()
        
        # Find active official promotions for this item
        current_promotions = OfficialSaleItem.objects.filter(
            item_code=item.item_code,
            promotion__sale_start_date__lte=current_date,
            promotion__sale_end_date__gte=current_date,
            promotion__is_processed=True
        ).select_related('promotion')
        
        for promotion_item in current_promotions:
            # Calculate what the user could pay with the promotion
            if promotion_item.sale_type == 'discount_only':
                # This is a "$X OFF" promotion
                if promotion_item.instant_rebate and item.price > promotion_item.instant_rebate:
                    final_price = item.price - promotion_item.instant_rebate
                    savings = promotion_item.instant_rebate
                else:
                    continue
            elif promotion_item.sale_price and item.price > promotion_item.sale_price:
                # Standard promotion with sale price
                final_price = promotion_item.sale_price
                savings = item.price - promotion_item.sale_price
            else:
                # User already paid the same or less
                logger.info(f"Skipping promotion for {item.description} - user paid ${item.price}, sale price is ${promotion_item.sale_price}")
                continue
            
            # Only create alert if savings is significant ($0.50+)
            if savings >= Decimal('0.50'):
                # Check if user already has an alert for this item
                existing_alert = PriceAdjustmentAlert.objects.filter(
                    user=receipt.user,
                    item_code=item.item_code,
                    is_active=True,
                    is_dismissed=False,
                    purchase_date=receipt.transaction_date
                ).first()
                
                if existing_alert:
                    # Update existing alert if this is a better deal
                    if final_price < existing_alert.lower_price:
                        existing_alert.lower_price = final_price
                        existing_alert.data_source = 'official_promo'
                        existing_alert.official_sale_item = promotion_item
                        existing_alert.cheaper_store_city = 'All Costco Locations'
                        existing_alert.cheaper_store_number = 'ALL'
                        existing_alert.is_dismissed = False
                        existing_alert.save()
                        logger.info(f"Updated official promotion alert for {receipt.user.username} on {item.description}")
                else:
                    # Create new alert
                    PriceAdjustmentAlert.objects.create(
                        user=receipt.user,
                        item_code=item.item_code,
                        item_description=promotion_item.description,
                        original_price=item.price,
                        lower_price=final_price,
                        original_store_city=receipt.store_city,
                        original_store_number=receipt.store_number,
                        cheaper_store_city='All Costco Locations',
                        cheaper_store_number='ALL',
                        purchase_date=receipt.transaction_date,
                        data_source='official_promo',
                        official_sale_item=promotion_item,
                        is_active=True,
                        is_dismissed=False
                    )
                    
                    logger.info(
                        f"Official promotion alert created for {receipt.user.username} "
                        f"on {promotion_item.description} (${item.price} -> ${final_price})"
                    )

        logger.info(f"=== END OFFICIAL SALES PRICE CHECK for {item.description} ===")

    except Exception as e:
        logger.error(f"Error checking official price promotions for {item.description}: {str(e)}")
        raise

def update_price_database(parsed_data: Dict, user=None) -> None:
    """Update the price database with information from a parsed receipt."""
    try:
        # Get or create the warehouse (still needed for store location tracking)
        warehouse, _ = CostcoWarehouse.objects.get_or_create(
            store_number=parsed_data['store_number'],
            defaults={'location': parsed_data['store_location']}
        )

        # Get or create the receipt
        receipt_data = {
            'store_location': parsed_data['store_location'],
            'store_number': parsed_data['store_number'],
            'transaction_date': parsed_data['transaction_date']
        }
        
        # Always filter by user when provided to avoid duplicate receipts
        lookup_fields = {'transaction_number': parsed_data['transaction_number']}
        if user:
            receipt_data['user'] = user
            lookup_fields['user'] = user

        receipt, _ = Receipt.objects.get_or_create(
            **lookup_fields,
            defaults=receipt_data
        )

        # Process each item - simplified to only track items, not warehouse-specific pricing
        for item_data in parsed_data['items']:
            # Get or create the item
            costco_item, _ = CostcoItem.objects.get_or_create(
                item_code=item_data['item_code'],
                defaults={
                    'description': item_data['description'],
                    'current_price': item_data['price']
                }
            )

            # Update the item's current price if it has changed
            price_changed = costco_item.update_price(
                new_price=item_data['price'],
                warehouse=warehouse,
                date_seen=parsed_data['transaction_date']
            )

            if price_changed:
                print(f"Price updated for {costco_item.description}")

    except Exception as e:
        print(f"Error updating price database: {str(e)}")
        raise

def process_receipt_pdf(pdf_path: str, user=None) -> Dict:
    """Process a receipt PDF file and return parsed data."""
    try:
        text = extract_text_from_pdf(pdf_path)
        print("Extracted text from PDF:", text)
        parsed_data = parse_receipt(text)
        
        # Strict validation of item count
        actual_item_count = len(parsed_data.get('items', []))
        expected_item_count = parsed_data.get('total_items_sold', 0)
        
        if expected_item_count > 0:  # Only validate if we found the total items count
            if actual_item_count != expected_item_count:
                return {
                    'store_location': parsed_data.get('store_location', 'Costco Warehouse'),
                    'store_number': parsed_data.get('store_number', '0000'),
                    'transaction_date': parsed_data.get('transaction_date', timezone.now()),
                    'transaction_number': parsed_data.get('transaction_number'),
                    'items': parsed_data.get('items', []),
                    'subtotal': parsed_data.get('subtotal', Decimal('0.00')),
                    'tax': parsed_data.get('tax', Decimal('0.00')),
                    'total': parsed_data.get('total', Decimal('0.00')),
                    'instant_savings': parsed_data.get('instant_savings'),
                    'total_items_sold': expected_item_count,
                    'needs_review': True,  # Flag for frontend to show edit UI
                    'review_reason': f'Item count mismatch: Found {actual_item_count} items but receipt shows {expected_item_count} items sold. Please review and adjust quantities.',
                    'parse_error': None,
                    'parsed_successfully': False
                }
        
        # Add metadata for editing to each item
        for item in parsed_data.get('items', []):
            item['editable'] = True
            item['original_description'] = item['description']
            item['original_quantity'] = item['quantity']
            item['needs_quantity_review'] = True
        
        # Only update price database if user confirms quantities
        if parsed_data['parsed_successfully'] and user and not parsed_data.get('needs_review'):
            update_price_database(parsed_data, user=user)
            
        return parsed_data
    except Exception as e:
        print(f"PDF Processing Error: {str(e)}")
        return {
            'store_location': 'Costco Warehouse',
            'store_number': '0000',
            'transaction_date': timezone.now(),
            'items': [],
            'subtotal': Decimal('0.00'),
            'tax': Decimal('0.00'),
            'total': Decimal('0.00'),
            'ebt_amount': None,
            'instant_savings': None,
            'needs_review': False,
            'parse_error': f"Failed to process PDF: {str(e)}",
            'parsed_successfully': False
        }

def extract_text_from_image(image_path: str) -> str:
    """Extract text from an image file using Gemini Vision with enhanced preprocessing."""
    try:
        # Check if file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Read the image file as binary
        with open(image_path, 'rb') as file:
            image_content = file.read()
        
        # Determine MIME type based on file extension
        file_ext = os.path.splitext(image_path)[1].lower()
        print(f"Processing image with extension: {file_ext}")
        
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.avif': 'image/avif'
        }
        mime_type = mime_types.get(file_ext, 'image/jpeg')
        print(f"Using MIME type: {mime_type} for file extension: {file_ext}")
        
        # Configure Gemini
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise Exception("Gemini API key not configured")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Enhanced prompt for photo receipt processing
        prompt = """This is a photo of a Costco receipt. Please extract all the text from this receipt with high accuracy. Pay special attention to:

1. **Crossed-out/strikethrough text**: Some lines may have strikethrough marks from checkout - still extract the text underneath
2. **Item lines**: Lines starting with 'E' followed by item codes and descriptions
3. **Discount lines**: Lines that follow items and:
   - End with a minus sign (e.g. "3.00-")
   - Contain a forward slash followed by the item code (e.g. "/1726362")
   - Show instant savings amounts
4. **Store and transaction info**: Store location, number, date, and transaction number
5. **Totals**: Subtotal, tax, total, and instant savings

**IMPORTANT FOR PHOTO PROCESSING:**
- The image may be tilted, blurry, or have shadows - do your best to read through these issues
- Some text may be crossed out with lines - extract the text underneath the strikethrough
- Look for watermarks or stamps that may overlay text
- If numbers are partially obscured, make reasonable inferences based on context

Example format to look for:
E 1347776 KS WD FL HNY 12.99 3
346014 /1347776 3.00-
E 1726362 POUCH 13.89 3

Extract ALL visible text, maintaining line structure. If you're uncertain about a character, provide your best guess in [brackets]."""
        
        # Create the image data
        image_data = {
            "mime_type": mime_type,
            "data": base64.b64encode(image_content).decode('utf-8')
        }
        
        print(f"Sending image to Gemini with MIME type: {mime_type}")
        
        # Generate response
        response = model.generate_content([prompt, image_data], stream=False)
        
        print(f"Successfully processed image: {image_path}")
        
        # Return the extracted text
        return response.text
    except Exception as e:
        print(f"Error extracting text from image: {str(e)}")
        raise

def process_receipt_image(image_path: str, user=None) -> Dict:
    """Process a receipt image file and return parsed data."""
    try:
        text = extract_text_from_image(image_path)
        print("Extracted text from image:", text)
        parsed_data = parse_receipt(text)
        
        # Add confidence score for image-based receipts
        parsed_data['source_type'] = 'image'
        
        # Strict validation of item count
        actual_item_count = len(parsed_data.get('items', []))
        expected_item_count = parsed_data.get('total_items_sold', 0)
        
        if expected_item_count > 0:  # Only validate if we found the total items count
            if actual_item_count != expected_item_count:
                return {
                    'store_location': parsed_data.get('store_location', 'Costco Warehouse'),
                    'store_number': parsed_data.get('store_number', '0000'),
                    'transaction_date': parsed_data.get('transaction_date', timezone.now()),
                    'transaction_number': parsed_data.get('transaction_number'),
                    'items': parsed_data.get('items', []),
                    'subtotal': parsed_data.get('subtotal', Decimal('0.00')),
                    'tax': parsed_data.get('tax', Decimal('0.00')),
                    'total': parsed_data.get('total', Decimal('0.00')),
                    'instant_savings': parsed_data.get('instant_savings'),
                    'total_items_sold': expected_item_count,
                    'source_type': 'image',
                    'needs_review': True,
                    'review_reason': f'Photo processing: Found {actual_item_count} items but receipt shows {expected_item_count} items sold. Please review and adjust.',
                    'parse_error': None,
                    'parsed_successfully': False
                }
        
        # Add metadata for editing to each item
        for item in parsed_data.get('items', []):
            item['editable'] = True
            item['original_description'] = item['description']
            item['original_quantity'] = item['quantity']
            item['needs_quantity_review'] = True
        
        # Only update price database if user confirms data
        if parsed_data['parsed_successfully'] and user and not parsed_data.get('needs_review'):
            update_price_database(parsed_data, user=user)
            
        return parsed_data
    except Exception as e:
        print(f"Image Processing Error: {str(e)}")
        return {
            'store_location': 'Costco Warehouse',
            'store_number': '0000',
            'transaction_date': timezone.now(),
            'items': [],
            'subtotal': Decimal('0.00'),
            'tax': Decimal('0.00'),
            'total': Decimal('0.00'),
            'ebt_amount': None,
            'instant_savings': None,
            'source_type': 'image',
            'needs_review': True,
            'review_reason': 'Failed to process image - please verify all details',
            'parse_error': f"Failed to process image: {str(e)}",
            'parsed_successfully': False
        }

def process_receipt_file(file_path: str, user=None) -> Dict:
    """Process any receipt file (PDF or image) and return parsed data."""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.pdf':
        return process_receipt_pdf(file_path, user)
    elif file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif']:
        return process_receipt_image(file_path, user)
    else:
        raise ValueError(f"Unsupported file type: {file_ext}")

def extract_promo_data_from_image(image_path: str) -> str:
    """Extract promotional sale data from a Costco booklet page."""
    try:
        # Check if file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Read the image file as binary
        with open(image_path, 'rb') as file:
            image_content = file.read()
        
        # Determine MIME type based on file extension
        file_ext = os.path.splitext(image_path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.avif': 'image/avif',
        }
        mime_type = mime_types.get(file_ext, 'image/jpeg')
        
        # Configure Gemini
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise Exception("Gemini API key not configured")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Specialized prompt for promotional booklet processing
        prompt = """This is a page from an official Costco promotional booklet showing monthly member deals and instant rebates. 

Extract ALL sale items from this page. There are TWO types of promotions:

TYPE 1: "$X OFF" (discount amount only)
- Example: "$40 OFF" means $40 discount, but no final price shown
- For these: use "discount_only" as sale_type and put discount amount in REBATE_AMOUNT

TYPE 2: "$X.XX AFTER $Y OFF" (final price after discount)  
- Example: "$32.99 AFTER $7 OFF" means final price is $32.99, discount is $7
- For these: use "instant_rebate" as sale_type

Format each item as:
ITEM_CODE | DESCRIPTION | REGULAR_PRICE | SALE_PRICE | REBATE_AMOUNT | SALE_TYPE

FORMATTING RULES:
- Use ONLY numbers for prices (no $ symbol, no commas)
- If regular price isn't shown, use "null"
- For TYPE 1 ($X OFF): SALE_PRICE should be "null", REBATE_AMOUNT is the discount
- For TYPE 2 ($X.XX AFTER $Y OFF): SALE_PRICE is the final price, REBATE_AMOUNT is the discount
- Use underscores in sale_type: "discount_only" or "instant_rebate"
- For ITEM_CODE: Use the specific item number if visible, otherwise use "Item Numbers Vary"

Examples from this image:
1654628 | CORE Pop-up Canopy | null | null | 40.00 | discount_only
Item Numbers Vary | Timber Ridge Chair | null | null | 10.00 | discount_only
1872066 | Titan Cooler | 39.99 | 32.99 | 7.00 | instant_rebate
1671616 | DeWalt Vacuum | null | null | 20.00 | discount_only
Item Numbers Vary | Philips Shaver Family | null | null | 30.00 | discount_only

Extract every visible sale item from this promotional page."""
        
        # Create the image data
        image_data = {
            "mime_type": mime_type,
            "data": base64.b64encode(image_content).decode('utf-8')
        }
        
        # Generate response
        response = model.generate_content([prompt, image_data], stream=False)
        
        return response.text
        
    except Exception as e:
        logger.error(f"Error extracting promo data from image: {str(e)}")
        raise

def parse_promo_text(text: str) -> list:
    """Parse extracted promotional text into structured sale items."""
    sale_items = []
    
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or '|' not in line:
            continue
            
        try:
            parts = [part.strip() for part in line.split('|')]
            if len(parts) >= 6:
                item_code = parts[0]
                # Handle missing or invalid item codes
                if not item_code or item_code.lower() in ['null', 'none', '', 'n/a', 'varies', 'various']:
                    item_code = "Item Numbers Vary"
                
                description = parts[1]
                regular_price_str = parts[2]
                sale_price_str = parts[3]
                rebate_amount_str = parts[4]
                sale_type = parts[5]
                
                # Parse prices
                regular_price = None
                if regular_price_str and regular_price_str.lower() != 'null':
                    # Clean price string: remove $, commas, extra spaces
                    clean_price = regular_price_str.replace('$', '').replace(',', '').strip()
                    try:
                        regular_price = Decimal(clean_price)
                    except (ValueError, InvalidOperation):
                        logger.warning(f"Could not parse regular price: '{regular_price_str}'")
                
                sale_price = None
                instant_rebate = None
                
                # Handle different promotional formats based on sale_type
                if sale_type == 'discount_only':
                    # This is a "$X OFF" promotion - we only know the discount amount
                    if rebate_amount_str and rebate_amount_str.lower() != 'null':
                        clean_rebate = rebate_amount_str.replace('$', '').replace(',', '').strip()
                        try:
                            instant_rebate = Decimal(clean_rebate)
                            # For discount_only, leave sale_price as None, store discount in instant_rebate
                            sale_price = None  # No final price known
                            logger.info(f"Processing discount-only promotion: ${instant_rebate} OFF for {description}")
                        except (ValueError, InvalidOperation):
                            logger.warning(f"Could not parse discount amount: '{rebate_amount_str}' - skipping item")
                            continue
                    else:
                        logger.warning(f"No discount amount found for discount_only promotion - skipping item")
                        continue
                        
                elif sale_price_str.lower() == 'null' or not sale_price_str.strip():
                    # Legacy handling for null sale prices (fallback)
                    if rebate_amount_str and rebate_amount_str.lower() != 'null':
                        clean_rebate = rebate_amount_str.replace('$', '').replace(',', '').strip()
                        try:
                            instant_rebate = Decimal(clean_rebate)
                            # Keep sale_price as None; treat as discount-only style
                            sale_price = None
                            logger.info(f"Legacy promo format with null sale price: using discount amount ${instant_rebate}")
                        except (ValueError, InvalidOperation):
                            logger.warning(f"Could not parse rebate amount: '{rebate_amount_str}' - skipping item")
                            continue
                    else:
                        logger.warning(f"No sale price or rebate amount found - skipping item")
                        continue
                else:
                    # Normal promotion with actual sale price
                    clean_sale_price = sale_price_str.replace('$', '').replace(',', '').strip()
                    try:
                        sale_price = Decimal(clean_sale_price)
                    except (ValueError, InvalidOperation):
                        logger.warning(f"Could not parse sale price: '{sale_price_str}' - skipping item")
                        continue
                    
                    # Parse rebate amount if provided
                    if rebate_amount_str and rebate_amount_str.lower() != 'null':
                        clean_rebate = rebate_amount_str.replace('$', '').replace(',', '').strip()
                        try:
                            instant_rebate = Decimal(clean_rebate)
                        except (ValueError, InvalidOperation):
                            logger.warning(f"Could not parse rebate amount: '{rebate_amount_str}'")
                    elif regular_price:
                        instant_rebate = regular_price - sale_price
                
                # Ensure item_code is never empty or null
                if not item_code or item_code.lower() in ['null', 'none', '', 'n/a']:
                    item_code = "Item Numbers Vary"
                    
                sale_items.append({
                    'item_code': item_code,
                    'description': description,
                    'regular_price': regular_price,
                    'sale_price': sale_price,
                    'instant_rebate': instant_rebate,
                    'sale_type': sale_type
                })
                
        except (ValueError, IndexError) as e:
            logger.warning(f"Error parsing promo line '{line}': {str(e)}")
            continue
    
    return sale_items

def process_official_promotion(promotion_id: int, max_pages: int = None) -> dict:
    """Process an official Costco promotion and create price adjustment alerts."""
    import gc
    import time
    
    try:
        promotion = CostcoPromotion.objects.get(id=promotion_id)
        results = {
            'pages_processed': 0,
            'items_extracted': 0,
            'alerts_created': 0,
            'errors': [],
            'skipped_pages': 0
        }
        
        # Get pages to process (only unprocessed pages, limit if specified)
        pages_queryset = promotion.pages.filter(is_processed=False).order_by('page_number')
        if max_pages:
            pages_queryset = pages_queryset[:max_pages]
            logger.info(f"Processing limited to {max_pages} unprocessed pages to prevent timeout")
        
        total_pages = pages_queryset.count()
        logger.info(f"Starting to process {total_pages} pages for promotion '{promotion.title}'")
        
        # Process each page of the promotion
        for page_num, page in enumerate(pages_queryset, 1):
            try:
                logger.info(f"Processing page {page_num}/{total_pages}: {page.page_number}")
                
                # Memory cleanup between pages - more frequent for large items
                if page_num % 3 == 0:  # Every 3 pages instead of 5
                    gc.collect()
                    logger.info(f"Memory cleanup after page {page_num}")
                
                # Check if image file exists
                if not page.image or not os.path.exists(page.image.path):
                    error_msg = f"Image file not found for page {page.page_number}: {page.image.name if page.image else 'No image'}"
                    results['errors'].append(error_msg)
                    page.processing_error = error_msg
                    page.save()
                    logger.error(error_msg)
                    continue
                
                # Extract text from the image
                extracted_text = extract_promo_data_from_image(page.image.path)
                page.extracted_text = extracted_text
                
                # Parse the sale items
                sale_items = parse_promo_text(extracted_text)
                logger.info(f"Found {len(sale_items)} sale items on page {page.page_number}")
                
                # Extra cleanup if we're processing large pages with many discount items
                if len(sale_items) > 15:  # Many items on page
                    gc.collect()
                    logger.info(f"Extra memory cleanup - large page with {len(sale_items)} items")
                
                # Create OfficialSaleItem records
                page_items_created = 0
                page_alerts_created = 0
                
                for item_data in sale_items:
                    try:
                        official_item, created = OfficialSaleItem.objects.get_or_create(
                            promotion=promotion,
                            item_code=item_data['item_code'],
                            defaults={
                                'description': item_data['description'],
                                'regular_price': item_data['regular_price'],
                                'sale_price': item_data['sale_price'],
                                'instant_rebate': item_data['instant_rebate'],
                                'sale_type': item_data['sale_type']
                            }
                        )
                        
                        if created:
                            page_items_created += 1
                            
                            # Create price adjustment alerts for users who bought this item
                            alerts_created = create_official_price_alerts(official_item)
                            official_item.alerts_created = alerts_created
                            official_item.save()
                            page_alerts_created += alerts_created
                        else:
                            # Update existing record if fields have changed, and (re)create alerts
                            updated = False
                            if official_item.description != item_data['description']:
                                official_item.description = item_data['description']
                                updated = True
                            if official_item.regular_price != item_data['regular_price']:
                                official_item.regular_price = item_data['regular_price']
                                updated = True
                            if official_item.sale_price != item_data['sale_price']:
                                official_item.sale_price = item_data['sale_price']
                                updated = True
                            if official_item.instant_rebate != item_data['instant_rebate']:
                                official_item.instant_rebate = item_data['instant_rebate']
                                updated = True
                            if official_item.sale_type != item_data['sale_type']:
                                official_item.sale_type = item_data['sale_type']
                                updated = True
                            
                            if updated:
                                official_item.save()
                            
                            # Always attempt to create/update alerts for current promotion items
                            alerts_created = create_official_price_alerts(official_item)
                            # Do not overwrite cumulative count; track for page summary
                            page_alerts_created += alerts_created
                            
                    except Exception as e:
                        logger.error(f"Error creating item {item_data.get('item_code', 'unknown')}: {str(e)}")
                        continue
                
                results['items_extracted'] += page_items_created
                results['alerts_created'] += page_alerts_created
                
                page.is_processed = True
                page.save()
                results['pages_processed'] += 1
                
                logger.info(f"Page {page.page_number} complete: {page_items_created} items, {page_alerts_created} alerts")
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.1)
                
            except Exception as e:
                error_msg = f"Error processing page {page.page_number}: {str(e)}"
                results['errors'].append(error_msg)
                page.processing_error = error_msg
                page.save()
                logger.error(error_msg)
                
                # Continue processing other pages
                continue
        
        # Mark promotion as processed if we processed all pages (or hit the limit)
        remaining_pages = promotion.pages.filter(is_processed=False).count()
        if remaining_pages == 0 or max_pages:
            promotion.is_processed = True
            promotion.processed_date = timezone.now()
        
        if results['errors']:
            promotion.processing_error = '; '.join(results['errors'])
        promotion.save()
        
        logger.info(f"Promotion processing complete: {results}")
        return results
        
    except Exception as e:
        error_msg = f"Error processing promotion {promotion_id}: {str(e)}"
        logger.error(error_msg)
        return {'error': error_msg}

def create_official_price_alerts(official_sale_item) -> int:
    """Create price adjustment alerts based on official sale data."""
    alerts_created = 0
    
    try:
        # Find users who bought this item at regular price in the last 30 days from current date
        # (since this is for currently active promotions)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Look for purchases where users paid more than the sale price
        higher_price_purchases = LineItem.objects.filter(
            item_code=official_sale_item.item_code,
            receipt__transaction_date__gte=thirty_days_ago,
            receipt__user__isnull=False
        ).select_related('receipt', 'receipt__user')
        
        # For "OFF" promotions where sale_price represents the discount amount,
        # we need to find users who could benefit from this discount
        for purchase in higher_price_purchases:
            # IMPORTANT: Skip items that were already bought on sale
            # If the purchase has instant_savings, they already got a deal
            if purchase.instant_savings and purchase.instant_savings > 0:
                logger.info(f"Skipping {purchase.description} - user already bought on sale (saved ${purchase.instant_savings})")
                continue
            
            # Also skip if the item was marked as on_sale
            if hasattr(purchase, 'on_sale') and purchase.on_sale:
                logger.info(f"Skipping {purchase.description} - item was already marked as on sale")
                continue
            
            # Check if user already has an alert for this item
            existing_alert = PriceAdjustmentAlert.objects.filter(
                user=purchase.receipt.user,
                item_code=official_sale_item.item_code,
                is_active=True,
                is_dismissed=False
            ).first()
            
            # Calculate potential savings
            if official_sale_item.sale_type == 'discount_only':
                # This is a "$X OFF" promotion - calculate savings as the discount amount
                savings = official_sale_item.instant_rebate  # Use instant_rebate for discount amount
                final_price = purchase.price - savings  # What they could pay after discount
                
                # Only create alert if the discount is meaningful and results in positive price
                if final_price <= 0 or savings < Decimal('0.50'):
                    continue  # Skip if discount is too large or too small
                    
                logger.info(f"Discount-only promotion: User paid ${purchase.price}, can save ${savings} (final: ${final_price})")
                
            elif official_sale_item.sale_price:
                # Standard promotion with sale price (regular price optional)
                if purchase.price > official_sale_item.sale_price:
                    savings = purchase.price - official_sale_item.sale_price
                    final_price = official_sale_item.sale_price
                else:
                    # User already paid the same or less - no benefit
                    logger.info(f"Skipping {purchase.description} - user paid ${purchase.price}, sale price is ${official_sale_item.sale_price}")
                    continue
            else:
                # Skip if we don't have enough price information
                logger.warning(f"Insufficient price data for {official_sale_item.description} - skipping")
                continue
            
            # Only create alert if savings is significant ($0.50+)
            if savings >= Decimal('0.50'):
                if existing_alert:
                    # Update existing alert if this is a better deal
                    if final_price < existing_alert.lower_price:
                        existing_alert.lower_price = final_price
                        existing_alert.data_source = 'official_promo'
                        existing_alert.official_sale_item = official_sale_item
                        existing_alert.is_dismissed = False  # Re-activate
                        existing_alert.save()
                        alerts_created += 1
                        logger.info(f"Updated price alert for {purchase.receipt.user.username} on {official_sale_item.description}")
                else:
                    # Create new alert
                    PriceAdjustmentAlert.objects.create(
                        user=purchase.receipt.user,
                        item_code=official_sale_item.item_code,
                        item_description=official_sale_item.description,
                        original_price=purchase.price,
                        lower_price=final_price,  # Use calculated final price
                        original_store_city=purchase.receipt.store_city,
                        original_store_number=purchase.receipt.store_number,
                        cheaper_store_city='All Costco Locations',  # Official promos apply everywhere
                        cheaper_store_number='ALL',
                        purchase_date=purchase.receipt.transaction_date,
                        data_source='official_promo',
                        official_sale_item=official_sale_item,
                        is_active=True,
                        is_dismissed=False
                    )
                    alerts_created += 1
                    
                    logger.info(
                        f"Official price alert created for user {purchase.receipt.user.username} "
                        f"on {official_sale_item.description} (${purchase.price} -> ${final_price}, saved ${savings})"
                    )
        
    except Exception as e:
        logger.error(f"Error creating official price alerts for {official_sale_item.description}: {str(e)}")
        
    return alerts_created

def check_current_user_for_price_adjustments(item: LineItem, receipt: Receipt) -> int:
    """
    Check if the current user can benefit from official Costco promotions only.
    This is called when a user edits their receipt to see if they overpaid.
    
    Returns the number of new alerts created for the current user.
    """
    alerts_created = 0
    
    try:
        if not item.item_code:
            return 0

        # Skip if this item was bought on sale - user already got the discount
        if item.on_sale or (item.instant_savings and item.instant_savings > 0):
            logger.info(f"Skipping price adjustment check for {item.description} - item was bought on sale")
            return 0

        # Check official promotions only (highest trust)
        from .models import OfficialSaleItem, PriceAdjustmentAlert
        
        # For official promotions, check what's currently active (use current date)
        current_date = timezone.now().date()
        
        # Find active official promotions for this item
        current_promotions = OfficialSaleItem.objects.filter(
            item_code=item.item_code,
            promotion__sale_start_date__lte=current_date,
            promotion__sale_end_date__gte=current_date,
            promotion__is_processed=True
        ).select_related('promotion')
        
        for promotion_item in current_promotions:
            # Calculate what the user could pay with the promotion
            if promotion_item.sale_type == 'discount_only':
                # This is a "$X OFF" promotion
                if promotion_item.instant_rebate and item.price > promotion_item.instant_rebate:
                    final_price = item.price - promotion_item.instant_rebate
                    savings = promotion_item.instant_rebate
                else:
                    continue
            elif promotion_item.sale_price and item.price > promotion_item.sale_price:
                # Standard promotion with sale price
                final_price = promotion_item.sale_price
                savings = item.price - promotion_item.sale_price
            else:
                # User already paid the same or less
                logger.info(f"Skipping promotion for {item.description} - user paid ${item.price}, sale price is ${promotion_item.sale_price}")
                continue
            
            # Only create alert if savings is significant ($0.50+)
            if savings >= Decimal('0.50'):
                # Check if user already has an alert for this item
                existing_alert = PriceAdjustmentAlert.objects.filter(
                    user=receipt.user,
                    item_code=item.item_code,
                    is_active=True,
                    is_dismissed=False,
                    purchase_date=receipt.transaction_date
                ).first()
                
                if existing_alert:
                    # Update existing alert if this is a better deal
                    if final_price < existing_alert.lower_price:
                        existing_alert.lower_price = final_price
                        existing_alert.data_source = 'official_promo'
                        existing_alert.official_sale_item = promotion_item
                        existing_alert.cheaper_store_city = 'All Costco Locations'
                        existing_alert.cheaper_store_number = 'ALL'
                        existing_alert.is_dismissed = False
                        existing_alert.save()
                        alerts_created += 1
                        logger.info(f"Updated official promotion alert for {receipt.user.username} on {item.description}")
                else:
                    # Create new alert
                    PriceAdjustmentAlert.objects.create(
                        user=receipt.user,
                        item_code=item.item_code,
                        item_description=promotion_item.description,
                        original_price=item.price,
                        lower_price=final_price,
                        original_store_city=receipt.store_city,
                        original_store_number=receipt.store_number,
                        cheaper_store_city='All Costco Locations',
                        cheaper_store_number='ALL',
                        purchase_date=receipt.transaction_date,
                        data_source='official_promo',
                        official_sale_item=promotion_item,
                        is_active=True,
                        is_dismissed=False
                    )
                    alerts_created += 1
                    
                    logger.info(
                        f"Official promotion alert created for current user {receipt.user.username} "
                        f"on {promotion_item.description} (${item.price} -> ${final_price})"
                    )
        
        return alerts_created
        
    except Exception as e:
        logger.error(f"Error checking current user price adjustments for {item.description if item else 'unknown item'}: {str(e)}")
        return 0 