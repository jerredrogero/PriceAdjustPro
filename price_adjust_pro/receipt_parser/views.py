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

from .models import (
    Receipt, LineItem, ItemWarehousePrice, CostcoItem,
    CostcoWarehouse, PriceAdjustmentAlert
)
from .utils import (
    process_receipt_pdf, extract_text_from_pdf, parse_receipt,
    update_price_database
)
from .serializers import ReceiptSerializer

logger = logging.getLogger(__name__)

@login_required
def upload_receipt(request):
    if request.method == 'POST' and request.FILES.get('receipt_file'):
        receipt_file = request.FILES['receipt_file']
        
        # Validate file type
        if not receipt_file.name.lower().endswith('.pdf'):
            messages.error(request, 'Please upload a PDF file.')
            return redirect('upload_receipt')
            
        try:
            # Save the uploaded file
            file_path = default_storage.save(
                f'receipts/{request.user.id}/{receipt_file.name}',
                ContentFile(receipt_file.read())
            )
            
            # Get the full path using the storage backend
            full_path = default_storage.path(file_path)
            
            # Process the receipt
            parsed_data = process_receipt_pdf(full_path, user=request.user)
            
            if parsed_data.get('parse_error'):
                messages.warning(request, f"Warning: {parsed_data['parse_error']}")
            
            # Check if receipt already exists
            existing_receipt = Receipt.objects.filter(
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
                    if parsed_data.get('parsed_successfully') and parsed_data.get('items'):
                        for item_data in parsed_data['items']:
                            try:
                                line_item = LineItem.objects.create(
                                    receipt=existing_receipt,
                                    item_code=item_data.get('item_code', '000000'),
                                    description=item_data.get('description', 'Unknown Item'),
                                    price=item_data.get('price', Decimal('0.00')),
                                    quantity=item_data.get('quantity', 1),
                                    discount=item_data.get('discount'),
                                    is_taxable=item_data.get('is_taxable', False)
                                )
                                # Check for potential price adjustments
                                check_for_price_adjustments(line_item, existing_receipt)
                            except Exception as e:
                                logger.error(f"Line item error: {str(e)}")
                    
                    update_price_database(parsed_data, user=request.user)
                    messages.success(request, 'Receipt updated successfully')
                    default_storage.delete(file_path)
                    return redirect('receipt_detail', transaction_number=existing_receipt.transaction_number)
                except Exception as e:
                    logger.error(f"Error processing duplicate receipt: {str(e)}")
                    messages.error(request, f'Error processing receipt data: {str(e)}')
                
                # Clean up the uploaded file since we don't need to store it
                default_storage.delete(file_path)
                return redirect('receipt_detail', transaction_number=existing_receipt.transaction_number)

            # Create new Receipt object if it doesn't exist
            try:
                receipt = Receipt.objects.create(
                    user=request.user,
                    file=file_path,
                    transaction_number=parsed_data.get('transaction_number'),
                    store_location=parsed_data.get('store_location', 'Unknown'),
                    store_number=parsed_data.get('store_number', ''),
                    transaction_date=parsed_data.get('transaction_date', timezone.now()),
                    subtotal=parsed_data.get('subtotal', Decimal('0.00')),
                    total=parsed_data.get('total', Decimal('0.00')),
                    ebt_amount=parsed_data.get('ebt_amount'),
                    instant_savings=parsed_data.get('instant_savings'),
                    parsed_successfully=parsed_data.get('parsed_successfully', False),
                    parse_error=parsed_data.get('parse_error')
                )
                
                # Create LineItem objects only if we have valid items
                if parsed_data.get('parsed_successfully') and parsed_data.get('items'):
                    for item_data in parsed_data['items']:
                        try:
                            line_item = LineItem.objects.create(
                                receipt=receipt,
                                item_code=item_data.get('item_code', '000000'),
                                description=item_data.get('description', 'Unknown Item'),
                                price=item_data.get('price', Decimal('0.00')),
                                quantity=item_data.get('quantity', 1),
                                discount=item_data.get('discount'),
                                is_taxable=item_data.get('is_taxable', False)
                            )
                            # Check for potential price adjustments
                            check_for_price_adjustments(line_item, receipt)
                        except Exception as e:
                            logger.error(f"Line item error: {str(e)}")
                
                messages.success(request, 'Receipt uploaded successfully.')
                return redirect('receipt_detail', transaction_number=receipt.transaction_number)
                
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
        receipts = Receipt.objects.filter(user=request.user).order_by('-transaction_date')
        
        # Get active price adjustments count
        adjustments_count = PriceAdjustmentAlert.objects.filter(
            user=request.user,
            is_active=True,
            is_dismissed=False
        ).count()
        
        return JsonResponse({
            'receipts': [{
                'transaction_number': receipt.transaction_number,
                'store_location': receipt.store_location,
                'store_number': receipt.store_number,
                'transaction_date': receipt.transaction_date.isoformat(),
                'total': str(receipt.total),
                'items_count': receipt.items.count(),
                'parsed_successfully': receipt.parsed_successfully,
                'parse_error': receipt.parse_error,
            } for receipt in receipts],
            'price_adjustments_count': adjustments_count
        }, safe=False)
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
        'discount': str(item.discount) if item.discount else None,
        'total_price': str(item.total_price),
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
    
    # Validate file type
    if not receipt_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Please upload a PDF file'}, status=400)
        
    try:
        # Save the uploaded file
        file_path = default_storage.save(
            f'receipts/{request.user.id}/{receipt_file.name}',
            ContentFile(receipt_file.read())
        )
        
        # Get the full path using the storage backend
        full_path = default_storage.path(file_path)
        
        # Process the receipt
        parsed_data = process_receipt_pdf(full_path, user=request.user)

        # Check if receipt already exists
        existing_receipt = Receipt.objects.filter(
            transaction_number=parsed_data.get('transaction_number')
        ).first()

        if existing_receipt:
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
                if parsed_data.get('parsed_successfully') and parsed_data.get('items'):
                    for item_data in parsed_data['items']:
                        try:
                            line_item = LineItem.objects.create(
                                receipt=existing_receipt,
                                item_code=item_data.get('item_code', '000000'),
                                description=item_data.get('description', 'Unknown Item'),
                                price=item_data.get('price', Decimal('0.00')),
                                quantity=item_data.get('quantity', 1),
                                discount=item_data.get('discount'),
                                is_taxable=item_data.get('is_taxable', False)
                            )
                            # Check for potential price adjustments
                            check_for_price_adjustments(line_item, existing_receipt)
                        except Exception as e:
                            logger.error(f"Line item error: {str(e)}")
                
                update_price_database(parsed_data, user=request.user)
                messages.success(request, 'Receipt updated successfully')
                default_storage.delete(file_path)
                return redirect('receipt_detail', transaction_number=existing_receipt.transaction_number)
            except Exception as e:
                logger.error(f"Error processing duplicate receipt: {str(e)}")
                default_storage.delete(file_path)
                return JsonResponse({'error': str(e)}, status=500)
        
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
            ebt_amount=parsed_data.get('ebt_amount'),
            instant_savings=parsed_data.get('instant_savings'),
            parsed_successfully=parsed_data.get('parsed_successfully', False),
            parse_error=parsed_data.get('parse_error')
        )
        
        # Create LineItem objects only if we have valid items
        if parsed_data.get('parsed_successfully') and parsed_data.get('items'):
            for item_data in parsed_data['items']:
                try:
                    line_item = LineItem.objects.create(
                        receipt=receipt,
                        item_code=item_data.get('item_code', '000000'),
                        description=item_data.get('description', 'Unknown Item'),
                        price=item_data.get('price', Decimal('0.00')),
                        quantity=item_data.get('quantity', 1),
                        discount=item_data.get('discount'),
                        is_taxable=item_data.get('is_taxable', False)
                    )
                    # Check for potential price adjustments
                    check_for_price_adjustments(line_item, receipt)
                except Exception as e:
                    logger.error(f"Line item error: {str(e)}")
        
        return JsonResponse({
            'transaction_number': receipt.transaction_number,
            'message': 'Receipt uploaded successfully',
            'parse_error': parsed_data.get('parse_error'),
            'parsed_successfully': parsed_data.get('parsed_successfully', False),
            'is_duplicate': False
        })
        
    except Exception as e:
        logger.error(f"Error processing receipt file: {str(e)}")
        # Clean up the uploaded file if it exists
        if 'file_path' in locals():
            default_storage.delete(file_path)
        return JsonResponse({'error': str(e)}, status=500)

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

def register(request):
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

@api_view(['POST'])
@authentication_classes([SessionAuthentication, BasicAuthentication])
@permission_classes([IsAuthenticated])
def upload_receipt(request):
    try:
        if 'receipt_file' not in request.FILES:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
            
        receipt_file = request.FILES['receipt_file']
        
        # Validate file type
        if not receipt_file.name.lower().endswith('.pdf'):
            return Response({'error': 'Please upload a PDF file'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Save and process the file
        file_path = default_storage.save(
            f'receipts/{request.user.id}/{receipt_file.name}',
            ContentFile(receipt_file.read())
        )
        
        # Get the full path and process the receipt
        full_path = default_storage.path(file_path)
        parsed_data = process_receipt_pdf(full_path, user=request.user)
        
        # Check for existing receipt
        existing_receipt = Receipt.objects.filter(
            transaction_number=parsed_data.get('transaction_number')
        ).first()
        
        if existing_receipt:
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
                if parsed_data.get('parsed_successfully') and parsed_data.get('items'):
                    for item_data in parsed_data['items']:
                        try:
                            line_item = LineItem.objects.create(
                                receipt=existing_receipt,
                                item_code=item_data.get('item_code', '000000'),
                                description=item_data.get('description', 'Unknown Item'),
                                price=item_data.get('price', Decimal('0.00')),
                                quantity=item_data.get('quantity', 1),
                                discount=item_data.get('discount'),
                                is_taxable=item_data.get('is_taxable', False)
                            )
                        except Exception as e:
                            logger.error(f"Line item error: {str(e)}")
                
                update_price_database(parsed_data, user=request.user)
                messages.success(request, 'Receipt updated successfully')
                default_storage.delete(file_path)
                return redirect('receipt_detail', transaction_number=existing_receipt.transaction_number)
            except Exception as e:
                logger.error(f"Error processing duplicate receipt: {str(e)}")
                default_storage.delete(file_path)
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Prepare receipt data for serialization
        receipt_data = {
            'user': request.user.id,
            'file': file_path,
            'transaction_number': parsed_data.get('transaction_number'),
            'store_location': parsed_data.get('store_location', 'Unknown'),
            'store_number': parsed_data.get('store_number', ''),
            'transaction_date': parsed_data.get('transaction_date', timezone.now()),
            'subtotal': parsed_data.get('subtotal', Decimal('0.00')),
            'total': parsed_data.get('total', Decimal('0.00')),
            'ebt_amount': parsed_data.get('ebt_amount'),
            'instant_savings': parsed_data.get('instant_savings'),
            'parsed_successfully': parsed_data.get('parsed_successfully', False),
            'parse_error': parsed_data.get('parse_error')
        }
        
        # Create receipt using serializer
        serializer = ReceiptSerializer(data=receipt_data)
        if serializer.is_valid():
            receipt = serializer.save()
            
            # Create line items if parsing was successful
            if parsed_data.get('parsed_successfully') and parsed_data.get('items'):
                for item_data in parsed_data['items']:
                    try:
                        line_item = LineItem.objects.create(
                            receipt=receipt,
                            item_code=item_data.get('item_code', '000000'),
                            description=item_data.get('description', 'Unknown Item'),
                            price=item_data.get('price', Decimal('0.00')),
                            quantity=item_data.get('quantity', 1),
                            discount=item_data.get('discount'),
                            is_taxable=item_data.get('is_taxable', False)
                        )
                        # Check for potential price adjustments
                        check_for_price_adjustments(line_item, receipt)
                    except Exception as e:
                        logger.error(f"Line item error: {str(e)}")
            
            return Response({
                'transaction_number': receipt.transaction_number,
                'message': 'Receipt uploaded successfully',
                'parse_error': parsed_data.get('parse_error'),
                'parsed_successfully': parsed_data.get('parsed_successfully', False),
                'is_duplicate': False
            }, status=status.HTTP_201_CREATED)
        
        # If serializer validation failed, clean up and return errors
        default_storage.delete(file_path)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        # Clean up the uploaded file if it exists
        if 'file_path' in locals():
            default_storage.delete(file_path)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
