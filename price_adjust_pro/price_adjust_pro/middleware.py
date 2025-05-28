from django.shortcuts import redirect
from django.conf import settings
import re

class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Compile the paths that should bypass authentication
        self.exempt_urls = [
            re.compile(r'^/admin/.*$'),
            re.compile(r'^/api/auth/.*$'),
            re.compile(r'^/hijack/.*$'),  # Allow hijack URLs
            re.compile(r'^/login/$'),
            re.compile(r'^/register/$'),
            re.compile(r'^/static/.*$'),
            re.compile(r'^/favicon.ico$'),
            re.compile(r'^/manifest.json$'),
            re.compile(r'^/asset-manifest.json$'),
            re.compile(r'^/robots.txt$'),
        ]
        print("AuthenticationMiddleware initialized")

    def __call__(self, request):
        # Check for debugging
        if 'HTTP_X_DEBUG_MIDDLEWARE' in request.META:
            print(f"Middleware processing path: {request.path}")
        
        # Always allow the request to proceed
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Always return None to let all requests pass through"""
        # For testing purposes, always allow the request
        return None 