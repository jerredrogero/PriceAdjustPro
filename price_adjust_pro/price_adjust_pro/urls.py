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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
import json

from receipt_parser.urls import urls_api as receipt_api_urls

def home_redirect(request):
    return redirect('receipt_list')

@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({
                'id': user.id,
                'username': user.username,
            })
        return JsonResponse({'error': 'Invalid credentials'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_logout(request):
    if request.method == 'POST':
        logout(request)
        return JsonResponse({'message': 'Logged out successfully'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_user(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'id': request.user.id,
            'username': request.user.username,
        })
    return JsonResponse({'error': 'Not authenticated'}, status=401)

urlpatterns = [
    path('', home_redirect, name='home'),
    path('admin/', admin.site.urls),
    
    # Traditional URLs
    path('receipts/', include('receipt_parser.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='receipt_parser/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # API URLs
    path('api/auth/login/', api_login, name='api_login'),
    path('api/auth/logout/', api_logout, name='api_logout'),
    path('api/auth/user/', api_user, name='api_user'),
    path('api/', include(receipt_api_urls())),  # Mount receipt_parser API endpoints under /api/
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
