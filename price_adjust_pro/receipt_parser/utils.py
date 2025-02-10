import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional
import json
import os
from django.conf import settings
import google.generativeai as genai
from django.utils import timezone
import base64
from .models import (
    CostcoItem, CostcoWarehouse, ItemWarehousePrice,
    PriceAdjustmentAlert, Receipt, LineItem
)

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file using Gemini Vision."""
    try:
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
        prompt = """This is a Costco receipt. Please extract all the text from this receipt, preserving the exact format and numbers. Include all item details, prices, dates, and totals. Output the text exactly as it appears, maintaining line breaks and spacing. Be sure to include:
1. Store location and number
2. Transaction date and number
3. All items with their codes, descriptions, prices, and quantities
4. Subtotal, tax, and total amounts
5. Any instant savings or discounts"""
        
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
    prompt = """You are a specialized Costco receipt parser. Extract and return these fields from the receipt:

store_location: Store name and location (e.g. "Costco Athens #1621")
store_number: Store number only (e.g. "1621")
transaction_date: Date and time (format EXACTLY as MM/DD/YYYY HH:MM, e.g. 12/27/2024 16:54)
transaction_number: The 13-digit number after the date/time (e.g. 1621206176706)
items: List each item with:
- item_code
- description
- price
- quantity
- is_taxable (Y/N)
subtotal: Total before tax
tax: Tax amount
total: Final total
instant_savings: Total savings amount if present

Format each field on a new line with a colon separator like this:
store_location: Costco Athens #1621
store_number: 1621
transaction_date: 12/27/2024 16:54
transaction_number: 1621206176706
items:
- 1347776, KS WD FL HNY ORG PB, 12.99, 1, N
- 1726362, POUCH, 13.89, 1, N
subtotal: 59.15
tax: 1.28
total: 60.43
instant_savings: 7.00

Parse this receipt:
{text}"""

    try:
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise Exception("Gemini API key not configured")

        # Configure Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

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
                    if len(item_parts) >= 5:
                        item = {
                            'item_code': item_parts[0].strip(),
                            'description': item_parts[1].strip(),
                            'price': Decimal(item_parts[2].strip()),
                            'quantity': int(item_parts[3].strip()),
                            'is_taxable': item_parts[4].strip().upper() == 'Y',
                            'discount': None
                        }
                        parsed_data['items'].append(item)
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
                    except:
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
                else:
                    parsed_data[key] = value

        # Normalize store location format
        if parsed_data.get('store_number') == '1621':
            parsed_data['store_location'] = 'Costco Athens #1621'

        # Ensure transaction number is present
        if not parsed_data.get('transaction_number'):
            # Try to extract from text directly as fallback
            matches = re.findall(r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s+(\d{13})', text)
            if matches:
                parsed_data['transaction_number'] = matches[0]
            else:
                parsed_data['parse_error'] = "Failed to extract transaction number"
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
            'parse_error': f"Failed to parse receipt: {str(e)}",
            'parsed_successfully': False
        }

def check_for_price_adjustments(item: LineItem, receipt: Receipt) -> None:
    """
    Check if there are any potential price adjustments for a line item.
    Creates PriceAdjustmentAlert if a lower price is found.
    """
    try:
        # Only check items with valid item codes
        if not item.item_code:
            return

        # Get the date 30 days ago
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Find any lower prices for this item in the last 30 days
        lower_prices = ItemWarehousePrice.objects.filter(
            item__item_code=item.item_code,
            last_seen__gte=thirty_days_ago,
            price__lt=item.price  # Find lower prices
        ).select_related('warehouse').order_by('price')

        if lower_prices.exists():
            lowest_price = lower_prices.first()
            price_difference = item.price - lowest_price.price
            
            # Only create alert if the difference is significant (e.g., > $0.50)
            if price_difference >= Decimal('0.50'):
                # Extract city from warehouse location
                warehouse_location = lowest_price.warehouse.location
                city = ' '.join(warehouse_location.split()[1:-1]) if warehouse_location else ''

                # Create or update the alert
                alert, created = PriceAdjustmentAlert.objects.get_or_create(
                    user=receipt.user,
                    item_code=item.item_code,
                    original_price=item.price,
                    purchase_date=receipt.transaction_date,
                    defaults={
                        'item_description': item.description,
                        'lower_price': lowest_price.price,
                        'original_store_city': receipt.store_city,
                        'original_store_number': receipt.store_number,
                        'cheaper_store_city': city,
                        'cheaper_store_number': lowest_price.warehouse.store_number,
                        'is_active': True,
                        'is_dismissed': False
                    }
                )

                if not created:
                    # Update the alert if we found an even lower price
                    if lowest_price.price < alert.lower_price:
                        alert.lower_price = lowest_price.price
                        alert.cheaper_store_city = city
                        alert.cheaper_store_number = lowest_price.warehouse.store_number
                        alert.is_dismissed = False  # Re-activate if user dismissed it before
                        alert.save()

    except Exception as e:
        print(f"Error checking price adjustments for {item.description}: {str(e)}")

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
        
        # Update price database if parsing was successful and we have a user
        if parsed_data['parsed_successfully'] and user:
            update_price_database(parsed_data, user=user)
            
        parsed_data['parsed_successfully'] = len(parsed_data.get('items', [])) > 0
        if not parsed_data['parsed_successfully']:
            parsed_data['parse_error'] = 'No items found in receipt'
            
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
            'parse_error': f"Failed to process PDF: {str(e)}",
            'parsed_successfully': False
        } 