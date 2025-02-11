from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.db import models
from django.forms import TextInput, Textarea
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg
from .models import (
    Receipt, LineItem, CostcoItem, CostcoWarehouse,
    ItemPriceHistory, ItemWarehousePrice, PriceAdjustmentAlert
)

csrf_protect_m = method_decorator(csrf_protect)

class BaseModelAdmin(admin.ModelAdmin):
    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        return super().changeform_view(request, object_id, form_url, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)

    @csrf_protect_m
    def history_view(self, request, object_id, extra_context=None):
        return super().history_view(request, object_id, extra_context)

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

class LineItemInline(admin.TabularInline):
    model = LineItem
    extra = 0
    readonly_fields = ('total_price',)
    fields = ('item_code', 'description', 'price', 'quantity', 'discount', 'is_taxable', 'instant_savings', 'total_price')
    show_change_link = True
    raw_id_fields = ('receipt',)
    max_num = 100  # Limit number of inline items for performance
    classes = ('collapse',)  # Collapsible by default

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('receipt')  # Optimize queries

@admin.register(Receipt)
class ReceiptAdmin(BaseModelAdmin):
    list_display = ('transaction_number', 'store_location', 'store_city', 'store_number', 
                   'transaction_date', 'total', 'items_count', 'instant_savings_display', 
                   'parsed_successfully', 'user_link')
    list_filter = (
        'store_location', 
        'store_city', 
        'parsed_successfully', 
        'transaction_date',
        'user__username',
        ('instant_savings', admin.EmptyFieldListFilter),
    )
    search_fields = ('transaction_number', 'store_location', 'store_city', 'user__username', 'items__description')
    inlines = [LineItemInline]
    readonly_fields = ('created_at', 'store_city', 'items_count', 'total_savings')
    date_hierarchy = 'transaction_date'
    list_per_page = 50
    show_full_result_count = False  # Performance optimization for large datasets
    raw_id_fields = ('user',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('items')

    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'Items'

    def instant_savings_display(self, obj):
        if obj.instant_savings:
            return format_html('<span style="color: green">${}</span>', obj.instant_savings)
        return '-'
    instant_savings_display.short_description = 'Savings'

    def user_link(self, obj):
        return format_html('<a href="/admin/auth/user/{}/">{}</a>', obj.user.id, obj.user.username)
    user_link.short_description = 'User'

@admin.register(PriceAdjustmentAlert)
class PriceAdjustmentAlertAdmin(BaseModelAdmin):
    list_display = ('item_description', 'user', 'original_store_city', 'cheaper_store_city',
                   'price_difference_display', 'days_remaining', 'status_display', 'created_at')
    list_filter = (
        'is_active', 
        'is_dismissed', 
        'original_store_city', 
        'cheaper_store_city',
        'user__username',
        'created_at'
    )
    search_fields = ('item_description', 'item_code', 'user__username', 
                    'original_store_city', 'cheaper_store_city')
    readonly_fields = ('price_difference', 'days_remaining', 'is_expired', 'created_at')
    date_hierarchy = 'purchase_date'
    list_per_page = 50
    raw_id_fields = ('user',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def price_difference_display(self, obj):
        return format_html('<span style="color: green">${:.2f}</span>', obj.price_difference)
    price_difference_display.short_description = "Potential Savings"

    def status_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red">Expired</span>')
        if obj.is_dismissed:
            return format_html('<span style="color: grey">Dismissed</span>')
        return format_html('<span style="color: green">Active</span>')
    status_display.short_description = "Status"

@admin.register(LineItem)
class LineItemAdmin(BaseModelAdmin):
    list_display = ('item_code', 'description', 'price', 'quantity', 'total_price', 
                   'instant_savings_display', 'receipt_link')
    list_filter = (
        'receipt__store_location',
        'is_taxable',
        ('instant_savings', admin.EmptyFieldListFilter),
        'receipt__transaction_date'
    )
    search_fields = ('item_code', 'description', 'receipt__transaction_number')
    readonly_fields = ('total_price',)
    raw_id_fields = ('receipt',)
    list_per_page = 100
    show_full_result_count = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('receipt')

    def instant_savings_display(self, obj):
        if obj.instant_savings:
            return format_html('<span style="color: green">${}</span>', obj.instant_savings)
        return '-'
    instant_savings_display.short_description = 'Savings'

    def receipt_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/receipt/{}/">{}</a>', 
                         obj.receipt.id, obj.receipt.transaction_number)
    receipt_link.short_description = 'Receipt'

@admin.register(CostcoItem)
class CostcoItemAdmin(BaseModelAdmin):
    list_display = ('item_code', 'description', 'current_price', 'price_history_count', 
                   'last_price_update', 'updated_at')
    list_filter = (('last_price_update', admin.EmptyFieldListFilter),)
    search_fields = ('item_code', 'description')
    readonly_fields = ('last_price_update', 'created_at', 'updated_at', 'price_history_count')
    ordering = ('item_code',)
    list_per_page = 100

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            price_history_count=Count('price_history')
        )

    def price_history_count(self, obj):
        return obj.price_history_count
    price_history_count.short_description = 'Price Changes'
    price_history_count.admin_order_field = 'price_history_count'

@admin.register(CostcoWarehouse)
class CostcoWarehouseAdmin(BaseModelAdmin):
    list_display = ('store_number', 'location', 'city', 'state', 'item_count', 'updated_at')
    list_filter = ('state', 'city')
    search_fields = ('store_number', 'location', 'city', 'state')
    readonly_fields = ('created_at', 'updated_at', 'item_count')
    ordering = ('store_number',)
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            item_count=Count('itemwarehouseprice')
        )

    def item_count(self, obj):
        return obj.item_count
    item_count.short_description = 'Items Tracked'
    item_count.admin_order_field = 'item_count'

@admin.register(ItemPriceHistory)
class ItemPriceHistoryAdmin(BaseModelAdmin):
    list_display = ('item_link', 'warehouse_link', 'old_price', 'new_price', 
                   'price_change_display', 'date_changed')
    list_filter = ('warehouse', 'date_changed')
    search_fields = ('item__item_code', 'item__description', 'warehouse__store_number')
    readonly_fields = ('created_at',)
    ordering = ('-date_changed',)
    raw_id_fields = ('item', 'warehouse')
    list_per_page = 100
    show_full_result_count = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('item', 'warehouse')

    def price_change_display(self, obj):
        if obj.old_price and obj.new_price:
            change = obj.new_price - obj.old_price
            color = 'red' if change > 0 else 'green'
            return format_html('<span style="color: {}">{:+.2f}</span>', color, change)
        return '-'
    price_change_display.short_description = 'Price Change'

    def item_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/costcoitem/{}/">{} - {}</a>', 
                         obj.item.item_code, obj.item.item_code, obj.item.description)
    item_link.short_description = 'Item'

    def warehouse_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/costcowarehouse/{}/">{}</a>', 
                         obj.warehouse.store_number, obj.warehouse.location)
    warehouse_link.short_description = 'Warehouse'

@admin.register(ItemWarehousePrice)
class ItemWarehousePriceAdmin(BaseModelAdmin):
    list_display = ('item_link', 'warehouse_link', 'price', 'last_seen', 'updated_at')
    list_filter = ('warehouse', 'last_seen')
    search_fields = ('item__item_code', 'item__description', 'warehouse__store_number')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('item', 'warehouse')
    raw_id_fields = ('item', 'warehouse')
    list_per_page = 100
    show_full_result_count = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('item', 'warehouse')

    def item_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/costcoitem/{}/">{} - {}</a>', 
                         obj.item.item_code, obj.item.item_code, obj.item.description)
    item_link.short_description = 'Item'

    def warehouse_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/costcowarehouse/{}/">{}</a>', 
                         obj.warehouse.store_number, obj.warehouse.location)
    warehouse_link.short_description = 'Warehouse'
