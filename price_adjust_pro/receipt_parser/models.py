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
    file = models.FileField(upload_to='receipts/%Y/%m/%d/')  # Organize by date
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

    @property
    def total_items(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def total_savings(self):
        return self.instant_savings or Decimal('0.00')

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
    instant_savings = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
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

    @property
    def days_remaining(self):
        days_since_purchase = (timezone.now() - self.purchase_date).days
        return max(0, 30 - days_since_purchase)

    @property
    def is_expired(self):
        return self.days_remaining == 0

    def save(self, *args, **kwargs):
        if self.is_expired:
            self.is_active = False
        super().save(*args, **kwargs)

    @classmethod
    def get_active_alerts(cls, user):
        """Get all active, non-dismissed alerts for a user."""
        return cls.objects.filter(
            user=user,
            is_active=True,
            is_dismissed=False,
            purchase_date__gte=timezone.now() - timezone.timedelta(days=30)
        )
