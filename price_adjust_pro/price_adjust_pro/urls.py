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
                
                response = JsonResponse({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
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
            
            # Validate required fields
            username = data.get('username')
            email = data.get('email')
            password1 = data.get('password1')
            password2 = data.get('password2')
            
            print(f"Registration attempt for user: {username}, email: {email}")
            
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
            
            # Log the user in
            login(request, user)
            print(f"User {username} created and logged in successfully")
            
            # Set session cookie attributes and expiry
            request.session.set_expiry(1209600)  # 2 weeks
            
            # Ensure CSRF token is set
            csrf_token = get_token(request)
            
            response = JsonResponse({
                'message': 'Account created successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
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

def api_user(request):
    print(f"API User request received - Auth: {request.user.is_authenticated}")
    if request.user.is_authenticated:
        user_data = {
            'id': request.user.id,
            'username': request.user.username,
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
                # In development, use the same host as the current request
                protocol = 'https' if request.is_secure() else 'http'
                host = request.get_host()
                reset_url = f"{protocol}://{host}/reset-password/{uid}/{token}/"
            else:
                # In production, use the actual domain
                reset_url = f"https://{current_site.domain}/reset-password/{uid}/{token}/"
            
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
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                
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

