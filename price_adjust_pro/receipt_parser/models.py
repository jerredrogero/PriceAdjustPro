from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import RegexValidator

# Create your models here.

class Receipt(models.Model):
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
        null=False,  # Enforce user association
        blank=False
    )
    file = models.FileField(upload_to='receipts/')
    store_location = models.CharField(max_length=255, blank=True)
    store_number = models.CharField(max_length=50, blank=True)
    store_city = models.CharField(max_length=100, blank=True)  # Added for city tracking
    transaction_date = models.DateTimeField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ebt_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    instant_savings = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    parsed_successfully = models.BooleanField(default=False)
    parse_error = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Receipt {self.transaction_number} - {self.store_location} ({self.transaction_date})"

    def save(self, *args, **kwargs):
        # Extract city from store_location if not set
        if not self.store_city and self.store_location:
            # Assuming format like "Costco Athens #1621"
            parts = self.store_location.split()
            if len(parts) > 1:
                # Remove "Costco" and store number, join remaining words as city
                self.store_city = ' '.join(parts[1:-1])
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-transaction_date']
        unique_together = ['user', 'transaction_number']  # Make transaction number unique per user
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'transaction_number'],
                name='unique_user_transaction'
            )
        ]

class LineItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    item_code = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)
    discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_taxable = models.BooleanField(default=False)
    instant_savings = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Price before instant savings

    def __str__(self):
        return f"{self.description} - ${self.price}"

    @property
    def total_price(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        # If we have instant savings, store the original price
        if self.instant_savings and not self.original_price:
            self.original_price = self.price + self.instant_savings
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['id']

class CostcoItem(models.Model):
    item_code = models.CharField(max_length=50, primary_key=True)
    description = models.CharField(max_length=255)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    last_price_update = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} ({self.item_code})"

    class Meta:
        ordering = ['item_code']

    def update_price(self, new_price, warehouse, date_seen):
        """
        Update the item's price if it has changed and record the change in history.
        Returns True if price was updated, False if no change was needed.
        """
        if self.current_price != new_price:
            # Record the price change in history
            ItemPriceHistory.objects.create(
                item=self,
                warehouse=warehouse,
                old_price=self.current_price,
                new_price=new_price,
                date_changed=date_seen
            )
            
            # Update current price
            self.current_price = new_price
            self.last_price_update = date_seen
            self.save()
            return True
        return False

class CostcoWarehouse(models.Model):
    store_number = models.CharField(max_length=50, primary_key=True)
    location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.location} (#{self.store_number})"

    class Meta:
        ordering = ['store_number']

class ItemPriceHistory(models.Model):
    """
    Records the history of price changes for items.
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

    def __str__(self):
        return f"{self.item} price changed from ${self.old_price} to ${self.new_price} at {self.warehouse}"

class ItemWarehousePrice(models.Model):
    """
    Tracks the current price of items at specific warehouses.
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

    def __str__(self):
        return f"{self.item} at {self.warehouse}: ${self.price}"

    @classmethod
    def update_price(cls, item, warehouse, new_price, date_seen):
        """
        Update the price for an item at a specific warehouse if it has changed.
        Returns True if price was updated, False if no change was needed.
        """
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
        # Auto-deactivate if expired
        if self.is_expired:
            self.is_active = False
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'item_code']),
            models.Index(fields=['purchase_date']),
            models.Index(fields=['is_active']),
        ]
