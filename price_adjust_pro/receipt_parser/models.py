from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import RegexValidator
from django.db.models import Q

# Create your models here.

class Receipt(models.Model):
    """
    Stores receipt information with proper indexing for efficient querying.
    """
    transaction_number = models.CharField(
        max_length=50,
        validators=[RegexValidator(
            regex=r'^\d+$',
            message='Transaction number must be numeric'
        )]
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='receipts',
        db_index=True  # Add index for user lookups
    )
    file = models.FileField(upload_to='receipts/%Y/%m/%d/', blank=True, null=True)  # Optional file storage
    store_location = models.CharField(max_length=255, db_index=True)  # Add index for store lookups
    store_number = models.CharField(max_length=50, db_index=True)
    store_city = models.CharField(max_length=100, db_index=True)
    transaction_date = models.DateTimeField(db_index=True, default=timezone.now)  # Add index for date queries
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    ebt_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    instant_savings = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parsed_successfully = models.BooleanField(default=False)
    parse_error = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-transaction_date']
        unique_together = ['user', 'transaction_number']
        indexes = [
            models.Index(fields=['user', 'transaction_date']),
            models.Index(fields=['store_location', 'store_number']),
            models.Index(fields=['parsed_successfully']),
        ]
        verbose_name = 'Receipt'
        verbose_name_plural = 'Receipts'

    def __str__(self):
        return f"Receipt {self.transaction_number} - {self.store_location} ({self.transaction_date})"

    def save(self, *args, **kwargs):
        # Extract city from store_location if not set
        if not self.store_city and self.store_location:
            parts = self.store_location.split()
            if len(parts) > 1:
                self.store_city = ' '.join(parts[1:-1])
        super().save(*args, **kwargs)

    def get_total_items(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_total_savings(self):
        return self.instant_savings or Decimal('0.00')

    def delete(self, *args, **kwargs):
        """Override delete to also remove related price adjustment alerts."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Delete related price adjustment alerts
        item_codes = list(self.items.values_list('item_code', flat=True))
        
        if item_codes:
            # Use string reference to avoid issues with model order
            from django.apps import apps
            PriceAdjustmentAlert = apps.get_model('receipt_parser', 'PriceAdjustmentAlert')
            
            alerts_to_delete = PriceAdjustmentAlert.objects.filter(
                user=self.user,
                item_code__in=item_codes,
                purchase_date__date=self.transaction_date.date(),
                original_store_number=self.store_number
            )
            
            deleted_count = alerts_to_delete.count()
            alerts_to_delete.delete()
            
            if deleted_count > 0:
                logger.info(f"Auto-deleted {deleted_count} price adjustment alerts for receipt {self.transaction_number}")
        
        # Call the parent delete method
        super().delete(*args, **kwargs)

class LineItem(models.Model):
    """
    Stores individual items from receipts with price tracking capabilities.
    """
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    item_code = models.CharField(max_length=50, db_index=True)
    description = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)
    discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_taxable = models.BooleanField(default=False)
    on_sale = models.BooleanField(default=False, help_text="Mark this item as on sale if the parsing missed it")
    instant_savings = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Original total from receipt, separate from calculated price * quantity")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['item_code', 'price']),
            models.Index(fields=['receipt', 'item_code']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Line Item'
        verbose_name_plural = 'Line Items'

    def __str__(self):
        return f"{self.description} - ${self.price}"

    @property
    def total_price(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        if self.instant_savings and not self.original_price:
            self.original_price = self.price + self.instant_savings
        super().save(*args, **kwargs)

class CostcoItem(models.Model):
    """
    Master list of Costco items with current pricing information.
    """
    item_code = models.CharField(max_length=50, primary_key=True)
    description = models.CharField(max_length=255)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    last_price_update = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_code']
        indexes = [
            models.Index(fields=['description']),
            models.Index(fields=['last_price_update']),
        ]
        verbose_name = 'Costco Item'
        verbose_name_plural = 'Costco Items'

    def __str__(self):
        return f"{self.description} ({self.item_code})"

    def update_price(self, new_price, warehouse, date_seen):
        """Update item price and record history if changed."""
        if self.current_price != new_price:
            ItemPriceHistory.objects.create(
                item=self,
                warehouse=warehouse,
                old_price=self.current_price,
                new_price=new_price,
                date_changed=date_seen
            )
            self.current_price = new_price
            self.last_price_update = date_seen
            self.save()
            return True
        return False

    def get_price_history(self, days=30):
        """Get price history for the last N days."""
        start_date = timezone.now() - timezone.timedelta(days=days)
        return self.price_history.filter(date_changed__gte=start_date).order_by('date_changed')

class CostcoWarehouse(models.Model):
    """
    Stores information about Costco warehouse locations.
    """
    store_number = models.CharField(max_length=50, primary_key=True)
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100, default='Unknown')
    state = models.CharField(max_length=2, default='NA')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['store_number']
        indexes = [
            models.Index(fields=['city', 'state']),
        ]
        verbose_name = 'Costco Warehouse'
        verbose_name_plural = 'Costco Warehouses'

    def __str__(self):
        return f"{self.location} (#{self.store_number})"

    def get_current_prices(self):
        """Get all current prices for this warehouse."""
        return self.itemwarehouseprice_set.select_related('item').all()

class ItemPriceHistory(models.Model):
    """
    Tracks historical price changes for items at specific warehouses.
    """
    item = models.ForeignKey(CostcoItem, on_delete=models.CASCADE, related_name='price_history')
    warehouse = models.ForeignKey(CostcoWarehouse, on_delete=models.CASCADE)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    date_changed = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_changed']
        indexes = [
            models.Index(fields=['item', 'date_changed']),
            models.Index(fields=['warehouse', 'date_changed']),
        ]
        verbose_name = 'Item Price History'
        verbose_name_plural = 'Item Price Histories'

    def __str__(self):
        return f"{self.item} price changed from ${self.old_price} to ${self.new_price} at {self.warehouse}"

class ItemWarehousePrice(models.Model):
    """
    Tracks current prices of items at specific warehouses.
    """
    item = models.ForeignKey(CostcoItem, on_delete=models.CASCADE, related_name='warehouse_prices')
    warehouse = models.ForeignKey(CostcoWarehouse, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    last_seen = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['item', 'warehouse']
        indexes = [
            models.Index(fields=['item', 'price']),
            models.Index(fields=['warehouse', 'last_seen']),
        ]
        verbose_name = 'Item Warehouse Price'
        verbose_name_plural = 'Item Warehouse Prices'

    def __str__(self):
        return f"{self.item} at {self.warehouse}: ${self.price}"

    @classmethod
    def update_price(cls, item, warehouse, new_price, date_seen):
        """Update or create price record for an item at a warehouse."""
        price_record, created = cls.objects.get_or_create(
            item=item,
            warehouse=warehouse,
            defaults={
                'price': new_price,
                'last_seen': date_seen
            }
        )

        if not created and price_record.price != new_price:
            price_record.price = new_price
            price_record.last_seen = date_seen
            price_record.save()
            return True
        
        return created

class PriceAdjustmentAlert(models.Model):
    """
    Tracks potential price adjustment opportunities for users.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_alerts')
    item_code = models.CharField(max_length=50)
    item_description = models.CharField(max_length=255)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    lower_price = models.DecimalField(max_digits=10, decimal_places=2)
    original_store_city = models.CharField(max_length=100)
    original_store_number = models.CharField(max_length=50)
    cheaper_store_city = models.CharField(max_length=100)
    cheaper_store_number = models.CharField(max_length=50)
    purchase_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_dismissed = models.BooleanField(default=False)
    data_source = models.CharField(
        max_length=20, 
        choices=[
            ('ocr_parsed', 'OCR Parsed'),
            ('user_edit', 'User Edit'),
            ('official_promo', 'Official Promotion')
        ],
        default='ocr_parsed',
        help_text="Source of the price data that triggered this alert"
    )
    official_sale_item = models.ForeignKey(
        'OfficialSaleItem', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='generated_alerts',
        help_text="Official sale item that generated this alert"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'item_code']),
            models.Index(fields=['purchase_date']),
            models.Index(fields=['is_active', 'is_dismissed']),
        ]
        verbose_name = 'Price Adjustment Alert'
        verbose_name_plural = 'Price Adjustment Alerts'

    def __str__(self):
        return f"Price Alert: {self.item_description} - Save ${self.price_difference}"

    @property
    def price_difference(self):
        return self.original_price - self.lower_price

    def get_original_transaction_number(self):
        """Find the transaction number for the original purchase."""
        try:
            # Find the receipt for the original purchase
            from datetime import timedelta
            
            # Look for receipts within a day of the purchase date to account for timezone differences
            start_date = self.purchase_date.date() - timedelta(days=1)
            end_date = self.purchase_date.date() + timedelta(days=1)
            
            receipt = Receipt.objects.filter(
                user=self.user,
                transaction_date__date__gte=start_date,
                transaction_date__date__lte=end_date,
                store_number=self.original_store_number,
                items__item_code=self.item_code
            ).first()
            
            return receipt.transaction_number if receipt else None
        except Exception:
            return None
    
    def get_cheaper_transaction_number(self):
        """Find the transaction number for the cheaper purchase."""
        try:
            if self.data_source == 'user_edit':
                # For user_edit, look for another receipt from the same user with the lower price
                receipt = Receipt.objects.filter(
                    user=self.user,
                    store_number=self.cheaper_store_number,
                    items__item_code=self.item_code,
                    items__price=self.lower_price
                ).exclude(
                    # Exclude the original purchase receipt
                    transaction_date__date=self.purchase_date.date(),
                    store_number=self.original_store_number
                ).first()
                
                return receipt.transaction_number if receipt else None
            else:
                # For ocr_parsed, we can't link to other users' receipts for privacy
                return None
        except Exception:
            return None

    @property
    def source_description_data(self):
        """Get structured data for the frontend to create links properly."""
        original_transaction = self.get_original_transaction_number()
        cheaper_transaction = self.get_cheaper_transaction_number()
        
        if self.data_source == 'official_promo' and self.official_sale_item:
            # Official Costco promotion
            promo = self.official_sale_item.promotion
            if self.official_sale_item.sale_type == 'discount_only':
                return {
                    'text': f"This item is currently on sale nationwide with ${self.official_sale_item.instant_rebate} off. This promotion is valid until {promo.sale_end_date.strftime('%B %d, %Y')}.",
                    'links': []
                }
            else:
                return {
                    'text': f"This item is currently on sale nationwide for ${self.lower_price} (was ${self.original_price}). This promotion is valid until {promo.sale_end_date.strftime('%B %d, %Y')}.",
                    'links': []
                }
        
        elif self.data_source == 'user_edit':
            # Same user comparing their own receipts - include links
            links = []
            if original_transaction:
                links.append({
                    'text': f'receipt from {self.purchase_date.strftime("%B %d, %Y")}',
                    'url': f'/receipts/{original_transaction}',
                    'type': 'original'
                })
            if cheaper_transaction:
                links.append({
                    'text': 'later receipt',
                    'url': f'/receipts/{cheaper_transaction}',
                    'type': 'cheaper'
                })
            
            return {
                'text': f"You purchased this item at {self.original_store_city} for ${self.original_price}. You later found it for ${self.lower_price} at {self.cheaper_store_city}. You may be eligible for a price adjustment.",
                'links': links
            }
        
        elif self.data_source == 'ocr_parsed':
            # Other users' receipts - only link to the user's own receipt
            links = []
            if original_transaction:
                links.append({
                    'text': 'your receipt',
                    'url': f'/receipts/{original_transaction}',
                    'type': 'original'
                })
            
            if self.original_store_city == self.cheaper_store_city:
                text = f"You purchased this item at {self.original_store_city} for ${self.original_price}. Another member found it for ${self.lower_price} at the same location. You may have a price adjustment available."
            else:
                text = f"You purchased this item at {self.original_store_city} for ${self.original_price}. Another member found it for ${self.lower_price} at {self.cheaper_store_city}. You may have a price adjustment available."
            
            return {
                'text': text,
                'links': links
            }
        
        else:
            # Fallback
            return {
                'text': f"You purchased this item for ${self.original_price}. A lower price of ${self.lower_price} was found. You may have a price adjustment available.",
                'links': []
            }

    @property
    def source_description(self):
        """Generate a plain text description for backwards compatibility."""
        data = self.source_description_data
        text = data['text']
        
        # Add simple text references to receipts
        for link in data['links']:
            if link['type'] == 'original':
                text = text.replace(f"${self.original_price}", f"${self.original_price} (see {link['text']})")
            elif link['type'] == 'cheaper':
                text = text.replace(f"${self.lower_price}", f"${self.lower_price} (see {link['text']})")
        
        return text

    @property
    def source_type_display(self):
        """Get a user-friendly display name for the data source."""
        source_types = {
            'official_promo': 'Official Costco Promotion',
            'user_edit': 'Your Purchase History',
            'ocr_parsed': 'Community Price Data'
        }
        return source_types.get(self.data_source, 'Price Comparison')

    @property
    def confidence_level(self):
        """Get confidence level for this price adjustment."""
        if self.data_source == 'official_promo':
            return 'High'  # Official promotions are highly reliable
        elif self.data_source == 'user_edit':
            return 'High'  # User's own receipts are highly reliable
        elif self.data_source == 'ocr_parsed':
            return 'Medium'  # OCR data from other users is medium confidence
        else:
            return 'Low'

    @property
    def action_required(self):
        """Get the recommended action for this price adjustment."""
        if self.data_source == 'official_promo':
            return f"Visit any Costco customer service with your membership card and list of eligible item #'s. This item's number is {self.item_code}."
        elif self.data_source == 'user_edit':
            return f"Visit any Costco customer service with your membership card and list of eligible item #'s. This item's number is {self.item_code}."
        else:
            return f"Visit any Costco customer service with your membership card and list of eligible item #'s. This item's number is {self.item_code}."

    @property
    def location_context(self):
        """Get location-specific context for the price adjustment."""
        if self.data_source == 'official_promo':
            return {
                'type': 'nationwide',
                'description': 'Available at all Costco locations',
                'store_specific': False
            }
        elif self.original_store_number == self.cheaper_store_number:
            return {
                'type': 'same_store',
                'description': f'Price difference at {self.original_store_city}',
                'store_specific': True
            }
        else:
            return {
                'type': 'different_store',
                'description': f'Lower price found at {self.cheaper_store_city}',
                'store_specific': True
            }

    @property
    def days_remaining(self):
        # For official promotions, calculate days until promotion ends
        if self.data_source == 'official_promo' and self.official_sale_item:
            days_until_promo_ends = (self.official_sale_item.promotion.sale_end_date - timezone.now().date()).days
            return max(0, days_until_promo_ends)
        
        # For all other price adjustments (user_edit, ocr_parsed), use 30-day window from purchase
        # Costco's price adjustment policy is 30 days from the original purchase date
        days_since_purchase = (timezone.now() - self.purchase_date).days
        return max(0, 30 - days_since_purchase)

    @property
    def is_expired(self):
        # For official promotions, check if promotion has ended
        if self.data_source == 'official_promo' and self.official_sale_item:
            return timezone.now().date() > self.official_sale_item.promotion.sale_end_date
        
        # For all other price adjustments (user_edit, ocr_parsed), check if 30 days have passed since purchase
        return self.days_remaining == 0

    def save(self, *args, **kwargs):
        # Don't check expiration on initial creation since created_at won't be set yet
        is_new_record = self.pk is None
        
        # Call super save first so created_at gets set
        super().save(*args, **kwargs)
        
        # Now check expiration after the record has been saved and created_at is set
        if not is_new_record and self.is_expired:
            self.is_active = False
            # Save again to update the is_active field, but avoid recursion
            super().save(update_fields=['is_active'])

    @classmethod
    def get_active_alerts(cls, user):
        """Get all active, non-dismissed alerts for a user."""
        from django.db.models import Q
        
        # Get alerts that are either:
        # 1. Regular price adjustments within 30 days of purchase
        # 2. Official promotions that haven't ended yet
        regular_alerts = Q(
            data_source__in=['ocr_parsed', 'user_edit'],
            purchase_date__gte=timezone.now() - timezone.timedelta(days=30)
        )
        
        official_promo_alerts = Q(
            data_source='official_promo',
            official_sale_item__promotion__sale_end_date__gte=timezone.now().date()
        )
        
        return cls.objects.filter(
            user=user,
            is_active=True,
            is_dismissed=False
        ).filter(regular_alerts | official_promo_alerts)

class CostcoPromotion(models.Model):
    """
    Stores official Costco promotional sale data from monthly booklets.
    """
    title = models.CharField(max_length=255, help_text="e.g., 'January 2024 Member Deals'")
    upload_date = models.DateTimeField(auto_now_add=True)
    processed_date = models.DateTimeField(null=True, blank=True)
    sale_start_date = models.DateField(help_text="When the sale period begins")
    sale_end_date = models.DateField(help_text="When the sale period ends")
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_promotions')
    
    class Meta:
        ordering = ['-sale_start_date']
        verbose_name = 'Costco Promotion'
        verbose_name_plural = 'Costco Promotions'
    
    def __str__(self):
        return f"{self.title} ({self.sale_start_date} - {self.sale_end_date})"

class CostcoPromotionPage(models.Model):
    """
    Individual pages/images from the promotional booklet.
    """
    promotion = models.ForeignKey(CostcoPromotion, on_delete=models.CASCADE, related_name='pages')
    image = models.ImageField(upload_to='promo_booklets/%Y/%m/')
    page_number = models.IntegerField(default=1)
    extracted_text = models.TextField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['promotion', 'page_number']
        unique_together = ['promotion', 'page_number']
        verbose_name = 'Promotion Page'
        verbose_name_plural = 'Promotion Pages'
    
    def __str__(self):
        return f"{self.promotion.title} - Page {self.page_number}"

class OfficialSaleItem(models.Model):
    """
    Individual sale items extracted from promotional booklets.
    """
    promotion = models.ForeignKey(CostcoPromotion, on_delete=models.CASCADE, related_name='sale_items')
    item_code = models.CharField(max_length=50, db_index=True)
    description = models.CharField(max_length=255)
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    instant_rebate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_type = models.CharField(
        max_length=20,
        choices=[
            ('instant_rebate', 'Instant Rebate'),
            ('discount_only', 'Discount Only'),
            ('markdown', 'Markdown Sale'),
            ('member_only', 'Member Only Deal'),
            ('manufacturer', 'Manufacturer Coupon')
        ],
        default='instant_rebate'
    )
    alerts_created = models.IntegerField(default=0, help_text="Number of price adjustment alerts created")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['promotion', 'item_code']
        unique_together = ['promotion', 'item_code']
        indexes = [
            models.Index(fields=['item_code', 'sale_price']),
            models.Index(fields=['promotion', 'sale_type']),
        ]
        verbose_name = 'Official Sale Item'
        verbose_name_plural = 'Official Sale Items'
    
    def __str__(self):
        return f"{self.description} - ${self.sale_price} (was ${self.regular_price})"
    
    @property
    def savings_amount(self):
        if self.regular_price:
            return self.regular_price - self.sale_price
        return self.instant_rebate or Decimal('0.00')
