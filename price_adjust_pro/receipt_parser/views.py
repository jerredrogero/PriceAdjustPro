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
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
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
    CostcoWarehouse, PriceAdjustmentAlert, OfficialSaleItem, CostcoPromotion,
    EmailVerificationToken, UserProfile
)
from .utils import (
    process_receipt_pdf, extract_text_from_pdf, parse_receipt,
    update_price_database, process_receipt_image, process_receipt_file
)
from .serializers import ReceiptSerializer
from receipt_parser.notifications.auth import get_request_user_via_bearer_session

logger = logging.getLogger(__name__)

def _api_user_or_401(request):
    """
    API auth bridge:
    - Cookie session (request.user.is_authenticated)
    - OR Authorization: Bearer <django_session_key> (sessionid)
    """
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    if user is None:
        user = get_request_user_via_bearer_session(request)
    if user is None:
        # WARNING level so this shows up in production logs without extra config.
        logger.warning(
            "API auth required: path=%s ua=%s has_auth=%s cookies=%s",
            getattr(request, "path", ""),
            (request.META.get("HTTP_USER_AGENT", "") or "")[:120],
            bool(request.META.get("HTTP_AUTHORIZATION")),
            ",".join(sorted(list(request.COOKIES.keys())))[:200],
        )
        return None, JsonResponse({"error": "Authentication required"}, status=401)
    return user, None

def user_has_paid_account(user):
    """Check if user has a paid account using the simple account type system."""
    try:
        from .models import UserProfile
        profile = UserProfile.objects.get(user=user)
        return profile.is_paid_account
    except UserProfile.DoesNotExist:
        # If no profile exists, create one with default free account
        UserProfile.objects.create(user=user, account_type='free')
        return False

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
                    created_line_items = []
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
                                created_line_items.append(line_item)
                                # Check if current user can benefit from existing promotions
                                from .utils import check_current_user_for_price_adjustments
                                check_current_user_for_price_adjustments(line_item, existing_receipt)
                            except Exception as e:
                                logger.error(f"Line item error: {str(e)}")
                    
                    # Calculate and update receipt-level instant_savings from line items to avoid double counting
                    calculated_instant_savings = sum(item.instant_savings or Decimal('0.00') for item in created_line_items)
                    if calculated_instant_savings > 0:
                        existing_receipt.instant_savings = calculated_instant_savings
                        existing_receipt.save()
                        logger.info(f"Updated existing receipt instant_savings to: {existing_receipt.instant_savings}")
                    
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
                created_line_items = []
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
                            created_line_items.append(line_item)
                            # Check if current user can benefit from existing promotions
                            from .utils import check_current_user_for_price_adjustments
                            check_current_user_for_price_adjustments(line_item, receipt)
                        except Exception as e:
                            logger.error(f"Line item error: {str(e)}")
                            continue
                
                # Calculate and update receipt-level instant_savings from line items to avoid double counting
                calculated_instant_savings = sum(item.instant_savings or Decimal('0.00') for item in created_line_items)
                if calculated_instant_savings > 0:
                    receipt.instant_savings = calculated_instant_savings
                    receipt.save()
                    logger.info(f"Updated new receipt instant_savings to: {receipt.instant_savings}")
                
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
def api_receipt_list(request):
    user, err = _api_user_or_401(request)
    if err is not None:
        return err
    if request.method == 'GET':
        try:
            # Get all receipts for the user, ordered by date
            receipts = Receipt.objects.filter(user=user).order_by('-transaction_date').prefetch_related('items')
            
            # Debug logging
            logger.info(f"Found {receipts.count()} receipts for user {user.email}")
            
            # Get active price adjustments count
            adjustments_count = PriceAdjustmentAlert.objects.filter(
                user=user,
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
                        # price is the final paid amount (after discounts)
                        'price': str(item.price),
                        'final_price': str(item.price),
                        'price_already_discounted': True if item.instant_savings else False,
                        # original_price reflects price before discounts when known
                        'display_original_price': str(item.original_price) if item.original_price else None,
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

def api_receipt_detail(request, transaction_number):
    user, err = _api_user_or_401(request)
    if err is not None:
        return err
    receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=user)
    
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
                user=user,
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
    
    # Handle GET requests (existing functionality) - make discount state explicit for mobile
    items = [{
        'id': item.id,
        'item_code': item.item_code,
        'description': item.description,
        # price is the final paid amount (after discounts)
        'price': str(item.price),
        'final_price': str(item.price),
        'price_already_discounted': True if item.instant_savings else False,
        # original_price reflects price before discounts when known
        'display_original_price': str(item.original_price) if item.original_price else None,
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
def api_receipt_upload(request):
    user, err = _api_user_or_401(request)
    if err is not None:
        return err
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
        push_window_start = timezone.now()
        # Save the uploaded file
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        file_path = default_storage.save(
            f'receipts/{user.id}/{timestamp}_{receipt_file.name}',
            ContentFile(receipt_file.read())
        )
        
        # Get the full path using the storage backend
        full_path = default_storage.path(file_path)
        
        # Process the receipt using the unified function
        parsed_data = process_receipt_file(full_path, user=user)

        # Check for existing receipt
        existing_receipt = Receipt.objects.filter(
            transaction_number=parsed_data['transaction_number'],
            user=user  # Add user filter
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
            existing_receipt.user = user  # Ensure user is set
            existing_receipt.save()

            # Delete existing line items
            existing_receipt.items.all().delete()

            # Create new line items
            price_adjustments_created = 0  # Initialize counter for tracking price adjustment alerts
            for item_data in parsed_data['items']:
                line_item = LineItem.objects.create(
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

                # Re-run matching for late uploads/updates and count newly-created alerts
                try:
                    from .utils import check_current_user_for_price_adjustments
                    price_adjustments_created += check_current_user_for_price_adjustments(line_item, existing_receipt)
                except Exception as e:
                    logger.error(f"Error checking price adjustments for {line_item.description}: {str(e)}")

            receipt = existing_receipt

            # Push summary if new alerts were created
            if price_adjustments_created > 0:
                try:
                    from receipt_parser.models import PriceAdjustmentAlert
                    from receipt_parser.notifications.push import send_price_adjustment_summary_to_user
                    from decimal import Decimal as D

                    new_alerts = PriceAdjustmentAlert.objects.filter(
                        user=user,
                        created_at__gte=push_window_start,
                    ).order_by("-id")
                    total_savings = D("0.00")
                    for a in new_alerts:
                        total_savings += (a.original_price - a.lower_price)

                    latest = new_alerts.first()
                    if latest:
                        send_price_adjustment_summary_to_user(
                            user_id=user.id,
                            latest_alert_id=latest.id,
                            count=new_alerts.count(),
                            total_savings=total_savings,
                        )
                except Exception as e:
                    logger.error(f"Failed to send push summary for receipt update: {str(e)}")

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
            user=user,
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
        created_line_items = []
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
                    created_line_items.append(line_item)
                    # Check if current user can benefit from existing promotions
                    from .utils import check_current_user_for_price_adjustments
                    price_adjustments_created += check_current_user_for_price_adjustments(line_item, receipt)
                except Exception as e:
                    logger.error(f"Error creating line item: {str(e)}")
                    continue
        
        # Calculate and update receipt-level instant_savings from line items to avoid double counting
        calculated_instant_savings = sum(item.instant_savings or Decimal('0.00') for item in created_line_items)
        if calculated_instant_savings > 0:
            receipt.instant_savings = calculated_instant_savings
            receipt.save()
            logger.info(f"Updated API receipt instant_savings to: {receipt.instant_savings}")

        # Push summary if new alerts were created during receipt processing
        if price_adjustments_created > 0:
            try:
                from receipt_parser.models import PriceAdjustmentAlert
                from receipt_parser.notifications.push import send_price_adjustment_summary_to_user
                from decimal import Decimal as D

                new_alerts = PriceAdjustmentAlert.objects.filter(
                    user=user,
                    created_at__gte=push_window_start,
                ).order_by("-id")
                total_savings = D("0.00")
                for a in new_alerts:
                    total_savings += (a.original_price - a.lower_price)

                latest = new_alerts.first()
                if latest:
                    send_price_adjustment_summary_to_user(
                        user_id=user.id,
                        latest_alert_id=latest.id,
                        count=new_alerts.count(),
                        total_savings=total_savings,
                    )
            except Exception as e:
                logger.error(f"Failed to send push summary for receipt upload: {str(e)}")
        
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
def api_receipt_delete(request, transaction_number):
    user, err = _api_user_or_401(request)
    if err is not None:
        return err
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Validate transaction number
    if not transaction_number or transaction_number in ['null', 'N/A', '', 'None']:
        return JsonResponse({'error': 'Invalid transaction number'}, status=400)
    
    try:
        receipt = Receipt.objects.get(transaction_number=transaction_number, user=user)
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
            user=user,
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
        # Web form: email, password1, password2
        # iOS app: first_name, last_name, email, password
        
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        
        # Fallback to web form format
        if not password and 'password1' in data:
            password = data.get('password1')
            password2 = data.get('password2')
            if password != password2:
                return JsonResponse({'error': 'Passwords do not match'}, status=400)

        if not email or not password:
            return JsonResponse({'error': 'Email and password are required'}, status=400)
            
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Email already registered. Note: Emails are case sensitive.'}, status=400)

        # Use email as username
        username = email
        
        logger.info(f"Creating user with email: {email}")
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Auto-verify user and create profile
        try:
            from receipt_parser.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={'account_type': 'free', 'is_email_verified': True}
            )
        except Exception as e:
            logger.error(f"Error creating user profile: {str(e)}")
            class DummyProfile:
                is_paid_account = False
            profile = DummyProfile()
        
        # Log the user in since verification is disabled
        from django.contrib.auth import login
        login(request, user)
        
        # Email verification temporarily disabled
        # Still creating token in case we want to re-enable it later
        try:
            from receipt_parser.models import EmailVerificationToken
            EmailVerificationToken.create_token(user)
        except Exception:
            pass
        
        account_type = 'paid' if getattr(profile, 'is_paid_account', False) else 'free'
        
        return JsonResponse({
            'message': 'Account created successfully.',
            'email': user.email,
            'username': user.username,
            'verification_required': False,
            'verified': True,
            'sessionid': request.session.session_key,
            'user': {
                'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_email_verified': True,
            'account_type': account_type,
            'receipt_count': 0,
            'receipt_limit': 3 if account_type == 'free' else 999999,
            }
        })

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

def api_verify_email(request, token):
    """API endpoint to verify user email with token."""
    try:
        # Find the verification token
        verification_token = EmailVerificationToken.objects.filter(token=token).first()
        
        if not verification_token:
            return JsonResponse({'error': 'Invalid verification token'}, status=400)
        
        if verification_token.is_used:
            return JsonResponse({'error': 'This verification link has already been used'}, status=400)
        
        if verification_token.is_expired:
            return JsonResponse({'error': 'This verification link has expired'}, status=400)
        
        # Mark token as used
        verification_token.is_used = True
        verification_token.used_at = timezone.now()
        verification_token.save()
        
        # Mark user's email as verified and activate account
        user = verification_token.user
        user.is_active = True
        user.save()
        
        profile = user.profile
        profile.is_email_verified = True
        profile.email_verified_at = timezone.now()
        profile.save()
        
        logger.info(f"Email verified for user: {user.email}")
        
        return JsonResponse({
            'message': 'Email verified successfully! You can now log in.',
            'verified': True
        })
        
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        return JsonResponse({'error': 'An error occurred during verification'}, status=500)

@csrf_exempt
def api_verify_code(request):
    """
    API endpoint to verify user email with 6-digit code.
    Supports both web app format (email + code) and iOS app format (code only).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        email = data.get('email')
        code = data.get('code', '').strip()
        
        if not code:
            return JsonResponse({'error': 'Verification code is required'}, status=400)
        
        if len(code) != 6 or not code.isdigit():
            return JsonResponse({'error': 'Please enter a valid 6-digit code'}, status=400)
        
        # Find the verification token by code first (for iOS app - code only)
        verification_token = EmailVerificationToken.objects.filter(
            code=code,
            is_used=False
        ).first()
        
        if not verification_token:
            return JsonResponse({
                'error': 'Invalid verification code. Please check the code and try again.'
            }, status=400)
        
        if verification_token.is_expired:
            return JsonResponse({
                'error': 'This verification code has expired. Please request a new one.'
            }, status=400)
        
        user = verification_token.user
        
        # Check if already verified
        try:
            profile = user.profile
            if profile.is_email_verified:
                return JsonResponse({'error': 'Email is already verified'}, status=400)
        except:
            pass
        
        # Mark token as used
        verification_token.is_used = True
        verification_token.used_at = timezone.now()
        verification_token.save()
        
        # Mark user's email as verified and activate account
        user.is_active = True
        user.save()
        
        profile = user.profile
        profile.is_email_verified = True
        profile.email_verified_at = timezone.now()
        profile.save()
        
        logger.info(f"Email verified for user: {user.email} using code")
        
        # Get account type for iOS app response
        account_type = 'paid' if profile.is_paid_account else 'free'
        
        # Return format compatible with both web and iOS app
        return JsonResponse({
            'message': 'Email verified successfully',
            'verified': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_email_verified': True,
                'account_type': account_type,
                'receipt_count': user.receipts.count(),
                'receipt_limit': 3 if account_type == 'free' else 999999,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        return JsonResponse({'error': 'An error occurred during verification'}, status=500)

@csrf_exempt
def api_resend_verification(request):
    """API endpoint to resend verification email."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)
        
        # Find user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return JsonResponse({
                'message': 'If this email is registered, a verification link has been sent.'
            })
        
        # Check if already verified
        if user.profile.is_email_verified:
            return JsonResponse({'error': 'Email is already verified'}, status=400)
        
        # Invalidate old tokens
        EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)
        
        # Create new verification token
        verification_token = EmailVerificationToken.create_token(user)
        
        # Send verification email with new 6-digit code and link
        try:
            from django.utils.http import urlsafe_base64_encode
            from django.utils.encoding import force_bytes
            from django.urls import reverse
            from django.contrib.sites.shortcuts import get_current_site
            
            current_site = get_current_site(request)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            # Point to the React verification page instead of the Django /web/ view
            verification_link = f"{request.scheme}://{current_site.domain}/verify-email/{verification_token.token}"
            
            subject = 'Verify your PriceAdjustPro account'
            message = f"""
Hi {user.first_name or user.email},

Here's your new verification code for PriceAdjustPro:

Your verification code is:
{verification_token.code}

Alternatively, you can click the link below to verify your account:
{verification_link}

Enter the code in the app or click the link to verify your account. This code and link will expire in 30 minutes.

If you didn't request this, you can safely ignore this email.

Best regards,
The PriceAdjustPro Team
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"New verification code sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
            return JsonResponse({'error': 'Failed to send verification email'}, status=500)
        
        return JsonResponse({
            'message': 'Verification email sent. Please check your inbox.'
        })
        
    except Exception as e:
        logger.error(f"Resend verification error: {str(e)}")
        return JsonResponse({'error': 'An error occurred'}, status=500)

def verify_email(request, uidb64, token):
    """Web view to verify user email with link."""
    try:
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str
        from django.contrib.auth.models import User
        
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        token_obj = EmailVerificationToken.objects.get(user=user, token=token)
        
        if user.is_active:
            messages.info(request, "Your account is already verified. Please log in.")
            return redirect('login')
        
        if token_obj.is_valid:
            user.is_active = True
            user.save()
            
            profile = user.profile
            profile.is_email_verified = True
            profile.email_verified_at = timezone.now()
            profile.save()
            
            # Mark token as used
            token_obj.is_used = True
            token_obj.used_at = timezone.now()
            token_obj.save()
            
            messages.success(request, "Email verified successfully! You can now log in.")
            return render(request, 'receipt_parser/login.html')
        else:
            messages.error(request, "The verification link has expired. Please request a new one.")
            return redirect('login')
            
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, EmailVerificationToken.DoesNotExist):
        messages.error(request, "The verification link is invalid.")
        return redirect('login')

def register(request):
    """Web view for user registration."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Set user as inactive until verified (like in DropShipHQ)
            user.is_active = False
            user.save()
            
            # Create verification token
            verification_token = EmailVerificationToken.create_token(user)
            
            # Send verification email with 6-digit code and link
            try:
                from django.utils.http import urlsafe_base64_encode
                from django.utils.encoding import force_bytes
                from django.urls import reverse
                from django.contrib.sites.shortcuts import get_current_site
                
                current_site = get_current_site(request)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                # Point to the React verification page instead of the Django /web/ view
                verification_link = f"{request.scheme}://{current_site.domain}/verify-email/{verification_token.token}"
                
                subject = 'Verify your PriceAdjustPro account'
                message = f"""
Hi {user.email},

Thank you for signing up for PriceAdjustPro! Please verify your email address to get started.

Your verification code is:
{verification_token.code}

Alternatively, you can click the link below to verify your account:
{verification_link}

This code and link will expire in 30 minutes.

If you didn't create this account, you can safely ignore this email.

Best regards,
The PriceAdjustPro Team
                """
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                logger.info(f"Verification code sent to {user.email}")
                messages.success(request, 'Account created successfully! Please check your email for your verification code.')
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
                messages.warning(request, 'Account created, but we could not send a verification email. Please contact support.')
            
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'receipt_parser/register.html', {'form': form})

@login_required
def settings_view(request):
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
                logger.info(f"Deleting {alerts_count} price adjustment alerts for user {user.email}")
            
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
                    # Handle discount-only promotions OR promotions with only instant_rebate (no sale_price)
                    if promotion_item.sale_type == 'discount_only' or (promotion_item.instant_rebate and not promotion_item.sale_price):
                        # This is a "$X OFF" promotion or a promotion with only rebate info
                        if promotion_item.instant_rebate and item.price > promotion_item.instant_rebate:
                            final_price = item.price - promotion_item.instant_rebate
                        else:
                            continue
                    elif promotion_item.sale_price and item.price > promotion_item.sale_price:
                        # Standard promotion with sale price
                        final_price = promotion_item.sale_price
                    else:
                        # User already paid the same or less, or no valid promotion data
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
        logger.info(f"Getting price adjustments for user: {request.user.email}")
        
        # Get all active alerts for the user
        alerts = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            is_active=True,
            is_dismissed=False
        ).select_related('user')  # Add select_related to optimize queries

        # Only show alerts where the user is still within the 30-day PA window
        # (Users can only request a PA within 30 days of their purchase, even if the sale lasts longer.)
        from datetime import timedelta
        pa_cutoff = timezone.now() - timedelta(days=30)
        alerts = alerts.filter(purchase_date__gte=pa_cutoff)

        # For official promotions, also hide alerts after the promotion ends
        today = timezone.now().date()
        alerts = alerts.exclude(
            data_source="official_promo",
            official_sale_item__promotion__sale_end_date__lt=today,
        )

        logger.info(f"Found {alerts.count()} active alerts for user {request.user.email}")

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
                    'store_location': f"Costco {alert.cheaper_store_city or 'All Costco Locations'}",
                    'store_number': alert.cheaper_store_number or 'ALL',
                    'purchase_date': alert.purchase_date.isoformat(),
                    # Single window: earliest of sale end vs user's 30-day PA window
                    'days_remaining': safe_get_property(alert, 'days_remaining', 0),
                    'claim_days_remaining': safe_get_property(alert, 'claim_days_remaining', None),
                    # Keep detailed fields available for debugging / future UI if needed
                    'sale_days_remaining': safe_get_property(alert, 'sale_days_remaining', None),
                    'pa_days_remaining': safe_get_property(alert, 'pa_days_remaining', None),
                    'original_store': f"Costco {alert.original_store_city or 'Unknown'}",
                    'original_store_number': alert.original_store_number or '',
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
    """Dismiss price adjustment alerts for a specific item code (prevents them from reappearing)."""
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
        
        # Mark alerts as dismissed (this prevents them from reappearing on login)
        dismissed_count = alerts.update(is_dismissed=True)
        
        logger.info(f"Dismissed {dismissed_count} price adjustment alerts for item {item_code} for user {request.user.email}")
        
        return JsonResponse({
            'message': f'Successfully removed {dismissed_count} alert(s)',
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
def api_receipt_update(request, transaction_number):
    """Update a receipt after review."""
    user, err = _api_user_or_401(request)
    if err is not None:
        return err
    if request.method not in ['POST', 'PATCH']:
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=user)
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
            
            # Automatically calculate receipt-level instant_savings from line items to avoid double counting
            calculated_instant_savings = sum(item.instant_savings or Decimal('0.00') for item in created_line_items)
            logger.info(f"Calculated instant_savings from line items: {calculated_instant_savings}")
            
            # Update receipt's instant_savings to match sum of line items (prevents double counting)
            if calculated_instant_savings > 0:
                receipt.instant_savings = calculated_instant_savings
                receipt.save(update_fields=['instant_savings'])
                logger.info(f"Updated receipt instant_savings to: {receipt.instant_savings}")

            # Recalculate subtotal and total from line items to avoid stale totals from clients
            calculated_subtotal = sum((item.price or Decimal('0.00')) * item.quantity for item in created_line_items)
            # If the client sent tax, use it; otherwise keep the existing tax
            tax_value = Decimal(str(data.get('tax', receipt.tax)))
            receipt.subtotal = calculated_subtotal
            receipt.tax = tax_value
            receipt.total = calculated_subtotal + tax_value
            receipt.save(update_fields=['subtotal', 'tax', 'total'])
            logger.info(f"Recalculated totals: subtotal={receipt.subtotal}, tax={receipt.tax}, total={receipt.total}")
            
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_enhanced_analytics(request):
    """Get enhanced analytics with trends and categories."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import F, Q, Case, When, IntegerField
        from django.db.models.functions import TruncWeek, TruncDay
        
        receipts = Receipt.objects.filter(user=request.user, parsed_successfully=True).prefetch_related('items')
        
        # Calculate date ranges
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)
        ninety_days_ago = now - timedelta(days=90)
        one_year_ago = now - timedelta(days=365)
        
        # Current period spending (last 30 days)
        current_period = receipts.filter(transaction_date__gte=thirty_days_ago)
        current_spending = current_period.aggregate(
            total=Sum('total', default=Decimal('0.00'))
        )['total']
        current_receipts = current_period.count()
        
        # Previous period spending (30-60 days ago)
        previous_period = receipts.filter(
            transaction_date__gte=sixty_days_ago,
            transaction_date__lt=thirty_days_ago
        )
        previous_spending = previous_period.aggregate(
            total=Sum('total', default=Decimal('0.00'))
        )['total']
        previous_receipts = previous_period.count()
        
        # Calculate trends
        spending_change = float(current_spending) - float(previous_spending)
        spending_change_percent = (spending_change / float(previous_spending) * 100) if previous_spending > 0 else 0
        
        receipts_change = current_receipts - previous_receipts
        receipts_change_percent = (receipts_change / previous_receipts * 100) if previous_receipts > 0 else 0
        
        # Weekly spending trend (last 12 weeks)
        weekly_spending = receipts.filter(
            transaction_date__gte=now - timedelta(weeks=12)
        ).annotate(
            week=TruncWeek('transaction_date')
        ).values('week').annotate(
            total=Sum('total'),
            count=Count('id')
        ).order_by('week')
        
        weekly_trend = []
        for week_data in weekly_spending:
            weekly_trend.append({
                'week': week_data['week'].strftime('%Y-%m-%d'),
                'total': float(week_data['total']),
                'count': week_data['count']
            })
        
        # Category analysis (simplified categories based on item codes and descriptions)
        category_spending = {}
        
        # Get all line items for analysis
        line_items = LineItem.objects.filter(
            receipt__user=request.user,
            receipt__parsed_successfully=True
        ).select_related('receipt')
        
        # Categorize items (simplified categories)
        for item in line_items:
            category = categorize_item(item.description)
            if category not in category_spending:
                category_spending[category] = {
                    'total': Decimal('0.00'),
                    'count': 0,
                    'items': 0
                }
            category_spending[category]['total'] += item.price * item.quantity
            category_spending[category]['count'] += 1
            category_spending[category]['items'] += item.quantity
        
        # Convert to list format
        categories = []
        for category, data in category_spending.items():
            categories.append({
                'category': category,
                'total': float(data['total']),
                'count': data['count'],
                'items': data['items']
            })
        categories.sort(key=lambda x: x['total'], reverse=True)
        
        # Price adjustment savings tracking
        from .models import PriceAdjustmentAlert
        price_alerts = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            created_at__gte=one_year_ago
        )
        
        total_potential_savings = price_alerts.aggregate(
            total=Sum(F('original_price') - F('lower_price'), default=Decimal('0.00'))
        )['total']
        
        active_alerts = price_alerts.filter(is_active=True, is_dismissed=False).count()
        
        # Monthly savings opportunity
        monthly_alerts = price_alerts.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            savings=Sum(F('original_price') - F('lower_price')),
            count=Count('id')
        ).order_by('-month')[:12]
        
        savings_by_month = {}
        for alert_data in monthly_alerts:
            month_key = alert_data['month'].strftime('%Y-%m')
            savings_by_month[month_key] = {
                'savings': float(alert_data['savings']),
                'count': alert_data['count']
            }
        
        return Response({
            'trends': {
                'current_period_spending': float(current_spending),
                'previous_period_spending': float(previous_spending),
                'spending_change': spending_change,
                'spending_change_percent': round(spending_change_percent, 2),
                'current_period_receipts': current_receipts,
                'previous_period_receipts': previous_receipts,
                'receipts_change': receipts_change,
                'receipts_change_percent': round(receipts_change_percent, 2),
                'weekly_spending': weekly_trend
            },
            'categories': categories[:10],  # Top 10 categories
            'savings_tracking': {
                'total_potential_savings': float(total_potential_savings),
                'active_alerts': active_alerts,
                'savings_by_month': savings_by_month
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating enhanced analytics: {str(e)}")
        return Response(
            {'error': 'Failed to generate enhanced analytics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def categorize_item(description):
    """Categorize items based on description keywords."""
    description_lower = description.lower()
    
    # Food categories
    if any(word in description_lower for word in ['organic', 'produce', 'fruit', 'vegetable', 'banana', 'apple', 'lettuce', 'tomato']):
        return 'Fresh Produce'
    elif any(word in description_lower for word in ['meat', 'beef', 'chicken', 'pork', 'fish', 'salmon', 'turkey']):
        return 'Meat & Seafood'
    elif any(word in description_lower for word in ['milk', 'cheese', 'yogurt', 'butter', 'dairy', 'eggs']):
        return 'Dairy & Eggs'
    elif any(word in description_lower for word in ['bread', 'bakery', 'cake', 'muffin', 'bagel']):
        return 'Bakery'
    elif any(word in description_lower for word in ['frozen', 'ice cream', 'pizza']):
        return 'Frozen Foods'
    elif any(word in description_lower for word in ['cereal', 'pasta', 'rice', 'beans', 'canned']):
        return 'Pantry & Dry Goods'
    elif any(word in description_lower for word in ['snack', 'chips', 'candy', 'chocolate', 'cookie']):
        return 'Snacks & Candy'
    elif any(word in description_lower for word in ['beverage', 'soda', 'juice', 'water', 'coffee', 'tea']):
        return 'Beverages'
    
    # Non-food categories
    elif any(word in description_lower for word in ['shampoo', 'soap', 'toothpaste', 'deodorant', 'lotion', 'beauty']):
        return 'Health & Beauty'
    elif any(word in description_lower for word in ['vitamin', 'supplement', 'medicine', 'pharmacy']):
        return 'Health & Pharmacy'
    elif any(word in description_lower for word in ['detergent', 'paper towel', 'toilet paper', 'cleaning']):
        return 'Household Essentials'
    elif any(word in description_lower for word in ['clothing', 'shirt', 'pants', 'jacket', 'apparel']):
        return 'Clothing & Apparel'
    elif any(word in description_lower for word in ['electronics', 'tv', 'computer', 'phone', 'tablet']):
        return 'Electronics'
    elif any(word in description_lower for word in ['book', 'toy', 'game', 'sports', 'outdoor']):
        return 'Entertainment & Sports'
    elif any(word in description_lower for word in ['auto', 'tire', 'battery', 'oil', 'car']):
        return 'Automotive'
    elif any(word in description_lower for word in ['home', 'furniture', 'decor', 'kitchen', 'appliance']):
        return 'Home & Garden'
    
    # Default category
    return 'Other'

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
            'user': request.user.email,
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

# On-Sale API View
@api_view(['GET'])
def api_on_sale(request):
    """Get current on-sale items from active promotions (Premium only)."""
    # Check if user is authenticated and premium
    user, err = _api_user_or_401(request)
    if err:
        return err
    
    if not user_has_paid_account(user):
        return JsonResponse({
            'error': 'Premium feature',
            'details': 'The On Sale directory is exclusive to PriceAdjustPro Premium members.',
            'sales': [],
            'total_count': 0,
            'active_promotions': []
        }, status=403)

    try:
        from django.db.models import Q, Count
        from .serializers import OnSaleItemSerializer, PromotionSerializer, OnSaleResponseSerializer
        
        # Get current date
        today = timezone.now().date()
        
        # Get active promotions (current or future, not ended)
        active_promotions = CostcoPromotion.objects.filter(
            is_processed=True,
            sale_end_date__gte=today
        ).annotate(
            items_count=Count('sale_items')
        ).order_by('-sale_start_date')
        
        # Get all sale items from active promotions
        on_sale_items = OfficialSaleItem.objects.select_related('promotion').filter(
            promotion__in=active_promotions
        ).order_by('promotion__sale_start_date', 'item_code')
        
        # Serialize the data
        sales_serializer = OnSaleItemSerializer(on_sale_items, many=True)
        promotions_serializer = PromotionSerializer(active_promotions, many=True)
        
        # Build response data
        response_data = {
            'sales': sales_serializer.data,
            'total_count': on_sale_items.count(),
            'active_promotions': promotions_serializer.data,
            'current_date': today,
            'last_updated': timezone.now()
        }
        
        # Add CORS headers for iOS app
        response = Response(response_data)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in api_on_sale: {str(e)}")
        error_response = Response(
            {
                'error': 'Failed to fetch on-sale items',
                'sales': [],
                'total_count': 0,
                'active_promotions': [],
                'current_date': timezone.now().date(),
                'last_updated': timezone.now()
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        # Add CORS headers even for error responses
        error_response['Access-Control-Allow-Origin'] = '*'
        error_response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        error_response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        
        return error_response


# Subscription API Views
import stripe
from django.conf import settings
from datetime import datetime

# Note: Stripe API key is configured in each function to avoid module-level initialization issues

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_subscription_status(request):
    """Get user's current account status using simple account type system."""
    try:
        from .models import UserProfile, UserSubscription
        from django.conf import settings
        import stripe
        
        # Get or create user profile
        try:
            profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user, account_type='free')
        
        # If user just returned from a successful checkout but isn't premium yet,
        # try to verify with Stripe directly since we don't have a webhook.
        success_param = request.GET.get('success') == 'true'
        if success_param and not profile.is_premium:
            logger.info(f"User {request.user.email} returned with success=true. Verifying with Stripe...")
            stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
            
            # Look for recent checkout sessions for this customer
            try:
                # Use customer email to find sessions
                sessions = stripe.checkout.Session.list(
                    customer_details={'email': request.user.email},
                    limit=10
                )
                
                # If no sessions found by email, try searching by client_reference_id
                if not sessions.data:
                    logger.info(f"No sessions found for email {request.user.email}, trying client_reference_id {request.user.id}")
                    sessions = stripe.checkout.Session.list(limit=50)
                
                found_session = False
                for session in sessions.data:
                    # Match by email OR client_reference_id
                    is_user_session = (
                        (session.get('customer_details') and session['customer_details'].get('email') == request.user.email) or
                        (session.get('client_reference_id') == str(request.user.id))
                    )
                    
                    if is_user_session and session.payment_status == 'paid' and session.status == 'complete':
                        # Found a successful session! Upgrade the user.
                        subscription_id = session.get('subscription')
                        customer_id = session.get('customer')
                        
                        logger.info(f"Found successful session {session.id} for user {request.user.email}. Sub ID: {subscription_id}")
                        
                        if subscription_id:
                            from .models import SubscriptionProduct
                            
                            # Try to get the product from session metadata or line items
                            product = None
                            product_id_from_meta = session.get('metadata', {}).get('product_id')
                            is_test_mode = getattr(settings, 'STRIPE_TEST_MODE', False)

                            if product_id_from_meta:
                                product = SubscriptionProduct.objects.filter(id=product_id_from_meta, is_test_mode=is_test_mode).first()
                            
                            if not product:
                                # Try to find by price ID from line items
                                try:
                                    line_items = stripe.checkout.Session.list_line_items(session.id, limit=1)
                                    if line_items.data:
                                        price_id = line_items.data[0].price.id
                                        product = SubscriptionProduct.objects.filter(stripe_price_id=price_id, is_test_mode=is_test_mode).first()
                                except Exception as e:
                                    logger.error(f"Error fetching line items: {str(e)}")
                            
                            if not product:
                                # Fallback to any mode if not found in current mode
                                if product_id_from_meta:
                                    product = SubscriptionProduct.objects.filter(id=product_id_from_meta).first()
                                if not product:
                                    product = SubscriptionProduct.objects.filter(is_active=True, is_test_mode=is_test_mode).first()

                            # Find or create the subscription record
                            user_sub, created = UserSubscription.objects.update_or_create(
                                user=request.user,
                                defaults={
                                    'stripe_subscription_id': subscription_id,
                                    'stripe_customer_id': customer_id or '',
                                    'status': 'active',
                                    'current_period_start': timezone.now(),
                                    'current_period_end': timezone.now() + timezone.timedelta(days=30),
                                    'product': product
                                }
                            )
                            
                            # Upgrade profile
                            profile.is_premium = True
                            profile.account_type = 'paid'
                            profile.subscription_type = 'stripe'
                            profile.save()
                            logger.info(f"Successfully upgraded user {request.user.email} via session verification")
                            found_session = True
                            break
                
                if not found_session:
                    logger.warning(f"No successful Stripe session found for user {request.user.email} after checkout")
            except Exception as stripe_err:
                logger.error(f"Error verifying Stripe session: {str(stripe_err)}")

        is_paid = profile.is_premium or profile.account_type == 'paid'
        
        # Try to get detailed subscription info if it exists
        user_sub = UserSubscription.objects.filter(user=request.user).first()
        
        return Response({
            'has_subscription': is_paid,
            'status': user_sub.status if user_sub else ('active' if is_paid else 'free'),
            'is_active': is_paid,
            'account_type': profile.account_type,
            'account_type_display': profile.get_account_type_display(),
            'current_period_end': user_sub.current_period_end.isoformat() if user_sub and user_sub.current_period_end else None,
            'cancel_at_period_end': user_sub.cancel_at_period_end if user_sub else False,
            'days_until_renewal': user_sub.days_until_renewal if user_sub else None,
            'product': {
                'name': user_sub.product.name if user_sub else ('Paid Account' if is_paid else 'Free Account'),
                'price': str(user_sub.product.price) if user_sub else ('9.99' if is_paid else '0.00'),
                'billing_interval': user_sub.product.billing_interval if user_sub else ('month' if is_paid else 'free'),
            } if is_paid else None
        })
        
    except Exception as e:
        logger.error(f"Error getting account status: {str(e)}")
        return Response(
            {'error': 'Failed to get account status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_subscription_products(request):
    """Get available subscription products."""
    try:
        from .models import SubscriptionProduct
        from django.conf import settings
        
        # Filter products based on current Stripe mode (Test vs Live)
        is_test_mode = getattr(settings, 'STRIPE_TEST_MODE', False)
        products = SubscriptionProduct.objects.filter(is_active=True, is_test_mode=is_test_mode)
        
        # If no products found in database for current mode, provide defaults
        if not products.exists():
            if is_test_mode:
                # Auto-seed test products if none exist
                products = [
                    SubscriptionProduct.objects.create(
                        stripe_product_id='prod_test_monthly',
                        stripe_price_id='price_1T4OHjCBOzePXFXgdFkskMkE',
                        name='Premium Monthly',
                        price=4.99,
                        billing_interval='month',
                        is_test_mode=True
                    ),
                    SubscriptionProduct.objects.create(
                        stripe_product_id='prod_test_yearly',
                        stripe_price_id='price_1T4OI1CBOzePXFXgm6GxGlgd',
                        name='Premium Yearly',
                        price=49.99,
                        billing_interval='year',
                        is_test_mode=True
                    )
                ]
            else:
                # For live mode, we don't auto-seed, but we can return the live IDs as a fallback
                # if they exist in the DB. If not, the admin needs to add them.
                pass

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
                name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
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
        
        # Update user profile to premium
        from .models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.is_premium = True
        profile.subscription_type = 'stripe'
        profile.account_type = 'paid'
        profile.save()
        
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
                
                # Update user profile to free
                from .models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.is_premium = False
                profile.subscription_type = 'free'
                profile.account_type = 'free'
                profile.save()
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
                    name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
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
def api_subscription_webhook(request):
    """Handle Stripe webhook events."""
    if request.method != "POST":
        return HttpResponse(status=405)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

    if not endpoint_secret:
        logger.warning("Stripe webhook secret not configured")
        return HttpResponse("Webhook secret not configured", status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret,
        )
    except ValueError:
        logger.error("Stripe webhook: invalid payload")
        return HttpResponse("Invalid payload", status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Stripe webhook: invalid signature")
        # Log the first ~200 bytes of payload and the signature header for debugging
        logger.error(f"Signature header: {sig_header}")
        logger.error(f"Payload start: {payload[:200]!r}")
        return HttpResponse("Invalid signature", status=400)
    except Exception as e:
        logger.exception(f"Stripe webhook: construct_event failed: {str(e)}")
        return HttpResponse("Webhook construction failed", status=400)

    etype = event.get("type")
    
    # Store the event
    try:
        from .models import SubscriptionEvent
        SubscriptionEvent.objects.create(
            stripe_event_id=event['id'],
            event_type=etype,
            event_data=event['data']
        )
    except Exception as e:
        logger.error(f"Error storing webhook event: {str(e)}")
        # Continue processing even if we can't store the event

    try:
        from .models import UserSubscription, User
        from datetime import datetime
        from django.utils import timezone

        if etype == 'checkout.session.completed':
            session = event['data']['object']
            client_reference_id = session.get('client_reference_id')
            subscription_id = session.get('subscription')
            customer_id = session.get('customer')
            
            logger.info(f"Processing checkout.session.completed for session {session.get('id')}")
            
            if client_reference_id and subscription_id:
                try:
                    from .models import UserSubscription, SubscriptionProduct, User
                    user = User.objects.get(id=int(client_reference_id))
                    
                    # Try to find existing pending subscription
                    user_subscription = UserSubscription.objects.filter(
                        stripe_subscription_id=f"pending_{session['id']}"
                    ).first()
                    
                    if not user_subscription:
                        # Try to get product from metadata
                        product = None
                        product_id_from_meta = session.get('metadata', {}).get('product_id')
                        if product_id_from_meta:
                            product = SubscriptionProduct.objects.filter(id=product_id_from_meta, is_test_mode=is_test_mode).first()
                        
                        if not product:
                            product = SubscriptionProduct.objects.filter(is_active=True, is_test_mode=is_test_mode).first()

                        # Fallback to user if session ID doesn't match
                        user_subscription, _ = UserSubscription.objects.get_or_create(
                            user=user,
                            defaults={
                                'stripe_subscription_id': subscription_id,
                                'stripe_customer_id': customer_id or '',
                                'status': 'active',
                                'current_period_start': timezone.now(),
                                'current_period_end': timezone.now() + timezone.timedelta(days=30),
                                'product': product
                            }
                        )
                    
                    user_subscription.stripe_subscription_id = subscription_id
                    user_subscription.stripe_customer_id = customer_id or user_subscription.stripe_customer_id
                    user_subscription.status = 'active'
                    user_subscription.save()
                    
                    # Update user profile to premium
                    from .models import UserProfile
                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.is_premium = True
                    profile.subscription_type = 'stripe'
                    profile.account_type = 'paid'
                    profile.save()
                    
                    logger.info(f"Successfully upgraded user {user.email} to premium via webhook")
                except Exception as e:
                    logger.error(f"Error processing checkout.session.completed: {str(e)}")

        elif etype == 'customer.subscription.created':
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
                user_subscription.save()

                # Update user profile to premium
                from .models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=user_subscription.user)
                profile.is_premium = True
                profile.subscription_type = 'stripe'
                profile.account_type = 'paid'
                profile.save()
            except UserSubscription.DoesNotExist:
                logger.warning(f"UserSubscription not found for Stripe subscription {subscription_data['id']}")
        
        elif etype == 'customer.subscription.updated':
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

                # Update user profile to premium if active
                if user_subscription.status == 'active':
                    from .models import UserProfile
                    profile, _ = UserProfile.objects.get_or_create(user=user_subscription.user)
                    profile.is_premium = True
                    profile.subscription_type = 'stripe'
                    profile.account_type = 'paid'
                    profile.save()
            except UserSubscription.DoesNotExist:
                logger.warning(f"UserSubscription not found for Stripe subscription {subscription_data['id']}")
        
        elif etype == 'customer.subscription.deleted':
            subscription_data = event['data']['object']
            try:
                user_subscription = UserSubscription.objects.get(
                    stripe_subscription_id=subscription_data['id']
                )
                user_subscription.status = 'canceled'
                user_subscription.canceled_at = timezone.now()
                user_subscription.save()

                # Update user profile to free
                from .models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=user_subscription.user)
                profile.is_premium = False
                profile.subscription_type = 'free'
                profile.account_type = 'free'
                profile.save()
            except UserSubscription.DoesNotExist:
                logger.warning(f"UserSubscription not found for Stripe subscription {subscription_data['id']}")
        
        elif etype == 'invoice.payment_succeeded':
            invoice_data = event['data']['object']
            subscription_id = invoice_data.get('subscription')
            if subscription_id:
                try:
                    user_subscription = UserSubscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    if user_subscription.status in ['incomplete', 'past_due']:
                        user_subscription.status = 'active'
                        user_subscription.save()

                    # Update user profile to premium
                    from .models import UserProfile
                    profile, _ = UserProfile.objects.get_or_create(user=user_subscription.user)
                    profile.is_premium = True
                    profile.subscription_type = 'stripe'
                    profile.account_type = 'paid'
                    profile.save()
                except UserSubscription.DoesNotExist:
                    logger.warning(f"UserSubscription not found for Stripe subscription {subscription_id}")
        
        elif etype == 'invoice.payment_failed':
            invoice_data = event['data']['object']
            subscription_id = invoice_data.get('subscription')
            if subscription_id:
                try:
                    user_subscription = UserSubscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    user_subscription.status = 'past_due'
                    user_subscription.save()

                    # Optionally update user profile if payment failed (e.g., if it's no longer active)
                    # For now, we keep it as is, but Stripe will eventually send customer.subscription.deleted
                except UserSubscription.DoesNotExist:
                    logger.warning(f"UserSubscription not found for Stripe subscription {subscription_id}")
        
        logger.info(f"Handled webhook event: {etype}")
        
    except Exception as e:
        logger.exception(f"Stripe webhook: processing failed for {etype}: {str(e)}")
        # Return 200 to acknowledge receipt even if processing failed
        return HttpResponse(status=200)

    return HttpResponse(status=200)


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

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication that doesn't enforce CSRF."""
    def enforce_csrf(self, request):
        return  # To not perform the csrf check previously happening

class CreateCheckoutSessionView(APIView):
    """Create a Stripe checkout session for subscription."""
    
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
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
            logger.info(f"User authenticated: {request.user.is_authenticated}, User ID: {request.user.id}")
            
            # Get the product/price ID from request
            price_id = request.data.get('price_id')
            product_id = request.data.get('product_id')
            
            if not price_id:
                return Response(
                    {'error': 'price_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Try to find the product in our DB
            from .models import SubscriptionProduct
            from django.conf import settings
            product = None
            is_test_mode = getattr(settings, 'STRIPE_TEST_MODE', False)
            
            if product_id:
                product = SubscriptionProduct.objects.filter(id=product_id, is_test_mode=is_test_mode).first()
            if not product:
                product = SubscriptionProduct.objects.filter(stripe_price_id=price_id, is_test_mode=is_test_mode).first()
            
            # Fallback to any mode if not found in current mode (to be safe)
            if not product:
                if product_id:
                    product = SubscriptionProduct.objects.filter(id=product_id).first()
                if not product:
                    product = SubscriptionProduct.objects.filter(stripe_price_id=price_id).first()
            
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
                        'product_id': product.id if product else product_id,
                    },
                    allow_promotion_codes=True,
                    billing_address_collection='auto',
                )
                
                logger.info(f"Successfully created checkout session: {checkout_session.id}")

                # Create or update UserSubscription record
                if product:
                    from .models import UserSubscription
                    try:
                        # We don't have the subscription ID yet, but we can create the record
                        # It will be updated by the webhook once the payment is successful
                        user_subscription, created = UserSubscription.objects.get_or_create(
                            user=request.user,
                            defaults={
                                'product': product,
                                'stripe_subscription_id': f"pending_{checkout_session.id}",
                                'stripe_customer_id': '',
                                'status': 'incomplete',
                                'current_period_start': timezone.now(),
                                'current_period_end': timezone.now() + timezone.timedelta(days=30),
                            }
                        )
                        if not created:
                            user_subscription.product = product
                            user_subscription.status = 'incomplete'
                            user_subscription.save()
                    except Exception as e:
                        logger.error(f"Error creating pending UserSubscription: {str(e)}")
                else:
                    logger.warning(f"Could not find SubscriptionProduct for price_id {price_id}. Pending record not created.")
                
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

# Create an instance of the view that bypasses CSRF
api_create_checkout_session = method_decorator(csrf_exempt, name='dispatch')(CreateCheckoutSessionView).as_view()


# ============================================================================
# Apple In-App Purchase Subscription Endpoints
# ============================================================================

def validate_apple_receipt(receipt_data, shared_secret):
    """
    Validate receipt with Apple's servers.
    
    Strategy:
    1. Try production server first
    2. If status code is 21007 (sandbox receipt sent to production), retry with sandbox
    3. If status code is 21008 (production receipt sent to sandbox), retry with production
    
    Returns:
        tuple: (is_valid, response_data, is_sandbox)
    """
    import requests
    from django.conf import settings
    
    payload = {
        'receipt-data': receipt_data,
        'password': shared_secret,
        'exclude-old-transactions': False
    }
    
    # Try production first
    try:
        logger.info("Validating receipt with Apple production server")
        response = requests.post(settings.APPLE_PRODUCTION_URL, json=payload, timeout=10)
        response_data = response.json()
        
        status_code = response_data.get('status')
        logger.info(f"Apple production validation status: {status_code}")
        
        # Status 21007 means this is a sandbox receipt sent to production
        if status_code == 21007:
            logger.info("Sandbox receipt detected, retrying with sandbox server")
            response = requests.post(settings.APPLE_SANDBOX_URL, json=payload, timeout=10)
            response_data = response.json()
            status_code = response_data.get('status')
            logger.info(f"Apple sandbox validation status: {status_code}")
            
            if status_code == 0:
                return True, response_data, True
            else:
                return False, response_data, True
        
        # Status 0 means success
        elif status_code == 0:
            return True, response_data, False
        
        # Any other status code is an error
        else:
            logger.warning(f"Apple receipt validation failed with status {status_code}")
            return False, response_data, False
            
    except requests.RequestException as e:
        logger.error(f"Error validating receipt with Apple: {str(e)}")
        return False, {'error': str(e)}, False
    except Exception as e:
        logger.error(f"Unexpected error during receipt validation: {str(e)}")
        return False, {'error': str(e)}, False


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_apple_purchase(request):
    """
    Process a new Apple In-App Purchase subscription.
    
    Expected request body:
    {
        "transaction_id": "1000000123456789",
        "product_id": "com.priceadjustpro.monthly",
        "receipt_data": "MIITtgYJKoZIhvcNAQcCoIITpzCCE...",
        "original_transaction_id": "1000000123456789",
        "purchase_date": "2025-01-15T10:30:00Z",
        "expiration_date": "2025-02-15T10:30:00Z"
    }
    
    Returns:
    {
        "success": true,
        "subscription_id": 123,
        "is_sandbox": true,
        "created": true
    }
    """
    from .serializers import ApplePurchaseRequestSerializer, AppleSubscriptionSerializer
    from .models import AppleSubscription, UserProfile
    from dateutil import parser as date_parser
    
    logger.info(f"Apple purchase request from user: {request.user.email}")
    
    # Validate request data
    serializer = ApplePurchaseRequestSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning(f"Invalid Apple purchase request: {serializer.errors}")
        return Response(
            {'success': False, 'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    data = serializer.validated_data
    receipt_data = data['receipt_data']
    original_transaction_id = data['original_transaction_id']
    
    # Validate receipt with Apple
    shared_secret = settings.APPLE_SHARED_SECRET
    if not shared_secret:
        logger.error("APPLE_SHARED_SECRET not configured")
        return Response(
            {'success': False, 'error': 'Server configuration error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    is_valid, validation_response, is_sandbox = validate_apple_receipt(receipt_data, shared_secret)
    
    if not is_valid:
        logger.warning(f"Invalid Apple receipt for user {request.user.email}")
        return Response(
            {
                'success': False,
                'error': 'Receipt validation failed',
                'apple_status': validation_response.get('status'),
                'apple_message': validation_response.get('error', 'Unknown error')
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Extract subscription info from Apple's response
    try:
        receipt = validation_response.get('receipt', {})
        latest_receipt_info = validation_response.get('latest_receipt_info', [])
        
        # Find the matching transaction in the receipt info
        transaction_info = None
        for info in latest_receipt_info:
            if info.get('original_transaction_id') == original_transaction_id:
                transaction_info = info
                break
        
        # If not found in latest_receipt_info, use the data from the request
        if transaction_info:
            # Parse dates from Apple's response (in milliseconds)
            purchase_date_ms = transaction_info.get('purchase_date_ms')
            expiration_date_ms = transaction_info.get('expires_date_ms')
            
            if purchase_date_ms:
                purchase_date = timezone.datetime.fromtimestamp(int(purchase_date_ms) / 1000, tz=timezone.utc)
            else:
                purchase_date = data['purchase_date']
            
            if expiration_date_ms:
                expiration_date = timezone.datetime.fromtimestamp(int(expiration_date_ms) / 1000, tz=timezone.utc)
            else:
                expiration_date = data.get('expiration_date')
        else:
            # Use dates from request
            purchase_date = data['purchase_date']
            expiration_date = data.get('expiration_date')
        
    except Exception as e:
        logger.error(f"Error parsing Apple receipt response: {str(e)}")
        # Fall back to request data
        purchase_date = data['purchase_date']
        expiration_date = data.get('expiration_date')
    
    # Create or update subscription
    try:
        with transaction.atomic():
            subscription, created = AppleSubscription.objects.update_or_create(
                original_transaction_id=original_transaction_id,
                defaults={
                    'user': request.user,
                    'transaction_id': data['transaction_id'],
                    'product_id': data['product_id'],
                    'receipt_data': receipt_data,
                    'purchase_date': purchase_date,
                    'expiration_date': expiration_date,
                    'is_active': True,
                    'is_sandbox': is_sandbox,
                    'last_validation_response': validation_response,
                    'last_validated_at': timezone.now()
                }
            )
            
            # Update user profile to premium
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.is_premium = True
            profile.subscription_type = 'apple'
            profile.account_type = 'paid'
            profile.save()
            
            logger.info(f"Apple subscription {'created' if created else 'updated'} for user {request.user.email}")
            
            return Response({
                'success': True,
                'subscription_id': subscription.id,
                'is_sandbox': is_sandbox,
                'created': created,
                'expiration_date': subscription.expiration_date.isoformat() if subscription.expiration_date else None
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Error creating Apple subscription: {str(e)}")
        return Response(
            {'success': False, 'error': 'Failed to create subscription'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_apple_validate(request):
    """
    Validate current Apple subscription status.
    
    This endpoint checks if the user has an active Apple subscription
    and optionally re-validates it with Apple's servers.
    
    Request body (optional):
    {
        "receipt_data": "MIITtgYJKoZIhvcNAQcCoIITpzCCE...",
        "revalidate": true
    }
    
    Returns:
    {
        "has_subscription": true,
        "is_active": true,
        "subscription": { ... subscription details ... },
        "revalidated": false
    }
    """
    from .serializers import AppleSubscriptionSerializer
    from .models import AppleSubscription, UserProfile
    
    logger.info(f"Apple subscription validation request from user: {request.user.email}")
    
    # Get user's active Apple subscriptions
    subscriptions = AppleSubscription.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-created_at')
    
    if not subscriptions.exists():
        logger.info(f"No active Apple subscriptions found for user {request.user.email}")
        return Response({
            'has_subscription': False,
            'is_active': False,
            'subscription': None,
            'revalidated': False
        })
    
    subscription = subscriptions.first()
    
    # Check if subscription is expired
    if subscription.is_expired:
        logger.info(f"Apple subscription expired for user {request.user.email}")
        subscription.is_active = False
        subscription.save()
        
        # Update user profile
        profile = request.user.profile
        profile.is_premium = False
        profile.subscription_type = 'free'
        profile.account_type = 'free'
        profile.save()
        
        return Response({
            'has_subscription': True,
            'is_active': False,
            'subscription': AppleSubscriptionSerializer(subscription).data,
            'revalidated': False,
            'message': 'Subscription expired'
        })
    
    # Optionally revalidate with Apple
    should_revalidate = request.data.get('revalidate', False)
    receipt_data = request.data.get('receipt_data')
    revalidated = False
    
    if should_revalidate and receipt_data:
        logger.info(f"Revalidating Apple subscription for user {request.user.email}")
        
        shared_secret = settings.APPLE_SHARED_SECRET
        if shared_secret:
            is_valid, validation_response, is_sandbox = validate_apple_receipt(receipt_data, shared_secret)
            
            if is_valid:
                # Update subscription with new validation data
                try:
                    latest_receipt_info = validation_response.get('latest_receipt_info', [])
                    
                    for info in latest_receipt_info:
                        if info.get('original_transaction_id') == subscription.original_transaction_id:
                            expiration_date_ms = info.get('expires_date_ms')
                            if expiration_date_ms:
                                expiration_date = timezone.datetime.fromtimestamp(
                                    int(expiration_date_ms) / 1000,
                                    tz=timezone.utc
                                )
                                subscription.expiration_date = expiration_date
                            break
                    
                    subscription.last_validation_response = validation_response
                    subscription.last_validated_at = timezone.now()
                    subscription.save()
                    revalidated = True
                    
                    logger.info(f"Apple subscription revalidated successfully for user {request.user.email}")
                    
                except Exception as e:
                    logger.error(f"Error updating subscription after revalidation: {str(e)}")
            else:
                logger.warning(f"Apple subscription revalidation failed for user {request.user.email}")
    
    return Response({
        'has_subscription': True,
        'is_active': subscription.is_active,
        'subscription': AppleSubscriptionSerializer(subscription).data,
        'revalidated': revalidated
    })
