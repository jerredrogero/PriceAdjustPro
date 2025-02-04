from django.contrib import admin
from .models import Receipt, LineItem

class LineItemInline(admin.TabularInline):
    model = LineItem
    extra = 0
    readonly_fields = ('total_price',)

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('store_location', 'store_number', 'transaction_date', 'total', 'parsed_successfully')
    list_filter = ('store_location', 'parsed_successfully', 'transaction_date')
    search_fields = ('store_location', 'store_number', 'user__username')
    inlines = [LineItemInline]
    readonly_fields = ('created_at',)
    date_hierarchy = 'transaction_date'

@admin.register(LineItem)
class LineItemAdmin(admin.ModelAdmin):
    list_display = ('receipt', 'description', 'item_code', 'price', 'quantity', 'discount', 'total_price')
    list_filter = ('is_taxable',)
    search_fields = ('description', 'item_code', 'receipt__store_location')
    readonly_fields = ('total_price',)
