from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Receipt, LineItem, UserProfile, OfficialSaleItem, CostcoPromotion, AppleSubscription
from decimal import Decimal
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with account type information."""
    account_type = serializers.SerializerMethodField()
    account_type_display = serializers.SerializerMethodField()
    is_paid_account = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'account_type', 'account_type_display', 'is_paid_account'
        ]
    
    def get_account_type(self, obj):
        """Get account type from UserProfile, return iOS app compatible value."""
        try:
            profile = obj.profile
            # Return iOS app compatible values
            if profile.is_paid_account:
                return 'paid'  # iOS app expects: "paid", "premium", "pro", "subscription", "active", "subscriber"
            else:
                return 'free'  # iOS app expects: "free", "basic", "trial", "inactive"
        except UserProfile.DoesNotExist:
            # Create profile if it doesn't exist
            UserProfile.objects.create(user=obj, account_type='free')
            return 'free'
    
    def get_account_type_display(self, obj):
        """Get human-readable account type."""
        try:
            profile = obj.profile
            return profile.get_account_type_display()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=obj, account_type='free')
            return 'Free Account'
    
    def get_is_paid_account(self, obj):
        """Boolean indicating if user has paid account."""
        try:
            profile = obj.profile
            return profile.is_paid_account
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=obj, account_type='free')
            return False

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


class PromotionSerializer(serializers.ModelSerializer):
    """Serializer for promotion information."""
    days_remaining = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CostcoPromotion
        fields = [
            'title', 'sale_start_date', 'sale_end_date', 
            'days_remaining', 'items_count'
        ]
    
    def get_days_remaining(self, obj):
        """Calculate days remaining until promotion ends."""
        today = timezone.now().date()
        if obj.sale_end_date > today:
            return (obj.sale_end_date - today).days
        return 0
    
    def get_items_count(self, obj):
        """Get count of items in this promotion."""
        return obj.sale_items.count()


class OnSaleItemSerializer(serializers.ModelSerializer):
    """Serializer for individual sale items."""
    savings = serializers.SerializerMethodField()
    promotion = PromotionSerializer(read_only=True)
    
    class Meta:
        model = OfficialSaleItem
        fields = [
            'id', 'item_code', 'description', 'regular_price', 
            'sale_price', 'instant_rebate', 'savings', 'sale_type', 'promotion'
        ]
    
    def get_savings(self, obj):
        """Calculate savings amount."""
        if obj.sale_type == 'discount_only' and obj.instant_rebate:
            return obj.instant_rebate
        elif obj.regular_price and obj.sale_price:
            return obj.regular_price - obj.sale_price
        elif obj.instant_rebate:
            return obj.instant_rebate
        return None


class OnSaleResponseSerializer(serializers.Serializer):
    """Serializer for the complete on-sale API response."""
    sales = OnSaleItemSerializer(many=True)
    total_count = serializers.IntegerField()
    active_promotions = PromotionSerializer(many=True)
    current_date = serializers.DateField()
    last_updated = serializers.DateTimeField()


class AppleSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Apple In-App Purchase subscriptions."""
    days_remaining = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = AppleSubscription
        fields = [
            'id', 'transaction_id', 'original_transaction_id', 'product_id',
            'purchase_date', 'expiration_date', 'is_active', 'is_sandbox',
            'days_remaining', 'is_expired', 'last_validated_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_validated_at']
    
    def get_days_remaining(self, obj):
        """Get days remaining until expiration."""
        return obj.days_remaining
    
    def get_is_expired(self, obj):
        """Check if subscription is expired."""
        return obj.is_expired


class ApplePurchaseRequestSerializer(serializers.Serializer):
    """Serializer for Apple purchase request."""
    transaction_id = serializers.CharField(max_length=255, required=True)
    product_id = serializers.CharField(max_length=255, required=True)
    receipt_data = serializers.CharField(required=True)
    original_transaction_id = serializers.CharField(max_length=255, required=True)
    purchase_date = serializers.DateTimeField(required=True)
    expiration_date = serializers.DateTimeField(required=False, allow_null=True)