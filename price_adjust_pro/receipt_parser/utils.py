import re
from datetime import datetime
from decimal import Decimal
import pdfplumber
from typing import Dict, List, Optional, Union
import requests
import json
import os
from django.conf import settings

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file."""
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text.append(page_text)
    return "\n".join(full_text)

def clean_decimal(value: str) -> Optional[Decimal]:
    """Convert string to Decimal, handling None and removing common currency symbols."""
    if not value:
        return None
    try:
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[^\d.-]', '', value)
        return Decimal(cleaned)
    except:
        return None

def parse_with_regex(text: str) -> Dict:
    """
    Parse receipt text using regex patterns for basic information extraction.
    This is a fallback method when AI parsing is not available.
    """
    lines = text.split('\n')
    parsed_data = {
        'store_location': 'Costco Warehouse',  # Default value
        'store_number': '0000',  # Default value
        'transaction_date': datetime.now(),  # Default to current time if not found
        'items': [],
        'subtotal': Decimal('0.00'),  # Default value
        'tax': Decimal('0.00'),  # Default value
        'total': Decimal('0.00'),  # Default value
        'ebt_amount': None,
        'instant_savings': None,
        'parse_error': None
    }
    
    # Try to find store info (usually in first few lines)
    store_found = False
    for line in lines[:10]:  # Increased search range
        if 'COSTCO' in line.upper() and ('WHOLESALE' in line.upper() or 'WAREHOUSE' in line.upper()):
            parsed_data['store_location'] = line.strip()
            store_found = True
            break
    
    # Try to find store number
    for line in lines[:10]:  # Increased search range
        if any(x in line.upper() for x in ['WAREHOUSE', 'STORE', 'LOCATION']) and '#' in line:
            number_match = re.search(r'#(\d+)', line)
            if number_match:
                parsed_data['store_number'] = number_match.group(1)
                break
    
    # Try to find date
    date_found = False
    for line in lines[:15]:  # Increased search range
        # Try different date formats
        date_patterns = [
            r'(\d{2}/\d{2}/\d{4})\s*(\d{1,2}:\d{2})',  # MM/DD/YYYY HH:MM
            r'(\d{2}/\d{2}/\d{2})\s*(\d{1,2}:\d{2})',  # MM/DD/YY HH:MM
            r'(\d{2}-\d{2}-\d{4})\s*(\d{1,2}:\d{2})',  # MM-DD-YYYY HH:MM
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, line)
            if date_match:
                try:
                    date_str = f"{date_match.group(1)} {date_match.group(2)}"
                    if len(date_match.group(1)) == 8:  # MM/DD/YY format
                        parsed_data['transaction_date'] = datetime.strptime(date_str, "%m/%d/%y %H:%M")
                    else:
                        parsed_data['transaction_date'] = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
                    date_found = True
                    break
                except ValueError:
                    continue
        if date_found:
            break
    
    # Process items
    current_item = None
    for line in lines:
        # Look for item patterns (item number followed by description and price)
        item_patterns = [
            r'(\d{6,})\s+(.*?)\s+(\d+\.\d{2})',  # Basic pattern
            r'(\d{6,})\s+(.*?)\s+(\d+)\s+@\s+[\d.]+\s+(\d+\.\d{2})',  # Quantity pattern
        ]
        
        for pattern in item_patterns:
            item_match = re.search(pattern, line)
            if item_match:
                if current_item:
                    parsed_data['items'].append(current_item)
                
                if len(item_match.groups()) == 4:  # Quantity pattern matched
                    quantity = int(item_match.group(3))
                    price = Decimal(item_match.group(4))
                else:
                    quantity = 1
                    price = Decimal(item_match.group(3))
                
                current_item = {
                    'item_code': item_match.group(1),
                    'description': item_match.group(2).strip(),
                    'price': price,
                    'quantity': quantity,
                    'discount': None,
                    'is_taxable': 'T' in line or '*' in line  # Common indicators for taxable items
                }
                break
        
        # Look for totals
        if 'SUBTOTAL' in line.upper():
            amount_match = re.search(r'\d+\.\d{2}', line)
            if amount_match:
                parsed_data['subtotal'] = Decimal(amount_match.group())
        elif 'TAX' in line.upper() and not 'TAXABLE' in line.upper():
            amount_match = re.search(r'\d+\.\d{2}', line)
            if amount_match:
                parsed_data['tax'] = Decimal(amount_match.group())
        elif 'TOTAL' in line.upper() and not any(x in line.upper() for x in ['SUBTOTAL', 'TAX']):
            amount_match = re.search(r'\d+\.\d{2}', line)
            if amount_match:
                parsed_data['total'] = Decimal(amount_match.group())
        elif 'INSTANT SAVINGS' in line.upper():
            amount_match = re.search(r'\d+\.\d{2}', line)
            if amount_match:
                parsed_data['instant_savings'] = Decimal(amount_match.group())
        elif 'EBT' in line.upper():
            amount_match = re.search(r'\d+\.\d{2}', line)
            if amount_match:
                parsed_data['ebt_amount'] = Decimal(amount_match.group())
    
    # Add last item if exists
    if current_item:
        parsed_data['items'].append(current_item)
    
    # Set parse error if we couldn't find critical information
    if not parsed_data['items']:
        parsed_data['parse_error'] = "Could not find any items in the receipt"
    elif not parsed_data['total']:
        parsed_data['parse_error'] = "Could not find total amount"
    elif not store_found:
        parsed_data['parse_error'] = "Could not find store information"
    elif not date_found:
        parsed_data['parse_error'] = "Could not find transaction date"
    
    return parsed_data

def parse_with_deepseek(text: str) -> Dict:
    """
    Parse receipt text using DeepSeek API for more accurate extraction.
    """
    prompt = """
    Parse this Costco receipt and extract the following information in JSON format:
    - store_location (string)
    - store_number (string)
    - transaction_date (string in format MM/DD/YYYY HH:MM)
    - items (array of objects with):
        - item_code (string)
        - description (string)
        - price (decimal)
        - quantity (integer)
        - discount (decimal or null)
        - is_taxable (boolean)
    - subtotal (decimal)
    - tax (decimal)
    - total (decimal)
    - ebt_amount (decimal or null)
    - instant_savings (decimal or null)

    Receipt text:
    {text}

    Return only valid JSON without any additional text or explanation.
    """

    try:
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            raise Exception("DeepSeek API key not configured")

        # Make API call to DeepSeek
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt.format(text=text)
                    }
                ],
                "temperature": 0.1
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.text}")

        # Parse the response
        parsed_json = response.json()
        parsed_data = json.loads(parsed_json['choices'][0]['message']['content'])

        # Convert date string to datetime object
        if parsed_data.get('transaction_date'):
            try:
                parsed_data['transaction_date'] = datetime.strptime(
                    parsed_data['transaction_date'], 
                    "%m/%d/%Y %H:%M"
                )
            except ValueError:
                parsed_data['parse_error'] = "Failed to parse transaction date"

        # Convert string amounts to Decimal
        for field in ['subtotal', 'tax', 'total', 'ebt_amount', 'instant_savings']:
            if parsed_data.get(field):
                try:
                    parsed_data[field] = Decimal(str(parsed_data[field]))
                except:
                    parsed_data[field] = None

        # Convert item amounts to Decimal
        for item in parsed_data.get('items', []):
            try:
                item['price'] = Decimal(str(item['price']))
                if item.get('discount'):
                    item['discount'] = Decimal(str(item['discount']))
            except:
                continue

        return parsed_data

    except Exception as e:
        # If DeepSeek fails, fall back to regex parsing
        parsed_data = parse_with_regex(text)
        parsed_data['parse_error'] = f"AI parsing unavailable, using basic parsing: {str(e)}"
        return parsed_data

def process_receipt_pdf(pdf_path: str) -> Dict:
    """Process a receipt PDF file and return parsed data."""
    try:
        text = extract_text_from_pdf(pdf_path)
        return parse_with_deepseek(text)
    except Exception as e:
        return {
            'parse_error': f"Failed to process PDF: {str(e)}",
            'store_location': None,
            'store_number': None,
            'transaction_date': None,
            'items': [],
            'subtotal': None,
            'tax': None,
            'total': None,
            'ebt_amount': None,
            'instant_savings': None
        } 