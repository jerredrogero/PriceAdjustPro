from rest_framework import serializers
from .models import Receipt, LineItem

class LineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineItem
        fields = ['item_code', 'description', 'price', 'quantity', 'discount']

class ReceiptSerializer(serializers.ModelSerializer):
    items = LineItemSerializer(many=True, read_only=True)
    
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
            'user'
        ]
        read_only_fields = ['created_at', 'store_city']