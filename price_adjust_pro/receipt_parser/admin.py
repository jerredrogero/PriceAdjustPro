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
from hijack.contrib.admin import HijackUserAdminMixin
from django.http import HttpResponse
import csv
import json
from datetime import datetime
from .models import (
    Receipt, LineItem, CostcoItem, CostcoWarehouse,
    ItemPriceHistory, PriceAdjustmentAlert,
    CostcoPromotion, CostcoPromotionPage, OfficialSaleItem,
    SubscriptionProduct, UserSubscription, SubscriptionEvent,
    UserProfile, AppleSubscription, EmailVerificationToken,
    EmailOTP, PushDevice, PushDelivery,
)
from django.conf import settings
from django.utils import timezone
from .utils import process_official_promotion
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, reverse
from django.contrib.auth import login
from django.core.mail import send_mail
from django.contrib.sessions.models import Session
import os
import logging
from decimal import Decimal, InvalidOperation
import io

logger = logging.getLogger(__name__)

# Helper function to get or create user profile
def get_or_create_user_profile(user):
    """Get or create user profile for account type management."""
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=user)


def send_admin_verification_email(user, initiated_by=None):
    """
    Generate a fresh verification code for the user and email it.

    Raises:
        ValueError: If the user has no email address on file.
        Exception: If sending the email fails.
    """
    if not user.email:
        raise ValueError('User has no email address on file.')

    # Invalidate any active codes before issuing a fresh one
    EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)

    verification_token = EmailVerificationToken.create_token(user)
    greeting_name = user.first_name or user.email or 'there'

    intro_line = (
        "A member of the PriceAdjustPro support team just sent you a new verification code "
        "so you can finish securing your account."
    )

    message = f"""
Hi {greeting_name},

{intro_line}

Your verification code is:

{verification_token.code}

Enter this code in the app or website to verify your email address.

This code will expire in 30 minutes.

If you didn't request this, you can safely ignore this email.

Best regards,
The PriceAdjustPro Team
"""

    send_mail(
        'Your PriceAdjustPro Verification Code',
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

    logger.info(
        "Admin-triggered verification code sent to %s by %s",
        user.email,
        initiated_by or 'system',
    )
    return verification_token


def resend_codes_for_users(request, admin_obj, users):
    """Common helper to resend verification codes for admin actions."""
    sent = 0
    for user in users:
        profile = get_or_create_user_profile(user)
        if profile.is_email_verified:
            admin_obj.message_user(
                request,
                f'{user.email} is already verified; skipped.',
                level=messages.INFO,
            )
            continue

        try:
            send_admin_verification_email(user, initiated_by=request.user.email)
            sent += 1
        except ValueError as exc:
            admin_obj.message_user(
                request,
                f'{user.email}: {exc}',
                level=messages.WARNING,
            )
        except Exception as exc:
            logger.error("Failed to send verification email to %s: %s", user.email, exc)
            admin_obj.message_user(
                request,
                f'{user.email}: Failed to send verification email.',
                level=messages.ERROR,
            )

    if sent:
        admin_obj.message_user(
            request,
            f'Sent verification emails to {sent} user(s).',
            level=messages.SUCCESS,
        )
    return sent

# Customize admin site
admin.site.site_header = 'PriceAdjustPro Administration'
admin.site.site_title = 'PriceAdjustPro Admin'
admin.site.index_title = 'Dashboard'

# Unregister default User and Group admin
admin.site.unregister(User)
admin.site.unregister(Group)

# Custom User admin with limited fields and hijack functionality
@admin.register(User)
class CustomUserAdmin(HijackUserAdminMixin, UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'date_joined', 'last_login', 'is_active', 'is_staff', 'account_type_display')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    readonly_fields = ('date_joined', 'last_login')
    ordering = ('-date_joined',)
    actions = ['upgrade_to_paid', 'downgrade_to_free', 'resend_two_factor_email']
    
    # Limit what fields can be changed
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Limit what fields are shown when creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    
    # HijackUserAdminMixin will add a "hijack user" button column automatically
    
    def account_type_display(self, obj):
        """Display user's account type."""
        profile = get_or_create_user_profile(obj)
        if profile.is_paid_account:
            return format_html('<span style="color: green; font-weight: bold;">💎 PAID</span>')
        else:
            return format_html('<span style="color: grey;">🆓 FREE</span>')
    account_type_display.short_description = 'Account Type'
    
    def upgrade_to_paid(self, request, queryset):
        """Upgrade selected users to paid accounts."""
        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can modify account types.')
            return
        
        upgraded_count = 0
        
        for user in queryset:
            profile = get_or_create_user_profile(user)
            if profile.is_paid_account:
                messages.info(request, f'{user.email} already has a paid account.')
                continue
            
            profile.account_type = 'paid'
            profile.save()
            upgraded_count += 1
            messages.success(request, f'{user.email}: Upgraded to paid account.')
        
        if upgraded_count > 0:
            messages.success(request, f'Successfully upgraded {upgraded_count} user(s) to paid accounts.')
    
    upgrade_to_paid.short_description = "💎 Upgrade to Paid Account"
    
    def downgrade_to_free(self, request, queryset):
        """Downgrade selected users to free accounts."""
        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can modify account types.')
            return
        
        downgraded_count = 0
        
        for user in queryset:
            profile = get_or_create_user_profile(user)
            if profile.is_free_account:
                messages.info(request, f'{user.email} already has a free account.')
                continue
            
            profile.account_type = 'free'
            profile.save()
            downgraded_count += 1
            messages.success(request, f'{user.email}: Downgraded to free account.')
        
        if downgraded_count > 0:
            messages.success(request, f'Successfully downgraded {downgraded_count} user(s) to free accounts.')
    
    downgrade_to_free.short_description = "🆓 Downgrade to Free Account"
    
    def delete_queryset(self, request, queryset):
        """Override delete to handle foreign key constraints properly."""
        from django.db import transaction
        
        for user in queryset:
            try:
                with transaction.atomic():
                    # Delete related objects in the correct order
                    # 1. Price adjustment alerts
                    user.price_alerts.all().delete()
                    
                    # 2. Receipts (this will also delete line items)
                    user.receipts.all().delete()
                    
                    # 3. User subscription if exists
                    if hasattr(user, 'subscription'):
                        user.subscription.delete()
                    
                    # 4. User profile if exists
                    if hasattr(user, 'profile'):
                        user.profile.delete()
                    
                    # 5. Uploaded promotions
                    user.uploaded_promotions.all().delete()
                    
                    # 6. Finally delete the user
                    user.delete()
                    
            except Exception as e:
                messages.error(request, f'Error deleting user {user.email}: {str(e)}')
                continue
        
        messages.success(request, f'Successfully deleted {len(queryset)} user(s) and all related data.')

    def resend_two_factor_email(self, request, queryset):
        """Send a fresh verification code email to each selected user."""
        resend_codes_for_users(request, self, queryset)
    resend_two_factor_email.short_description = "🔐 Resend verification email"

csrf_protect_m = method_decorator(csrf_protect)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'account_type', 'is_premium', 'subscription_type', 'is_email_verified', 'created_at', 'updated_at')
    list_filter = ('account_type', 'is_premium', 'subscription_type', 'is_email_verified', 'created_at')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at', 'email_verified_at')
    raw_id_fields = ('user',)
    ordering = ('-created_at',)
    actions = ['upgrade_to_paid', 'downgrade_to_free', 'resend_two_factor_email']
    
    def upgrade_to_paid(self, request, queryset):
        """Upgrade selected profiles to paid accounts."""
        count = queryset.filter(account_type='free').update(account_type='paid', is_premium=True)
        self.message_user(request, f'{count} user(s) upgraded to paid accounts.')
    upgrade_to_paid.short_description = "💎 Upgrade to Paid Account"
    
    def downgrade_to_free(self, request, queryset):
        """Downgrade selected profiles to free accounts."""
        count = queryset.filter(account_type='paid').update(account_type='free', is_premium=False, subscription_type='free')
        self.message_user(request, f'{count} user(s) downgraded to free accounts.')
    downgrade_to_free.short_description = "🆓 Downgrade to Free Account"

    def resend_two_factor_email(self, request, queryset):
        """Send a fresh verification code email to profile owners."""
        users = [profile.user for profile in queryset.select_related('user')]
        resend_codes_for_users(request, self, users)
    resend_two_factor_email.short_description = "🔐 Resend verification email"

@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_email', 'is_used', 'is_expired', 'created_at', 'expires_at')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__email', 'token')
    readonly_fields = ('token', 'created_at', 'expires_at', 'used_at', 'is_expired', 'is_valid')
    raw_id_fields = ('user',)
    ordering = ('-created_at',)
    actions = ['mark_as_used', 'delete_expired_tokens']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def mark_as_used(self, request, queryset):
        """Mark selected tokens as used."""
        count = queryset.filter(is_used=False).update(is_used=True, used_at=timezone.now())
        self.message_user(request, f'{count} token(s) marked as used.')
    mark_as_used.short_description = 'Mark as used'
    
    def delete_expired_tokens(self, request, queryset):
        """Delete expired verification tokens."""
        now = timezone.now()
        expired = queryset.filter(expires_at__lt=now)
        count = expired.count()
        expired.delete()
        self.message_user(request, f'Deleted {count} expired token(s).')
    delete_expired_tokens.short_description = 'Delete expired tokens'

@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_email', 'attempts', 'created_at', 'expires_at', 'used_at', 'is_active')
    list_filter = ('created_at', 'expires_at', 'used_at')
    search_fields = ('user__email', 'code_hash')
    readonly_fields = ('user', 'code_hash', 'created_at', 'expires_at', 'used_at', 'attempts', 'last_sent_at', 'is_expired', 'is_used')
    raw_id_fields = ('user',)
    ordering = ('-created_at',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def is_active(self, obj):
        return not obj.is_expired() and not obj.is_used()
    is_active.boolean = True
    is_active.short_description = 'Active'

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
    fields = ('item_code', 'description', 'price', 'quantity', 'discount', 'is_taxable', 'instant_savings', 'total_price', 'created_at')
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
    search_fields = ('transaction_number', 'store_location', 'store_city', 'user__email', 'items__description')
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
        return format_html('<a href="/admin/auth/user/{}/">{}</a>', obj.user.id, obj.user.email)
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
                      'parsed_successfully', 'user__email']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=receipts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        # Write header
        writer.writerow(field_names)
        
        # Write data
        for obj in queryset:
            row = []
            for field in field_names:
                if field == 'user__email':
                    row.append(obj.user.email)
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
                'user': receipt.user.email,
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
    list_display = ('item_description', 'user', 'trigger_reference', 'original_store_city', 'cheaper_store_city',
                   'price_difference_display', 'days_remaining', 'status_display', 'created_at')
    list_filter = (
        'data_source',
        'is_active', 
        'is_dismissed', 
        'original_store_city', 
        'cheaper_store_city',
        'user__email',
        'created_at',
        ('official_sale_item', admin.EmptyFieldListFilter),
    )
    search_fields = ('item_description', 'item_code', 'user__email', 
                    'original_store_city', 'cheaper_store_city', 'official_sale_item__promotion__title')
    readonly_fields = ('price_difference', 'days_remaining', 'is_expired', 'created_at', 
                      'data_source', 'official_sale_item')
    date_hierarchy = 'purchase_date'
    list_per_page = 50
    raw_id_fields = ('user',)
    actions = ['mark_as_expired', 'mark_as_dismissed', 'send_push_summary_now', 'export_as_csv', 'export_as_json']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'item_code', 'item_description')
        }),
        ('Price Details', {
            'fields': ('original_price', 'lower_price', 'price_difference')
        }),
        ('Location Information', {
            'fields': ('original_store_city', 'original_store_number', 'cheaper_store_city', 'cheaper_store_number')
        }),
        ('Trigger Source', {
            'fields': ('data_source', 'official_sale_item'),
            'description': 'Shows what triggered this price alert'
        }),
        ('Dates & Status', {
            'fields': ('purchase_date', 'created_at', 'days_remaining', 'is_expired', 'is_active', 'is_dismissed')
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        When an admin manually creates an alert, trigger a push immediately.

        Note: Normal app flows trigger pushes elsewhere (receipt upload / promo processing),
        so we keep this scoped to admin-created objects to make manual testing reliable.
        """
        super().save_model(request, obj, form, change)

        if change:
            return

        try:
            from receipt_parser.notifications.push import send_price_adjustment_summary_to_user

            total_savings = (obj.original_price - obj.lower_price) if (obj.original_price is not None and obj.lower_price is not None) else Decimal("0.00")
            sent = send_price_adjustment_summary_to_user(
                user_id=obj.user_id,
                latest_alert_id=obj.id,
                count=1,
                total_savings=total_savings,
                throttle_minutes=0,  # admin create should be immediate for testing
            )
            if sent:
                self.message_user(request, f"Push sent to {sent} device(s).", level=messages.SUCCESS)
            else:
                total_devices = PushDevice.objects.filter(user_id=obj.user_id).count()
                enabled_devices = PushDevice.objects.filter(
                    user_id=obj.user_id,
                    is_enabled=True,
                    price_adjustment_alerts_enabled=True,
                ).count()
                disabled_devices = PushDevice.objects.filter(user_id=obj.user_id, is_enabled=False).count()
                apns_configured = bool(
                    getattr(settings, "APNS_TEAM_ID", "").strip()
                    and getattr(settings, "APNS_KEY_ID", "").strip()
                    and getattr(settings, "APNS_BUNDLE_ID", "").strip()
                    and (
                        (getattr(settings, "APNS_PRIVATE_KEY_P8", "") or "").strip()
                        or getattr(settings, "APNS_PRIVATE_KEY_P8_PATH", "").strip()
                        or getattr(settings, "APNS_PRIVATE_KEY_P8_BASE64", "").strip()
                    )
                )

                if enabled_devices == 0:
                    # Try to surface why the device is disabled (if applicable)
                    last_reason = None
                    try:
                        last_delivery = (
                            PushDelivery.objects.filter(device__user_id=obj.user_id, kind="price_adjustment_summary")
                            .order_by("-created_at")
                            .first()
                        )
                        snap = (last_delivery.payload_snapshot or {}) if last_delivery else {}
                        ar = snap.get("apns_result") if isinstance(snap, dict) else None
                        if isinstance(ar, dict):
                            r = ar.get("reason")
                            sc = ar.get("status_code")
                            if r or sc:
                                last_reason = f"{r} (status {sc})"
                    except Exception:
                        pass

                    self.message_user(
                        request,
                        (
                            f"No push sent: backend has 0 enabled push devices for this user (total devices: {total_devices}, disabled: {disabled_devices}). "
                            + (f"Last APNs result: {last_reason}. " if last_reason else "")
                            + "Being logged in is not enough—iOS must register an APNs token via /api/notifications/devices/ "
                            "and price adjustment notifications must be enabled."
                        ),
                        level=messages.WARNING,
                    )
                elif not apns_configured:
                    self.message_user(
                        request,
                        f"No push sent: {enabled_devices} enabled device(s) found, but APNs is not configured on the server "
                        "(missing APNS_* settings). Check Render env vars and logs.",
                        level=messages.WARNING,
                    )
                else:
                    # Try to surface the exact APNs failure reason from the latest PushDelivery payload snapshots.
                    reasons = []
                    try:
                        dedupe_key = f"latest_alert:{obj.id}"
                        recent = (
                            PushDelivery.objects.filter(
                                device__user_id=obj.user_id,
                                kind="price_adjustment_summary",
                                dedupe_key=dedupe_key,
                            )
                            .select_related("device")
                            .order_by("-created_at")[:10]
                        )
                        for d in recent:
                            snap = d.payload_snapshot or {}
                            ar = snap.get("apns_result") if isinstance(snap, dict) else None
                            if isinstance(ar, dict) and ar.get("reason"):
                                reasons.append(f"{ar.get('reason')} (status {ar.get('status_code')})")
                    except Exception:
                        pass

                    self.message_user(
                        request,
                        (
                            f"No push sent: {enabled_devices} enabled device(s) found, but APNs delivery failed. "
                            + (f"Last APNs reason(s): {', '.join(reasons[:3])}. " if reasons else "")
                            + "Check Render logs and Push Deliveries."
                        ),
                        level=messages.WARNING,
                    )
        except Exception as e:
            logger.error("Failed to send admin-triggered push for PriceAdjustmentAlert %s: %s", getattr(obj, "id", None), e)
            self.message_user(request, f"Failed to send push: {e}", level=messages.ERROR)

    def send_push_summary_now(self, request, queryset):
        """
        Admin action: send a push summary for selected alerts immediately.
        """
        try:
            from receipt_parser.notifications.push import send_price_adjustment_summary_to_user, summarize_new_alerts_for_user
        except Exception as e:
            self.message_user(request, f"Failed to import push sender: {e}", level=messages.ERROR)
            return

        sent_total = 0
        # Group by user so selecting multiple alerts doesn't spam multiple pushes.
        by_user = {}
        for alert in queryset:
            by_user.setdefault(alert.user_id, []).append(alert.id)

        for user_id, alert_ids in by_user.items():
            try:
                summary = summarize_new_alerts_for_user(user_id=user_id, alert_ids=alert_ids)
                latest_alert_id = max(alert_ids)
                sent = send_price_adjustment_summary_to_user(
                    user_id=user_id,
                    latest_alert_id=latest_alert_id,
                    count=summary["count"],
                    total_savings=summary["total_savings"],
                    throttle_minutes=0,
                )
                sent_total += sent
            except Exception as e:
                logger.error("Failed to send manual push summary for user %s: %s", user_id, e)
                self.message_user(request, f"Failed to send push for user_id={user_id}: {e}", level=messages.ERROR)

        if sent_total:
            self.message_user(request, f"Push sent to {sent_total} device(s).", level=messages.SUCCESS)
        else:
            self.message_user(request, "No pushes sent. Check Push Devices (enabled + prefs), APNS_* env vars, and logs.", level=messages.WARNING)
    send_push_summary_now.short_description = "Send push summary now (selected alerts)"

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

    def trigger_reference(self, obj):
        """Display what triggered this price alert."""
        if obj.data_source == 'official_promo' and obj.official_sale_item:
            promo = obj.official_sale_item.promotion
            return format_html(
                '<span style="color: #1976d2; font-weight: bold;">📘 Official Promo</span><br>'
                '<small><a href="/admin/receipt_parser/costcopromotion/{}/" target="_blank">{}</a><br>'
                'Sale Type: {}</small>',
                promo.id,
                promo.title,
                obj.official_sale_item.get_sale_type_display()
            )
        elif obj.data_source == 'user_edit':
            original_transaction = obj.get_original_transaction_number()
            cheaper_transaction = obj.get_cheaper_transaction_number()
            links = []
            
            if original_transaction:
                links.append(f'<a href="/receipts/{original_transaction}" target="_blank">Original Purchase</a>')
            if cheaper_transaction:
                links.append(f'<a href="/receipts/{cheaper_transaction}" target="_blank">Later Purchase</a>')
            
            link_text = ' | '.join(links) if links else 'Receipt comparison'
            
            return format_html(
                '<span style="color: #388e3c; font-weight: bold;">👤 Own Receipts</span><br>'
                '<small>{}</small>',
                link_text
            )
        else:
            return format_html('<span style="color: gray;">Unknown</span>')
    
    trigger_reference.short_description = "Trigger Source"
    trigger_reference.allow_tags = True

    def price_difference_display(self, obj):
        if obj.price_difference is None:
            return format_html('<span style="color: grey">-</span>')
        return format_html(
            '<span style="color: green">${}</span>',
            '{:.2f}'.format(float(obj.price_difference)),
        )
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
                      'days_remaining', 'is_active', 'is_dismissed', 'user__email',
                      'data_source', 'trigger_description', 'original_transaction', 'promotion_title']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=price_adjustments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        # Write header
        writer.writerow(field_names)
        
        # Write data
        for obj in queryset:
            row = []
            for field in field_names:
                if field == 'user__email':
                    row.append(obj.user.email)
                elif field == 'data_source':
                    row.append(obj.get_data_source_display())
                elif field == 'trigger_description':
                    if obj.data_source == 'official_promo' and obj.official_sale_item:
                        row.append(f"Official promotion: {obj.official_sale_item.promotion.title}")
                    elif obj.data_source == 'user_edit':
                        row.append("Official promotion comparison")
                    else:
                        row.append("Unknown trigger")
                elif field == 'original_transaction':
                    row.append(obj.get_original_transaction_number() or "")
                elif field == 'promotion_title':
                    if obj.data_source == 'official_promo' and obj.official_sale_item:
                        row.append(obj.official_sale_item.promotion.title)
                    else:
                        row.append("")
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
                'price_difference': str(alert.price_difference) if alert.price_difference is not None else None,
                'original_store_city': alert.original_store_city,
                'cheaper_store_city': alert.cheaper_store_city,
                'purchase_date': alert.purchase_date.strftime('%Y-%m-%d %H:%M:%S'),
                'days_remaining': alert.days_remaining,
                'is_active': alert.is_active,
                'is_dismissed': alert.is_dismissed,
                'user': alert.user.email,
                'data_source': alert.get_data_source_display(),
                'trigger_info': {
                    'source_type': alert.data_source,
                    'original_transaction': alert.get_original_transaction_number(),
                    'cheaper_transaction': alert.get_cheaper_transaction_number() if alert.data_source == 'user_edit' else None,
                    'promotion_title': alert.official_sale_item.promotion.title if alert.data_source == 'official_promo' and alert.official_sale_item else None,
                    'sale_type': alert.official_sale_item.get_sale_type_display() if alert.data_source == 'official_promo' and alert.official_sale_item else None,
                }
            }
            data.append(alert_data)

        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename=price_adjustments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        json.dump(data, response, indent=2)
        return response
    export_as_json.short_description = "Export selected alerts as JSON"


@admin.register(PushDevice)
class PushDeviceAdmin(BaseModelAdmin):
    list_display = (
        "user",
        "platform",
        "device_id",
        "is_enabled",
        "price_adjustment_alerts_enabled",
        "sale_alerts_enabled",
        "receipt_processing_alerts_enabled",
        "price_drop_alerts_enabled",
        "last_seen_at",
        "updated_at",
    )
    list_filter = (
        "platform",
        "is_enabled",
        "price_adjustment_alerts_enabled",
        "sale_alerts_enabled",
        "receipt_processing_alerts_enabled",
        "price_drop_alerts_enabled",
    )
    search_fields = ("user__email", "device_id", "apns_token")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    raw_id_fields = ("user",)
    ordering = ("-updated_at",)


@admin.register(PushDelivery)
class PushDeliveryAdmin(BaseModelAdmin):
    list_display = ("device", "kind", "dedupe_key", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("device__user__email", "device__device_id", "dedupe_key")
    readonly_fields = ("created_at",)
    raw_id_fields = ("device",)
    ordering = ("-created_at",)

@admin.register(LineItem)
class LineItemAdmin(BaseModelAdmin):
    list_display = ('item_code', 'description', 'price', 'quantity', 'total_price', 
                   'instant_savings_display', 'email', 'receipt_link', 'created_at', 'updated_at')
    list_filter = (
        'receipt__store_location',
        'receipt__user__email',
        'is_taxable',
        ('instant_savings', admin.EmptyFieldListFilter),
        'receipt__transaction_date',
        'created_at',
        'updated_at'
    )
    search_fields = ('item_code', 'description', 'receipt__transaction_number', 'receipt__user__email')
    readonly_fields = ('total_price', 'updated_at')  # created_at is now editable
    raw_id_fields = ('receipt',)
    list_per_page = 100
    show_full_result_count = False
    actions = ['export_as_csv', 'export_as_json']
    date_hierarchy = 'created_at'

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

    def email(self, obj):
        if obj.receipt and obj.receipt.user:
            return obj.receipt.user.email
        return '-'
    email.short_description = 'User Email'

    def receipt_link(self, obj):
        return format_html('<a href="/admin/receipt_parser/receipt/{}/">{}</a>', 
                         obj.receipt.id, obj.receipt.transaction_number)
    receipt_link.short_description = 'Receipt'

    def export_as_csv(self, request, queryset):
        field_names = ['item_code', 'description', 'price', 'quantity', 'discount',
                      'is_taxable', 'instant_savings', 'original_price', 'email', 'receipt__transaction_number',
                      'created_at', 'updated_at']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=line_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        writer = csv.writer(response)

        writer.writerow(['item_code', 'description', 'price', 'quantity', 'discount',
                        'is_taxable', 'instant_savings', 'original_price', 'email', 'receipt_transaction_number',
                        'created_at', 'updated_at'])
        for obj in queryset:
            row = []
            for field in field_names:
                if field == 'receipt__transaction_number':
                    row.append(obj.receipt.transaction_number)
                elif field == 'email':
                    row.append(obj.receipt.user.email if obj.receipt and obj.receipt.user else '')
                elif field in ['created_at', 'updated_at']:
                    value = getattr(obj, field)
                    row.append(value.strftime('%Y-%m-%d %H:%M:%S') if value else '')
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
                'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else None,
                'updated_at': item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else None,
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

# ItemWarehousePrice admin removed - no longer needed since we only use official promotions
# @admin.register(ItemWarehousePrice)
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
    list_display = ('title', 'sale_start_date', 'sale_end_date', 'get_promotion_status', 'pages_count', 'items_count', 'alerts_count')
    list_filter = ('is_processed', 'sale_start_date', 'uploaded_by')
    search_fields = ('title',)
    readonly_fields = ('upload_date', 'processed_date', 'uploaded_by', 'pages_count', 'items_count', 'alerts_count')
    inlines = [CostcoPromotionPageInline, OfficialSaleItemInline]
    
    actions = ['process_next_batch', 'process_full_promotion', 'run_price_adjustment_check', 'export_promotion_data_csv']
    
    def run_price_adjustment_check(self, request, queryset):
        """
        Manually trigger a price adjustment check for all items in the selected promotions.
        This is useful if you've already processed the pages but want to re-scan user receipts
        (e.g., after new users have signed up or uploaded more receipts).
        """
        from .utils import create_official_price_alerts
        from receipt_parser.notifications.services import push_summaries_for_official_sale_item
        
        total_alerts_created = 0
        promotions_checked = 0
        
        for promotion in queryset:
            promo_alerts = 0
            sale_items = promotion.sale_items.all()
            
            if not sale_items.exists():
                messages.warning(request, f"'{promotion.title}' has no extracted sale items. Process the pages first.")
                continue
                
            for item in sale_items:
                try:
                    # Run the check against all user receipts
                    new_alerts = create_official_price_alerts(item)
                    if new_alerts > 0:
                        item.alerts_created = (item.alerts_created or 0) + new_alerts
                        item.save()
                        promo_alerts += new_alerts
                        
                        # Trigger push notifications for the new alerts
                        try:
                            push_summaries_for_official_sale_item(official_sale_item_id=item.id)
                        except Exception as e:
                            logger.error(f"Push fanout failed for sale item {item.id}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error checking alerts for item {item.item_code}: {str(e)}")
            
            if promo_alerts > 0:
                messages.success(request, f"Found {promo_alerts} new price adjustment opportunities for '{promotion.title}'.")
                total_alerts_created += promo_alerts
            else:
                messages.info(request, f"Checked '{promotion.title}' - no new matches found.")
            
            promotions_checked += 1
            
        if total_alerts_created > 0:
            messages.success(request, f"Successfully created {total_alerts_created} total new alerts across {promotions_checked} promotion(s).")
        elif promotions_checked > 0:
            messages.info(request, "Check complete. No new price adjustment opportunities were found for the selected promotions.")

    run_price_adjustment_check.short_description = "🔍 Run Price Adjustment Check (New Users/Receipts)"

    def process_full_promotion(self, request, queryset):
        """Process all unprocessed pages for the selected promotions."""
        processed_count = 0
        for promotion in queryset:
            try:
                unprocessed_pages = promotion.pages.filter(is_processed=False).count()
                
                if unprocessed_pages == 0:
                    messages.info(request, f"'{promotion.title}' - All pages already processed.")
                    continue
                
                messages.info(
                    request,
                    f"Processing all {unprocessed_pages} remaining pages of '{promotion.title}'..."
                )
                
                # We pass max_pages=None to process everything
                results = process_official_promotion(promotion.id, max_pages=None)
                
                if 'error' not in results:
                    processed_count += 1
                    messages.success(
                        request, 
                        f"Successfully processed '{promotion.title}': {results['pages_processed']} pages, "
                        f"{results['items_extracted']} items, {results['alerts_created']} alerts created"
                    )
                else:
                    messages.error(request, f"Failed to process '{promotion.title}': {results['error']}")
            except Exception as e:
                messages.error(request, f"Error processing '{promotion.title}': {str(e)}")
        
        if processed_count > 0:
            messages.success(request, f"Successfully processed {processed_count} promotion(s) completely.")
    
    process_full_promotion.short_description = "🚀 Process FULL promotion (all pages)"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:promotion_id>/csv-import/',
                self.admin_site.admin_view(self.csv_import_view),
                name='receipt_parser_costcopromotion_csv_import',
            ),
        ]
        return custom_urls + urls
    

    
    def csv_import_view(self, request, promotion_id):
        """Custom view for importing sale items from CSV."""
        promotion = get_object_or_404(CostcoPromotion, id=promotion_id)
        
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            
            if not csv_file:
                messages.error(request, 'Please select a CSV file to upload.')
                return redirect(request.path)
            
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Please upload a CSV file.')
                return redirect(request.path)
            
            try:
                # Read and process the CSV
                file_data = csv_file.read().decode('utf-8')
                csv_reader = csv.DictReader(io.StringIO(file_data))
                
                # Validate required columns
                required_columns = ['item_code', 'description', 'sale_type']
                missing_columns = [col for col in required_columns if col not in csv_reader.fieldnames]
                
                if missing_columns:
                    messages.error(request, f'Missing required columns: {", ".join(missing_columns)}')
                    return redirect(request.path)
                
                # Process the data
                created_items = []
                errors = []
                updated_items = 0
                
                for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                    try:
                        # Clean and validate data
                        item_code = row.get('item_code', '').strip()
                        description = row.get('description', '').strip()
                        sale_type = row.get('sale_type', 'instant_rebate').strip()
                        
                        if not item_code or not description:
                            errors.append(f'Row {row_num}: Missing item_code or description')
                            continue
                        
                        # Parse prices
                        regular_price = None
                        sale_price = None
                        instant_rebate = None
                        
                        if row.get('regular_price'):
                            try:
                                regular_price = Decimal(str(row['regular_price']).replace('$', '').replace(',', '').strip())
                            except (ValueError, InvalidOperation):
                                errors.append(f'Row {row_num}: Invalid regular_price format')
                                continue
                        
                        if row.get('sale_price'):
                            try:
                                sale_price = Decimal(str(row['sale_price']).replace('$', '').replace(',', '').strip())
                            except (ValueError, InvalidOperation):
                                errors.append(f'Row {row_num}: Invalid sale_price format')
                                continue
                        
                        if row.get('instant_rebate'):
                            try:
                                instant_rebate = Decimal(str(row['instant_rebate']).replace('$', '').replace(',', '').strip())
                            except (ValueError, InvalidOperation):
                                errors.append(f'Row {row_num}: Invalid instant_rebate format')
                                continue
                        
                        # Validate sale_type
                        valid_sale_types = ['instant_rebate', 'discount_only', 'markdown', 'member_only', 'manufacturer']
                        if sale_type not in valid_sale_types:
                            errors.append(f'Row {row_num}: Invalid sale_type "{sale_type}". Must be one of: {", ".join(valid_sale_types)}')
                            continue
                        
                        # Create or update the sale item
                        sale_item, created = OfficialSaleItem.objects.update_or_create(
                            promotion=promotion,
                            item_code=item_code,
                            defaults={
                                'description': description,
                                'regular_price': regular_price,
                                'sale_price': sale_price,
                                'instant_rebate': instant_rebate,
                                'sale_type': sale_type,
                                'alerts_created': 0  # Will be updated when processing
                            }
                        )
                        
                        if created:
                            created_items.append(sale_item)
                        else:
                            updated_items += 1
                            
                    except Exception as e:
                        errors.append(f'Row {row_num}: {str(e)}')
                        continue
                
                # Show results
                if created_items:
                    messages.success(request, f'Successfully imported {len(created_items)} new sale items.')
                
                if updated_items:
                    messages.info(request, f'Updated {updated_items} existing sale items.')
                
                if errors:
                    for error in errors[:10]:  # Show first 10 errors
                        messages.error(request, error)
                    if len(errors) > 10:
                        messages.error(request, f'... and {len(errors) - 10} more errors.')
                
                # Optionally create price adjustment alerts
                if created_items and request.POST.get('create_alerts'):
                    from .utils import create_official_price_alerts
                    total_alerts = 0
                    
                    for sale_item in created_items:
                        try:
                            alerts_created = create_official_price_alerts(sale_item)
                            sale_item.alerts_created = alerts_created
                            sale_item.save()
                            total_alerts += alerts_created
                        except Exception as e:
                            logger.error(f'Error creating alerts for {sale_item.description}: {str(e)}')
                    
                    if total_alerts > 0:
                        messages.success(request, f'Created {total_alerts} price adjustment alerts for users.')
                
                return redirect('admin:receipt_parser_costcopromotion_change', promotion.id)
                
            except Exception as e:
                logger.error(f'Error processing CSV import: {str(e)}')
                messages.error(request, f'Error processing CSV file: {str(e)}')
                return redirect(request.path)
        
        # GET request - show the upload form
        context = {
            'promotion': promotion,
            'title': f'CSV Import for {promotion.title}',
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request, promotion),
            'csv_template_columns': [
                'item_code',
                'description', 
                'regular_price',
                'sale_price',
                'instant_rebate',
                'sale_type',
                'notes'
            ]
        }
        return render(request, 'admin/receipt_parser/csv_import.html', context)
    
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
    
    def process_next_batch(self, request, queryset):
        """Process the next batch of unprocessed pages (up to 5 pages per promotion)."""
        processed_count = 0
        for promotion in queryset:
            try:
                unprocessed_pages = promotion.pages.filter(is_processed=False).count()
                
                if unprocessed_pages == 0:
                    messages.info(request, f"'{promotion.title}' - All pages already processed.")
                    continue
                
                max_pages = 5
                
                messages.info(
                    request,
                    f"Processing next {min(max_pages, unprocessed_pages)} pages of '{promotion.title}' "
                    f"({unprocessed_pages} unprocessed pages remaining)."
                )
                
                results = process_official_promotion(promotion.id, max_pages=max_pages)
                if 'error' not in results:
                    processed_count += 1
                    remaining = promotion.pages.filter(is_processed=False).count()
                    
                    messages.success(
                        request, 
                        f"Processed batch for '{promotion.title}': {results['pages_processed']} pages, "
                        f"{results['items_extracted']} items, {results['alerts_created']} alerts created"
                    )
                    
                    if remaining > 0:
                        messages.info(
                            request,
                            f"'{promotion.title}' still has {remaining} pages remaining. "
                            f"Run this action again to process the next batch."
                        )
                    else:
                        messages.success(
                            request,
                            f"'{promotion.title}' is now fully processed! 🎉"
                        )
                else:
                    messages.error(request, f"Failed to process '{promotion.title}': {results['error']}")
            except Exception as e:
                messages.error(request, f"Error processing '{promotion.title}': {str(e)}")
        
        if processed_count > 0:
            messages.success(request, f"Successfully processed batches for {processed_count} promotion(s)")
    
    process_next_batch.short_description = "📦 Process next 5 pages"
    
    def export_promotion_data_csv(self, request, queryset):
        """Export all sale items from selected promotions to CSV."""
        from django.http import HttpResponse
        import csv
        from datetime import datetime
        
        # Get all sale items from selected promotions
        sale_items = OfficialSaleItem.objects.filter(
            promotion__in=queryset
        ).select_related('promotion').order_by('promotion__title', 'item_code')
        
        if not sale_items.exists():
            messages.warning(request, "No sale items found in selected promotions.")
            return
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response['Content-Disposition'] = f'attachment; filename="promotion_data_{timestamp}.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Promotion Title',
            'Sale Start Date',
            'Sale End Date', 
            'Item Code',
            'Description',
            'Regular Price',
            'Sale Price',
            'Instant Rebate',
            'Sale Type',
            'Alerts Created',
            'Savings Amount',
            'Savings Percentage'
        ])
        
        # Write data
        for item in sale_items:
            # Calculate savings
            savings_amount = None
            savings_percentage = None
            
            if item.regular_price and item.sale_price:
                savings_amount = item.regular_price - item.sale_price
                if item.regular_price > 0:
                    savings_percentage = (savings_amount / item.regular_price) * 100
            elif item.instant_rebate:
                savings_amount = item.instant_rebate
                if item.regular_price and item.regular_price > 0:
                    savings_percentage = (savings_amount / item.regular_price) * 100
            
            writer.writerow([
                item.promotion.title,
                item.promotion.sale_start_date,
                item.promotion.sale_end_date,
                item.item_code,
                item.description,
                str(item.regular_price) if item.regular_price else '',
                str(item.sale_price) if item.sale_price else '',
                str(item.instant_rebate) if item.instant_rebate else '',
                item.sale_type,
                item.alerts_created,
                str(savings_amount) if savings_amount else '',
                f"{savings_percentage:.1f}%" if savings_percentage else ''
            ])
        
        promotion_titles = ", ".join([p.title for p in queryset])
        messages.success(
            request, 
            f"Exported {sale_items.count()} sale items from: {promotion_titles}"
        )
        
        return response
    
    export_promotion_data_csv.short_description = "📊 Export to CSV"
    
    def get_promotion_status(self, obj):
        """Get detailed status information about promotion processing."""
        total_pages = obj.pages.count()
        processed_pages = obj.pages.filter(is_processed=True).count()
        unprocessed_pages = total_pages - processed_pages
        
        if total_pages == 0:
            return format_html('<span style="color: orange;">No pages uploaded</span>')
        elif unprocessed_pages == 0:
            return format_html('<span style="color: green;">✅ Complete ({}/{})</span>', processed_pages, total_pages)
        else:
            return format_html('<span style="color: blue;">⏳ Partial ({}/{}) - {} remaining</span>', 
                             processed_pages, total_pages, unprocessed_pages)
    
    get_promotion_status.short_description = "Processing Status"
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view."""
        extra_context = extra_context or {}
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

# Subscription Admin Classes
@admin.register(SubscriptionProduct)
class SubscriptionProductAdmin(BaseModelAdmin):
    list_display = ('name', 'price', 'currency', 'billing_interval', 'is_active', 'created_at')
    list_filter = ('is_active', 'billing_interval', 'currency', 'created_at')
    search_fields = ('name', 'description', 'stripe_product_id', 'stripe_price_id')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('name', 'description', 'stripe_product_id', 'stripe_price_id', 'price', 'currency', 'billing_interval', 'is_active')
    ordering = ('price', 'name')
    actions = ['activate_products', 'deactivate_products']

    def activate_products(self, request, queryset):
        """Activate selected subscription products."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} products activated successfully.')
    activate_products.short_description = 'Activate selected products'

    def deactivate_products(self, request, queryset):
        """Deactivate selected subscription products."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} products deactivated successfully.')
    deactivate_products.short_description = 'Deactivate selected products'

@admin.register(UserSubscription)
class UserSubscriptionAdmin(BaseModelAdmin):
    list_display = ('user', 'product', 'status', 'is_active', 'current_period_end', 'cancel_at_period_end', 'days_until_renewal', 'created_at')
    list_filter = ('status', 'cancel_at_period_end', 'product', 'created_at')
    search_fields = ('user__email', 'product__name', 'stripe_subscription_id', 'stripe_customer_id')
    readonly_fields = ('stripe_subscription_id', 'stripe_customer_id', 'is_active', 'days_until_renewal', 'created_at', 'updated_at')
    raw_id_fields = ('user', 'product')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['export_as_csv']

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'product', 'status')
        }),
        ('Stripe Information', {
            'fields': ('stripe_subscription_id', 'stripe_customer_id'),
            'classes': ('collapse',)
        }),
        ('Billing Periods', {
            'fields': ('current_period_start', 'current_period_end', 'cancel_at_period_end', 'canceled_at')
        }),
        ('Status', {
            'fields': ('is_active', 'days_until_renewal'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')

    def export_as_csv(self, request, queryset):
        """Export selected subscriptions as CSV."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="subscriptions.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['User', 'Email', 'Product', 'Status', 'Created', 'Current Period End', 'Cancel at Period End'])
        
        for subscription in queryset:
            writer.writerow([
                subscription.user.email,
                subscription.user.email,
                subscription.product.name,
                subscription.status,
                subscription.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                subscription.current_period_end.strftime('%Y-%m-%d %H:%M:%S'),
                subscription.cancel_at_period_end
            ])
        
        return response
    export_as_csv.short_description = 'Export selected subscriptions as CSV'

@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(BaseModelAdmin):
    list_display = ('stripe_event_id', 'event_type', 'subscription', 'processed', 'created_at')
    list_filter = ('event_type', 'processed', 'created_at')
    search_fields = ('stripe_event_id', 'event_type', 'subscription__user__email')
    readonly_fields = ('stripe_event_id', 'event_type', 'event_data', 'created_at')
    raw_id_fields = ('subscription',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['mark_as_processed', 'export_as_csv']

    fieldsets = (
        ('Event Information', {
            'fields': ('stripe_event_id', 'event_type', 'subscription', 'processed')
        }),
        ('Event Data', {
            'fields': ('event_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def mark_as_processed(self, request, queryset):
        """Mark selected events as processed."""
        count = queryset.update(processed=True)
        self.message_user(request, f'{count} events marked as processed.')
    mark_as_processed.short_description = 'Mark selected events as processed'

    def export_as_csv(self, request, queryset):
        """Export selected events as CSV."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="subscription_events.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Event ID', 'Event Type', 'Subscription', 'Processed', 'Created'])
        
        for event in queryset:
            writer.writerow([
                event.stripe_event_id,
                event.event_type,
                str(event.subscription) if event.subscription else '',
                event.processed,
                event.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_as_csv.short_description = 'Export selected events as CSV'


# Apple In-App Purchase Subscription Admin
@admin.register(AppleSubscription)
class AppleSubscriptionAdmin(BaseModelAdmin):
    list_display = ('user', 'product_id', 'status_display', 'is_sandbox', 'purchase_date', 'expiration_date', 'days_remaining', 'created_at')
    list_filter = ('is_active', 'is_sandbox', 'product_id', 'purchase_date', 'expiration_date')
    search_fields = ('user__email', 'transaction_id', 'original_transaction_id', 'product_id')
    readonly_fields = ('transaction_id', 'original_transaction_id', 'is_expired', 'days_remaining', 
                      'last_validation_response', 'last_validated_at', 'created_at', 'updated_at')
    raw_id_fields = ('user',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['mark_as_inactive', 'export_as_csv']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'product_id', 'is_active', 'is_sandbox')
        }),
        ('Transaction Details', {
            'fields': ('transaction_id', 'original_transaction_id', 'purchase_date', 'expiration_date')
        }),
        ('Receipt Data', {
            'fields': ('receipt_data',),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('last_validated_at', 'last_validation_response'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_expired', 'days_remaining')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def status_display(self, obj):
        """Display subscription status with color coding."""
        if obj.is_expired:
            return format_html('<span style="color: red;">⏰ Expired</span>')
        elif obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: orange;">⚠ Inactive</span>')
    status_display.short_description = 'Status'
    
    def mark_as_inactive(self, request, queryset):
        """Mark selected subscriptions as inactive."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} subscription(s) marked as inactive.')
    mark_as_inactive.short_description = 'Mark as inactive'
    
    def export_as_csv(self, request, queryset):
        """Export selected Apple subscriptions as CSV."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="apple_subscriptions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'User', 'Email', 'Product ID', 'Transaction ID', 'Original Transaction ID',
            'Purchase Date', 'Expiration Date', 'Is Active', 'Is Sandbox', 'Days Remaining', 'Created'
        ])
        
        for subscription in queryset:
            writer.writerow([
                subscription.user.email,
                subscription.user.email,
                subscription.product_id,
                subscription.transaction_id,
                subscription.original_transaction_id,
                subscription.purchase_date.strftime('%Y-%m-%d %H:%M:%S'),
                subscription.expiration_date.strftime('%Y-%m-%d %H:%M:%S') if subscription.expiration_date else '',
                subscription.is_active,
                subscription.is_sandbox,
                subscription.days_remaining,
                subscription.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_as_csv.short_description = 'Export selected subscriptions as CSV'
