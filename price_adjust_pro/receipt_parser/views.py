from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
import logging
import json

from .models import Receipt, LineItem
from .utils import process_receipt_pdf

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
            
            # Get the full path to the saved file
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            
            # Process the receipt
            parsed_data = process_receipt_pdf(full_path)
            
            if parsed_data.get('parse_error'):
                messages.warning(request, f"Warning: {parsed_data['parse_error']}")
            
            # Create Receipt object
            try:
                receipt = Receipt.objects.create(
                    user=request.user,
                    file=file_path,
                    store_location=parsed_data.get('store_location'),
                    store_number=parsed_data.get('store_number'),
                    transaction_date=parsed_data.get('transaction_date'),
                    subtotal=parsed_data.get('subtotal'),
                    tax=parsed_data.get('tax'),
                    total=parsed_data.get('total'),
                    ebt_amount=parsed_data.get('ebt_amount'),
                    instant_savings=parsed_data.get('instant_savings'),
                    parsed_successfully=not bool(parsed_data.get('parse_error')),
                    parse_error=parsed_data.get('parse_error')
                )
                
                # Create LineItem objects
                items_created = 0
                for item_data in parsed_data.get('items', []):
                    try:
                        LineItem.objects.create(
                            receipt=receipt,
                            item_code=item_data.get('item_code'),
                            description=item_data.get('description'),
                            price=item_data.get('price'),
                            quantity=item_data.get('quantity', 1),
                            discount=item_data.get('discount'),
                            is_taxable=item_data.get('is_taxable', False)
                        )
                        items_created += 1
                    except Exception as e:
                        logger.error(f"Error creating line item: {str(e)}")
                        messages.warning(request, f"Warning: Some items may not have been processed correctly.")
                
                if items_created > 0:
                    messages.success(request, f'Receipt uploaded and processed successfully. {items_created} items found.')
                else:
                    messages.warning(request, 'Receipt uploaded but no items were found. Please check the PDF format.')
                
                return redirect('receipt_detail', receipt_id=receipt.id)
                
            except Exception as e:
                logger.error(f"Error creating receipt: {str(e)}")
                # Clean up the uploaded file if receipt creation fails
                if os.path.exists(full_path):
                    os.remove(full_path)
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
def receipt_detail(request, receipt_id):
    receipt = get_object_or_404(Receipt, pk=receipt_id, user=request.user)
    return render(request, 'receipt_parser/receipt_detail.html', {'receipt': receipt})

# API Views
@login_required
def api_receipt_list(request):
    if request.method == 'GET':
        receipts = Receipt.objects.filter(user=request.user).order_by('-transaction_date')
        return JsonResponse([{
            'id': receipt.id,
            'store_location': receipt.store_location,
            'store_number': receipt.store_number,
            'transaction_date': receipt.transaction_date,
            'total': str(receipt.total),
            'items_count': receipt.items.count(),
            'parsed_successfully': receipt.parsed_successfully,
            'parse_error': receipt.parse_error,
        } for receipt in receipts], safe=False)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def api_receipt_detail(request, receipt_id):
    receipt = get_object_or_404(Receipt, pk=receipt_id, user=request.user)
    items = [{
        'id': item.id,
        'item_code': item.item_code,
        'description': item.description,
        'price': str(item.price),
        'quantity': item.quantity,
        'discount': str(item.discount) if item.discount else None,
        'is_taxable': item.is_taxable,
        'total_price': str(item.total_price),
    } for item in receipt.items.all()]
    
    return JsonResponse({
        'id': receipt.id,
        'store_location': receipt.store_location,
        'store_number': receipt.store_number,
        'transaction_date': receipt.transaction_date,
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
        
        # Get the full path to the saved file
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        
        # Process the receipt
        parsed_data = process_receipt_pdf(full_path)
        
        # Create Receipt object
        receipt = Receipt.objects.create(
            user=request.user,
            file=file_path,
            store_location=parsed_data.get('store_location'),
            store_number=parsed_data.get('store_number'),
            transaction_date=parsed_data.get('transaction_date'),
            subtotal=parsed_data.get('subtotal'),
            tax=parsed_data.get('tax'),
            total=parsed_data.get('total'),
            ebt_amount=parsed_data.get('ebt_amount'),
            instant_savings=parsed_data.get('instant_savings'),
            parsed_successfully=not bool(parsed_data.get('parse_error')),
            parse_error=parsed_data.get('parse_error')
        )
        
        # Create LineItem objects
        for item_data in parsed_data.get('items', []):
            try:
                LineItem.objects.create(
                    receipt=receipt,
                    item_code=item_data.get('item_code'),
                    description=item_data.get('description'),
                    price=item_data.get('price'),
                    quantity=item_data.get('quantity', 1),
                    discount=item_data.get('discount'),
                    is_taxable=item_data.get('is_taxable', False)
                )
            except Exception as e:
                logger.error(f"Error creating line item: {str(e)}")
        
        return JsonResponse({
            'id': receipt.id,
            'message': 'Receipt uploaded successfully',
            'parse_error': parsed_data.get('parse_error'),
        })
        
    except Exception as e:
        logger.error(f"Error processing receipt file: {str(e)}")
        # Clean up the uploaded file if it exists
        if 'full_path' in locals() and os.path.exists(full_path):
            os.remove(full_path)
        return JsonResponse({'error': str(e)}, status=500)
