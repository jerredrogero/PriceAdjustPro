# Django Backend: Email Verification API Implementation Instructions

## Overview
The iOS mobile app needs two API endpoints to handle email verification. These endpoints should accept POST requests with JSON payloads and return JSON responses.

## Required Endpoints

1. **POST** `/api/auth/verify-email/` - Verify email with 6-digit code
2. **POST** `/api/auth/resend-verification/` - Resend verification email

---

## Implementation Steps

### Step 1: Update User Model

Ensure your User model has these fields for email verification:

```python
# In your User model (likely in accounts/models.py or similar)
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email_verification_code = models.CharField(max_length=6, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    verification_code_created_at = models.DateTimeField(null=True, blank=True)  # Optional: for expiration
    
    # ... your other existing fields ...
```

**Run migrations after adding these fields:**
```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Step 2: Create API Views

Create or update your views file (e.g., `accounts/views.py` or `api/views.py`):

```python
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
import random

User = get_user_model()

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_api(request):
    """
    API endpoint for mobile app to verify email with 6-digit code.
    
    Request Body:
    {
        "code": "123456"
    }
    
    Response (Success):
    {
        "message": "Email verified successfully",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "username": "username",
            "first_name": "John",
            "last_name": "Doe",
            "is_email_verified": true,
            "account_type": "free",
            "receipt_count": 0,
            "receipt_limit": 5
        }
    }
    
    Response (Error):
    {
        "error": "Invalid or expired verification code"
    }
    """
    code = request.data.get('code')
    
    if not code:
        return Response(
            {'error': 'Verification code is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find user with this verification code
        user = User.objects.get(
            email_verification_code=code,
            is_email_verified=False
        )
        
        # Optional: Check if code has expired (e.g., 30 minutes)
        if user.verification_code_created_at:
            expiration_time = user.verification_code_created_at + timedelta(minutes=30)
            if datetime.now() > expiration_time:
                return Response(
                    {'error': 'Verification code has expired. Please request a new one.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Mark email as verified
        user.is_email_verified = True
        user.email_verification_code = None  # Clear the code
        user.verification_code_created_at = None
        user.save()
        
        # Return user data matching the iOS app's expected format
        user_data = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_email_verified': True,
            'account_type': getattr(user, 'account_type', 'free'),
            'receipt_count': getattr(user, 'receipt_count', 0),
            'receipt_limit': getattr(user, 'receipt_limit', 5),
        }
        
        return Response({
            'message': 'Email verified successfully',
            'user': user_data
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid or expired verification code'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Verification failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_api(request):
    """
    API endpoint for mobile app to resend verification email.
    
    Request Body:
    {
        "email": "user@example.com"
    }
    
    Response (Success):
    {
        "message": "Verification email sent successfully"
    }
    
    Response (Error):
    {
        "error": "User not found or already verified"
    }
    """
    email = request.data.get('email')
    
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Find unverified user with this email
        user = User.objects.get(email=email, is_email_verified=False)
        
        # Generate new 6-digit verification code
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        user.email_verification_code = verification_code
        user.verification_code_created_at = datetime.now()
        user.save()
        
        # Send verification email
        send_verification_email(user, verification_code)
        
        return Response({
            'message': 'Verification email sent successfully'
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found or already verified'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to send verification email: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def send_verification_email(user, code):
    """
    Send verification email with 6-digit code.
    Reuse your existing email sending logic or create new.
    """
    subject = 'Verify Your Email - PriceAdjustPro'
    message = f'''
    Hi {user.first_name or user.username},
    
    Thank you for registering with PriceAdjustPro!
    
    Your verification code is: {code}
    
    This code will expire in 30 minutes.
    
    If you didn't request this, please ignore this email.
    
    Best regards,
    The PriceAdjustPro Team
    '''
    
    html_message = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .code {{ font-size: 32px; font-weight: bold; color: #E00034; text-align: center; 
                     padding: 20px; background: #f5f5f5; border-radius: 8px; margin: 20px 0; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Verify Your Email</h2>
            <p>Hi {user.first_name or user.username},</p>
            <p>Thank you for registering with PriceAdjustPro!</p>
            <p>Your verification code is:</p>
            <div class="code">{code}</div>
            <p>This code will expire in 30 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <div class="footer">
                <p>Best regards,<br>The PriceAdjustPro Team</p>
            </div>
        </div>
    </body>
    </html>
    '''
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
```

---

### Step 3: Update Registration View

Update your existing registration endpoint to generate and send verification code:

```python
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Updated registration endpoint that sends verification email.
    """
    email = request.data.get('email')
    password = request.data.get('password')
    first_name = request.data.get('first_name')
    last_name = request.data.get('last_name')
    
    # Validate input
    if not all([email, password, first_name, last_name]):
        return Response(
            {'error': 'All fields are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if user already exists
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Create user
        user = User.objects.create_user(
            username=email,  # or generate unique username
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_email_verified=False
        )
        
        # Generate verification code
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        user.email_verification_code = verification_code
        user.verification_code_created_at = datetime.now()
        user.save()
        
        # Send verification email
        send_verification_email(user, verification_code)
        
        # Return response matching iOS app's expected format
        return Response({
            'message': 'Account created successfully. Please check your email for your verification code.',
            'email': user.email,
            'username': user.username,
            'verification_required': True
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Registration failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
```

---

### Step 4: Add URL Routes

Add the new endpoints to your `urls.py`:

```python
# In your main urls.py or api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ... your existing URLs ...
    
    # Registration
    path('api/auth/register/', views.register, name='register'),
    
    # Email verification endpoints for mobile app
    path('api/auth/verify-email/', views.verify_email_api, name='verify_email_api'),
    path('api/auth/resend-verification/', views.resend_verification_api, name='resend_verification_api'),
]
```

---

### Step 5: Configure Email Settings

Ensure your `settings.py` has email configuration:

```python
# Email configuration (example using Gmail)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'PriceAdjustPro <noreply@priceadjustpro.com>'

# Or for development/testing, use console backend:
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

---

### Step 6: Update CORS Settings

If not already done, ensure your Django app allows requests from mobile apps:

```python
# In settings.py

INSTALLED_APPS = [
    # ...
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ...
]

# For development
CORS_ALLOW_ALL_ORIGINS = True

# For production, specify allowed origins
CORS_ALLOWED_ORIGINS = [
    "https://yourdomain.com",
]

# Trust your domain for CSRF
CSRF_TRUSTED_ORIGINS = [
    'https://priceadjustpro.onrender.com',
]
```

---

## Testing the Endpoints

### Test Verify Email:
```bash
curl -X POST https://priceadjustpro.onrender.com/api/auth/verify-email/ \
  -H "Content-Type: application/json" \
  -d '{"code": "123456"}'
```

Expected response:
```json
{
  "message": "Email verified successfully",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "user",
    "first_name": "John",
    "last_name": "Doe",
    "is_email_verified": true,
    "account_type": "free",
    "receipt_count": 0,
    "receipt_limit": 5
  }
}
```

### Test Resend Verification:
```bash
curl -X POST https://priceadjustpro.onrender.com/api/auth/resend-verification/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

Expected response:
```json
{
  "message": "Verification email sent successfully"
}
```

---

## Important Notes

1. **@csrf_exempt**: Required for mobile API endpoints since they can't handle CSRF tokens the same way browsers do.

2. **AllowAny Permission**: Verification endpoints need to be accessible without authentication since users aren't logged in yet.

3. **Code Expiration**: The 30-minute expiration is optional but recommended for security.

4. **Email Sending**: Make sure your email backend is properly configured before deploying.

5. **Error Handling**: All endpoints include proper error handling and return appropriate HTTP status codes.

6. **Security**: 
   - Codes are single-use (cleared after verification)
   - Optional expiration time
   - Rate limiting should be added in production

---

## Deployment Checklist

- [ ] User model has required fields
- [ ] Migrations are created and applied
- [ ] New API views are created
- [ ] URL routes are added
- [ ] Email backend is configured
- [ ] CORS settings are updated
- [ ] Code has been tested locally
- [ ] Changes are deployed to production
- [ ] Endpoints are accessible from mobile app

---

## Expected iOS App Flow

1. User registers → receives `verification_required: true`
2. iOS app shows verification screen
3. User enters 6-digit code from email
4. iOS app calls `/api/auth/verify-email/`
5. Backend verifies code and returns user data
6. iOS app authenticates user and shows main app

---

## Need Help?

If you encounter issues:
1. Check Django logs for errors
2. Test endpoints with curl or Postman
3. Verify email settings are correct
4. Check that migrations were applied
5. Ensure CORS is configured properly

After implementing these changes, redeploy your Django backend and the iOS app should be able to verify emails successfully!

