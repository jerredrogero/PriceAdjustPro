from rest_framework import serializers
from .models import Receipt, LineItem
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class LineItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    class Meta:
        model = LineItem
        fields = [
            'item_code', 'description', 'price', 'quantity', 
            'discount', 'on_sale', 'total_price', 'is_taxable',
            'instant_savings', 'original_price', 'original_total_price'
        ]

class ReceiptSerializer(serializers.ModelSerializer):
    items = LineItemSerializer(many=True, required=False)
    accept_manual_edits = serializers.BooleanField(default=False, required=False, write_only=True)
    
    class Meta:
        model = Receipt
        fields = [
            'transaction_number',
            'store_location',
            'store_number',
            'store_city',
            'transaction_date',
            'subtotal',
            'tax',
            'total',
            'ebt_amount',
            'instant_savings',
            'parsed_successfully',
            'parse_error',
            'items',
            'file',
            'user',
            'accept_manual_edits'
        ]
        read_only_fields = ['created_at', 'store_city', 'user']
    
    def update(self, instance, validated_data):
        """Handle updating receipt with nested items."""
        logger.info(f"Updating receipt {instance.transaction_number} with validated data")
        
        # Extract items data and accept_manual_edits flag
        items_data = validated_data.pop('items', None)
        accept_manual_edits = validated_data.pop('accept_manual_edits', False)
        
        logger.info(f"Serializer update: accept_manual_edits={accept_manual_edits}")
        
        # Update receipt fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            logger.info(f"Updating {len(items_data)} items for receipt {instance.transaction_number}")
            
            # Delete existing items
            instance.items.all().delete()
            
            # Create new items
            for item_data in items_data:
                # When accepting manual edits, preserve total_price as original_total_price
                if accept_manual_edits and 'total_price' in item_data:
                    item_data['original_total_price'] = Decimal(str(item_data['total_price']))
                
                # Remove total_price from item_data as it's calculated by the model
                item_data.pop('total_price', None)
                
                LineItem.objects.create(
                    receipt=instance,
                    **item_data
                )
                
        return instance