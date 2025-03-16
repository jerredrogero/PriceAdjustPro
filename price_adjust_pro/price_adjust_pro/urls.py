"""
URL configuration for price_adjust_pro project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
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
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return JsonResponse({'error': 'Username and password are required'}, status=400)
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
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
                
                return response
                
            return JsonResponse({'error': 'Invalid credentials'}, status=401)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"Login error: {str(e)}")  # Log the error
            return JsonResponse({'error': 'Login failed'}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_logout(request):
    if request.method in ['POST', 'GET']:
        logout(request)
        # Check if the request wants JSON response or redirect
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'message': 'Logged out successfully'})
        else:
            # Redirect to login page
            return redirect('/login')
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            from django.contrib.auth.models import User
            
            # Validate required fields
            username = data.get('username')
            email = data.get('email')
            password1 = data.get('password1')
            password2 = data.get('password2')
            
            if not all([username, email, password1, password2]):
                return JsonResponse({'error': 'All fields are required'}, status=400)
            
            if password1 != password2:
                return JsonResponse({'error': 'Passwords do not match'}, status=400)
            
            if User.objects.filter(username=username).exists():
                return JsonResponse({'error': 'Username already exists'}, status=400)
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
            
            # Log the user in
            login(request, user)
            
            return JsonResponse({
                'message': 'Account created successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_user(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'id': request.user.id,
            'username': request.user.username,
        })
    return JsonResponse({'error': 'Not authenticated'}, status=401)

# API URLs
api_urlpatterns = [
    path('auth/login/', api_login, name='api_login'),
    path('auth/logout/', api_logout, name='api_logout'),
    path('auth/register/', api_register, name='api_register'),
    path('auth/user/', api_user, name='api_user'),
] + receipt_api_urls()

urlpatterns = [
    # Admin URLs - must be first to take precedence
    path('admin/', admin.site.urls),
    
    # API URLs
    path('api/', include(api_urlpatterns)),
    
    # Static files from React build
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    path('favicon.ico', serve_react_file, kwargs={'filename': 'favicon.ico'}),
    path('manifest.json', serve_react_file, kwargs={'filename': 'manifest.json'}),
    path('logo192.png', serve_react_file, kwargs={'filename': 'logo192.png'}),
    path('asset-manifest.json', serve_react_file, kwargs={'filename': 'asset-manifest.json'}),
    path('robots.txt', serve_react_file, kwargs={'filename': 'robots.txt'}),
]

# Add static/media serving in development
if settings.DEBUG:
    urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + \
                 static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + \
                 urlpatterns

# Add React App catch-all as the LAST pattern
urlpatterns += [
    re_path(r'.*', TemplateView.as_view(template_name='index.html')),
]

