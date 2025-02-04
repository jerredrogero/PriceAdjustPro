from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Receipt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='receipts/')
    store_location = models.CharField(max_length=255, blank=True)
    store_number = models.CharField(max_length=50, blank=True)
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
        return f"Receipt {self.id} - {self.store_location} ({self.transaction_date})"

    class Meta:
        ordering = ['-transaction_date']

class LineItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    item_code = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)
    discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_taxable = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.description} ({self.item_code})"

    class Meta:
        ordering = ['id']

    @property
    def total_price(self):
        base_price = self.price * self.quantity
        if self.discount:
            return base_price - self.discount
        return base_price
