from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import ReceiptUpdateAPIView

# Split URL patterns into web and API
web_urlpatterns = [
    path('', views.receipt_list, name='receipt_list'),
    path('upload/', views.upload_receipt, name='upload_receipt'),
    path('receipts/<str:transaction_number>/', views.receipt_detail, name='receipt_detail'),
    
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='receipt_parser/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    
    # Account Management URLs - handled by React frontend
]

api_urlpatterns = [
    # Receipt API endpoints
    path('receipts/', views.api_receipt_list, name='api_receipt_list'),
    path('receipts/upload/', views.api_receipt_upload, name='api_receipt_upload'),
    path('receipts/<str:transaction_number>/', views.api_receipt_detail, name='api_receipt_detail'),
    path('receipts/<str:transaction_number>/delete/', views.api_receipt_delete, name='api_receipt_delete'),
    path('receipts/<str:transaction_number>/update/', views.api_receipt_update, name='api_receipt_update'),
    # New class-based PATCH endpoint (alternative to the function-based one above)
    path('receipts/<str:transaction_number>/patch/', ReceiptUpdateAPIView.as_view(), name='api_receipt_patch'),
    path('price-adjustments/', views.api_price_adjustments, name='api_price_adjustments'),
    path('price-adjustments/dismiss/<str:item_code>/', views.api_dismiss_price_adjustment, name='api_dismiss_price_adjustment'),
    path('current-sales/', views.api_current_sales, name='api_current_sales'),
    path('debug/alerts/', views.debug_alerts, name='debug_alerts'),
    path('debug/reactivate/', views.reactivate_alerts, name='reactivate_alerts'),
    path('analytics/', views.api_user_analytics, name='api_user_analytics'),
    path('analytics/enhanced/', views.api_enhanced_analytics, name='api_enhanced_analytics'),
    path('on-sale/', views.api_on_sale, name='api_on_sale'),
    
    # Authentication API endpoints (to be implemented)
    
    # Subscription API endpoints
    path('subscriptions/status/', views.api_subscription_status, name='api_subscription_status'),
    path('subscriptions/products/', views.api_subscription_products, name='api_subscription_products'),
    path('subscriptions/create/', views.api_subscription_create, name='api_subscription_create'),
    path('subscriptions/cancel/', views.api_subscription_cancel, name='api_subscription_cancel'),
    path('subscriptions/update/', views.api_subscription_update, name='api_subscription_update'),
    path('subscriptions/create-payment-intent/', views.api_subscription_create_payment_intent, name='api_subscription_create_payment_intent'),
    path('subscriptions/create-checkout-session/', views.api_create_checkout_session, name='api_create_checkout_session'),
    path('subscriptions/webhook/', views.api_subscription_webhook, name='api_subscription_webhook'),
    path('debug/stripe-config/', views.api_debug_stripe_config, name='api_debug_stripe_config'),
    path('debug/auth-test/', views.api_debug_auth_test, name='api_debug_auth_test'),
]

# Use web_urlpatterns by default
urlpatterns = web_urlpatterns

# Add API patterns if this is included under /api/
def urls_api():
    return api_urlpatterns

urlpatterns.append(path('api/analytics/', views.analytics, name='analytics')) 