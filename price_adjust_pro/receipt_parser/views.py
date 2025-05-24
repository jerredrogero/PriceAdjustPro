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
from django.db import migrations
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth

from .models import (
    Receipt, LineItem, ItemWarehousePrice, CostcoItem,
    CostcoWarehouse, PriceAdjustmentAlert
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
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
        
        # Debug logging
        logger.info(f"Uploaded file: {receipt_file.name}, extension check: {file_ext}")
        
        is_valid_file = any(file_ext.endswith(ext) for ext in allowed_extensions)
        logger.info(f"File validation result: {is_valid_file}")
        
        if not is_valid_file:
            logger.warning(f"Invalid file type uploaded: {file_ext}")
            messages.error(request, f'Please upload a PDF or image file (JPG, PNG, WebP, etc.). Received: {file_ext}')
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
                    existing_receipt.store_number = parsed_data.get('store_number', existing_receipt.store_number)
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
                                # Check for potential price adjustments
                                check_for_price_adjustments(line_item, existing_receipt)
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
                if (parsed_data.get('transaction_number') and 
                    parsed_data.get('items') and 
                    parsed_data.get('total') and 
                    parsed_data.get('transaction_date')):
                    parsed_data['parsed_successfully'] = True
                    parsed_data['parse_error'] = None
                
                receipt = Receipt.objects.create(
                    user=request.user,
                    file=file_path,
                    transaction_number=parsed_data.get('transaction_number'),
                    store_location=parsed_data.get('store_location', 'Unknown'),
                    store_number=parsed_data.get('store_number', ''),
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
                            # Check for potential price adjustments
                            check_for_price_adjustments(line_item, receipt)
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
                    'items': [{  # Include item details
                        'id': item.id,
                        'item_code': item.item_code,
                        'description': item.description,
                        'price': str(item.price),
                        'quantity': item.quantity,
                        'total_price': str(item.total_price),
                        'on_sale': item.on_sale,
                        'instant_savings': str(item.instant_savings) if item.instant_savings else None,
                        'original_price': str(item.original_price) if item.original_price else None,
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

@login_required
def api_receipt_detail(request, transaction_number):
    receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=request.user)
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
        'original_price': str(item.original_price) if item.original_price else None
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
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
    
    # Debug logging
    logger.info(f"Uploaded file: {receipt_file.name}, extension check: {file_ext}")
    
    is_valid_file = any(file_ext.endswith(ext) for ext in allowed_extensions)
    logger.info(f"File validation result: {is_valid_file}")
    
    if not is_valid_file:
        logger.warning(f"Invalid file type uploaded: {file_ext}")
        return JsonResponse({'error': 'Please upload a PDF or image file (JPG, PNG, WebP, etc.)'}, status=400)
        
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
            # Update existing receipt
            existing_receipt.file.delete(save=False)  # Delete old file
            existing_receipt.file = file_path
            existing_receipt.store_location = parsed_data['store_location']
            existing_receipt.store_number = parsed_data['store_number']
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
        
        # Create Receipt object with default values if parsing failed
        receipt = Receipt.objects.create(
            user=request.user,
            file=file_path,
            transaction_number=parsed_data.get('transaction_number'),
            store_location=parsed_data.get('store_location', 'Unknown'),
            store_number=parsed_data.get('store_number', ''),
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
                        original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None
                    )
                    # Check for potential price adjustments
                    check_for_price_adjustments(line_item, receipt)
                except Exception as e:
                    logger.error(f"Line item error: {str(e)}")
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
    
    receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=request.user)
    
    try:
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
        
        return JsonResponse({'message': 'Receipt deleted successfully'})
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
        username = data.get('username')
        email = data.get('email')
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
            # Delete user's files
            user_receipts = Receipt.objects.filter(user=user)
            for receipt in user_receipts:
                if receipt.file:
                    try:
                        default_storage.delete(receipt.file.name)
                    except Exception as e:
                        logger.warning(f"Failed to delete file for receipt {receipt.transaction_number}: {str(e)}")
            
            # Delete the user account
            user.delete()
            messages.success(request, 'Your account has been deleted.')
            return redirect('login')
        else:
            messages.error(request, 'Incorrect password. Account deletion cancelled.')
    
    return redirect('settings')

@login_required
def api_check_price_adjustments(request):
    """Check for available price adjustments for the user's receipts."""
    try:
        # Get all receipts from the last 30 days
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        user_receipts = Receipt.objects.filter(
            user=request.user,
            transaction_date__gte=thirty_days_ago,
            parsed_successfully=True  # Only check successfully parsed receipts
        ).prefetch_related('items')

        adjustments = []
        
        # For each receipt
        for receipt in user_receipts:
            # For each item in the receipt
            for item in receipt.items.all():
                if not item.item_code:  # Skip items without item codes
                    continue
                    
                # Find any lower prices for this item in the last 30 days
                # across all warehouses
                lower_prices = ItemWarehousePrice.objects.filter(
                    item__item_code=item.item_code,
                    date_seen__gte=thirty_days_ago,
                    price__lt=item.price  # Find lower prices
                ).select_related('warehouse').order_by('price')

                if lower_prices.exists():
                    lowest_price = lower_prices.first()
                    price_difference = item.price - lowest_price.price
                    
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
                                'lower_price': float(lowest_price.price),
                                'price_difference': float(price_difference),
                                'store_location': lowest_price.warehouse.location,
                                'store_number': lowest_price.warehouse.store_number,
                                'purchase_date': receipt.transaction_date.isoformat(),
                                'days_remaining': days_remaining,
                                'original_store': receipt.store_location,
                                'original_store_number': receipt.store_number
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
    try:
        # Get all active alerts for the user
        alerts = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            is_active=True,
            is_dismissed=False
        ).select_related('user')  # Add select_related to optimize queries

        # Convert to list and sort by price difference
        alert_data = []
        total_savings = Decimal('0.00')

        for alert in alerts:
            price_diff = alert.original_price - alert.lower_price
            total_savings += price_diff
            
            alert_data.append({
                'item_code': alert.item_code,
                'description': alert.item_description,
                'current_price': float(alert.original_price),
                'lower_price': float(alert.lower_price),
                'price_difference': float(price_diff),
                'store_location': f"Costco {alert.cheaper_store_city}",
                'store_number': alert.cheaper_store_number,
                'purchase_date': alert.purchase_date.isoformat(),
                'days_remaining': alert.days_remaining,
                'original_store': f"Costco {alert.original_store_city}",
                'original_store_number': alert.original_store_number
            })

        # Sort by price difference (highest savings first)
        alert_data.sort(key=lambda x: x['price_difference'], reverse=True)

        return JsonResponse({
            'adjustments': alert_data,
            'total_potential_savings': float(total_savings)
        })
    except Exception as e:
        logger.error(f"Error checking price adjustments: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@csrf_exempt
def api_dismiss_price_adjustment(request, item_code):
    """Dismiss a price adjustment alert."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        alert = get_object_or_404(
            PriceAdjustmentAlert,
            user=request.user,
            item_code=item_code,
            is_active=True
        )
        alert.is_dismissed = True
        alert.save()
        return JsonResponse({'message': 'Alert dismissed successfully'})
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
            store_key = f"{receipt.store_location} #{receipt.store_number}"
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

@login_required
def api_receipt_update(request, transaction_number):
    """Update a receipt after review."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        receipt = get_object_or_404(Receipt, transaction_number=transaction_number, user=request.user)
        data = json.loads(request.body)
        
        # Validate total items count
        total_quantity = sum(item.get('quantity', 1) for item in data.get('items', []))
        if total_quantity != data.get('total_items_sold', 0):
            return JsonResponse({
                'error': f'Total quantity ({total_quantity}) must match receipt total ({data["total_items_sold"]})'
            }, status=400)
        
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
                # Parse the ISO format date from frontend
                from datetime import datetime
                receipt.transaction_date = datetime.fromisoformat(data['transaction_date'].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse transaction_date: {data.get('transaction_date')}, error: {str(e)}")
        
        receipt.save()
        
        # Update items
        receipt.items.all().delete()  # Remove existing items
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
                    original_price=Decimal(str(item_data['original_price'])) if item_data.get('original_price') else None
                )
                # Check for potential price adjustments
                check_for_price_adjustments(line_item, receipt)
            except Exception as e:
                logger.error(f"Error creating line item: {str(e)}")
                continue
        
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
        
        return JsonResponse({
            'message': 'Receipt updated successfully',
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
                    'original_price': str(item.original_price) if item.original_price else None
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
    receipts = Receipt.objects.filter(user=request.user)
    
    # Calculate totals
    total_spent = receipts.aggregate(
        total=Sum('total', default=Decimal('0.00'))
    )['total']
    
    instant_savings = receipts.aggregate(
        savings=Sum('instant_savings', default=Decimal('0.00'))
    )['savings']
    
    total_receipts = receipts.count()
    total_items = receipts.aggregate(
        items=Sum('items_count', default=0)
    )['items']
    
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
