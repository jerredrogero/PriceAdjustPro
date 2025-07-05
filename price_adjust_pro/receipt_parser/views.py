from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
import os
import logging
import json
from django.utils import timezone
from decimal import Decimal
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.db import migrations
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.db import transaction

from .models import (
    Receipt, LineItem, CostcoItem,
    CostcoWarehouse, PriceAdjustmentAlert, OfficialSaleItem, CostcoPromotion
)
from .utils import (
    process_receipt_pdf, extract_text_from_pdf, parse_receipt,
    update_price_database, check_for_price_adjustments,
    process_receipt_image, process_receipt_file
)
from .serializers import ReceiptSerializer

logger = logging.getLogger(__name__)

@login_required
def upload_receipt(request):
    if request.method == 'POST' and request.FILES.get('receipt_file'):
        receipt_file = request.FILES['receipt_file']
        
        # Validate file type - now accepting images too
        file_ext = receipt_file.name.lower()
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif']
        
        # Debug logging
        logger.info(f"Uploaded file: {receipt_file.name}, extension check: {file_ext}")
        
        is_valid_file = any(file_ext.endswith(ext) for ext in allowed_extensions)
        logger.info(f"File validation result: {is_valid_file}")
        
        if not is_valid_file:
            logger.warning(f"Invalid file type uploaded: {file_ext}")
            messages.error(request, f'Please upload a PDF or image file (JPG, PNG, WebP, AVIF, etc.). Received: {file_ext}')
            return redirect('upload_receipt')
            
        try:
            # Save the uploaded file
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            file_path = default_storage.save(
                f'receipts/{request.user.id}/{timestamp}_{receipt_file.name}',
                ContentFile(receipt_file.read())
            )
            
            # Get the full path using the storage backend
            full_path = default_storage.path(file_path)
            
            # Process the receipt using the unified function
            parsed_data = process_receipt_file(full_path, user=request.user)
            
            if parsed_data.get('parse_error'):
                messages.warning(request, f"Warning: {parsed_data['parse_error']}")
            
            # Show additional warning for image uploads
            if parsed_data.get('source_type') == 'image':
                messages.info(request, 'Photo processed! Please review the extracted data for accuracy.')
            
            # Check if receipt already exists
            existing_receipt = Receipt.objects.filter(
                user=request.user,
                transaction_number=parsed_data.get('transaction_number')
            ).first()

            if existing_receipt:
                # Process the receipt data for price adjustments without creating a new receipt
                try:
                    # Update existing receipt with new data
                    existing_receipt.store_location = parsed_data.get('store_location', existing_receipt.store_location)
                    # Clean store location if it's null
                    if not existing_receipt.store_location or existing_receipt.store_location.lower() in ['null', 'n/a', '', 'none']:
                        store_number = parsed_data.get('store_number', '0000')
                        existing_receipt.store_location = f'Costco Warehouse #{store_number}' if store_number != '0000' else 'Costco Warehouse'
                    
                    existing_receipt.store_number = parsed_data.get('store_number', '0000') if parsed_data.get('store_number') and parsed_data.get('store_number').lower() not in ['null', '', 'none', 'n/a'] else '0000'
                    existing_receipt.transaction_date = parsed_data.get('transaction_date', existing_receipt.transaction_date)
                    existing_receipt.total = parsed_data.get('total', existing_receipt.total)
                    existing_receipt.subtotal = parsed_data.get('subtotal', existing_receipt.subtotal)
                    existing_receipt.tax = parsed_data.get('tax', existing_receipt.tax)
                    existing_receipt.parsed_successfully = parsed_data.get('parsed_successfully', existing_receipt.parsed_successfully)
                    existing_receipt.parse_error = parsed_data.get('parse_error', existing_receipt.parse_error)
                    existing_receipt.save()
                    
                    # Clear existing line items
                    existing_receipt.items.all().delete()
                    
                    # Create new line items
                    price_adjustments_created = 0  # Initialize counter for tracking price adjustment alerts
                    if parsed_data.get('items'):
                        for item_data in parsed_data['items']:
                            try:
                                line_item = LineItem.objects.create(
                                    receipt=existing_receipt,
                                    item_code=item_data.get('item_code', '000000'),
                                    description=item_data.get('description', 'Unknown Item'),
                                    price=Decimal(str(item_data.get('price', '0.00'))),
                                    quantity=item_data.get('quantity', 1),
                                    discount=item_data.get('discount'),
                                    is_taxable=item_data.get('is_taxable', False),
                                    instant_savings=Decimal(str(item_data['instant_savings'])) if item_data.get('instant_savings') else None,
                                    original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None
                                )
                                # Check if current user can benefit from existing promotions
                                from .utils import check_current_user_for_price_adjustments
                                check_current_user_for_price_adjustments(line_item, existing_receipt)
                            except Exception as e:
                                logger.error(f"Line item error: {str(e)}")
                    
                    update_price_database(parsed_data, user=request.user)
                    messages.success(request, 'Receipt updated successfully')
                    default_storage.delete(file_path)
                    return JsonResponse({
                        'transaction_number': existing_receipt.transaction_number,
                        'message': 'Receipt updated successfully',
                        'items': [
                            {
                                'item_code': item.item_code,
                                'description': item.description,
                                'price': str(item.price),
                                'quantity': item.quantity,
                                'discount': str(item.discount) if item.discount else None
                            }
                            for item in existing_receipt.items.all()
                        ],
                        'parse_error': parsed_data.get('parse_error'),
                        'parsed_successfully': parsed_data.get('parsed_successfully', False),
                        'is_duplicate': True
                    })
                except Exception as e:
                    logger.error(f"Error processing duplicate receipt: {str(e)}")
                    messages.error(request, f'Error processing receipt data: {str(e)}')
                
                # Clean up the uploaded file since we don't need to store it
                default_storage.delete(file_path)
                return redirect('receipt_detail', transaction_number=existing_receipt.transaction_number)

            # Create new Receipt object if it doesn't exist
            try:
                # Consider a receipt successfully parsed if it has:
                # 1. A valid transaction number
                # 2. Items with valid prices
                # 3. Valid total amount
                # 4. Valid transaction date
                transaction_number = parsed_data.get('transaction_number')
                
                # Ensure we have a valid transaction number
                if not transaction_number or transaction_number in ['null', 'N/A', '', 'None']:
                    # Generate a unique fallback transaction number
                    import uuid
                    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
                    store_number = parsed_data.get('store_number', '0000')
                    random_suffix = str(uuid.uuid4().hex)[:4].upper()
                    transaction_number = f"{store_number}{timestamp}{random_suffix}"
                    parsed_data['transaction_number'] = transaction_number
                    logger.warning(f"Generated fallback transaction number for upload: {transaction_number}")
                
                # Clean up store location
                store_location = parsed_data.get('store_location', '')
                store_number = parsed_data.get('store_number', '0000')
                if not store_location or store_location.lower() in ['null', 'n/a', '', 'none']:
                    store_location = f'Costco Warehouse #{store_number}' if store_number != '0000' else 'Costco Warehouse'
                    parsed_data['store_location'] = store_location
                
                if (transaction_number and 
                    parsed_data.get('items') and 
                    parsed_data.get('total') and 
                    parsed_data.get('transaction_date')):
                    parsed_data['parsed_successfully'] = True
                    parsed_data['parse_error'] = None
                
                receipt = Receipt.objects.create(
                    user=request.user,
                    file=None,  # No file storage - data only
                    transaction_number=transaction_number,  # Use validated transaction number
                    store_location=parsed_data.get('store_location', 'Costco Warehouse'),
                    store_number=parsed_data.get('store_number', '0000') if parsed_data.get('store_number') and parsed_data.get('store_number').lower() not in ['null', '', 'none', 'n/a'] else '0000',
                    transaction_date=parsed_data.get('transaction_date', timezone.now()),
                    subtotal=parsed_data.get('subtotal', Decimal('0.00')),
                    total=parsed_data.get('total', Decimal('0.00')),
                    tax=parsed_data.get('tax', Decimal('0.00')),
                    ebt_amount=parsed_data.get('ebt_amount'),
                    instant_savings=parsed_data.get('instant_savings'),
                    parsed_successfully=parsed_data.get('parsed_successfully', False),
                    parse_error=parsed_data.get('parse_error')
                )
                
                # Create LineItem objects only if we have valid items
                price_adjustments_created = 0  # Initialize counter for tracking price adjustment alerts
                if parsed_data.get('items'):
                    for item_data in parsed_data['items']:
                        try:
                            line_item = LineItem.objects.create(
                                receipt=receipt,
                                item_code=item_data.get('item_code', '000000'),
                                description=item_data.get('description', 'Unknown Item'),
                                price=Decimal(str(item_data.get('price', '0.00'))),
                                quantity=item_data.get('quantity', 1),
                                discount=item_data.get('discount'),
                                is_taxable=item_data.get('is_taxable', False),
                                instant_savings=Decimal(str(item_data['instant_savings'])) if item_data.get('instant_savings') else None,
                                original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None
                            )
                            # Check if current user can benefit from existing promotions
                            from .utils import check_current_user_for_price_adjustments
                            check_current_user_for_price_adjustments(line_item, receipt)
                        except Exception as e:
                            logger.error(f"Line item error: {str(e)}")
                            continue
                
                messages.success(request, 'Receipt uploaded successfully.')
                return JsonResponse({
                    'transaction_number': receipt.transaction_number,
                    'message': 'Receipt processed successfully',
                    'items': [
                        {
                            'item_code': item.item_code,
                            'description': item.description,
                            'price': str(item.price),
                            'quantity': item.quantity,
                            'discount': str(item.discount) if item.discount else None
                        }
                        for item in receipt.items.all()
                    ],
                    'parse_error': parsed_data.get('parse_error'),
                    'parsed_successfully': parsed_data.get('parsed_successfully', False),
                    'is_duplicate': False
                })
                
            except Exception as e:
                logger.error(f"Error creating receipt: {str(e)}")
                # Clean up the uploaded file if receipt creation fails
                default_storage.delete(file_path)
                messages.error(request, f'Error processing receipt data: {str(e)}')
                return redirect('upload_receipt')
            
        except Exception as e:
            logger.error(f"Error processing receipt file: {str(e)}")
            messages.error(request, f'Error processing receipt file: {str(e)}')
            return redirect('upload_receipt')
    
    return render(request, 'receipt_parser/upload.html')

@login_required
def receipt_list(request):
    receipts = Receipt.objects.filter(user=request.user).order_by('-transaction_date')
    return render(request, 'receipt_parser/receipt_list.html', {'receipts': receipts})

@login_required
def receipt_detail(request, transaction_number):
    receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=request.user)
    line_items = receipt.items.all().values(
        'item_code', 
        'description', 
        'price', 
        'quantity',
        'discount'
    )
    return JsonResponse({
        'receipt': {
            'transaction_number': receipt.transaction_number,
            'store_location': receipt.store_location,
            'store_number': receipt.store_number,
            'transaction_date': receipt.transaction_date.isoformat(),
            'total': str(receipt.total),
            'subtotal': str(receipt.subtotal),
            'tax': str(receipt.tax),
            'items': list(line_items),
            'parsed_successfully': receipt.parsed_successfully,
            'parse_error': receipt.parse_error
        }
    })

# API Views
@login_required
def api_receipt_list(request):
    if request.method == 'GET':
        try:
            # Get all receipts for the user, ordered by date
            receipts = Receipt.objects.filter(user=request.user).order_by('-transaction_date').prefetch_related('items')
            
            # Debug logging
            logger.info(f"Found {receipts.count()} receipts for user {request.user.username}")
            
            # Get active price adjustments count
            adjustments_count = PriceAdjustmentAlert.objects.filter(
                user=request.user,
                is_active=True,
                is_dismissed=False
            ).count()
            
            # Build response data
            response_data = {
                'receipts': [{
                    'transaction_number': receipt.transaction_number,
            'store_location': receipt.store_location,
            'store_number': receipt.store_number,
                    'transaction_date': receipt.transaction_date.isoformat(),
            'total': str(receipt.total),
                    'items_count': sum(item.quantity for item in receipt.items.all()),  # Sum actual quantities
            'parsed_successfully': receipt.parsed_successfully,
            'parse_error': receipt.parse_error,
                    'subtotal': str(receipt.subtotal),
                    'tax': str(receipt.tax),
                    'instant_savings': str(receipt.instant_savings) if receipt.instant_savings else None,
                    'items': [{
                        'id': item.id,
                        'item_code': item.item_code,
                        'description': item.description,
                        'price': str(item.price),
                        'quantity': item.quantity,
                        'total_price': str(item.total_price),
                        'is_taxable': item.is_taxable,
                        'on_sale': item.on_sale,
                        'instant_savings': str(item.instant_savings) if item.instant_savings else None,
                        'original_price': str(item.original_price) if item.original_price else None,
                        'original_total_price': str(item.original_total_price) if item.original_total_price else None
                    } for item in receipt.items.all()]
                } for receipt in receipts],
                'price_adjustments_count': adjustments_count
            }
            
            # Debug logging
            logger.info(f"Returning {len(response_data['receipts'])} receipts in response")
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error in api_receipt_list: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
@login_required
def api_receipt_detail(request, transaction_number):
    receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=request.user)
    
    # Handle DELETE requests (fix for iOS app bug)
    if request.method == 'DELETE':
        try:
            # Delete related price adjustment alerts first
            from .models import PriceAdjustmentAlert
            
            # Find all price adjustment alerts that were created from this receipt
            item_codes = list(receipt.items.values_list('item_code', flat=True))
            
            # Use a more comprehensive approach to find related alerts
            from datetime import timedelta
            purchase_date_start = (receipt.transaction_date - timedelta(hours=12)).date()
            purchase_date_end = (receipt.transaction_date + timedelta(hours=12)).date()
            
            alerts_to_delete = PriceAdjustmentAlert.objects.filter(
                user=request.user,
                item_code__in=item_codes,
                purchase_date__date__gte=purchase_date_start,
                purchase_date__date__lte=purchase_date_end
            )
            
            # Additional filter: if we have a valid store number, also match by that
            if receipt.store_number and receipt.store_number not in ['0000', 'null', '', 'None']:
                alerts_to_delete = alerts_to_delete.filter(
                    original_store_number=receipt.store_number
                )
            
            deleted_alerts_count = alerts_to_delete.count()
            
            # Log what we're about to delete for debugging
            if deleted_alerts_count > 0:
                logger.info(f"About to delete {deleted_alerts_count} price adjustment alerts for receipt {transaction_number}")
                for alert in alerts_to_delete:
                    logger.info(f"  - Alert: {alert.item_description} (${alert.original_price} -> ${alert.lower_price}), Purchase: {alert.purchase_date}")
            
            alerts_to_delete.delete()
            
            # Delete the physical file if it exists
            if receipt.file:
                # Get the full path using the storage backend
                file_path = receipt.file.path
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete file {file_path}: {str(e)}")
                    # Continue with receipt deletion even if file deletion fails
            
            # Delete the receipt (this will cascade delete line items)
            receipt.delete()
            
            return JsonResponse({
                'message': 'Receipt deleted successfully',
                'deleted_alerts': deleted_alerts_count
            }, status=200)
            
        except Exception as e:
            logger.error(f"Error deleting receipt: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    # Handle PATCH requests for updates (used by iOS app)
    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            
            # Check if user wants to accept manual edits without recalculation
            accept_manual_edits = data.get('accept_manual_edits', False)
            logger.info(f"PATCH to api_receipt_detail for {transaction_number}: accept_manual_edits={accept_manual_edits}")
            logger.info(f"Incoming data: subtotal={data.get('subtotal')}, tax={data.get('tax')}, total={data.get('total')}")
            
            # Update receipt fields
            receipt.store_location = data.get('store_location', receipt.store_location)
            receipt.store_number = data.get('store_number', receipt.store_number)
            receipt.subtotal = Decimal(str(data.get('subtotal', receipt.subtotal)))
            receipt.tax = Decimal(str(data.get('tax', receipt.tax)))
            receipt.total = Decimal(str(data.get('total', receipt.total)))
            receipt.instant_savings = Decimal(str(data.get('instant_savings', '0.00'))) if data.get('instant_savings') else None
            
            # Update transaction date if provided
            if data.get('transaction_date'):
                try:
                    from datetime import datetime
                    receipt.transaction_date = datetime.fromisoformat(data['transaction_date'].replace('Z', '+00:00'))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse transaction_date: {data.get('transaction_date')}, error: {str(e)}")
            
            receipt.save()
            
            # Update items if provided
            if data.get('items'):
                receipt.items.all().delete()  # Remove existing items
                
                for item_data in data.get('items', []):
                    try:
                        LineItem.objects.create(
                            receipt=receipt,
                            item_code=item_data.get('item_code', '000000'),
                            description=item_data.get('description', 'Unknown Item'),
                            price=Decimal(str(item_data.get('price', '0.00'))),
                            quantity=item_data.get('quantity', 1),
                            is_taxable=item_data.get('is_taxable', False),
                            on_sale=item_data.get('on_sale', False),
                            instant_savings=Decimal(str(item_data['instant_savings'])) if item_data.get('instant_savings') else None,
                            original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None,
                            original_total_price=Decimal(str(item_data['total_price'])) if item_data.get('total_price') else None
                        )
                    except Exception as e:
                        logger.error(f"Error creating line item: {str(e)}")
                        continue
            
            # FORCE manual values when accept_manual_edits=True (same fix as the other endpoint)
            if accept_manual_edits:
                logger.info("FORCING manual values to override any automatic calculations")
                receipt.subtotal = Decimal(str(data.get('subtotal', receipt.subtotal)))
                receipt.tax = Decimal(str(data.get('tax', receipt.tax)))
                receipt.total = Decimal(str(data.get('total', receipt.total)))
                receipt.instant_savings = Decimal(str(data.get('instant_savings', '0.00'))) if data.get('instant_savings') else None
                receipt.save()
                logger.info(f"After FORCING manual values: subtotal={receipt.subtotal}, tax={receipt.tax}, total={receipt.total}")
            
        except Exception as e:
            logger.error(f"Error updating receipt via PATCH: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    # Handle GET requests (existing functionality)
    items = [{
        'id': item.id,
        'item_code': item.item_code,
        'description': item.description,
        'price': str(item.price),
        'quantity': item.quantity,
        'total_price': str(item.total_price),
        'is_taxable': item.is_taxable,
        'on_sale': item.on_sale,
        'instant_savings': str(item.instant_savings) if item.instant_savings else None,
        'original_price': str(item.original_price) if item.original_price else None,
        'original_total_price': str(item.original_total_price) if item.original_total_price else None
    } for item in receipt.items.all()]
    
    return JsonResponse({
        'transaction_number': receipt.transaction_number,
        'store_location': receipt.store_location,
        'store_number': receipt.store_number,
        'transaction_date': receipt.transaction_date.isoformat(),
        'subtotal': str(receipt.subtotal),
        'tax': str(receipt.tax),
        'total': str(receipt.total),
        'ebt_amount': str(receipt.ebt_amount) if receipt.ebt_amount else None,
        'instant_savings': str(receipt.instant_savings) if receipt.instant_savings else None,
        'items': items,
        'parsed_successfully': receipt.parsed_successfully,
        'parse_error': receipt.parse_error,
        'file': receipt.file.url if receipt.file else None,
    })

@csrf_exempt
@login_required
def api_receipt_upload(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    if 'receipt_file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
        
    receipt_file = request.FILES['receipt_file']
    
    # Validate file type - now accepting images too
    file_ext = receipt_file.name.lower()
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif']
    
    # Debug logging
    logger.info(f"Uploaded file: {receipt_file.name}, extension check: {file_ext}")
    
    is_valid_file = any(file_ext.endswith(ext) for ext in allowed_extensions)
    logger.info(f"File validation result: {is_valid_file}")
    
    if not is_valid_file:
        logger.warning(f"Invalid file type uploaded: {file_ext}")
        return JsonResponse({'error': 'Please upload a PDF or image file (JPG, PNG, WebP, AVIF, etc.)'}, status=400)
        
    try:
        # Save the uploaded file
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        file_path = default_storage.save(
            f'receipts/{request.user.id}/{timestamp}_{receipt_file.name}',
            ContentFile(receipt_file.read())
        )
        
        # Get the full path using the storage backend
        full_path = default_storage.path(file_path)
        
        # Process the receipt using the unified function
        parsed_data = process_receipt_file(full_path, user=request.user)

        # Check for existing receipt
        existing_receipt = Receipt.objects.filter(
            transaction_number=parsed_data['transaction_number'],
            user=request.user  # Add user filter
        ).first()

        if existing_receipt:
            # Update existing receipt - no file storage
            existing_receipt.file = None
            existing_receipt.store_location = parsed_data['store_location']
            # Clean store location if it's null
            if not existing_receipt.store_location or existing_receipt.store_location.lower() in ['null', 'n/a', '', 'none']:
                store_number = parsed_data.get('store_number', '0000')
                existing_receipt.store_location = f'Costco Warehouse #{store_number}' if store_number != '0000' else 'Costco Warehouse'
            
            existing_receipt.store_number = parsed_data.get('store_number', '0000') if parsed_data.get('store_number') and parsed_data.get('store_number').lower() not in ['null', '', 'none', 'n/a'] else '0000'
            existing_receipt.transaction_date = parsed_data['transaction_date']
            existing_receipt.subtotal = Decimal(str(parsed_data['subtotal']))
            existing_receipt.tax = Decimal(str(parsed_data['tax']))
            existing_receipt.total = Decimal(str(parsed_data['total']))
            existing_receipt.instant_savings = Decimal(str(parsed_data['instant_savings'])) if parsed_data.get('instant_savings') else None
            existing_receipt.parsed_successfully = parsed_data['parsed_successfully']
            existing_receipt.parse_error = parsed_data.get('parse_error')
            existing_receipt.user = request.user  # Ensure user is set
            existing_receipt.save()

            # Delete existing line items
            existing_receipt.items.all().delete()

            # Create new line items
            price_adjustments_created = 0  # Initialize counter for tracking price adjustment alerts
            for item_data in parsed_data['items']:
                LineItem.objects.create(
                    receipt=existing_receipt,
                    item_code=item_data['item_code'],
                    description=item_data['description'],
                    price=Decimal(str(item_data['price'])),
                    quantity=int(item_data['quantity']),
                    is_taxable=item_data['is_taxable'],
                    on_sale=item_data.get('on_sale', False),
                    instant_savings=Decimal(str(item_data['instant_savings'])) if item_data.get('instant_savings') else None,
                    original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None
                )

            receipt = existing_receipt
            return JsonResponse({
                'transaction_number': receipt.transaction_number,
                'message': 'Receipt updated successfully',
                'items': parsed_data['items'],
                'parsed_successfully': True,
                'is_duplicate': True
            })
        
        # Consider a receipt successfully parsed if it has:
        # 1. A valid transaction number
        # 2. Items with valid prices
        # 3. Valid total amount
        # 4. Valid transaction date
        if (parsed_data.get('transaction_number') and 
            parsed_data.get('items') and 
            parsed_data.get('total') and 
            parsed_data.get('transaction_date')):
            parsed_data['parsed_successfully'] = True
            parsed_data['parse_error'] = None
        
        # Clean up store location for API uploads too
        store_location = parsed_data.get('store_location', '')
        store_number = parsed_data.get('store_number', '0000')
        if not store_location or store_location.lower() in ['null', 'n/a', '', 'none']:
            store_location = f'Costco Warehouse #{store_number}' if store_number != '0000' else 'Costco Warehouse'
            parsed_data['store_location'] = store_location
        
        # Create Receipt object with default values if parsing failed
        receipt = Receipt.objects.create(
            user=request.user,
            file=None,  # No file storage - data only
            transaction_number=parsed_data.get('transaction_number'),
            store_location=parsed_data.get('store_location', 'Costco Warehouse'),
            store_number=parsed_data.get('store_number', '0000') if parsed_data.get('store_number') and parsed_data.get('store_number').lower() not in ['null', '', 'none', 'n/a'] else '0000',
            transaction_date=parsed_data.get('transaction_date', timezone.now()),
            subtotal=parsed_data.get('subtotal', Decimal('0.00')),
            total=parsed_data.get('total', Decimal('0.00')),
            tax=parsed_data.get('tax', Decimal('0.00')),
            ebt_amount=parsed_data.get('ebt_amount'),
            instant_savings=parsed_data.get('instant_savings'),
            parsed_successfully=parsed_data.get('parsed_successfully', False),
            parse_error=parsed_data.get('parse_error')
        )
        
        # Create LineItem objects only if we have valid items
        price_adjustments_created = 0  # Initialize counter for tracking price adjustment alerts
        if parsed_data.get('items'):
            for item_data in parsed_data['items']:
                try:
                    line_item = LineItem.objects.create(
                        receipt=receipt,
                        item_code=item_data.get('item_code', '000000'),
                        description=item_data.get('description', 'Unknown Item'),
                        price=Decimal(str(item_data.get('price', '0.00'))),
                        quantity=item_data.get('quantity', 1),
                        discount=item_data.get('discount'),
                        is_taxable=item_data.get('is_taxable', False),
                        on_sale=item_data.get('on_sale', False),
                        instant_savings=Decimal(str(item_data['instant_savings'])) if item_data.get('instant_savings') else None,
                        original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None,
                        original_total_price=Decimal(str(item_data['total_price'])) if item_data.get('total_price') else None
                    )
                    # Check if current user can benefit from existing promotions
                    from .utils import check_current_user_for_price_adjustments
                    check_current_user_for_price_adjustments(line_item, receipt)
                except Exception as e:
                    logger.error(f"Error creating line item: {str(e)}")
                    continue
        
        return JsonResponse({
            'transaction_number': receipt.transaction_number,
            'message': 'Receipt processed successfully',
            'items': [
                {
                    'item_code': item.item_code,
                    'description': item.description,
                    'price': str(item.price),
                    'quantity': item.quantity,
                    'discount': str(item.discount) if item.discount else None
                }
                for item in receipt.items.all()
            ],
            'parse_error': parsed_data.get('parse_error'),
            'parsed_successfully': parsed_data.get('parsed_successfully', False),
            'is_duplicate': False
        })
        
    except Exception as e:
        logger.error(f"Error processing receipt file: {str(e)}")
        # Clean up the uploaded file if it exists
        if 'file_path' in locals():
            default_storage.delete(file_path)
        return JsonResponse({
            'error': str(e),
            'is_duplicate': 'UNIQUE constraint failed' in str(e)
        }, status=200)  # Return 200 even for duplicates

@csrf_exempt
@login_required
def api_receipt_delete(request, transaction_number):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Validate transaction number
    if not transaction_number or transaction_number in ['null', 'N/A', '', 'None']:
        return JsonResponse({'error': 'Invalid transaction number'}, status=400)
    
    try:
        receipt = Receipt.objects.get(transaction_number=transaction_number, user=request.user)
    except Receipt.DoesNotExist:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    
    try:
        # Delete related price adjustment alerts first
        from .models import PriceAdjustmentAlert
        
        # Find all price adjustment alerts that were created from this receipt
        # Match by user, item codes, purchase date, and store information
        item_codes = list(receipt.items.values_list('item_code', flat=True))
        
        # Use a more comprehensive approach to find related alerts
        # 1. Find alerts where this user bought items that are in this receipt
        # 2. Match by purchase date (within the same day, accounting for timezone differences)
        # 3. Optionally match by store (but don't require exact match in case of data inconsistencies)
        
        from datetime import timedelta
        purchase_date_start = (receipt.transaction_date - timedelta(hours=12)).date()
        purchase_date_end = (receipt.transaction_date + timedelta(hours=12)).date()
        
        alerts_to_delete = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            item_code__in=item_codes,
            purchase_date__date__gte=purchase_date_start,
            purchase_date__date__lte=purchase_date_end
        )
        
        # Additional filter: if we have a valid store number, also match by that
        if receipt.store_number and receipt.store_number not in ['0000', 'null', '', 'None']:
            alerts_to_delete = alerts_to_delete.filter(
                original_store_number=receipt.store_number
            )
        
        deleted_alerts_count = alerts_to_delete.count()
        
        # Log what we're about to delete for debugging
        if deleted_alerts_count > 0:
            logger.info(f"About to delete {deleted_alerts_count} price adjustment alerts for receipt {transaction_number}")
            for alert in alerts_to_delete:
                logger.info(f"  - Alert: {alert.item_description} (${alert.original_price} -> ${alert.lower_price}), Purchase: {alert.purchase_date}")
        
        alerts_to_delete.delete()
        
        # Delete the physical file if it exists
        if receipt.file:
            # Get the full path using the storage backend
            file_path = receipt.file.path
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {file_path}: {str(e)}")
                # Continue with receipt deletion even if file deletion fails
        
        # Delete the receipt (this will cascade delete line items)
        receipt.delete()
        
        return JsonResponse({
            'message': 'Receipt deleted successfully',
            'deleted_alerts': deleted_alerts_count
        })
    except Exception as e:
        logger.error(f"Error deleting receipt: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def delete_receipt(request, transaction_number):
    try:
        receipt = Receipt.objects.get(
            user=request.user,
            transaction_number=transaction_number
        )
        
        # Delete related price adjustment alerts first
        from .models import PriceAdjustmentAlert
        
        # Find all price adjustment alerts that were created from this receipt
        item_codes = list(receipt.items.values_list('item_code', flat=True))
        
        # Use a more comprehensive approach to find related alerts
        # 1. Find alerts where this user bought items that are in this receipt
        # 2. Match by purchase date (within the same day, accounting for timezone differences)
        # 3. Optionally match by store (but don't require exact match in case of data inconsistencies)
        
        from datetime import timedelta
        purchase_date_start = (receipt.transaction_date - timedelta(hours=12)).date()
        purchase_date_end = (receipt.transaction_date + timedelta(hours=12)).date()
        
        alerts_to_delete = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            item_code__in=item_codes,
            purchase_date__date__gte=purchase_date_start,
            purchase_date__date__lte=purchase_date_end
        )
        
        # Additional filter: if we have a valid store number, also match by that
        if receipt.store_number and receipt.store_number not in ['0000', 'null', '', 'None']:
            alerts_to_delete = alerts_to_delete.filter(
                original_store_number=receipt.store_number
            )
        
        deleted_alerts_count = alerts_to_delete.count()
        
        # Log what we're about to delete for debugging
        if deleted_alerts_count > 0:
            logger.info(f"About to delete {deleted_alerts_count} price adjustment alerts for receipt {transaction_number}")
            for alert in alerts_to_delete:
                logger.info(f"  - Alert: {alert.item_description} (${alert.original_price} -> ${alert.lower_price}), Purchase: {alert.purchase_date}")
        
        alerts_to_delete.delete()
        
        receipt.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Receipt.DoesNotExist:
        return Response(
            {'error': 'Receipt not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@csrf_exempt
def api_register(request):
    """API endpoint for user registration."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        
        # Handle both web form format and iOS app format
        # Web form: username, email, password1, password2
        # iOS app: first_name, last_name, email, password
        
        # Try iOS app format first
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        password = data.get('password')
        
        # Fallback to web form format
        if not first_name:
            username = data.get('username')
            password1 = data.get('password1')
            password2 = data.get('password2')
            
            # Validate required fields
            if not all([username, email, password1, password2]):
                return JsonResponse({'error': 'All fields are required'}, status=400)

            # Check if passwords match
            if password1 != password2:
                return JsonResponse({'error': 'Passwords do not match'}, status=400)

            # Check if username exists
            if User.objects.filter(username=username).exists():
                return JsonResponse({'error': 'Username already exists'}, status=400)

            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
        else:
            # iOS app format - create username from first name and email
            logger.info(f"iOS registration attempt for: {first_name} {last_name}, email: {email}")
            
            if not all([first_name, email, password]):
                return JsonResponse({'error': 'All fields are required'}, status=400)
            
            # Create username from first name and email domain
            base_username = first_name.lower()
            username = base_username
            counter = 1
            
            # Ensure username is unique
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            logger.info(f"Generated username: {username}")
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

        # Log the user in
        login(request, user)

        return JsonResponse({
            'message': 'Account created successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

def register(request):
    """Web view for user registration."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('receipt_list')
    else:
        form = UserCreationForm()
    return render(request, 'receipt_parser/register.html', {'form': form})

@login_required
def settings(request):
    return render(request, 'receipt_parser/settings.html')

@login_required
def update_profile(request):
    if request.method == 'POST':
        user = request.user
        email = request.POST.get('email')
        
        if email:
            user.email = email
            user.save()
            messages.success(request, 'Profile updated successfully!')
        
    return redirect('settings')

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return redirect('settings')

@login_required
def delete_account(request):
    if request.method == 'POST':
        password = request.POST.get('confirm_password')
        user = request.user
        
        if user.check_password(password):
            # Delete user's price adjustment alerts first (will be cascade deleted anyway, but being explicit)
            from .models import PriceAdjustmentAlert
            alerts_count = PriceAdjustmentAlert.objects.filter(user=user).count()
            if alerts_count > 0:
                logger.info(f"Deleting {alerts_count} price adjustment alerts for user {user.username}")
            
            # Delete user's files
            user_receipts = Receipt.objects.filter(user=user)
            for receipt in user_receipts:
                if receipt.file:
                    try:
                        default_storage.delete(receipt.file.name)
                    except Exception as e:
                        logger.warning(f"Failed to delete file for receipt {receipt.transaction_number}: {str(e)}")
            
            # Delete the user account (this will cascade delete all related data)
            user.delete()
            messages.success(request, 'Your account has been deleted.')
            return redirect('login')
        else:
            messages.error(request, 'Incorrect password. Account deletion cancelled.')
    
    return redirect('settings')

@login_required
def api_check_price_adjustments(request):
    """Check for available price adjustments based on official Costco promotions only."""
    try:
        from .models import OfficialSaleItem
        
        # Get all receipts from the last 30 days
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        user_receipts = Receipt.objects.filter(
            user=request.user,
            transaction_date__gte=thirty_days_ago,
            parsed_successfully=True  # Only check successfully parsed receipts
        ).prefetch_related('items')

        adjustments = []
        current_date = timezone.now().date()
        
        # For each receipt
        for receipt in user_receipts:
            # For each item in the receipt
            for item in receipt.items.all():
                if not item.item_code:  # Skip items without item codes
                    continue
                
                # Skip if item was bought on sale
                if item.on_sale or (item.instant_savings and item.instant_savings > 0):
                    continue
                    
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
                        else:
                            continue
                    elif promotion_item.sale_price and item.price > promotion_item.sale_price:
                        # Standard promotion with sale price
                        final_price = promotion_item.sale_price
                    else:
                        # User already paid the same or less
                        continue
                    
                    price_difference = item.price - final_price
                    
                    # Only alert if the difference is significant (e.g., > $0.50)
                    if price_difference >= Decimal('0.50'):
                        # Calculate days remaining for adjustment
                        days_since_purchase = (timezone.now() - receipt.transaction_date).days
                        days_remaining = 30 - days_since_purchase

                        if days_remaining > 0:
                            adjustments.append({
                                'item_code': item.item_code,
                                'description': item.description,
                                'current_price': float(item.price),
                                'lower_price': float(final_price),
                                'price_difference': float(price_difference),
                                'store_location': 'All Costco Locations',
                                'store_number': 'ALL',
                                'purchase_date': receipt.transaction_date.isoformat(),
                                'days_remaining': days_remaining,
                                'original_store': receipt.store_location,
                                'original_store_number': receipt.store_number,
                                'is_official': True,
                                'promotion_title': promotion_item.promotion.title if promotion_item.promotion else None
                            })

        # Sort adjustments by potential savings (highest first)
        adjustments.sort(key=lambda x: x['price_difference'], reverse=True)

        return JsonResponse({
            'adjustments': adjustments,
            'total_potential_savings': sum(adj['price_difference'] for adj in adjustments)
        })

    except Exception as e:
        logger.error(f"Error checking price adjustments: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_price_adjustments(request):
    """Get active price adjustment alerts for the current user."""
    
    def get_transaction_number_for_purchase(alert):
        """Helper function to find the transaction number for the original purchase."""
        try:
            # Find the receipt for this purchase
            receipt = Receipt.objects.filter(
                user=alert.user,
                transaction_date=alert.purchase_date,
                items__item_code=alert.item_code
            ).first()
            return receipt.transaction_number if receipt else None
        except Exception:
            return None
    
    def safe_get_property(obj, prop_name, default=None):
        """Safely get a property from an object, returning default if it fails."""
        try:
            return getattr(obj, prop_name, default)
        except Exception as e:
            logger.warning(f"Error accessing {prop_name}: {str(e)}")
            return default
    
    try:
        logger.info(f"Getting price adjustments for user: {request.user.username}")
        
        # Get all active alerts for the user
        alerts = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            is_active=True,
            is_dismissed=False
        ).select_related('user')  # Add select_related to optimize queries

        logger.info(f"Found {alerts.count()} active alerts for user {request.user.username}")

        # Convert to list and sort by price difference
        alert_data = []
        total_savings = Decimal('0.00')

        for alert in alerts:
            try:
                logger.info(f"Processing alert: {alert.item_description} - ${alert.original_price} -> ${alert.lower_price}")
                price_diff = alert.original_price - alert.lower_price
                total_savings += price_diff
                
                # Safely get properties that might fail
                promotion_title = None
                sale_type = None
                try:
                    if alert.official_sale_item and alert.official_sale_item.promotion:
                        promotion_title = alert.official_sale_item.promotion.title
                        sale_type = alert.official_sale_item.sale_type
                except Exception as e:
                    logger.warning(f"Error accessing official_sale_item: {str(e)}")
                
                # Add sales page link if this is an official promotion
                sales_page_link = None
                if alert.data_source == 'official_promo' and alert.official_sale_item:
                    sales_page_link = f"/on-sale?item={alert.item_code}"

                alert_data.append({
                    'item_code': alert.item_code,
                    'description': alert.item_description,
                    'current_price': float(alert.original_price),
                    'lower_price': float(alert.lower_price),
                    'price_difference': float(price_diff),
                    'store_location': f"Costco {alert.cheaper_store_city}",
                    'store_number': alert.cheaper_store_number,
                    'purchase_date': alert.purchase_date.isoformat(),
                    'days_remaining': safe_get_property(alert, 'days_remaining', 0),
                    'original_store': f"Costco {alert.original_store_city}",
                    'original_store_number': alert.original_store_number,
                    'data_source': alert.data_source,
                    'is_official': alert.data_source == 'official_promo',
                    'promotion_title': promotion_title,
                    'sale_type': sale_type,
                    'transaction_number': get_transaction_number_for_purchase(alert),
                    'source_description': safe_get_property(alert, 'source_description', 'Price difference found'),
                    'source_description_data': safe_get_property(alert, 'source_description_data', {'text': 'Price difference found', 'links': []}),
                    'source_type_display': safe_get_property(alert, 'source_type_display', 'Price Comparison'),
                    'action_required': safe_get_property(alert, 'action_required', 'Visit customer service at any Costco location'),
                    'location_context': safe_get_property(alert, 'location_context', {'type': 'unknown', 'description': 'Price difference found'}),
                    'sales_page_link': sales_page_link,
                    'official_sale_item_id': alert.official_sale_item.id if alert.official_sale_item else None
                })
            except Exception as e:
                logger.error(f"Error processing alert {alert.id}: {str(e)}")
                continue

        # Sort by price difference (highest savings first)
        alert_data.sort(key=lambda x: x['price_difference'], reverse=True)

        logger.info(f"Returning {len(alert_data)} alerts with total savings: ${total_savings}")

        return JsonResponse({
            'adjustments': alert_data,
            'total_potential_savings': float(total_savings)
        })
    except Exception as e:
        logger.error(f"Error checking price adjustments: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def api_dismiss_price_adjustment(request, item_code):
    """Dismiss all price adjustment alerts for a specific item code."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Check authentication manually for API endpoint
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    try:
        # Get all active alerts for this item code and user
        alerts = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            item_code=item_code,
            is_active=True,
            is_dismissed=False
        )
        
        if not alerts.exists():
            return JsonResponse({'error': 'No active alerts found for this item'}, status=404)
        
        # Dismiss all alerts for this item
        dismissed_count = alerts.update(is_dismissed=True)
        
        logger.info(f"Dismissed {dismissed_count} price adjustment alerts for item {item_code} for user {request.user.username}")
        
        return JsonResponse({
            'message': f'Successfully dismissed {dismissed_count} alert(s)',
            'dismissed_count': dismissed_count
        })
    except Exception as e:
        logger.error(f"Error dismissing price adjustment: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_user_analytics(request):
    """Get analytics data about user's purchasing habits."""
    try:
        # Get all user's receipts
        receipts = Receipt.objects.filter(
            user=request.user,
            parsed_successfully=True
        ).prefetch_related('items')

        # Initialize analytics data
        analytics = {
            'total_spent': Decimal('0.00'),
            'total_saved': Decimal('0.00'),
            'total_receipts': 0,
            'total_items': 0,
            'average_receipt_total': Decimal('0.00'),
            'most_purchased_items': [],
            'spending_by_month': {},
            'most_visited_stores': {},
            'tax_paid': Decimal('0.00'),
            'total_ebt_used': Decimal('0.00'),
            'instant_savings': Decimal('0.00'),
        }

        # Process each receipt
        for receipt in receipts:
            analytics['total_receipts'] += 1
            analytics['total_spent'] += receipt.total or Decimal('0.00')
            analytics['tax_paid'] += receipt.tax or Decimal('0.00')
            analytics['total_ebt_used'] += receipt.ebt_amount or Decimal('0.00')
            analytics['instant_savings'] += receipt.instant_savings or Decimal('0.00')

            # Track spending by month
            month_key = receipt.transaction_date.strftime('%Y-%m')
            if month_key not in analytics['spending_by_month']:
                analytics['spending_by_month'][month_key] = {
                    'total': Decimal('0.00'),
                    'count': 0
                }
            analytics['spending_by_month'][month_key]['total'] += receipt.total or Decimal('0.00')
            analytics['spending_by_month'][month_key]['count'] += 1

            # Track store visits
            store_number = receipt.store_number if receipt.store_number and receipt.store_number.lower() not in ['null', '', 'none', 'n/a'] else 'Unknown'

            # Check if store_location already contains the store number to avoid duplication
            if store_number != 'Unknown' and f"#{store_number}" in receipt.store_location:
                store_key = receipt.store_location  # Use as is since it already contains the number
            else:
                store_key = f"{receipt.store_location} #{store_number}"

            analytics['most_visited_stores'][store_key] = analytics['most_visited_stores'].get(store_key, 0) + 1

            # Process items
            analytics['total_items'] += receipt.items.count()

        # Calculate average receipt total
        if analytics['total_receipts'] > 0:
            analytics['average_receipt_total'] = analytics['total_spent'] / analytics['total_receipts']

        # Get most purchased items
        most_purchased = {}
        for receipt in receipts:
            for item in receipt.items.all():
                if item.item_code not in most_purchased:
                    most_purchased[item.item_code] = {
                        'description': item.description,
                        'count': 0,
                        'total_spent': Decimal('0.00')
                    }
                most_purchased[item.item_code]['count'] += item.quantity
                most_purchased[item.item_code]['total_spent'] += item.total_price

        # Sort and get top items
        analytics['most_purchased_items'] = sorted(
            [
                {
                    'item_code': k,
                    'description': v['description'],
                    'count': v['count'],
                    'total_spent': str(v['total_spent'])
                }
                for k, v in most_purchased.items()
            ],
            key=lambda x: x['count'],
            reverse=True
        )[:10]

        # Convert decimal values to strings for JSON serialization
        analytics['total_spent'] = str(analytics['total_spent'])
        analytics['average_receipt_total'] = str(analytics['average_receipt_total'])
        analytics['tax_paid'] = str(analytics['tax_paid'])
        analytics['total_ebt_used'] = str(analytics['total_ebt_used'])
        analytics['instant_savings'] = str(analytics['instant_savings'])
        
        # Convert spending by month decimals to strings
        for month in analytics['spending_by_month']:
            analytics['spending_by_month'][month]['total'] = str(
                analytics['spending_by_month'][month]['total']
            )

        # Sort store visits
        analytics['most_visited_stores'] = sorted(
            [
                {'store': k, 'visits': v}
                for k, v in analytics['most_visited_stores'].items()
            ],
            key=lambda x: x['visits'],
            reverse=True
        )

        return JsonResponse(analytics)

    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def api_receipt_update(request, transaction_number):
    """Update a receipt after review."""
    if request.method not in ['POST', 'PATCH']:
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=request.user)
        data = json.loads(request.body)
        
        # Check if user wants to accept manual edits without recalculation
        accept_manual_edits = data.get('accept_manual_edits', False)
        logger.info(f"Receipt update for {transaction_number}: accept_manual_edits={accept_manual_edits}")
        logger.info(f"Incoming data: subtotal={data.get('subtotal')}, tax={data.get('tax')}, total={data.get('total')}")
        logger.info(f"Full request data keys: {list(data.keys())}")
        
        # Validate total items count (optional validation - skip if accepting manual edits)
        if 'total_items_sold' in data and not accept_manual_edits:
            total_quantity = sum(item.get('quantity', 1) for item in data.get('items', []))
            if total_quantity != data.get('total_items_sold', 0):
                return JsonResponse({
                    'error': f'Total quantity ({total_quantity}) must match receipt total ({data["total_items_sold"]})'
                }, status=400)
        
        price_adjustments_created = 0  # Initialize counter for tracking price adjustment alerts
        
        # Use atomic transaction to ensure all changes are committed together
        with transaction.atomic():
            # Update receipt fields
            receipt.store_location = data.get('store_location', receipt.store_location)
            receipt.store_number = data.get('store_number', receipt.store_number)
            receipt.subtotal = Decimal(str(data.get('subtotal', receipt.subtotal)))
            receipt.tax = Decimal(str(data.get('tax', receipt.tax)))
            receipt.total = Decimal(str(data.get('total', receipt.total)))
            receipt.instant_savings = Decimal(str(data.get('instant_savings', '0.00'))) if data.get('instant_savings') else None
            
            logger.info(f"Before saving receipt: subtotal={receipt.subtotal}, tax={receipt.tax}, total={receipt.total}, instant_savings={receipt.instant_savings}")
            receipt.save()
            logger.info(f"After saving receipt: subtotal={receipt.subtotal}, tax={receipt.tax}, total={receipt.total}, instant_savings={receipt.instant_savings}")
            
            # Update transaction date if provided
            if data.get('transaction_date'):
                try:
                    # Parse the ISO format date from frontend
                    from datetime import datetime
                    receipt.transaction_date = datetime.fromisoformat(data['transaction_date'].replace('Z', '+00:00'))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse transaction_date: {data.get('transaction_date')}, error: {str(e)}")
            
            
            # Update items
            receipt.items.all().delete()  # Remove existing items
            
            # Create all line items first
            created_line_items = []
            for item_data in data.get('items', []):
                try:
                    line_item = LineItem.objects.create(
                        receipt=receipt,
                        item_code=item_data.get('item_code', '000000'),
                        description=item_data.get('description', 'Unknown Item'),
                        price=Decimal(str(item_data.get('price', '0.00'))),
                        quantity=item_data.get('quantity', 1),
                        is_taxable=item_data.get('is_taxable', False),
                        on_sale=item_data.get('on_sale', False),
                        instant_savings=Decimal(str(item_data['instant_savings'])) if item_data.get('instant_savings') else None,
                        original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None,
                        original_total_price=Decimal(str(item_data['total_price'])) if item_data.get('total_price') else None
                    )
                    created_line_items.append(line_item)
                    
                except Exception as e:
                    logger.error(f"Error creating line item: {str(e)}")
                    continue
            
            logger.info(f"After creating line items, receipt totals: subtotal={receipt.subtotal}, tax={receipt.tax}, total={receipt.total}, instant_savings={receipt.instant_savings}")
            
            # Check if any code is automatically recalculating instant_savings from line items
            calculated_instant_savings = sum(item.instant_savings or Decimal('0.00') for item in created_line_items)
            logger.info(f"Calculated instant_savings from line items: {calculated_instant_savings}")
            
            # Only update price database and check adjustments if not accepting manual edits
            if not accept_manual_edits:
                logger.info("Performing automatic calculations and price database updates")
                
                # Update price database
                update_price_database({
                    'transaction_number': transaction_number,
                    'store_location': receipt.store_location,
                    'store_number': receipt.store_number,
                    'transaction_date': receipt.transaction_date,
                    'items': data.get('items', []),
                    'subtotal': receipt.subtotal,
                    'tax': receipt.tax,
                    'total': receipt.total
                }, user=request.user)
                
                # Defer price adjustment checks until after transaction commits
                def check_price_adjustments_after_commit():
                    """This function runs after the database transaction is committed."""
                    nonlocal price_adjustments_created
                    
                    for line_item in created_line_items:
                        try:
                            logger.info(f"Post-commit: Checking price adjustments for edited item: {line_item.description} (${line_item.price})")
                            
                            # Check if CURRENT user can benefit from existing promotions
                            from .utils import check_current_user_for_price_adjustments
                            current_user_alerts = check_current_user_for_price_adjustments(line_item, receipt)
                            price_adjustments_created += current_user_alerts
                                
                        except Exception as e:
                            logger.error(f"Error checking price adjustments for {line_item.description}: {str(e)}")
                
                # Schedule price adjustment checks to run after transaction commits
                transaction.on_commit(check_price_adjustments_after_commit)
            else:
                logger.info("Skipping automatic calculations - accepting manual edits as-is")
                
                # FORCE manual values to stick by resetting them after any automatic calculations
                logger.info("FORCING manual values to override any automatic calculations")
                receipt.subtotal = Decimal(str(data.get('subtotal', receipt.subtotal)))
                receipt.tax = Decimal(str(data.get('tax', receipt.tax)))
                receipt.total = Decimal(str(data.get('total', receipt.total)))
                receipt.instant_savings = Decimal(str(data.get('instant_savings', '0.00'))) if data.get('instant_savings') else None
                receipt.save()
                logger.info(f"After FORCING manual values: subtotal={receipt.subtotal}, tax={receipt.tax}, total={receipt.total}, instant_savings={receipt.instant_savings}")
        
        # Refresh receipt from database to get final values
        receipt.refresh_from_db()
        logger.info(f"Final receipt values before response: subtotal={receipt.subtotal}, tax={receipt.tax}, total={receipt.total}, instant_savings={receipt.instant_savings}")
        
        return JsonResponse({
            'message': 'Receipt updated successfully',
            'accept_manual_edits': accept_manual_edits,
            'price_adjustments_created': price_adjustments_created,
            'receipt': {
                'transaction_number': receipt.transaction_number,
                'store_location': receipt.store_location,
                'store_number': receipt.store_number,
                'transaction_date': receipt.transaction_date.isoformat(),
                'subtotal': str(receipt.subtotal),
                'tax': str(receipt.tax),
                'total': str(receipt.total),
                'instant_savings': str(receipt.instant_savings) if receipt.instant_savings else None,
                'items': [{
                    'id': item.id,
                    'item_code': item.item_code,
                    'description': item.description,
                    'price': str(item.price),
                    'quantity': item.quantity,
                    'total_price': str(item.total_price),
                    'is_taxable': item.is_taxable,
                    'on_sale': item.on_sale,
                    'instant_savings': str(item.instant_savings) if item.instant_savings else None,
                    'original_price': str(item.original_price) if item.original_price else None,
                    'original_total_price': str(item.original_total_price) if item.original_total_price else None
                } for item in receipt.items.all()]
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating receipt: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics(request):
    """Get analytics summary for the dashboard."""
    receipts = Receipt.objects.filter(user=request.user).prefetch_related('items')
    
    # Calculate totals
    total_spent = receipts.aggregate(
        total=Sum('total', default=Decimal('0.00'))
    )['total']
    
    instant_savings = receipts.aggregate(
        savings=Sum('instant_savings', default=Decimal('0.00'))
    )['savings']
    
    total_receipts = receipts.count()
    
    # Calculate total items by summing quantities from line items
    total_items = 0
    for receipt in receipts:
        total_items += sum(item.quantity for item in receipt.items.all())
    
    # Calculate average receipt total
    average_receipt = receipts.aggregate(
        avg=Avg('total', default=Decimal('0.00'))
    )['avg']
    
    # Get spending by month for the last 12 months
    spending_by_month = {}
    monthly_spending = receipts.annotate(
        month=TruncMonth('transaction_date')
    ).values('month').annotate(
        total=Sum('total'),
        count=Count('id')
    ).order_by('-month')[:12]
    
    for spending in monthly_spending:
        month_key = spending['month'].strftime('%Y-%m')
        spending_by_month[month_key] = {
            'total': str(spending['total']),
            'count': spending['count']
        }
    
    return JsonResponse({
        'total_spent': str(total_spent),
        'instant_savings': str(instant_savings),
        'total_receipts': total_receipts,
        'total_items': total_items,
        'average_receipt_total': str(average_receipt),
        'spending_by_month': spending_by_month,
    })

@login_required
def debug_alerts(request):
    """Debug endpoint to check price adjustment alerts."""
    try:
        from .models import PriceAdjustmentAlert
        
        # Get all alerts for the user
        all_alerts = PriceAdjustmentAlert.objects.filter(user=request.user)
        active_alerts = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            is_active=True,
            is_dismissed=False
        )
        
        debug_data = {
            'user': request.user.username,
            'total_alerts': all_alerts.count(),
            'active_alerts': active_alerts.count(),
            'alerts': []
        }
        
        for alert in all_alerts:
            debug_data['alerts'].append({
                'item_description': alert.item_description,
                'original_price': str(alert.original_price),
                'lower_price': str(alert.lower_price),
                'price_difference': str(alert.price_difference),
                'purchase_date': alert.purchase_date.isoformat(),
                'days_remaining': alert.days_remaining,
                'is_active': alert.is_active,
                'is_dismissed': alert.is_dismissed,
                'data_source': alert.data_source,
                'is_expired': alert.is_expired
            })
        
        return JsonResponse(debug_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def reactivate_alerts(request):
    """Reactivate alerts that should be active under the updated logic."""
    try:
        from .models import PriceAdjustmentAlert
        
        # Get all alerts for the user that are currently inactive but not dismissed
        inactive_alerts = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            is_active=False,
            is_dismissed=False
        )
        
        reactivated_count = 0
        for alert in inactive_alerts:
            # Check if it should be active under the new logic
            if not alert.is_expired:
                alert.is_active = True
                alert.save()
                reactivated_count += 1
        
        return JsonResponse({
            'reactivated_count': reactivated_count,
            'message': f'Reactivated {reactivated_count} alerts'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_current_sales(request):
    """Get current sales/promotions from official weekly flyers."""
    try:
        from .models import OfficialSaleItem, CostcoPromotion
        from datetime import date, datetime
        from django.utils import timezone
        
        # Get currently active promotions based on today's date
        current_date = date.today()
        logger.info(f"Fetching current sales for date: {current_date}")
        
        active_promotions = CostcoPromotion.objects.filter(
            sale_start_date__lte=current_date,
            sale_end_date__gte=current_date,
            is_processed=True
        ).order_by('-sale_start_date')
        
        logger.info(f"Found {active_promotions.count()} active promotions")
        
        # Get all sale items from active promotions
        current_sales = OfficialSaleItem.objects.filter(
            promotion__in=active_promotions
        ).select_related('promotion').order_by('promotion__sale_start_date', 'description')
        
        # Format the data for frontend
        sales_data = []
        for sale_item in current_sales:
            # Calculate savings
            savings = None
            if sale_item.sale_type == 'discount_only':
                savings = sale_item.instant_rebate
            elif sale_item.regular_price and sale_item.sale_price:
                savings = sale_item.regular_price - sale_item.sale_price
            elif sale_item.instant_rebate:
                savings = sale_item.instant_rebate
            
            # Calculate days remaining
            days_remaining = (sale_item.promotion.sale_end_date - current_date).days
            
            sales_data.append({
                'id': sale_item.id,
                'item_code': sale_item.item_code,
                'description': sale_item.description,
                'regular_price': float(sale_item.regular_price) if sale_item.regular_price else None,
                'sale_price': float(sale_item.sale_price) if sale_item.sale_price else None,
                'instant_rebate': float(sale_item.instant_rebate) if sale_item.instant_rebate else None,
                'savings': float(savings) if savings else None,
                'sale_type': sale_item.sale_type,
                'promotion': {
                    'title': sale_item.promotion.title,
                    'sale_start_date': sale_item.promotion.sale_start_date.isoformat(),
                    'sale_end_date': sale_item.promotion.sale_end_date.isoformat(),
                    'days_remaining': days_remaining
                }
            })
        
        # Log summary for debugging
        logger.info(f"Returning {len(sales_data)} sale items from {active_promotions.count()} active promotions")
        
        return JsonResponse({
            'sales': sales_data,
            'total_count': len(sales_data),
            'current_date': current_date.isoformat(),
            'last_updated': timezone.now().isoformat(),
            'active_promotions': [
                {
                    'title': promo.title,
                    'sale_start_date': promo.sale_start_date.isoformat(),
                    'sale_end_date': promo.sale_end_date.isoformat(),
                    'items_count': promo.sale_items.count()
                }
                for promo in active_promotions
            ]
        })
        
    except Exception as e:
        logger.error(f"Error fetching current sales: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ReceiptUpdateAPIView(APIView):
    """
    Class-based API view for handling receipt PATCH updates.
    """
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, transaction_number):
        """Handle PATCH requests to update receipt data."""
        try:
            # Get the receipt for the authenticated user
            receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=request.user)
            
            # Check if user wants to accept manual edits without recalculation
            accept_manual_edits = request.data.get('accept_manual_edits', False)
            logger.info(f"Class-based receipt update for {transaction_number}: accept_manual_edits={accept_manual_edits}")
            
            # Use the serializer to validate and update the data
            serializer = ReceiptSerializer(receipt, data=request.data, partial=True)
            
            if serializer.is_valid():
                # Save the updated receipt
                updated_receipt = serializer.save()
                
                # Only update price database and check for price adjustments if not accepting manual edits
                if not accept_manual_edits:
                    logger.info("Performing automatic calculations and price database updates")
                    self._update_price_database_and_check_adjustments(updated_receipt, request.data)
                else:
                    logger.info("Skipping automatic calculations - accepting manual edits as-is")
                
                # Return the updated receipt data with manual edits flag
                response_data = serializer.data
                response_data['accept_manual_edits'] = accept_manual_edits
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                logger.error(f"Receipt update validation errors: {serializer.errors}")
                return Response({
                    'error': 'Validation failed',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error updating receipt {transaction_number}: {str(e)}")
            return Response({
                'error': f'Failed to update receipt: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _update_price_database_and_check_adjustments(self, receipt, request_data):
        """Update price database and check for price adjustments."""
        try:
            # Update price database
            update_price_database({
                'transaction_number': receipt.transaction_number,
                'store_location': receipt.store_location,
                'store_number': receipt.store_number,
                'transaction_date': receipt.transaction_date,
                'items': request_data.get('items', []),
                'subtotal': receipt.subtotal,
                'tax': receipt.tax,
                'total': receipt.total
            }, user=receipt.user)
            
            # Check for price adjustments
            from .utils import check_current_user_for_price_adjustments
            for item in receipt.items.all():
                try:
                    check_current_user_for_price_adjustments(item, receipt)
                except Exception as e:
                    logger.error(f"Error checking price adjustments for {item.description}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error updating price database: {str(e)}")

# Subscription API Views
import stripe
from django.conf import settings
from datetime import datetime

# Note: Stripe API key is configured in each function to avoid module-level initialization issues

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_subscription_status(request):
    """Get user's current subscription status."""
    try:
        from .models import UserSubscription
        
        try:
            subscription = UserSubscription.objects.get(user=request.user)
            return Response({
                'has_subscription': True,
                'status': subscription.status,
                'is_active': subscription.is_active,
                'current_period_end': subscription.current_period_end,
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'days_until_renewal': subscription.days_until_renewal,
                'product': {
                    'name': subscription.product.name,
                    'price': str(subscription.product.price),
                    'billing_interval': subscription.product.billing_interval,
                }
            })
        except UserSubscription.DoesNotExist:
            return Response({
                'has_subscription': False,
                'status': None,
                'is_active': False,
            })
    except Exception as e:
        logger.error(f"Error getting subscription status: {str(e)}")
        return Response(
            {'error': 'Failed to get subscription status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_subscription_products(request):
    """Get available subscription products."""
    try:
        from .models import SubscriptionProduct
        
        products = SubscriptionProduct.objects.filter(is_active=True)
        product_data = []
        
        for product in products:
            product_data.append({
                'id': product.id,
                'stripe_price_id': product.stripe_price_id,
                'name': product.name,
                'description': product.description,
                'price': str(product.price),
                'currency': product.currency,
                'billing_interval': product.billing_interval,
            })
        
        return Response({'products': product_data})
    except Exception as e:
        logger.error(f"Error getting subscription products: {str(e)}")
        return Response(
            {'error': 'Failed to get subscription products'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_subscription_create(request):
    """Create a new subscription."""
    try:
        from .models import SubscriptionProduct, UserSubscription
        
        # Configure Stripe API key
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        
        product_id = request.data.get('product_id')
        payment_method_id = request.data.get('payment_method_id')
        
        if not product_id or not payment_method_id:
            return Response(
                {'error': 'product_id and payment_method_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the product
        try:
            product = SubscriptionProduct.objects.get(id=product_id, is_active=True)
        except SubscriptionProduct.DoesNotExist:
            return Response(
                {'error': 'Invalid product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user already has a subscription
        if UserSubscription.objects.filter(user=request.user).exists():
            return Response(
                {'error': 'User already has an active subscription'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or get Stripe customer
        try:
            customer = stripe.Customer.create(
                email=request.user.email,
                name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                metadata={'user_id': request.user.id}
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation error: {str(e)}")
            return Response(
                {'error': 'Failed to create customer'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Attach payment method to customer
        try:
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer.id,
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer.id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
        except stripe.error.StripeError as e:
            logger.error(f"Payment method attachment error: {str(e)}")
            return Response(
                {'error': 'Failed to attach payment method'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Create subscription
        try:
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': product.stripe_price_id}],
                payment_behavior='default_incomplete',
                payment_settings={'save_default_payment_method': 'on_subscription'},
                expand=['latest_invoice.payment_intent'],
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription creation error: {str(e)}")
            return Response(
                {'error': 'Failed to create subscription'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Create UserSubscription record
        user_subscription = UserSubscription.objects.create(
            user=request.user,
            product=product,
            stripe_subscription_id=subscription.id,
            stripe_customer_id=customer.id,
            status=subscription.status,
            current_period_start=datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
        )
        
        return Response({
            'subscription_id': subscription.id,
            'client_secret': subscription.latest_invoice.payment_intent.client_secret,
            'status': subscription.status,
        })
    
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        return Response(
            {'error': 'Failed to create subscription'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_subscription_cancel(request):
    """Cancel user's subscription."""
    try:
        from .models import UserSubscription
        
        # Configure Stripe API key
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        
        try:
            user_subscription = UserSubscription.objects.get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response(
                {'error': 'No active subscription found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Cancel at period end by default
        cancel_immediately = request.data.get('cancel_immediately', False)
        
        try:
            if cancel_immediately:
                # Cancel immediately
                stripe.Subscription.delete(user_subscription.stripe_subscription_id)
                user_subscription.status = 'canceled'
                user_subscription.canceled_at = timezone.now()
                user_subscription.cancel_at_period_end = True
            else:
                # Cancel at period end
                stripe.Subscription.modify(
                    user_subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                user_subscription.cancel_at_period_end = True
            
            user_subscription.save()
            
            return Response({
                'message': 'Subscription canceled successfully',
                'cancel_at_period_end': user_subscription.cancel_at_period_end,
                'current_period_end': user_subscription.current_period_end,
            })
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe cancellation error: {str(e)}")
            return Response(
                {'error': 'Failed to cancel subscription'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    except Exception as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        return Response(
            {'error': 'Failed to cancel subscription'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_subscription_update(request):
    """Update user's subscription (reactivate canceled subscription)."""
    try:
        from .models import UserSubscription
        
        # Configure Stripe API key
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        
        try:
            user_subscription = UserSubscription.objects.get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response(
                {'error': 'No subscription found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow reactivation of subscriptions that are set to cancel at period end
        if not user_subscription.cancel_at_period_end:
            return Response(
                {'error': 'Subscription is not set to cancel'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Reactivate subscription
            stripe.Subscription.modify(
                user_subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            user_subscription.cancel_at_period_end = False
            user_subscription.save()
            
            return Response({
                'message': 'Subscription reactivated successfully',
                'cancel_at_period_end': user_subscription.cancel_at_period_end,
            })
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe update error: {str(e)}")
            return Response(
                {'error': 'Failed to update subscription'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    except Exception as e:
        logger.error(f"Error updating subscription: {str(e)}")
        return Response(
            {'error': 'Failed to update subscription'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_subscription_create_payment_intent(request):
    """Create a payment intent for one-time payments or setup intents."""
    try:
        from .models import UserSubscription
        
        # Configure Stripe API key
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        
        amount = request.data.get('amount')  # Amount in cents
        currency = request.data.get('currency', 'usd')
        
        if not amount:
            return Response(
                {'error': 'amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create customer
        try:
            user_subscription = UserSubscription.objects.get(user=request.user)
            customer_id = user_subscription.stripe_customer_id
        except UserSubscription.DoesNotExist:
            # Create new customer if user doesn't have a subscription
            try:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                    metadata={'user_id': request.user.id}
                )
                customer_id = customer.id
            except stripe.error.StripeError as e:
                logger.error(f"Stripe customer creation error: {str(e)}")
                return Response(
                    {'error': 'Failed to create customer'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        try:
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount),
                currency=currency,
                customer=customer_id,
                metadata={'user_id': request.user.id}
            )
            
            return Response({
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
            })
        
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation error: {str(e)}")
            return Response(
                {'error': 'Failed to create payment intent'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    except Exception as e:
        logger.error(f"Error creating payment intent: {str(e)}")
        return Response(
            {'error': 'Failed to create payment intent'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@csrf_exempt
@api_view(['POST'])
def api_subscription_webhook(request):
    """Handle Stripe webhook events."""
    try:
        from .models import UserSubscription, SubscriptionEvent
        
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        
        if not endpoint_secret:
            logger.warning("Stripe webhook secret not configured")
            return Response({'error': 'Webhook not configured'}, status=400)
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            logger.error("Invalid payload in webhook")
            return Response({'error': 'Invalid payload'}, status=400)
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature in webhook")
            return Response({'error': 'Invalid signature'}, status=400)
        
        # Store the event
        try:
            event_record = SubscriptionEvent.objects.create(
                stripe_event_id=event['id'],
                event_type=event['type'],
                event_data=event['data']
            )
        except Exception as e:
            logger.error(f"Error storing webhook event: {str(e)}")
            # Continue processing even if we can't store the event
        
        # Handle the event
        if event['type'] == 'customer.subscription.created':
            subscription_data = event['data']['object']
            # Update UserSubscription if it exists
            try:
                user_subscription = UserSubscription.objects.get(
                    stripe_subscription_id=subscription_data['id']
                )
                user_subscription.status = subscription_data['status']
                user_subscription.current_period_start = datetime.fromtimestamp(
                    subscription_data['current_period_start'], tz=timezone.utc
                )
                user_subscription.current_period_end = datetime.fromtimestamp(
                    subscription_data['current_period_end'], tz=timezone.utc
                )
                user_subscription.save()
                
                if 'event_record' in locals():
                    event_record.subscription = user_subscription
                    event_record.processed = True
                    event_record.save()
            except UserSubscription.DoesNotExist:
                logger.warning(f"UserSubscription not found for Stripe subscription {subscription_data['id']}")
        
        elif event['type'] == 'customer.subscription.updated':
            subscription_data = event['data']['object']
            try:
                user_subscription = UserSubscription.objects.get(
                    stripe_subscription_id=subscription_data['id']
                )
                user_subscription.status = subscription_data['status']
                user_subscription.current_period_start = datetime.fromtimestamp(
                    subscription_data['current_period_start'], tz=timezone.utc
                )
                user_subscription.current_period_end = datetime.fromtimestamp(
                    subscription_data['current_period_end'], tz=timezone.utc
                )
                user_subscription.cancel_at_period_end = subscription_data.get('cancel_at_period_end', False)
                user_subscription.save()
                
                if 'event_record' in locals():
                    event_record.subscription = user_subscription
                    event_record.processed = True
                    event_record.save()
            except UserSubscription.DoesNotExist:
                logger.warning(f"UserSubscription not found for Stripe subscription {subscription_data['id']}")
        
        elif event['type'] == 'customer.subscription.deleted':
            subscription_data = event['data']['object']
            try:
                user_subscription = UserSubscription.objects.get(
                    stripe_subscription_id=subscription_data['id']
                )
                user_subscription.status = 'canceled'
                user_subscription.canceled_at = timezone.now()
                user_subscription.save()
                
                if 'event_record' in locals():
                    event_record.subscription = user_subscription
                    event_record.processed = True
                    event_record.save()
            except UserSubscription.DoesNotExist:
                logger.warning(f"UserSubscription not found for Stripe subscription {subscription_data['id']}")
        
        elif event['type'] == 'invoice.payment_succeeded':
            # Handle successful payment
            invoice_data = event['data']['object']
            subscription_id = invoice_data.get('subscription')
            if subscription_id:
                try:
                    user_subscription = UserSubscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    # Update subscription status to active if it was incomplete
                    if user_subscription.status in ['incomplete', 'past_due']:
                        user_subscription.status = 'active'
                        user_subscription.save()
                        
                    if 'event_record' in locals():
                        event_record.subscription = user_subscription
                        event_record.processed = True
                        event_record.save()
                except UserSubscription.DoesNotExist:
                    logger.warning(f"UserSubscription not found for Stripe subscription {subscription_id}")
        
        elif event['type'] == 'invoice.payment_failed':
            # Handle failed payment
            invoice_data = event['data']['object']
            subscription_id = invoice_data.get('subscription')
            if subscription_id:
                try:
                    user_subscription = UserSubscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    user_subscription.status = 'past_due'
                    user_subscription.save()
                    
                    if 'event_record' in locals():
                        event_record.subscription = user_subscription
                        event_record.processed = True
                        event_record.save()
                except UserSubscription.DoesNotExist:
                    logger.warning(f"UserSubscription not found for Stripe subscription {subscription_id}")
        
        logger.info(f"Handled webhook event: {event['type']}")
        return Response({'status': 'success'})
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return Response({'error': 'Webhook processing failed'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_debug_stripe_config(request):
    """Debug endpoint to check Stripe configuration."""
    import os
    from django.conf import settings
    
    stripe_secret_from_env = os.getenv('STRIPE_SECRET_KEY', '')
    stripe_secret_from_settings = getattr(settings, 'STRIPE_SECRET_KEY', '')
    
    return Response({
        'env_var_exists': bool(stripe_secret_from_env),
        'env_var_starts_with': stripe_secret_from_env[:8] if stripe_secret_from_env else 'empty',
        'settings_exists': bool(stripe_secret_from_settings),
        'settings_starts_with': stripe_secret_from_settings[:8] if stripe_secret_from_settings else 'empty',
        'debug_mode': settings.DEBUG,
    })


@csrf_exempt
@api_view(['GET', 'POST'])  
def api_debug_auth_test(request):
    """Debug endpoint to test authentication without strict permissions."""
    return Response({
        'method': request.method,
        'user_authenticated': request.user.is_authenticated,
        'user_id': request.user.id if request.user.is_authenticated else None,
        'username': request.user.username if request.user.is_authenticated else None,
        'timestamp': timezone.now().isoformat(),
        'csrf_exempt': True,
        'message': 'This endpoint bypasses CSRF and permissions for testing'
    })

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_create_checkout_session(request):
    """Create a Stripe checkout session for subscription."""
    
    try:
        from .models import SubscriptionProduct
        import stripe
        from django.conf import settings
        
        # Configure Stripe API key
        stripe_secret_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        stripe.api_key = stripe_secret_key
        
        # Debug logging
        logger.info(f"STRIPE_SECRET_KEY from settings: {stripe_secret_key[:8]}..." if stripe_secret_key else "STRIPE_SECRET_KEY is empty")
        logger.info(f"Stripe API key configured: {bool(stripe.api_key)}")
        
        # Get the product/price ID from request
        price_id = request.data.get('price_id')
        product_id = request.data.get('product_id')
        
        if not price_id:
            return Response(
                {'error': 'price_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine success and cancel URLs
        success_url = f"{request.scheme}://{request.get_host()}/subscription?success=true"
        cancel_url = f"{request.scheme}://{request.get_host()}/subscription?canceled=true"
        
        # Create checkout session
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=request.user.email,
                client_reference_id=str(request.user.id),
                metadata={
                    'user_id': request.user.id,
                    'product_id': product_id,
                },
                allow_promotion_codes=True,
                billing_address_collection='auto',
            )
            
            return Response({
                'checkout_url': checkout_session.url,
                'session_id': checkout_session.id
            })
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout session creation error: {str(e)}")
            return Response(
                {'error': f'Failed to create checkout session: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except Exception as e:
        logger.error(f"Checkout session creation error: {str(e)}")
        return Response(
            {'error': 'Failed to create checkout session'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
