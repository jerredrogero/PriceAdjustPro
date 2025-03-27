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
            re.compile(r'^/login/$'),
            re.compile(r'^/register/$'),
            re.compile(r'^/static/.*$'),
            re.compile(r'^/favicon.ico$'),
            re.compile(r'^/manifest.json$'),
            re.compile(r'^/asset-manifest.json$'),
            re.compile(r'^/robots.txt$'),
        ]

    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Called just before Django calls the view.
        Return None to continue processing, or a Response to short-circuit.
        """
        # Check if the path is exempt
        path = request.path_info.lstrip('/')
        full_path = f'/{path}'
        
        # Allow access to exempt URLs without authentication
        for exempt_url in self.exempt_urls:
            if exempt_url.match(full_path):
                return None
                
        return None 