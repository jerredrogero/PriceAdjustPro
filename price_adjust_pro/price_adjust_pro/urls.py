"""
URL configuration for price_adjust_pro project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.views.generic import TemplateView
from django.middleware.csrf import get_token
import json
import os
from django.contrib.staticfiles.views import serve
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site

from receipt_parser.urls import urls_api as receipt_api_urls

# Configure admin site
admin.site.site_header = 'PriceAdjustPro Administration'
admin.site.site_title = 'PriceAdjustPro Admin'
admin.site.index_title = 'Site Administration'

def home_redirect(request):
    return redirect('receipt_list')

def serve_react_file(request, filename):
    """Serve React static files from the build directory."""
    file_path = os.path.join(settings.REACT_APP_BUILD_PATH, filename)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'))
    return serve(request, filename, document_root=settings.STATIC_ROOT)

@ensure_csrf_cookie
@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        try:
            print("Login attempt received")
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                print(f"Login error: Missing username or password")
                return JsonResponse({'error': 'Username and password are required'}, status=400)
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                print(f"User {username} authenticated successfully")
                login(request, user)
                
                # Set session cookie attributes
                request.session.set_expiry(1209600)  # 2 weeks
                
                # Ensure CSRF token is set
                csrf_token = get_token(request)
                
                # Get account type from user profile
                try:
                    from receipt_parser.models import UserProfile
                    profile = UserProfile.objects.get(user=user)
                    account_type = 'paid' if profile.is_paid_account else 'free'
                    is_paid_account = profile.is_paid_account
                except UserProfile.DoesNotExist:
                    # Create profile if it doesn't exist
                    UserProfile.objects.create(user=user, account_type='free')
                    account_type = 'free'
                    is_paid_account = False
                
                response = JsonResponse({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'account_type': account_type,
                    'is_paid_account': is_paid_account,
                })
                
                # Set CSRF cookie explicitly
                response.set_cookie(
                    'csrftoken',
                    csrf_token,
                    max_age=31536000,  # 1 year
                    secure=not settings.DEBUG,
                    httponly=False,
                    samesite='Lax',
                    domain=settings.CSRF_COOKIE_DOMAIN if not settings.DEBUG else None
                )
                
                print(f"Login response prepared for {username}")
                return response
                
            print(f"Login failed: Invalid credentials for {username}")
            return JsonResponse({'error': 'Invalid credentials'}, status=401)
        except json.JSONDecodeError:
            print("Login error: Invalid JSON")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"Login error: {str(e)}")
            return JsonResponse({'error': 'Login failed'}, status=500)
    
    print("Login error: Method not allowed")
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_logout(request):
    if request.method in ['POST', 'GET']:
        print(f"Logout request for user: {request.user.username if request.user.is_authenticated else 'anonymous'}")
        logout(request)
        # Check if the request wants JSON response or redirect
        if request.headers.get('Accept') == 'application/json':
            print("Sending JSON logout response")
            return JsonResponse({'message': 'Logged out successfully'})
        else:
            # Redirect to login page
            print("Redirecting to login page after logout")
            return redirect('/login')
    
    print("Logout error: Method not allowed")
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_register(request):
    if request.method == 'POST':
        try:
            print("Registration attempt received")
            data = json.loads(request.body)
            from django.contrib.auth.models import User
            
            # Handle both web form format and iOS app format
            # Web form: username, email, password1, password2
            # iOS app: first_name, last_name, email, password
            
            # Try iOS app format first
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            email = data.get('email')
            password = data.get('password')
            
            # Fallback to web form format
            if not first_name:
                username = data.get('username')
                password1 = data.get('password1')
                password2 = data.get('password2')
                
                print(f"Web registration attempt for user: {username}, email: {email}")
                
                if not all([username, email, password1, password2]):
                    print("Registration error: Missing required fields")
                    return JsonResponse({'error': 'All fields are required'}, status=400)
                
                if password1 != password2:
                    print("Registration error: Passwords do not match")
                    return JsonResponse({'error': 'Passwords do not match'}, status=400)
                
                if User.objects.filter(username=username).exists():
                    print(f"Registration error: Username {username} already exists")
                    return JsonResponse({'error': 'Username already exists'}, status=400)
                
                # Create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1
                )
            else:
                # iOS app format - create username from first name and email
                print(f"iOS registration attempt for: {first_name} {last_name}, email: {email}")
                
                if not all([first_name, email, password]):
                    print("Registration error: Missing required fields (first_name, email, password)")
                    return JsonResponse({'error': 'All fields are required'}, status=400)
                
                # Create username from first name and email domain
                base_username = first_name.lower()
                username = base_username
                counter = 1
                
                # Ensure username is unique
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                print(f"Generated username: {username}")
                
                # Create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
            
            # Log the user in
            login(request, user)
            print(f"User {username} created and logged in successfully")
            
            # Set session cookie attributes and expiry
            request.session.set_expiry(1209600)  # 2 weeks
            
            # Ensure CSRF token is set
            csrf_token = get_token(request)
            
            # Get account type from user profile (should be 'free' for new users)
            try:
                from receipt_parser.models import UserProfile
                profile = UserProfile.objects.get(user=user)
                account_type = 'paid' if profile.is_paid_account else 'free'
                is_paid_account = profile.is_paid_account
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist (should have been created by signal)
                UserProfile.objects.create(user=user, account_type='free')
                account_type = 'free'
                is_paid_account = False
            
            response = JsonResponse({
                'message': 'Account created successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'account_type': account_type,
                    'is_paid_account': is_paid_account,
                }
            })
            
            # Set CSRF cookie explicitly
            response.set_cookie(
                'csrftoken',
                csrf_token,
                max_age=31536000,  # 1 year
                secure=not settings.DEBUG,
                httponly=False,
                samesite='Lax',
                domain=settings.CSRF_COOKIE_DOMAIN if not settings.DEBUG else None
            )
            
            return response
        except Exception as e:
            print(f"Registration error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_delete_account(request):
    """Delete user account and all associated data."""
    if request.method == 'DELETE':
        try:
            if not request.user.is_authenticated:
                print(f"Delete account: User not authenticated")
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            print(f"Delete account request from user: {request.user.username}")
            print(f"Request body: {request.body}")
            print(f"Content type: {request.content_type}")
            
            # Try to parse JSON data first, then fall back to form data
            password = None
            try:
                if request.body:
                    data = json.loads(request.body)
                    password = data.get('password')
                    print(f"Parsed JSON data: {data}")
                else:
                    print("No request body provided")
                    data = {}
            except json.JSONDecodeError:
                # Fall back to form data or query parameters
                print("Failed to parse JSON, trying form data")
                data = {}
                if hasattr(request, 'POST') and request.POST:
                    password = request.POST.get('password')
                    print(f"Found password in POST data")
                elif hasattr(request, 'GET') and request.GET:
                    password = request.GET.get('password')
                    print(f"Found password in GET data")
            
            print(f"Final password status: {'[PRESENT]' if password else '[MISSING]'}")
            
            if not password:
                print(f"Delete account: Missing password. Body: {request.body}, POST: {getattr(request, 'POST', {})}")
                return JsonResponse({
                    'error': 'Password is required for account deletion',
                    'details': 'Please include password in request body as JSON: {"password": "your_password"}'
                }, status=400)
            
            user = request.user
            
            # Verify password
            if not user.check_password(password):
                return JsonResponse({'error': 'Incorrect password'}, status=400)
            
            # Import models here to avoid circular imports
            from receipt_parser.models import Receipt, PriceAdjustmentAlert, UserProfile
            import logging
            
            logger = logging.getLogger(__name__)
            
            try:
                # Log account deletion for audit purposes
                logger.info(f"Deleting account for user: {user.username} (ID: {user.id})")
                
                # Delete user's uploaded files
                user_receipts = Receipt.objects.filter(user=user)
                files_deleted = 0
                for receipt in user_receipts:
                    if receipt.file:
                        try:
                            from django.core.files.storage import default_storage
                            default_storage.delete(receipt.file.name)
                            files_deleted += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete file for receipt {receipt.transaction_number}: {str(e)}")
                
                # Get counts for logging
                receipts_count = user_receipts.count()
                alerts_count = PriceAdjustmentAlert.objects.filter(user=user).count()
                
                # Handle subscription cancellation if exists
                try:
                    from receipt_parser.models import UserSubscription
                    user_subscription = UserSubscription.objects.filter(user=user).first()
                    if user_subscription and user_subscription.is_active:
                        import stripe
                        stripe.api_key = settings.STRIPE_SECRET_KEY
                        try:
                            stripe.Subscription.delete(user_subscription.stripe_subscription_id)
                            logger.info(f"Cancelled Stripe subscription for user {user.username}")
                        except Exception as stripe_error:
                            logger.warning(f"Failed to cancel Stripe subscription: {str(stripe_error)}")
                except ImportError:
                    # UserSubscription model might not exist in all deployments
                    pass
                except Exception as sub_error:
                    logger.warning(f"Error handling subscription cancellation: {str(sub_error)}")
                
                # Delete the user account (this will cascade delete all related data)
                username = user.username
                user.delete()
                
                logger.info(f"Successfully deleted account for {username}. Removed {receipts_count} receipts, {alerts_count} alerts, and {files_deleted} files.")
                
                return JsonResponse({
                    'message': 'Account successfully deleted',
                    'deleted_data': {
                        'receipts': receipts_count,
                        'alerts': alerts_count,
                        'files': files_deleted
                    }
                })
                
            except Exception as delete_error:
                logger.error(f"Error during account deletion for user {user.username}: {str(delete_error)}")
                return JsonResponse({'error': 'Failed to delete account. Please try again or contact support.'}, status=500)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in account deletion: {str(e)}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_get_csrf_token(request):
    """Get CSRF token for API requests (though most endpoints are exempt)."""
    if request.method == 'GET':
        from django.middleware.csrf import get_token
        token = get_token(request)
        return JsonResponse({'csrf_token': token})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_user(request):
    print(f"API User request received - Auth: {request.user.is_authenticated}")
    if request.user.is_authenticated:
        # Get account type from user profile
        try:
            from receipt_parser.models import UserProfile
            profile = UserProfile.objects.get(user=request.user)
            account_type = 'paid' if profile.is_paid_account else 'free'
            is_paid_account = profile.is_paid_account
        except UserProfile.DoesNotExist:
            # Create profile if it doesn't exist
            UserProfile.objects.create(user=request.user, account_type='free')
            account_type = 'free'
            is_paid_account = False
        
        user_data = {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'account_type': account_type,
            'is_paid_account': is_paid_account,
        }
        print(f"Returning authenticated user data: {user_data}")
        return JsonResponse(user_data)
    
    print("User not authenticated")
    return JsonResponse({'error': 'Not authenticated'}, status=401)

def debug_session(request):
    """Debug endpoint to check session and cookie status."""
    response_data = {
        'is_authenticated': request.user.is_authenticated,
        'session_key': request.session.session_key,
        'has_csrf_cookie': 'csrftoken' in request.COOKIES,
        'has_session_cookie': 'sessionid' in request.COOKIES,
        'csrf_token': get_token(request),
        'cookies': list(request.COOKIES.keys())
    }
    
    if request.user.is_authenticated:
        response_data['user'] = {
            'username': request.user.username,
            'id': request.user.id
        }
    
    print(f"Debug session: {response_data}")
    return JsonResponse(response_data)

@csrf_exempt
def api_password_reset(request):
    """Send password reset email."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'error': 'Email is required'}, status=400)
            
            # Check if user exists
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # For security, don't reveal if email exists
                return JsonResponse({'message': 'If an account with this email exists, a password reset link has been sent.'})
            
            # Generate token and uid
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build reset URL
            current_site = get_current_site(request)
            if settings.DEBUG:
                # In development, use the React dev server port
                protocol = 'https' if request.is_secure() else 'http'
                host = request.get_host()
                # Replace Django dev server port with React dev server port
                if ':8000' in host:
                    host = host.replace(':8000', ':3000')
                reset_url = f"{protocol}://{host}/reset-password/{uid}/{token}"
            else:
                # In production, use the actual domain
                reset_url = f"https://{current_site.domain}/reset-password/{uid}/{token}"
            
            # Send email
            subject = 'Password Reset for PriceAdjustPro'
            message = f"""
Hello {user.username},

You requested a password reset for your PriceAdjustPro account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request this password reset, please ignore this email.

Best regards,
PriceAdjustPro Team
            """
            
            try:
                print(f"Attempting to send email from {settings.DEFAULT_FROM_EMAIL} to {email}")
                print(f"SMTP settings: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
                print(f"Using TLS: {settings.EMAIL_USE_TLS}")
                print(f"Email user: {settings.EMAIL_HOST_USER}")
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                
                print(f"Email sent successfully to {email}")
                return JsonResponse({'message': 'If an account with this email exists, a password reset link has been sent.'})
                
            except Exception as email_error:
                print(f"Email sending failed: {str(email_error)}")
                if settings.DEBUG:
                    # In development, log the email content to console instead
                    print("=" * 50)
                    print("PASSWORD RESET EMAIL (Console Output)")
                    print("=" * 50)
                    print(f"To: {email}")
                    print(f"Subject: {subject}")
                    print(f"Message:\n{message}")
                    print("=" * 50)
                    return JsonResponse({'message': 'Password reset email logged to console (development mode).'})
                else:
                    # In production, also log to console when SMTP fails
                    print("=" * 50)
                    print("PASSWORD RESET EMAIL (SMTP Failed - Console Fallback)")
                    print("=" * 50)
                    print(f"To: {email}")
                    print(f"Subject: {subject}")
                    print(f"Message:\n{message}")
                    print("=" * 50)
                    return JsonResponse({'message': 'Password reset email logged to server console (SMTP unavailable).'})
            
        except Exception as e:
            print(f"Password reset error: {str(e)}")
            return JsonResponse({'error': 'Failed to send reset email'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_password_reset_confirm(request):
    """Confirm password reset and set new password."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            uidb64 = data.get('uid')
            token = data.get('token')
            new_password = data.get('new_password')
            confirm_password = data.get('confirm_password')
            
            if not all([uidb64, token, new_password, confirm_password]):
                return JsonResponse({'error': 'All fields are required'}, status=400)
            
            if new_password != confirm_password:
                return JsonResponse({'error': 'Passwords do not match'}, status=400)
            
            if len(new_password) < 8:
                return JsonResponse({'error': 'Password must be at least 8 characters long'}, status=400)
            
            # Decode user ID
            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return JsonResponse({'error': 'Invalid reset link'}, status=400)
            
            # Check token
            if not default_token_generator.check_token(user, token):
                return JsonResponse({'error': 'Invalid or expired reset link'}, status=400)
            
            # Set new password
            user.set_password(new_password)
            user.save()
            
            return JsonResponse({'message': 'Password has been reset successfully'})
            
        except Exception as e:
            print(f"Password reset confirm error: {str(e)}")
            return JsonResponse({'error': 'Failed to reset password'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# API URLs
api_urlpatterns = [
    path('auth/login/', api_login, name='api_login'),
    path('auth/logout/', api_logout, name='api_logout'),
    path('auth/register/', api_register, name='api_register'),
    path('auth/user/', api_user, name='api_user'),
    path('auth/password-reset/', api_password_reset, name='api_password_reset'),
    path('auth/password-reset-confirm/', api_password_reset_confirm, name='api_password_reset_confirm'),
    path('auth/delete-account/', api_delete_account, name='api_delete_account'),
    path('csrf/', api_get_csrf_token, name='api_get_csrf_token'),
    path('get-csrf-token/', api_get_csrf_token, name='api_get_csrf_token_alt'),
    path('auth/csrf/', api_get_csrf_token, name='api_get_csrf_token_auth'),
    path('debug/session/', debug_session, name='debug_session'),
] + receipt_api_urls()

# Define Django-only URL patterns (these are completely separate from React)
django_urlpatterns = [
    # Admin URLs must be first
    path('admin/', admin.site.urls),
    
    # Hijack URLs
    path('hijack/', include('hijack.urls')),
    
    # API URLs
    path('api/', include(api_urlpatterns)),
]

# Define static files and React-specific files
static_urlpatterns = [
    # Static files
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    
    # React-specific files
    path('favicon.ico', serve_react_file, kwargs={'filename': 'favicon.ico'}),
    path('manifest.json', serve_react_file, kwargs={'filename': 'manifest.json'}),
    path('logo192.png', serve_react_file, kwargs={'filename': 'logo192.png'}),
    path('asset-manifest.json', serve_react_file, kwargs={'filename': 'asset-manifest.json'}),
    path('robots.txt', serve_react_file, kwargs={'filename': 'robots.txt'}),
]

# Define React app routes
react_urlpatterns = [
    # Explicit password reset routes (must come before catch-all)
    re_path(r'^reset-password/$', TemplateView.as_view(template_name='index.html')),
    re_path(r'^reset-password/[^/]+/[^/]+/$', TemplateView.as_view(template_name='index.html')),
    # All other paths go to the React app (excluding admin and api paths)
    re_path(r'^(?!admin)(?!api/).*$', TemplateView.as_view(template_name='index.html')),
]

# Combine URL patterns in the correct order
urlpatterns = django_urlpatterns + static_urlpatterns

# Add static/media serving in development
if settings.DEBUG:
    urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + \
                 static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + \
                 urlpatterns

# Add React routes LAST
urlpatterns += react_urlpatterns

