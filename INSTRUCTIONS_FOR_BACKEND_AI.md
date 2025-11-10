# Instructions for Django Backend Implementation - Apple IAP Support

## Context

You are working on the Django backend for **PriceAdjustPro**, a Costco receipt management web application. The iOS app has just been published to the App Store with subscription functionality, but users who purchase subscriptions through Apple In-App Purchases are not being upgraded to premium because the backend endpoints don't exist yet.

**GitHub Repository**: https://github.com/jerredrogero/PriceAdjustPro
**Backend URL**: https://priceadjustpro.onrender.com
**Hosting**: Render.com

## Current State

The repository has:
- Django backend in `price_adjust_pro/` directory
- React frontend in `frontend/` directory
- Existing user authentication (Django session-based)
- Existing Stripe subscription support (for web users)
- User model with profile/account system
- PostgreSQL database (on Render)

## What Needs to Be Done

The iOS app is trying to POST purchase data to these endpoints that **DON'T EXIST YET**:
- `POST /api/subscriptions/apple/purchase/` - Process new purchases
- `POST /api/subscriptions/apple/validate/` - Validate subscription status

You need to:
1. Create a new Django model for Apple subscriptions
2. Create two API endpoints to handle Apple IAP
3. Integrate with Apple's receipt validation servers
4. Update user premium status when purchases are validated
5. Deploy changes to Render.com

## iOS App's Expected Behavior

When a user makes a purchase, the iOS app sends this JSON:

```json
POST https://priceadjustpro.onrender.com/api/subscriptions/apple/purchase/
Headers:
  Content-Type: application/json
  Cookie: sessionid=... (Django session auth)

Body:
{
  "transaction_id": "1000000123456789",
  "product_id": "com.priceadjustpro.monthly",
  "receipt_data": "MIITtgYJKoZIhvcNAQcCoIITpzCCE6MCqGSIb3...",
  "original_transaction_id": "1000000123456789",
  "purchase_date": "2024-01-15T10:30:00Z",
  "expiration_date": "2024-02-15T10:30:00Z"
}
```

Expected response on success:
```json
{
  "success": true,
  "subscription_id": 123,
  "is_sandbox": true,
  "created": true
}
```

## Product IDs to Support

- `com.priceadjustpro.monthly` - $4.99/month subscription
- `com.priceadjustpro.yearly` - $49.99/year subscription

## Detailed Implementation Steps

### Step 1: Update requirements.txt

Add these dependencies:
```txt
requests>=2.31.0
python-dateutil>=2.8.2
```

### Step 2: Create Apple Subscription Model

**File to create**: `price_adjust_pro/models.py` (or if models are split, create `price_adjust_pro/models/apple_subscriptions.py`)

You need to create an `AppleSubscription` model with these fields:
- `user` (ForeignKey to User)
- `transaction_id` (CharField, indexed)
- `original_transaction_id` (CharField, unique, indexed) - This prevents duplicate purchases
- `product_id` (CharField) - Which subscription tier
- `receipt_data` (TextField) - Base64 encoded receipt from Apple
- `purchase_date` (DateTimeField)
- `expiration_date` (DateTimeField, nullable)
- `is_active` (BooleanField)
- `is_sandbox` (BooleanField) - Track test vs production purchases
- `created_at` / `updated_at` (DateTimeField)
- `last_validation_response` (JSONField, nullable) - Store Apple's response
- `last_validation_date` (DateTimeField, nullable)

Add an `is_expired` property method that checks if expiration_date has passed.

### Step 3: Update User/Profile Model

The existing User or UserProfile model needs these fields (if they don't already exist):
- `is_premium` (BooleanField, default=False)
- `subscription_type` (CharField with choices: 'stripe', 'apple', 'free')

**Important**: Check the existing codebase structure first. They might already have a UserProfile or similar model. Don't duplicate - just add these fields if missing.

### Step 4: Create Apple IAP Views

**File to create**: `price_adjust_pro/views/apple_iap.py` (or add to existing views file)

You need to implement:

#### Function 1: `process_apple_purchase(request)`
- Decorator: `@api_view(['POST'])` and `@permission_classes([IsAuthenticated])`
- Extract: transaction_id, product_id, receipt_data, original_transaction_id, purchase_date, expiration_date from request.data
- Validate all required fields are present
- Parse ISO8601 date strings using `dateutil.parser.parse()`
- Call `validate_apple_receipt()` to validate with Apple's servers
- If Apple returns status 0 (success):
  - Use `update_or_create()` with `original_transaction_id` as key (prevents duplicates)
  - Create/update AppleSubscription record
  - Get or create user's profile
  - Set `is_premium=True` and `subscription_type='apple'`
  - Return success response with subscription_id, is_sandbox, created flag
- If validation fails, return appropriate error message
- Log all operations for debugging

#### Function 2: `validate_apple_subscription(request)`
- Decorator: `@api_view(['POST'])` and `@permission_classes([IsAuthenticated])`
- Extract: receipt_data from request.data
- Call `validate_apple_receipt()`
- Parse `latest_receipt_info` from Apple's response
- Find most recent active subscription (where expiration_date > now)
- Return: is_active, product_id, expiration_date, subscription_type

#### Helper Function: `validate_apple_receipt(receipt_data)`
- This validates the receipt with Apple's servers
- URLs:
  - Production: `https://buy.itunes.apple.com/verifyReceipt`
  - Sandbox: `https://sandbox.itunes.apple.com/verifyReceipt`
- Payload: `{"receipt-data": receipt_data, "password": shared_secret}`
- **Strategy**: Try production first. If status code 21007 (sandbox receipt), retry with sandbox URL
- Return the Apple response JSON with added `is_sandbox` flag
- Handle request timeouts (10 seconds)

#### Helper Function: `get_apple_error_message(status_code)`
- Map Apple's numeric status codes to human-readable messages
- Common codes: 21000 (invalid JSON), 21003 (auth failed), 21007 (sandbox receipt), etc.

**Critical**: Apple receipt validation MUST happen server-side for security. Never trust the iOS app's validation.

### Step 5: Add URL Routes

**File to modify**: `price_adjust_pro/urls.py`

Add these patterns:
```python
from price_adjust_pro.views import apple_iap

urlpatterns = [
    # ... existing patterns ...
    path('api/subscriptions/apple/purchase/', apple_iap.process_apple_purchase, name='apple_purchase'),
    path('api/subscriptions/apple/validate/', apple_iap.validate_apple_subscription, name='apple_validate'),
]
```

### Step 6: Update Settings

**File to modify**: `price_adjust_pro/settings.py`

Add:
```python
# Apple In-App Purchase Configuration
APPLE_SHARED_SECRET = os.environ.get('APPLE_SHARED_SECRET', '')
```

The user will set this environment variable on Render.com after you implement the code.

### Step 7: Authentication Compatibility

The iOS app uses **session-based authentication** (cookies), not token-based. Ensure your API views accept Django session authentication. If using Django REST Framework, the settings should include:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    # ... other settings
}
```

### Step 8: Create and Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

Run this locally first to test, then it will need to run on Render.

### Step 9: Test Locally (if possible)

```bash
python manage.py runserver

# In another terminal:
curl http://localhost:8000/api/subscriptions/apple/purchase/
# Should return 401 Unauthorized or 403 Forbidden (auth required)
```

### Step 10: Deploy to Render

After committing changes:
1. Push to GitHub
2. Render will auto-deploy
3. Render runs migrations automatically (if configured in render.yaml)
4. Check Render logs for any deployment errors

## Apple Receipt Validation Details

Apple's receipt validation returns a status code:
- `0` = Valid receipt
- `21007` = Receipt is from sandbox environment (retry with sandbox URL)
- Other codes = Various errors

For auto-renewable subscriptions (which this is), you need the **App-Specific Shared Secret** from App Store Connect. This is passed as the `password` field in the validation request.

The response includes `latest_receipt_info` array with all transactions. You need to find the most recent one where `expires_date_ms` > current time.

## Security Considerations

1. **Always validate server-side** - The iOS app could be compromised
2. **Use original_transaction_id as unique key** - Prevents replay attacks
3. **Verify expiration dates** - Don't grant access for expired subscriptions
4. **Log all validation attempts** - For debugging and fraud detection
5. **Handle both sandbox and production** - Test purchases use sandbox, real purchases use production

## Error Handling

Be prepared to handle:
- Missing required fields → 400 Bad Request
- User not authenticated → 401 Unauthorized  
- Apple's servers down → 500 Server Error (retry logic helpful)
- Invalid receipt → 400 Bad Request with specific error message
- Duplicate transaction_id → Update existing record (not an error)

## Testing After Deployment

The user will test by:
1. Making a test purchase in the iOS app (using Sandbox Apple ID)
2. Checking if the request appears in Render logs
3. Checking if AppleSubscription record was created in database
4. Checking if user's is_premium was set to True
5. Verifying the iOS app shows premium features

You can help them test with:
```bash
curl -X POST https://priceadjustpro.onrender.com/api/subscriptions/apple/purchase/ \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=YOUR_SESSION_ID" \
  -d '{"transaction_id":"test","product_id":"com.priceadjustpro.monthly","receipt_data":"dummy","original_transaction_id":"test","purchase_date":"2024-01-01T00:00:00Z"}'
```

## Expected Outcome

After implementation:
1. ✅ Endpoints exist and return 401/403 without auth (not 404)
2. ✅ Authenticated iOS users can POST purchase data
3. ✅ Backend validates receipts with Apple's servers
4. ✅ Successful purchases create AppleSubscription records
5. ✅ Users are automatically upgraded to premium
6. ✅ iOS app can validate subscription status

## Django Admin Setup (Bonus)

After creating the model, register it in admin.py so the user can view subscriptions:

```python
from django.contrib import admin
from .models import AppleSubscription

@admin.register(AppleSubscription)
class AppleSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'product_id', 'is_active', 'is_sandbox', 'purchase_date', 'expiration_date']
    list_filter = ['is_active', 'is_sandbox', 'product_id']
    search_fields = ['user__email', 'transaction_id', 'original_transaction_id']
    readonly_fields = ['created_at', 'updated_at', 'last_validation_response']
```

## Reference Files

The iOS app implementation is complete. Reference these files if needed:
- iOS: `PriceAdjustPro/Services/StoreKitService.swift` - Handles purchases
- iOS: `PriceAdjustPro/Services/SubscriptionSyncService.swift` - Syncs with backend
- Docs: `DJANGO_APPLE_IAP_SETUP.md` - Detailed implementation guide
- Docs: `QUICK_START_BACKEND.md` - Copy-paste ready code snippets

## Common Pitfalls to Avoid

1. ❌ Don't use token authentication - the app uses session cookies
2. ❌ Don't forget to check both sandbox and production receipt validation
3. ❌ Don't store sensitive data in logs (receipt data is large and sensitive)
4. ❌ Don't allow duplicate subscriptions - use original_transaction_id as unique key
5. ❌ Don't forget to handle timezone-aware datetimes properly
6. ❌ Don't return detailed error messages that expose system internals

## Questions to Ask Before Starting

1. Does the codebase already have a UserProfile or similar model?
2. How is the user's premium status currently stored for Stripe subscriptions?
3. Are there existing API views you should follow as a pattern?
4. Is there a consistent location for new models and views?
5. Does render.yaml already handle migrations, or does it need to be updated?

## Summary

You need to:
- ✅ Create AppleSubscription model
- ✅ Update User/Profile model with is_premium and subscription_type
- ✅ Create two API endpoints for purchase processing and validation
- ✅ Implement Apple receipt validation logic
- ✅ Add URL routes
- ✅ Update settings for Apple shared secret
- ✅ Create and run migrations
- ✅ Deploy to Render

The iOS app is ready and waiting for these endpoints to exist. Once deployed, users will be able to purchase subscriptions and be automatically upgraded to premium.

## Success Criteria

Implementation is complete when:
1. `curl https://priceadjustpro.onrender.com/api/subscriptions/apple/purchase/` returns 401 (not 404)
2. iOS app can make a test purchase successfully
3. User's account shows as premium after purchase
4. AppleSubscription record appears in Django admin
5. No errors in Render deployment logs

Good luck! The iOS app is ready and waiting for your backend implementation.

