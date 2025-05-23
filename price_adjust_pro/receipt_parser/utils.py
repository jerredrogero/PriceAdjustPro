import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional
import json
import os
from django.conf import settings

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
    CostcoItem, CostcoWarehouse, ItemWarehousePrice,
    PriceAdjustmentAlert, Receipt, LineItem
)

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
instant_savings: Total of all discount lines (amounts ending in minus)
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
instant_savings: 7.00
total_items_sold: 8

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
                            price = Decimal(item_parts[2].strip())
                            instant_savings = item_parts[4].strip()
                            original_price = item_parts[5].strip()
                            
                            # Each line is one item
                            item = {
                                'item_code': item_parts[0].strip(),
                                'description': item_parts[1].strip(),
                                'price': price,
                                'quantity': 1,  # Each line represents one item
                                'is_taxable': item_parts[3].strip().upper() == 'Y',
                                'instant_savings': Decimal(instant_savings) if instant_savings != 'null' else None,
                                'original_price': Decimal(original_price) if original_price != 'null' else None
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

        # Normalize store location format
        if parsed_data.get('store_number') == '1621':
            parsed_data['store_location'] = 'Costco Athens #1621'

        # Ensure transaction number is present
        if not parsed_data.get('transaction_number'):
            # Try to extract from text directly as fallback
            matches = re.findall(r'Whse:\s*\d+\s*Trm:\s*(\d+)\s*Trn:\s*(\d+)', text)
            if matches:
                trm, trn = matches[0]
                store_number = parsed_data.get('store_number', '0000')
                parsed_data['transaction_number'] = f"{store_number}{trm}{trn}"
            else:
                parsed_data['parse_error'] = "Failed to extract transaction number"
                parsed_data['parsed_successfully'] = False

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

def check_for_price_adjustments(item: LineItem, receipt: Receipt) -> None:
    """
    When an item with instant savings is found, alert other users who bought 
    the same item at full price in the last 30 days.
    """
    try:
        # Only check items that have a lower price (either through instant savings or regular price)
        if not item.item_code:
            return

        # Get the date 30 days ago
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Find users who bought this item at a higher price in the last 30 days
        full_price_purchases = LineItem.objects.filter(
            item_code=item.item_code,
            receipt__transaction_date__gte=thirty_days_ago,
            price__gt=item.price,  # Find any items with a higher price
            receipt__user__isnull=False  # Ensure there's a user
        ).select_related('receipt', 'receipt__user')

        # Create alerts for users who bought at higher price
        for purchase in full_price_purchases:
            # Don't alert the same user who found the sale
            if purchase.receipt.user == receipt.user:
                continue

            price_difference = purchase.price - item.price
            
            # Only alert if the difference is significant (e.g., > $0.50)
            if price_difference >= Decimal('0.50'):
                # Create or update alert
                alert, created = PriceAdjustmentAlert.objects.get_or_create(
                    user=purchase.receipt.user,
                    item_code=item.item_code,
                    original_price=purchase.price,  # Their purchase price
                    purchase_date=purchase.receipt.transaction_date,
                    defaults={
                        'item_description': item.description,
                        'lower_price': item.price,  # The sale price
                        'original_store_city': purchase.receipt.store_city,
                        'original_store_number': purchase.receipt.store_number,
                        'cheaper_store_city': receipt.store_city,  # Where the sale was found
                        'cheaper_store_number': receipt.store_number,
                        'is_active': True,
                        'is_dismissed': False
                    }
                )

                if not created and item.price < alert.lower_price:
                    # Update the alert if we found an even lower price
                    alert.lower_price = item.price
                    alert.cheaper_store_city = receipt.store_city
                    alert.cheaper_store_number = receipt.store_number
                    alert.is_dismissed = False  # Re-activate if user dismissed it before
                    alert.save()

                # Log the alert creation/update
                logger.info(
                    f"Price adjustment alert created/updated for user {purchase.receipt.user.username} "
                    f"on item {item.description} (${purchase.price} -> ${item.price})"
                )

    except Exception as e:
        logger.error(f"Error checking price adjustments for {item.description}: {str(e)}")
        raise

def update_price_database(parsed_data: Dict, user=None) -> None:
    """Update the price database with information from a parsed receipt."""
    try:
        # Get or create the warehouse
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
        if user:
            receipt_data['user'] = user

        receipt, _ = Receipt.objects.get_or_create(
            transaction_number=parsed_data['transaction_number'],
            defaults=receipt_data
        )

        # Process each item
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

            # Update the warehouse-specific price
            warehouse_price_changed = ItemWarehousePrice.update_price(
                item=costco_item,
                warehouse=warehouse,
                new_price=item_data['price'],
                date_seen=parsed_data['transaction_date']
            )

            if price_changed or warehouse_price_changed:
                print(f"Price updated for {costco_item.description} at {warehouse.location}")

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
            item['editable'] = True  # Flag that this item can be edited
            item['original_description'] = item['description']  # Keep original for reference
            item['original_quantity'] = item['quantity']  # Keep original for reference
            item['needs_quantity_review'] = True  # Flag for frontend to highlight quantity field
        
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
            '.bmp': 'image/bmp'
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
        parsed_data['confidence_note'] = 'Extracted from photo - please verify accuracy'
        
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
                    'confidence_note': 'Extracted from photo - please verify accuracy',
                    'parse_error': None,
                    'parsed_successfully': False
                }
        
        # Add metadata for editing to each item
        for item in parsed_data.get('items', []):
            item['editable'] = True
            item['original_description'] = item['description']
            item['original_quantity'] = item['quantity']
            item['needs_quantity_review'] = True
            item['source_confidence'] = 'medium'  # Photos generally have medium confidence
        
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
            'confidence_note': 'Image processing failed - manual review required',
            'parse_error': f"Failed to process image: {str(e)}",
            'parsed_successfully': False
        }

def process_receipt_file(file_path: str, user=None) -> Dict:
    """Process any receipt file (PDF or image) and return parsed data."""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.pdf':
        return process_receipt_pdf(file_path, user)
    elif file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
        return process_receipt_image(file_path, user)
    else:
        raise ValueError(f"Unsupported file type: {file_ext}") 