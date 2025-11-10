# Django Backend Setup for Apple In-App Purchases

This guide shows you how to add Apple IAP support to your Django backend at https://priceadjustpro.onrender.com

## 🚨 Critical Issues Found

Your iOS app is trying to sync purchases but the backend endpoints don't exist yet. Here's what needs to be implemented.

## Required Backend Changes

### 1. Install Required Package

Add to your `requirements.txt`:

```txt
requests>=2.31.0
```

### 2. Create Apple Subscription Model

In `price_adjust_pro/models.py` (or create a new `subscriptions/models.py`):

```python
from django.db import models
from django.contrib.auth.models import User

class AppleSubscription(models.Model):
    """Stores Apple in-app purchase subscription data"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='apple_subscriptions')
    
    # Transaction identifiers from Apple
    transaction_id = models.CharField(max_length=255, db_index=True)
    original_transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Product details
    product_id = models.CharField(max_length=255)  # e.g., 'com.priceadjustpro.monthly'
    
    # Receipt data (base64 encoded)
    receipt_data = models.TextField()
    
    # Dates
    purchase_date = models.DateTimeField()
    expiration_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_sandbox = models.BooleanField(default=False)  # Track if this is a sandbox purchase
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Validation response from Apple
    last_validation_response = models.JSONField(null=True, blank=True)
    last_validation_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'apple_subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['original_transaction_id']),
        ]
    
    def __str__(self):
        return f"Apple Subscription - {self.user.email} - {self.product_id}"
    
    @property
    def is_expired(self):
        """Check if subscription is expired"""
        if not self.expiration_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.expiration_date
```

### 3. Update Your User Profile Model

Ensure your User or UserProfile model tracks subscription status. Add these fields if they don't exist:

```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_premium = models.BooleanField(default=False)
    subscription_type = models.CharField(
        max_length=20,
        choices=[('stripe', 'Stripe'), ('apple', 'Apple'), ('free', 'Free')],
        default='free'
    )
    # ... your other fields
```

### 4. Create Apple IAP Views

Create a new file `price_adjust_pro/views/apple_subscriptions.py`:

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
import requests
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Apple receipt validation URLs
APPLE_SANDBOX_URL = "https://sandbox.itunes.apple.com/verifyReceipt"
APPLE_PRODUCTION_URL = "https://buy.itunes.apple.com/verifyReceipt"


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_apple_purchase(request):
    """
    Process and validate Apple in-app purchase receipt
    
    Expected request body:
    {
        "transaction_id": "string",
        "product_id": "string",
        "receipt_data": "base64_encoded_string",
        "original_transaction_id": "string",
        "purchase_date": "ISO8601_datetime",
        "expiration_date": "ISO8601_datetime" (optional)
    }
    """
    try:
        # Extract data from request
        transaction_id = request.data.get('transaction_id')
        product_id = request.data.get('product_id')
        receipt_data = request.data.get('receipt_data')
        original_transaction_id = request.data.get('original_transaction_id')
        purchase_date_str = request.data.get('purchase_date')
        expiration_date_str = request.data.get('expiration_date')
        
        # Validate required fields
        if not all([transaction_id, product_id, receipt_data, original_transaction_id, purchase_date_str]):
            return Response(
                {'error': 'Missing required fields'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse dates
        from dateutil import parser
        purchase_date = parser.parse(purchase_date_str)
        expiration_date = parser.parse(expiration_date_str) if expiration_date_str else None
        
        # Validate with Apple's servers
        logger.info(f"Validating Apple receipt for user {request.user.email}")
        apple_response = validate_apple_receipt(receipt_data)
        
        if not apple_response:
            return Response(
                {'error': 'Failed to validate receipt with Apple'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        is_sandbox = apple_response.get('is_sandbox', False)
        
        if apple_response.get('status') == 0:  # Success
            # Import your models here
            from price_adjust_pro.models import AppleSubscription, UserProfile
            
            # Create or update subscription
            subscription, created = AppleSubscription.objects.update_or_create(
                original_transaction_id=original_transaction_id,
                defaults={
                    'user': request.user,
                    'product_id': product_id,
                    'transaction_id': transaction_id,
                    'receipt_data': receipt_data,
                    'purchase_date': purchase_date,
                    'expiration_date': expiration_date,
                    'is_active': True,
                    'is_sandbox': is_sandbox,
                    'last_validation_response': apple_response,
                    'last_validation_date': timezone.now()
                }
            )
            
            # Update user's premium status
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.is_premium = True
            profile.subscription_type = 'apple'
            profile.save()
            
            logger.info(f"Apple subscription {'created' if created else 'updated'} for user {request.user.email}")
            
            return Response({
                'success': True,
                'subscription_id': subscription.id,
                'is_sandbox': is_sandbox,
                'created': created
            }, status=status.HTTP_200_OK)
        else:
            error_msg = get_apple_error_message(apple_response.get('status'))
            logger.warning(f"Apple receipt validation failed: {error_msg}")
            return Response(
                {'error': f'Invalid receipt: {error_msg}'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Error processing Apple purchase: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_apple_subscription(request):
    """
    Validate current Apple subscription status
    
    Expected request body:
    {
        "receipt_data": "base64_encoded_string"
    }
    """
    try:
        receipt_data = request.data.get('receipt_data')
        
        if not receipt_data:
            return Response(
                {'error': 'Receipt data is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate with Apple
        apple_response = validate_apple_receipt(receipt_data)
        
        if not apple_response:
            return Response(
                {'error': 'Failed to validate receipt with Apple'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        if apple_response.get('status') == 0:
            # Check if subscription is still active
            latest_receipt_info = apple_response.get('latest_receipt_info', [])
            
            is_active = False
            expiration_date = None
            product_id = None
            
            # Find the most recent active subscription
            for receipt in latest_receipt_info:
                exp_date_ms = receipt.get('expires_date_ms')
                if exp_date_ms:
                    exp_date = datetime.fromtimestamp(int(exp_date_ms) / 1000, tz=timezone.utc)
                    if exp_date > timezone.now():
                        is_active = True
                        expiration_date = exp_date.isoformat()
                        product_id = receipt.get('product_id')
                        break
            
            return Response({
                'is_active': is_active,
                'product_id': product_id,
                'expiration_date': expiration_date,
                'subscription_type': 'apple'
            })
        else:
            return Response({
                'is_active': False,
                'product_id': None,
                'expiration_date': None,
                'subscription_type': None
            })
            
    except Exception as e:
        logger.error(f"Error validating Apple subscription: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def validate_apple_receipt(receipt_data):
    """
    Validate receipt with Apple's servers
    Tries production first, then sandbox
    """
    shared_secret = getattr(settings, 'APPLE_SHARED_SECRET', None)
    
    payload = {
        "receipt-data": receipt_data,
    }
    
    # Add shared secret if configured (required for auto-renewable subscriptions)
    if shared_secret:
        payload["password"] = shared_secret
    
    # Try production first
    try:
        response = requests.post(APPLE_PRODUCTION_URL, json=payload, timeout=10)
        result = response.json()
        
        # If status is 21007, receipt is from sandbox - retry with sandbox URL
        if result.get('status') == 21007:
            logger.info("Receipt is from sandbox, retrying with sandbox URL")
            response = requests.post(APPLE_SANDBOX_URL, json=payload, timeout=10)
            result = response.json()
            result['is_sandbox'] = True
            return result
        
        result['is_sandbox'] = False
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to validate receipt with Apple: {str(e)}")
        return None


def get_apple_error_message(status_code):
    """Get human-readable error message for Apple status codes"""
    error_messages = {
        21000: "The App Store could not read the JSON object you provided.",
        21002: "The data in the receipt-data property was malformed or missing.",
        21003: "The receipt could not be authenticated.",
        21004: "The shared secret you provided does not match the shared secret on file.",
        21005: "The receipt server is not currently available.",
        21006: "This receipt is valid but the subscription has expired.",
        21007: "This receipt is from the test environment.",
        21008: "This receipt is from the production environment.",
        21010: "This receipt could not be authorized.",
    }
    return error_messages.get(status_code, f"Unknown error (status {status_code})")
```

### 5. Add URL Routes

In your `price_adjust_pro/urls.py`, add:

```python
from django.urls import path
from .views import apple_subscriptions

urlpatterns = [
    # ... your existing URLs ...
    
    # Apple IAP endpoints
    path('api/subscriptions/apple/purchase/', apple_subscriptions.process_apple_purchase, name='apple_purchase'),
    path('api/subscriptions/apple/validate/', apple_subscriptions.validate_apple_subscription, name='apple_validate'),
]
```

### 6. Configure Settings

In your `price_adjust_pro/settings.py`, add:

```python
# Apple In-App Purchase Configuration
APPLE_SHARED_SECRET = os.environ.get('APPLE_SHARED_SECRET', '')

# Add python-dateutil if not already in requirements
# It's needed for parsing ISO8601 dates from iOS
```

Also add to `requirements.txt`:
```txt
python-dateutil>=2.8.2
```

### 7. Create and Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 8. Get Your Apple Shared Secret

1. Go to [App Store Connect](https://appstoreconnect.apple.com/)
2. Navigate to: **My Apps** → **Your App** → **Features** → **In-App Purchases**
3. Click **App-Specific Shared Secret** → **Generate**
4. Copy the shared secret

### 9. Set Environment Variable on Render.com

1. Go to your Render.com dashboard
2. Select your Django web service
3. Go to **Environment** tab
4. Add new environment variable:
   - Key: `APPLE_SHARED_SECRET`
   - Value: `your_shared_secret_from_app_store_connect`
5. Click **Save Changes** (this will trigger a redeploy)

### 10. Update Authentication (Important!)

Your iOS app sends a Bearer token, but your Django backend might be using session-based auth. You need to ensure the token is accepted.

If you're using Django REST Framework with token auth, make sure you have:

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',  # Add this
    ],
}
```

### 11. Testing

#### Test from iOS Simulator:
1. Run your iOS app in simulator/device
2. Make a test purchase using a Sandbox Apple ID
3. Check Django logs to see if the request reaches the endpoint
4. Check database to see if AppleSubscription was created

#### Test with curl:
```bash
curl -X POST https://priceadjustpro.onrender.com/api/subscriptions/apple/purchase/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "transaction_id": "test123",
    "product_id": "com.priceadjustpro.monthly",
    "receipt_data": "YOUR_BASE64_RECEIPT",
    "original_transaction_id": "test123",
    "purchase_date": "2024-01-01T00:00:00Z",
    "expiration_date": "2024-02-01T00:00:00Z"
  }'
```

## 🔍 Debugging Tips

### Check if endpoint exists:
```bash
curl https://priceadjustpro.onrender.com/api/subscriptions/apple/purchase/
```

### Check Django logs on Render:
1. Go to Render dashboard
2. Select your service
3. Go to **Logs** tab
4. Look for errors when iOS app makes requests

### Common Issues:

1. **401 Unauthorized**: Token authentication isn't working
   - Solution: Implement token auth or use session-based auth

2. **404 Not Found**: URL routing is wrong
   - Solution: Check your `urls.py` configuration

3. **500 Server Error**: Code error in the view
   - Solution: Check Render logs for stack trace

4. **Receipt validation fails**: Wrong shared secret
   - Solution: Verify APPLE_SHARED_SECRET is set correctly

## 📱 iOS App Status

✅ **Fixed Issues:**
- URL construction bug (was creating `/api/api/...`)
- Now correctly creates: `https://priceadjustpro.onrender.com/api/subscriptions/apple/purchase/`

⚠️ **Remaining iOS Issue:**
- Authentication token might not be present if using session-based auth
- The iOS app tries to get a Bearer token but might not have one

## Next Steps

1. ✅ Deploy these backend changes to your Django app
2. ⚠️ Set the APPLE_SHARED_SECRET environment variable
3. ⚠️ Verify authentication works (token or session)
4. ✅ Test a purchase from your iOS app
5. ✅ Check that user account upgrades to premium

## Support

If you encounter issues:
1. Check Render logs for backend errors
2. Check Xcode console for iOS errors
3. Verify the URL is correct: `https://priceadjustpro.onrender.com/api/subscriptions/apple/purchase/`
4. Verify authentication is configured correctly

