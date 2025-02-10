from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from .models import (
    Receipt, LineItem, CostcoItem, CostcoWarehouse,
    ItemPriceHistory, ItemWarehousePrice, PriceAdjustmentAlert
)

csrf_protect_m = method_decorator(csrf_protect)

class LineItemInline(admin.TabularInline):
    model = LineItem
    extra = 0
    readonly_fields = ('total_price',)

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('transaction_number', 'store_location', 'store_city', 'store_number', 
                   'transaction_date', 'total', 'parsed_successfully')
    list_filter = ('store_location', 'store_city', 'parsed_successfully', 'transaction_date')
    search_fields = ('transaction_number', 'store_location', 'store_city', 'user__username')
    inlines = [LineItemInline]
    readonly_fields = ('created_at', 'store_city')
    date_hierarchy = 'transaction_date'

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)

@admin.register(PriceAdjustmentAlert)
class PriceAdjustmentAlertAdmin(admin.ModelAdmin):
    list_display = ('item_description', 'user', 'original_store_city', 'cheaper_store_city',
                   'price_difference', 'days_remaining', 'is_active', 'is_dismissed')
    list_filter = ('is_active', 'is_dismissed', 'original_store_city', 'cheaper_store_city')
    search_fields = ('item_description', 'item_code', 'user__username')
    readonly_fields = ('price_difference', 'days_remaining', 'is_expired', 'created_at')
    date_hierarchy = 'purchase_date'
    
    def price_difference(self, obj):
        return f"${obj.price_difference:.2f}"
    price_difference.short_description = "Potential Savings"

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)

@admin.register(LineItem)
class LineItemAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'description', 'price', 'quantity', 'discount')
    list_filter = ('receipt__store_location',)
    search_fields = ('item_code', 'description')
    readonly_fields = ('total_price',)

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)

@admin.register(CostcoItem)
class CostcoItemAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'description', 'current_price', 'last_price_update', 'updated_at')
    search_fields = ('item_code', 'description')
    readonly_fields = ('last_price_update', 'created_at', 'updated_at')
    ordering = ('item_code',)

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)

@admin.register(CostcoWarehouse)
class CostcoWarehouseAdmin(admin.ModelAdmin):
    list_display = ('store_number', 'location', 'updated_at')
    search_fields = ('store_number', 'location')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('store_number',)

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)

@admin.register(ItemPriceHistory)
class ItemPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('item', 'warehouse', 'old_price', 'new_price', 'date_changed')
    list_filter = ('warehouse', 'date_changed')
    search_fields = ('item__item_code', 'item__description', 'warehouse__store_number')
    readonly_fields = ('created_at',)
    ordering = ('-date_changed',)
    raw_id_fields = ('item', 'warehouse')

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)

@admin.register(ItemWarehousePrice)
class ItemWarehousePriceAdmin(admin.ModelAdmin):
    list_display = ('item', 'warehouse', 'price', 'last_seen', 'updated_at')
    list_filter = ('warehouse', 'last_seen')
    search_fields = ('item__item_code', 'item__description', 'warehouse__store_number')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('item', 'warehouse')
    raw_id_fields = ('item', 'warehouse')

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context)

    @csrf_protect_m
    def delete_view(self, request, object_id, extra_context=None):
        return super().delete_view(request, object_id, extra_context)
