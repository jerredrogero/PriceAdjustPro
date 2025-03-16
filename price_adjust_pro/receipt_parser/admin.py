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
    ItemPriceHistory, ItemWarehousePrice, PriceAdjustmentAlert
)

# Customize admin site
admin.site.site_header = 'PriceAdjustPro Administration'
admin.site.site_title = 'PriceAdjustPro Admin'
admin.site.index_title = 'Dashboard'

# Unregister default User and Group admin
admin.site.unregister(User)
admin.site.unregister(Group)

# Custom User admin with limited fields
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'date_joined', 'last_login', 'is_active', 'is_staff')
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
    actions = ['export_as_csv', 'export_as_json']

    def get_queryset(self, request):
        return super().get_queryset(request)\
            .select_related('receipt')\
            .annotate(
                price_with_savings=F('price') - F('instant_savings'),
                total_with_savings=F('price_with_savings') * F('quantity')
            )

    def instant_savings_display(self, obj):
        if obj.instant_savings:
            return format_html('<span style="color: green">${}</span>', obj.instant_savings)
        return '-'
    instant_savings_display.short_description = 'Savings'

    def receipt_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/receipt/{}/">{}</a>', 
                         obj.receipt.id, obj.receipt.transaction_number)
    receipt_link.short_description = 'Receipt'

    def export_as_csv(self, request, queryset):
        field_names = ['item_code', 'description', 'price', 'quantity', 'discount',
                      'is_taxable', 'instant_savings', 'original_price', 'receipt__transaction_number']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=line_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            row = []
            for field in field_names:
                if field == 'receipt__transaction_number':
                    row.append(obj.receipt.transaction_number)
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
