from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.db import models
from django.forms import TextInput, Textarea
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, F, Window
from django.db.models.functions import ExtractYear, ExtractMonth, TruncDate
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponse
import csv
import json
from datetime import datetime
from .models import (
    Receipt, LineItem, CostcoItem, CostcoWarehouse,
    ItemPriceHistory, ItemWarehousePrice, PriceAdjustmentAlert,
    CostcoPromotion, CostcoPromotionPage, OfficialSaleItem
)
from .utils import process_official_promotion
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, reverse
import os
import logging
from .utils import process_official_promotion

logger = logging.getLogger(__name__)

# Customize admin site
admin.site.site_header = 'PriceAdjustPro Administration'
admin.site.site_title = 'PriceAdjustPro Admin'
admin.site.index_title = 'Dashboard'

# Unregister default User and Group admin
admin.site.unregister(User)
admin.site.unregister(Group)

# Custom User admin with limited fields and hijack functionality
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'date_joined', 'last_login', 'is_active', 'is_staff', 'hijack_user_button')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    readonly_fields = ('date_joined', 'last_login')
    ordering = ('-date_joined',)
    
    # Limit what fields can be changed
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Limit what fields are shown when creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )
    
    def hijack_user_button(self, obj):
        """Custom hijack button for user admin."""
        if obj.pk == self.request.user.pk:
            return format_html('<span style="color: grey;">Cannot hijack yourself</span>')
        
        if not self.request.user.is_superuser:
            return format_html('<span style="color: grey;">Permission denied</span>')
        
        hijack_url = f'/hijack/{obj.pk}/?next=/'
        return format_html(
            '<a href="{}" class="button" style="background-color: #417690; color: white; padding: 4px 8px; '
            'text-decoration: none; border-radius: 3px; font-size: 11px;">🔓 Hijack User</a>',
            hijack_url
        )
    hijack_user_button.short_description = 'Hijack'
    hijack_user_button.allow_tags = True
    
    def get_list_display(self, request):
        """Store request for use in hijack_user_button method."""
        self.request = request
        return super().get_list_display(request)

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

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete objects
        return request.user.is_superuser

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
                   'transaction_date', 'total_display', 'items_count', 'instant_savings_display', 
                   'parse_status', 'user_link')
    list_filter = (
        'store_location', 
        'store_city', 
        'parsed_successfully', 
        'transaction_date',
        ('user', admin.RelatedOnlyFieldListFilter),
        ('instant_savings', admin.EmptyFieldListFilter),
    )
    search_fields = ('transaction_number', 'store_location', 'store_city', 'user__username', 'items__description')
    inlines = [LineItemInline]
    readonly_fields = ('created_at', 'store_city', 'items_count', 'total_savings_display', 'parse_status', 'parse_error')
    date_hierarchy = 'transaction_date'
    list_per_page = 50
    show_full_result_count = False
    raw_id_fields = ('user',)
    actions = ['mark_as_parsed', 'export_as_csv', 'export_as_json']
    ordering = ('-transaction_date',)

    def get_queryset(self, request):
        # Non-superusers can only see their own receipts
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs.select_related('user').prefetch_related('items')

    def has_change_permission(self, request, obj=None):
        # Users can only edit their own receipts
        if not obj or request.user.is_superuser:
            return True
        return obj.user == request.user

    def get_readonly_fields(self, request, obj=None):
        # Make more fields readonly for non-superusers
        if not request.user.is_superuser:
            return self.readonly_fields + ('user', 'transaction_number', 'transaction_date')
        return self.readonly_fields

    def total_display(self, obj):
        return format_html('${}', '{:.2f}'.format(float(obj.total)))
    total_display.short_description = 'Total'

    def total_savings_display(self, obj):
        if obj.instant_savings:
            return format_html('${}', '{:.2f}'.format(float(obj.instant_savings)))
        return '-'
    total_savings_display.short_description = 'Total Savings'

    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'Items'

    def instant_savings_display(self, obj):
        if obj.instant_savings:
            return format_html('<span style="color: green">${}</span>', 
                '{:.2f}'.format(float(obj.instant_savings)))
        return '-'
    instant_savings_display.short_description = 'Savings'

    def user_link(self, obj):
        return format_html('<a href="/admin/auth/user/{}/">{}</a>', obj.user.id, obj.user.username)
    user_link.short_description = 'User'

    def parse_status(self, obj):
        if obj.parsed_successfully:
            return format_html('<span style="color: green">✓ Parsed Successfully</span>')
        else:
            error_msg = obj.parse_error if obj.parse_error else 'Unknown parsing error'
            return format_html(
                '<span style="color: red">⚠ Parse Error</span>'
                '<br><small style="color: grey">{}</small>', 
                error_msg
            )
    parse_status.short_description = 'Parse Status'

    def mark_as_parsed(self, request, queryset):
        """Mark selected receipts as successfully parsed if they have all required data."""
        updated = 0
        for receipt in queryset:
            if (receipt.transaction_number and 
                receipt.items.exists() and 
                receipt.total and 
                receipt.transaction_date):
                receipt.parsed_successfully = True
                receipt.parse_error = None
                receipt.save()
                updated += 1
        self.message_user(request, f'{updated} receipts marked as successfully parsed.')
    mark_as_parsed.short_description = "Mark selected receipts as successfully parsed"

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = ['transaction_number', 'store_location', 'store_city', 'store_number',
                      'transaction_date', 'total', 'subtotal', 'tax', 'instant_savings',
                      'parsed_successfully', 'user__username']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=receipts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        # Write header
        writer.writerow(field_names)
        
        # Write data
        for obj in queryset:
            row = []
            for field in field_names:
                if field == 'user__username':
                    row.append(obj.user.username)
                else:
                    value = getattr(obj, field)
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    row.append(value)
            writer.writerow(row)

        return response
    export_as_csv.short_description = "Export selected receipts as CSV"

    def export_as_json(self, request, queryset):
        data = []
        for receipt in queryset:
            receipt_data = {
                'transaction_number': receipt.transaction_number,
                'store_location': receipt.store_location,
                'store_city': receipt.store_city,
                'store_number': receipt.store_number,
                'transaction_date': receipt.transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
                'total': str(receipt.total),
                'subtotal': str(receipt.subtotal),
                'tax': str(receipt.tax),
                'instant_savings': str(receipt.instant_savings) if receipt.instant_savings else None,
                'parsed_successfully': receipt.parsed_successfully,
                'user': receipt.user.username,
                'items': [{
                    'item_code': item.item_code,
                    'description': item.description,
                    'price': str(item.price),
                    'quantity': item.quantity,
                    'is_taxable': item.is_taxable,
                    'instant_savings': str(item.instant_savings) if item.instant_savings else None,
                } for item in receipt.items.all()]
            }
            data.append(receipt_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=receipts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected receipts as JSON"

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
    actions = ['mark_as_expired', 'mark_as_dismissed', 'export_as_csv', 'export_as_json']

    def mark_as_expired(self, request, queryset):
        updated = queryset.update(is_active=False, is_expired=True)
        self.message_user(request, f'{updated} alerts marked as expired.')
    mark_as_expired.short_description = "Mark selected alerts as expired"
    
    def mark_as_dismissed(self, request, queryset):
        updated = queryset.update(is_dismissed=True)
        self.message_user(request, f'{updated} alerts marked as dismissed.')
    mark_as_dismissed.short_description = "Mark selected alerts as dismissed"

    def get_queryset(self, request):
        return super().get_queryset(request)\
            .select_related('user')\
            .annotate(
                potential_savings=F('original_price') - F('lower_price'),
                days_active=TruncDate('created_at') - TruncDate(F('purchase_date'))
            )

    def price_difference_display(self, obj):
        return format_html('<span style="color: green">${}</span>', 
            '{:.2f}'.format(float(obj.price_difference)))
    price_difference_display.short_description = "Potential Savings"

    def status_display(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red">Expired</span>')
        if obj.is_dismissed:
            return format_html('<span style="color: grey">Dismissed</span>')
        return format_html('<span style="color: green">Active</span>')
    status_display.short_description = "Status"

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = ['item_code', 'item_description', 'original_price', 'lower_price',
                      'original_store_city', 'cheaper_store_city', 'purchase_date',
                      'days_remaining', 'is_active', 'is_dismissed', 'user__username']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=price_adjustments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        # Write header
        writer.writerow(field_names)
        
        # Write data
        for obj in queryset:
            row = []
            for field in field_names:
                if field == 'user__username':
                    row.append(obj.user.username)
                else:
                    value = getattr(obj, field)
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    row.append(value)
            writer.writerow(row)

        return response
    export_as_csv.short_description = "Export selected alerts as CSV"

    def export_as_json(self, request, queryset):
        data = []
        for alert in queryset:
            alert_data = {
                'item_code': alert.item_code,
                'item_description': alert.item_description,
                'original_price': str(alert.original_price),
                'lower_price': str(alert.lower_price),
                'price_difference': str(alert.price_difference),
                'original_store_city': alert.original_store_city,
                'cheaper_store_city': alert.cheaper_store_city,
                'purchase_date': alert.purchase_date.strftime('%Y-%m-%d %H:%M:%S'),
                'days_remaining': alert.days_remaining,
                'is_active': alert.is_active,
                'is_dismissed': alert.is_dismissed,
                'user': alert.user.username,
            }
            data.append(alert_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=price_adjustments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected alerts as JSON"

@admin.register(LineItem)
class LineItemAdmin(BaseModelAdmin):
    list_display = ('item_code', 'description', 'price', 'quantity', 'total_price', 
                   'instant_savings_display', 'username', 'receipt_link')
    list_filter = (
        'receipt__store_location',
        'receipt__user__username',
        'is_taxable',
        ('instant_savings', admin.EmptyFieldListFilter),
        'receipt__transaction_date'
    )
    search_fields = ('item_code', 'description', 'receipt__transaction_number', 'receipt__user__username')
    readonly_fields = ('total_price',)
    raw_id_fields = ('receipt',)
    list_per_page = 100
    show_full_result_count = False
    actions = ['export_as_csv', 'export_as_json']

    def get_queryset(self, request):
        return super().get_queryset(request)\
            .select_related('receipt', 'receipt__user')\
            .annotate(
                price_with_savings=F('price') - F('instant_savings'),
                total_with_savings=F('price_with_savings') * F('quantity')
            )

    def instant_savings_display(self, obj):
        if obj.instant_savings:
            return format_html('<span style="color: green">${}</span>', obj.instant_savings)
        return '-'
    instant_savings_display.short_description = 'Savings'

    def username(self, obj):
        if obj.receipt and obj.receipt.user:
            return format_html('<a href="/admin/auth/user/{}/">{}</a>', 
                             obj.receipt.user.id, obj.receipt.user.username)
        return '-'
    username.short_description = 'User'

    def receipt_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/receipt/{}/">{}</a>', 
                         obj.receipt.id, obj.receipt.transaction_number)
    receipt_link.short_description = 'Receipt'

    def export_as_csv(self, request, queryset):
        field_names = ['item_code', 'description', 'price', 'quantity', 'discount',
                      'is_taxable', 'instant_savings', 'original_price', 'username', 'receipt__transaction_number']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=line_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        writer.writerow(['item_code', 'description', 'price', 'quantity', 'discount',
                        'is_taxable', 'instant_savings', 'original_price', 'username', 'receipt_transaction_number'])
        for obj in queryset:
            row = []
            for field in field_names:
                if field == 'receipt__transaction_number':
                    row.append(obj.receipt.transaction_number)
                elif field == 'username':
                    row.append(obj.receipt.user.username if obj.receipt and obj.receipt.user else '')
                else:
                    value = getattr(obj, field)
                    row.append(str(value) if value is not None else '')
            writer.writerow(row)

        return response
    export_as_csv.short_description = "Export selected items as CSV"

    def export_as_json(self, request, queryset):
        data = []
        for item in queryset:
            item_data = {
                'item_code': item.item_code,
                'description': item.description,
                'price': str(item.price),
                'quantity': item.quantity,
                'discount': str(item.discount) if item.discount else None,
                'is_taxable': item.is_taxable,
                'instant_savings': str(item.instant_savings) if item.instant_savings else None,
                'original_price': str(item.original_price) if item.original_price else None,
                'username': item.receipt.user.username if item.receipt and item.receipt.user else None,
                'receipt': {
                    'transaction_number': item.receipt.transaction_number,
                    'store_location': item.receipt.store_location,
                    'transaction_date': item.receipt.transaction_date.strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            data.append(item_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=line_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected items as JSON"

@admin.register(CostcoItem)
class CostcoItemAdmin(BaseModelAdmin):
    list_display = ('item_code', 'description', 'current_price', 'price_history_count', 
                   'last_price_update', 'updated_at')
    list_filter = (('last_price_update', admin.EmptyFieldListFilter),)
    search_fields = ('item_code', 'description')
    readonly_fields = ('last_price_update', 'created_at', 'updated_at', 'price_history_count')
    ordering = ('item_code',)
    list_per_page = 100
    actions = ['export_as_csv', 'export_as_json']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            price_history_count=Count('price_history'),
            # Remove problematic annotations
            # avg_price=Avg('warehouse_prices__price'),
            # price_volatility=Window(
            #     expression=Avg('price_history__new_price'),
            #     order_by=F('price_history__date_changed').desc()
            # )
        )

    def price_history_count(self, obj):
        return obj.price_history_count
    price_history_count.short_description = 'Price Changes'
    price_history_count.admin_order_field = 'price_history_count'

    def export_as_csv(self, request, queryset):
        field_names = ['item_code', 'description', 'current_price', 'last_price_update']
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=costco_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            row = []
            for field in field_names:
                value = getattr(obj, field)
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                row.append(str(value) if value is not None else '')
            writer.writerow(row)

        return response
    export_as_csv.short_description = "Export selected items as CSV"

    def export_as_json(self, request, queryset):
        data = []
        for item in queryset:
            item_data = {
                'item_code': item.item_code,
                'description': item.description,
                'current_price': str(item.current_price) if item.current_price else None,
                'last_price_update': item.last_price_update.strftime('%Y-%m-%d %H:%M:%S') if item.last_price_update else None,
                'price_history': [{
                    'date': history.date_changed.strftime('%Y-%m-%d %H:%M:%S'),
                    'old_price': str(history.old_price) if history.old_price else None,
                    'new_price': str(history.new_price),
                    'warehouse': history.warehouse.store_number
                } for history in item.price_history.all()]
            }
            data.append(item_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=costco_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected items as JSON"

@admin.register(CostcoWarehouse)
class CostcoWarehouseAdmin(BaseModelAdmin):
    list_display = ('store_number', 'location', 'city', 'state', 'item_count', 'updated_at')
    list_filter = ('state', 'city')
    search_fields = ('store_number', 'location', 'city', 'state')
    readonly_fields = ('created_at', 'updated_at', 'item_count')
    ordering = ('store_number',)
    list_per_page = 50
    actions = ['export_as_csv', 'export_as_json']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            item_count=Count('itemwarehouseprice')
        )

    def item_count(self, obj):
        return obj.item_count
    item_count.short_description = 'Items Tracked'
    item_count.admin_order_field = 'item_count'

    def export_as_csv(self, request, queryset):
        field_names = ['store_number', 'location', 'city', 'state']
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=warehouses_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])

        return response
    export_as_csv.short_description = "Export selected warehouses as CSV"

    def export_as_json(self, request, queryset):
        data = []
        for warehouse in queryset:
            warehouse_data = {
                'store_number': warehouse.store_number,
                'location': warehouse.location,
                'city': warehouse.city,
                'state': warehouse.state,
                'current_prices': [{
                    'item_code': price.item.item_code,
                    'description': price.item.description,
                    'price': str(price.price),
                    'last_seen': price.last_seen.strftime('%Y-%m-%d %H:%M:%S')
                } for price in warehouse.itemwarehouseprice_set.select_related('item').all()]
            }
            data.append(warehouse_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=warehouses_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected warehouses as JSON"

@admin.register(ItemPriceHistory)
class ItemPriceHistoryAdmin(BaseModelAdmin):
    list_display = ('item', 'warehouse', 'old_price', 'new_price', 'date_changed')
    list_filter = ('warehouse', 'date_changed')
    search_fields = ('item__item_code', 'item__description', 'warehouse__store_number')
    raw_id_fields = ('item', 'warehouse')
    ordering = ('-date_changed',)
    actions = ['export_as_csv', 'export_as_json']

    def export_as_csv(self, request, queryset):
        field_names = ['item__item_code', 'item__description', 'warehouse__store_number',
                      'old_price', 'new_price', 'date_changed']
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=price_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        writer.writerow(['item_code', 'description', 'store_number', 'old_price', 'new_price', 'date_changed'])
        for obj in queryset:
            row = [
                obj.item.item_code,
                obj.item.description,
                obj.warehouse.store_number,
                str(obj.old_price) if obj.old_price else '',
                str(obj.new_price),
                obj.date_changed.strftime('%Y-%m-%d %H:%M:%S')
            ]
            writer.writerow(row)

        return response
    export_as_csv.short_description = "Export selected price history as CSV"

    def export_as_json(self, request, queryset):
        data = []
        for history in queryset:
            history_data = {
                'item': {
                    'item_code': history.item.item_code,
                    'description': history.item.description
                },
                'warehouse': {
                    'store_number': history.warehouse.store_number,
                    'location': history.warehouse.location
                },
                'old_price': str(history.old_price) if history.old_price else None,
                'new_price': str(history.new_price),
                'date_changed': history.date_changed.strftime('%Y-%m-%d %H:%M:%S'),
                'price_change': str(float(history.new_price) - float(history.old_price)) if history.old_price else None
            }
            data.append(history_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=price_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected price history as JSON"

@admin.register(ItemWarehousePrice)
class ItemWarehousePriceAdmin(BaseModelAdmin):
    list_display = ('item', 'warehouse', 'price', 'last_seen')
    list_filter = ('warehouse', 'last_seen')
    search_fields = ('item__item_code', 'item__description', 'warehouse__store_number')
    raw_id_fields = ('item', 'warehouse')
    ordering = ('item', 'warehouse')
    actions = ['export_as_csv', 'export_as_json']

    def export_as_csv(self, request, queryset):
        field_names = ['item__item_code', 'item__description', 'warehouse__store_number',
                      'price', 'last_seen']
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=current_prices_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        writer.writerow(['item_code', 'description', 'store_number', 'price', 'last_seen'])
        for obj in queryset:
            row = [
                obj.item.item_code,
                obj.item.description,
                obj.warehouse.store_number,
                str(obj.price),
                obj.last_seen.strftime('%Y-%m-%d %H:%M:%S')
            ]
            writer.writerow(row)

        return response
    export_as_csv.short_description = "Export selected prices as CSV"

    def export_as_json(self, request, queryset):
        data = []
        for price in queryset:
            price_data = {
                'item': {
                    'item_code': price.item.item_code,
                    'description': price.item.description,
                    'current_price': str(price.item.current_price) if price.item.current_price else None
                },
                'warehouse': {
                    'store_number': price.warehouse.store_number,
                    'location': price.warehouse.location,
                    'city': price.warehouse.city,
                    'state': price.warehouse.state
                },
                'price': str(price.price),
                'last_seen': price.last_seen.strftime('%Y-%m-%d %H:%M:%S')
            }
            data.append(price_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=current_prices_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected prices as JSON"

class CostcoPromotionPageInline(admin.TabularInline):
    model = CostcoPromotionPage
    extra = 1
    readonly_fields = ('uploaded_at', 'is_processed', 'processing_error')
    fields = ('page_number', 'image', 'is_processed', 'processing_error')

class OfficialSaleItemInline(admin.TabularInline):
    model = OfficialSaleItem
    extra = 0
    readonly_fields = ('alerts_created', 'savings_amount', 'created_at')
    fields = ('item_code', 'description', 'regular_price', 'sale_price', 'instant_rebate', 'sale_type', 'alerts_created')

@admin.register(CostcoPromotion)
class CostcoPromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'sale_start_date', 'sale_end_date', 'is_processed', 'pages_count', 'items_count', 'alerts_count')
    list_filter = ('is_processed', 'sale_start_date', 'uploaded_by')
    search_fields = ('title',)
    readonly_fields = ('upload_date', 'processed_date', 'uploaded_by', 'pages_count', 'items_count', 'alerts_count')
    inlines = [CostcoPromotionPageInline, OfficialSaleItemInline]
    
    actions = ['process_promotions', 'process_promotions_safe']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:promotion_id>/bulk-upload/',
                self.admin_site.admin_view(self.bulk_upload_view),
                name='receipt_parser_costcopromotion_bulk_upload',
            ),
        ]
        return custom_urls + urls
    
    def bulk_upload_view(self, request, promotion_id):
        """Custom view for bulk uploading promotional images."""
        promotion = get_object_or_404(CostcoPromotion, id=promotion_id)
        
        if request.method == 'POST':
            uploaded_files = request.FILES.getlist('images')
            if not uploaded_files:
                messages.error(request, 'No files were uploaded.')
                return redirect(request.path)
            
            # Validate file types
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif', '.bmp']
            valid_files = []
            
            for file in uploaded_files:
                file_ext = os.path.splitext(file.name)[1].lower()
                if file_ext in allowed_extensions:
                    valid_files.append(file)
                else:
                    messages.warning(request, f'Skipped invalid file type: {file.name}')
            
            if not valid_files:
                messages.error(request, 'No valid image files found.')
                return redirect(request.path)
            
            # Get the next page number
            last_page = promotion.pages.order_by('-page_number').first()
            next_page_number = (last_page.page_number + 1) if last_page else 1
            
            # Create CostcoPromotionPage records
            created_pages = 0
            for i, file in enumerate(valid_files):
                try:
                    page = CostcoPromotionPage.objects.create(
                        promotion=promotion,
                        image=file,
                        page_number=next_page_number + i
                    )
                    created_pages += 1
                except Exception as e:
                    messages.error(request, f'Error uploading {file.name}: {str(e)}')
            
            if created_pages > 0:
                messages.success(request, f'Successfully uploaded {created_pages} promotional page(s).')
            
            # Redirect to the promotion change page
            return redirect('admin:receipt_parser_costcopromotion_change', promotion.id)
        
        # GET request - show the upload form
        context = {
            'promotion': promotion,
            'title': f'Bulk Upload Images for {promotion.title}',
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request, promotion),
        }
        return render(request, 'admin/receipt_parser/bulk_upload.html', context)
    
    def pages_count(self, obj):
        return obj.pages.count()
    pages_count.short_description = "Pages"
    
    def items_count(self, obj):
        return obj.sale_items.count()
    items_count.short_description = "Sale Items"
    
    def alerts_count(self, obj):
        return sum(item.alerts_created for item in obj.sale_items.all())
    alerts_count.short_description = "Alerts Created"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set on creation
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    def process_promotions(self, request, queryset):
        """Admin action to process selected promotions with safety limits."""
        processed_count = 0
        for promotion in queryset:
            if not promotion.is_processed:
                try:
                    # Limit to 10 pages per request to prevent timeouts
                    max_pages = 10
                    total_pages = promotion.pages.count()
                    
                    if total_pages > max_pages:
                        messages.warning(
                            request,
                            f"'{promotion.title}' has {total_pages} pages. Processing first {max_pages} to prevent timeout. "
                            f"Use the management command for full processing: python manage.py process_promotions --promotion-id {promotion.id}"
                        )
                    
                    results = process_official_promotion(promotion.id, max_pages=max_pages)
                    if 'error' not in results:
                        processed_count += 1
                        messages.success(
                            request, 
                            f"Processed '{promotion.title}': {results['pages_processed']}/{total_pages} pages, "
                            f"{results['items_extracted']} items, {results['alerts_created']} alerts created"
                        )
                        
                        if total_pages > max_pages:
                            remaining = total_pages - results['pages_processed']
                            messages.info(
                                request,
                                f"'{promotion.title}' has {remaining} pages remaining. "
                                f"Run the management command to process all pages."
                            )
                    else:
                        messages.error(request, f"Failed to process '{promotion.title}': {results['error']}")
                except Exception as e:
                    messages.error(request, f"Error processing '{promotion.title}': {str(e)}")
        
        if processed_count > 0:
            messages.success(request, f"Successfully processed {processed_count} promotion(s)")
    
    process_promotions.short_description = "Process selected promotions (limited to 10 pages each)"
    
    def process_promotions_safe(self, request, queryset):
        """Admin action to safely process selected promotions with very conservative limits."""
        processed_count = 0
        for promotion in queryset:
            if not promotion.is_processed:
                try:
                    # Very conservative limit for admin interface
                    max_pages = 3
                    total_pages = promotion.pages.count()
                    
                    messages.info(
                        request,
                        f"Processing first {max_pages} pages of '{promotion.title}' ({total_pages} total pages). "
                        f"This is safe for the admin interface."
                    )
                    
                    results = process_official_promotion(promotion.id, max_pages=max_pages)
                    if 'error' not in results:
                        processed_count += 1
                        messages.success(
                            request, 
                            f"Safely processed '{promotion.title}': {results['pages_processed']} pages, "
                            f"{results['items_extracted']} items, {results['alerts_created']} alerts"
                        )
                        
                        if total_pages > max_pages:
                            remaining = total_pages - results['pages_processed']
                            messages.warning(
                                request,
                                f"'{promotion.title}' has {remaining} pages remaining. "
                                f"For full processing, use: python manage.py process_promotions --promotion-id {promotion.id}"
                            )
                    else:
                        messages.error(request, f"Failed to process '{promotion.title}': {results['error']}")
                except Exception as e:
                    messages.error(request, f"Error processing '{promotion.title}': {str(e)}")
        
        if processed_count > 0:
            messages.success(request, f"Safely processed {processed_count} promotion(s)")
    
    process_promotions_safe.short_description = "🛡️ Safe process (3 pages max each)"
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add bulk upload button."""
        extra_context = extra_context or {}
        if object_id:
            extra_context['show_bulk_upload'] = True
            extra_context['bulk_upload_url'] = reverse(
                'admin:receipt_parser_costcopromotion_bulk_upload',
                args=[object_id]
            )
        return super().change_view(request, object_id, form_url, extra_context)

@admin.register(CostcoPromotionPage)
class CostcoPromotionPageAdmin(admin.ModelAdmin):
    list_display = ('promotion', 'page_number', 'image_display', 'is_processed', 'processing_status', 'uploaded_at')
    list_filter = ('is_processed', 'uploaded_at', 'promotion')
    readonly_fields = ('uploaded_at', 'extracted_text', 'processing_error')
    actions = ['process_selected_pages', 'reprocess_pages', 'mark_as_unprocessed']
    
    def image_display(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px;" />',
                obj.image.url
            )
        return "No image"
    image_display.short_description = "Preview"
    
    def processing_status(self, obj):
        if obj.is_processed:
            if obj.processing_error:
                return format_html('<span style="color: orange">✓ Processed (with errors)</span>')
            else:
                return format_html('<span style="color: green">✓ Processed Successfully</span>')
        else:
            if obj.processing_error:
                return format_html('<span style="color: red">✗ Failed</span>')
            else:
                return format_html('<span style="color: grey">⏳ Pending</span>')
    processing_status.short_description = "Status"
    
    def process_selected_pages(self, request, queryset):
        """Process selected promotion pages individually."""
        from .utils import extract_promo_data_from_image, parse_promo_text, create_official_price_alerts
        
        processed_count = 0
        total_items = 0
        total_alerts = 0
        errors = []
        
        # Only process unprocessed pages to avoid duplicates
        unprocessed_pages = queryset.filter(is_processed=False)
        
        if not unprocessed_pages.exists():
            messages.warning(request, "No unprocessed pages selected. Use 'Reprocess pages' to process already processed pages.")
            return
        
        for page in unprocessed_pages:
            try:
                messages.info(request, f"Processing page {page.page_number} of '{page.promotion.title}'...")
                
                # Check if image file exists
                if not page.image or not os.path.exists(page.image.path):
                    error_msg = f"Image file not found for page {page.page_number}: {page.image.name if page.image else 'No image'}"
                    errors.append(error_msg)
                    page.processing_error = error_msg
                    page.save()
                    logger.error(error_msg)
                    messages.error(request, error_msg)
                    continue
                
                # Extract text from the image
                extracted_text = extract_promo_data_from_image(page.image.path)
                page.extracted_text = extracted_text
                
                # Parse the sale items
                sale_items = parse_promo_text(extracted_text)
                
                # Create OfficialSaleItem records
                page_items_created = 0
                page_alerts_created = 0
                
                for item_data in sale_items:
                    try:
                        official_item, created = OfficialSaleItem.objects.get_or_create(
                            promotion=page.promotion,
                            item_code=item_data['item_code'],
                            defaults={
                                'description': item_data['description'],
                                'regular_price': item_data['regular_price'],
                                'sale_price': item_data['sale_price'],
                                'instant_rebate': item_data['instant_rebate'],
                                'sale_type': item_data['sale_type']
                            }
                        )
                        
                        if created:
                            page_items_created += 1
                            
                            # Create price adjustment alerts for users who bought this item
                            alerts_created = create_official_price_alerts(official_item)
                            official_item.alerts_created = alerts_created
                            official_item.save()
                            page_alerts_created += alerts_created
                            
                    except Exception as e:
                        error_msg = f"Error creating item {item_data.get('item_code', 'unknown')} on page {page.page_number}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        continue
                
                # Mark page as processed
                page.is_processed = True
                page.processing_error = None  # Clear any previous errors
                page.save()
                
                processed_count += 1
                total_items += page_items_created
                total_alerts += page_alerts_created
                
                messages.success(
                    request,
                    f"Page {page.page_number}: {page_items_created} items extracted, {page_alerts_created} alerts created"
                )
                
            except Exception as e:
                error_msg = f"Error processing page {page.page_number}: {str(e)}"
                errors.append(error_msg)
                page.processing_error = error_msg
                page.save()
                logger.error(error_msg)
                messages.error(request, error_msg)
        
        # Summary message
        if processed_count > 0:
            messages.success(
                request,
                f"Successfully processed {processed_count} page(s): "
                f"{total_items} total items, {total_alerts} total alerts"
            )
        
        if errors:
            messages.warning(
                request,
                f"Encountered {len(errors)} error(s) during processing. Check individual page errors for details."
            )
    
    process_selected_pages.short_description = "🔄 Process selected pages"
    
    def reprocess_pages(self, request, queryset):
        """Reprocess selected pages (including already processed ones)."""
        from .utils import extract_promo_data_from_image, parse_promo_text, create_official_price_alerts
        
        processed_count = 0
        total_items = 0
        total_alerts = 0
        errors = []
        
        for page in queryset:
            try:
                messages.info(request, f"Reprocessing page {page.page_number} of '{page.promotion.title}'...")
                
                # Check if image file exists
                if not page.image or not os.path.exists(page.image.path):
                    error_msg = f"Image file not found for page {page.page_number}: {page.image.name if page.image else 'No image'}"
                    errors.append(error_msg)
                    page.processing_error = error_msg
                    page.save()
                    logger.error(error_msg)
                    messages.error(request, error_msg)
                    continue
                
                # Extract text from the image
                extracted_text = extract_promo_data_from_image(page.image.path)
                page.extracted_text = extracted_text
                
                # Parse the sale items
                sale_items = parse_promo_text(extracted_text)
                
                # Create OfficialSaleItem records (get_or_create handles duplicates)
                page_items_created = 0
                page_alerts_created = 0
                
                for item_data in sale_items:
                    try:
                        official_item, created = OfficialSaleItem.objects.get_or_create(
                            promotion=page.promotion,
                            item_code=item_data['item_code'],
                            defaults={
                                'description': item_data['description'],
                                'regular_price': item_data['regular_price'],
                                'sale_price': item_data['sale_price'],
                                'instant_rebate': item_data['instant_rebate'],
                                'sale_type': item_data['sale_type']
                            }
                        )
                        
                        if created:
                            page_items_created += 1
                            
                            # Create price adjustment alerts for users who bought this item
                            alerts_created = create_official_price_alerts(official_item)
                            official_item.alerts_created = alerts_created
                            official_item.save()
                            page_alerts_created += alerts_created
                        else:
                            # Update existing item if data changed
                            updated = False
                            if official_item.description != item_data['description']:
                                official_item.description = item_data['description']
                                updated = True
                            if official_item.regular_price != item_data['regular_price']:
                                official_item.regular_price = item_data['regular_price']
                                updated = True
                            if official_item.sale_price != item_data['sale_price']:
                                official_item.sale_price = item_data['sale_price']
                                updated = True
                            if official_item.instant_rebate != item_data['instant_rebate']:
                                official_item.instant_rebate = item_data['instant_rebate']
                                updated = True
                            if official_item.sale_type != item_data['sale_type']:
                                official_item.sale_type = item_data['sale_type']
                                updated = True
                                
                            if updated:
                                official_item.save()
                                messages.info(request, f"Updated existing item: {official_item.description}")
                            
                    except Exception as e:
                        error_msg = f"Error processing item {item_data.get('item_code', 'unknown')} on page {page.page_number}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        continue
                
                # Mark page as processed
                page.is_processed = True
                page.processing_error = None  # Clear any previous errors
                page.save()
                
                processed_count += 1
                total_items += page_items_created
                total_alerts += page_alerts_created
                
                messages.success(
                    request,
                    f"Page {page.page_number}: {page_items_created} new items, {page_alerts_created} new alerts"
                )
                
            except Exception as e:
                error_msg = f"Error reprocessing page {page.page_number}: {str(e)}"
                errors.append(error_msg)
                page.processing_error = error_msg
                page.save()
                logger.error(error_msg)
                messages.error(request, error_msg)
        
        # Summary message
        if processed_count > 0:
            messages.success(
                request,
                f"Reprocessed {processed_count} page(s): "
                f"{total_items} new items, {total_alerts} new alerts"
            )
        
        if errors:
            messages.warning(
                request,
                f"Encountered {len(errors)} error(s) during reprocessing."
            )
    
    reprocess_pages.short_description = "🔄 Reprocess pages (including processed ones)"
    
    def mark_as_unprocessed(self, request, queryset):
        """Mark selected pages as unprocessed to allow reprocessing."""
        updated = queryset.update(is_processed=False, processing_error=None)
        messages.success(request, f"Marked {updated} page(s) as unprocessed.")
    
    mark_as_unprocessed.short_description = "↩️ Mark as unprocessed"

@admin.register(OfficialSaleItem)
class OfficialSaleItemAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'description', 'regular_price', 'sale_price', 'savings_amount', 'sale_type', 'alerts_created', 'promotion')
    list_filter = ('sale_type', 'promotion', 'created_at')
    search_fields = ('item_code', 'description')
    readonly_fields = ('savings_amount', 'alerts_created', 'created_at')
