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
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from receipt_parser.notifications.auth import get_request_user_via_bearer_session

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
def login_start(request):
    """
    Step 1 of login: Validate credentials and issue OTP.
    Stores pre-auth state in session.
    """
    print(f"login_start received: method={request.method}")
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        # Clear any existing session to prevent stale state
        from django.contrib.auth import logout
        if request.user.is_authenticated:
            logout(request)
        
        # Explicitly clear any old pre-auth keys
        for k in ["preauth_user_id", "otp_id", "otp_verified", "remember_me"]:
            request.session.pop(k, None)

        print(f"Request body: {request.body}")
        data = json.loads(request.body)
        email_input = data.get('email', '').strip()
        password = data.get('password', '')
        
        # Use email as the primary identifier
        identifier = email_input.strip()
        print(f"Attempting auth for email: '{identifier}'")
        
        if not identifier or not password:
            return JsonResponse({'error': 'Email and password are required'}, status=400)
        
        # 1. Try direct authentication with provided email as username
        user = authenticate(request, username=identifier, password=password)
        
        # 2. If that fails, try looking up the user by email to handle case sensitivity
        if not user:
            try:
                from django.contrib.auth.models import User
                from django.db.models import Q
                
                # Look for user by exact email or case-insensitive email
                user_obj = User.objects.filter(email__iexact=identifier).first()
                
                if user_obj:
                    print(f"Found user {user_obj.username} matching email {identifier}. Attempting auth with actual username.")
                    # Try authenticating with the actual username (which should be the email)
                    user = authenticate(request, username=user_obj.username, password=password)
                    
                    if not user:
                        # If authenticate() still fails, check password manually for inactive users
                        # or in case of custom auth backend issues
                        if user_obj.check_password(password):
                            if not user_obj.is_active:
                                print(f"User {user_obj.username} is inactive but password is correct. Proceeding to OTP.")
                                user = user_obj
                            else:
                                # If active but authenticate() failed, it might be a backend issue
                                # but we'll trust check_password() here for the login-start phase
                                print(f"User {user_obj.username} password correct but authenticate() failed. Proceeding.")
                                user = user_obj
                        else:
                            print(f"User {user_obj.username} found but password check failed.")
                else:
                    print(f"No user found matching identifier: {identifier}")
            except Exception as e:
                print(f"Error during user lookup: {e}")
            
        if not user:
            print(f"Authentication failed for identifier: {identifier}")
            return JsonResponse({'error': 'Invalid email or password'}, status=400)

        print(f"User {user.username} authenticated, issuing OTP")
        # Issue OTP
        from receipt_parser.services import issue_email_otp
        otp, _ = issue_email_otp(user)

        # Store "pre-auth" state in session
        request.session["preauth_user_id"] = user.id
        request.session["otp_id"] = otp.id
        request.session["otp_verified"] = False
        request.session["remember_me"] = data.get('remember_me', False)
        request.session.modified = True

        print(f"Session updated with preauth state. Session key: {request.session.session_key}")

        return JsonResponse({
            "requires_2fa": True,
            "message": "Verification code sent to your email.",
            "email": user.email
        })
        
    except Exception as e:
        import traceback
        print(f"Login start error: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': f'An error occurred during login: {str(e)}'}, status=500)

@csrf_exempt
def verify_otp(request):
    """
    Step 2 of login: Verify OTP and complete login.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip()
        
        otp_id = request.session.get("otp_id")
        user_id = request.session.get("preauth_user_id")
        remember_me = request.session.get("remember_me", False)

        if not otp_id or not user_id:
            return JsonResponse({'error': 'No pending verification. Please log in again.'}, status=400)

        from receipt_parser.models import EmailOTP
        otp = EmailOTP.objects.filter(id=otp_id, user_id=user_id, used_at__isnull=True).first()
        
        if not otp:
            return JsonResponse({'error': 'No pending verification found.'}, status=400)

        # 1) Enforce lockout BEFORE hashing
        if otp.attempts >= 8:
            return JsonResponse({'error': 'Too many attempts. Please try logging in again.'}, status=429)

        # 2) Check expiration
        if otp.is_expired:
            return JsonResponse({'error': 'Code has expired. Please request a new one.'}, status=400)

        # 3) Compare hash
        if EmailOTP.hash_code(code) != otp.code_hash:
            # 4) Increment only on failure
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            return JsonResponse({'error': 'Invalid code'}, status=400)

        # Mark OTP as used
        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])

        # Complete login
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        
        # Mark email as verified if it wasn't already
        from receipt_parser.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.is_email_verified:
            profile.is_email_verified = True
            profile.email_verified_at = timezone.now()
            profile.save()
            
        # Activate user if they were inactive
        if not user.is_active:
            user.is_active = True
            user.save()

        login(request, user)

        # PA check logic (copied from old api_login)
        try:
            from receipt_parser.models import Receipt
            from receipt_parser.utils import check_current_user_for_price_adjustments
            from datetime import timedelta
            
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_receipts = Receipt.objects.filter(
                user=user,
                transaction_date__gte=thirty_days_ago
            ).prefetch_related('items')
            
            for receipt in recent_receipts:
                for item in receipt.items.all():
                    if item.on_sale or (item.instant_savings and item.instant_savings > 0):
                        continue
                    check_current_user_for_price_adjustments(item, receipt)
        except Exception as pa_error:
            print(f"Login PA check error (non-fatal): {str(pa_error)}")

        # Cleanup session
        for k in ["preauth_user_id", "otp_id", "otp_verified", "remember_me"]:
            request.session.pop(k, None)
        
        # Set expiry
        session_duration = settings.SESSION_COOKIE_AGE if remember_me else 0
        request.session.set_expiry(session_duration)
        request.session.modified = True

        account_type = 'paid' if profile.is_paid_account else 'free'
        
        response_data = {
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'account_type': account_type,
                'is_paid_account': profile.is_paid_account,
                'is_email_verified': True,
            }
        }

        # 5) Return session key only if mobile client asks
        if request.headers.get('X-Client') == 'ios' or request.GET.get('client') == 'ios':
            response_data['session_key'] = request.session.session_key

        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"OTP verification error: {str(e)}")
        return JsonResponse({'error': 'An error occurred during verification'}, status=500)

@csrf_exempt
def api_resend_otp(request):
    """
    Resend OTP for a pending verification session.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        user_id = request.session.get("preauth_user_id")
        if not user_id:
            return JsonResponse({'error': 'No pending verification.'}, status=400)
            
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        
        from receipt_parser.models import EmailOTP
        # Check cooldown (60 seconds)
        last_otp = EmailOTP.objects.filter(user=user).order_by('-created_at').first()
        if last_otp:
            cooldown_seconds = 60
            time_since_last = (timezone.now() - last_otp.created_at).total_seconds()
            if time_since_last < cooldown_seconds:
                remaining = int(cooldown_seconds - time_since_last)
                return JsonResponse({'error': f'Please wait {remaining} seconds before requesting a new code.'}, status=429)

        # Issue new OTP
        from receipt_parser.services import issue_email_otp
        otp, _ = issue_email_otp(user)
        
        # Update session
        request.session["otp_id"] = otp.id
        request.session.modified = True
        
        return JsonResponse({'message': 'A new verification code has been sent to your email.'})
        
    except Exception as e:
        print(f"OTP resend error: {str(e)}")
        return JsonResponse({'error': 'An error occurred during resend'}, status=500)

@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        try:
            print("Login attempt received")
            # Decode request body if it's bytes
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body)
            
            def parse_bool(value, default=False):
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.strip().lower() in ['1', 'true', 'yes', 'on']
                if isinstance(value, (int, float)):
                    return value != 0
                return default
            
            email_input = data.get('email', '').strip()
            password = data.get('password', '')
            remember_me = parse_bool(data.get('remember_me'), default=False)
            
            print(f"Login attempt - email: {email_input}, password provided: {bool(password)}")
            
            if not email_input or not password:
                print(f"Login error: Missing email or password")
                return JsonResponse({'error': 'Email and password are required'}, status=400)
            
            # Try to find the user by email
            user_obj = None
            try:
                user_obj = User.objects.filter(email__iexact=email_input).first()
            except Exception as e:
                print(f"Error finding user: {str(e)}")

            # Use the actual username for authentication if found
            auth_username = user_obj.username if user_obj else email_input
            
            # Try authenticate without request first (some backends don't need it)
            user = authenticate(username=auth_username, password=password)
            if user is None:
                # Try with request parameter
                user = authenticate(request, username=auth_username, password=password)
            
            # If authentication failed, check if it's because the user is inactive (unverified)
            if user is None and user_obj and not user_obj.is_active:
                if user_obj.check_password(password):
                    print(f"User {user_obj.username} is inactive (unverified). Sending code.")
                    
                    # Invalidate old tokens and create a new one
                    from receipt_parser.models import EmailVerificationToken
                    EmailVerificationToken.objects.filter(user=user_obj, is_used=False).update(is_used=True)
                    verification_token = EmailVerificationToken.create_token(user_obj)
                    
                    # Send verification email with 6-digit code and link
                    try:
                        from django.utils.http import urlsafe_base64_encode
                        from django.utils.encoding import force_bytes
                        from django.urls import reverse
                        from django.contrib.sites.shortcuts import get_current_site
                        
                        current_site = get_current_site(request)
                        uid = urlsafe_base64_encode(force_bytes(user_obj.pk))
                        verification_link = f"{request.scheme}://{current_site.domain}{reverse('verify_email', kwargs={'uidb64': uid, 'token': verification_token.token})}"
                        
                        subject = 'Verify your PriceAdjustPro account'
                        message = f"""
Hi {user_obj.first_name or user_obj.email},

Please verify your email address to log in to PriceAdjustPro.

Your verification code is:
{verification_token.code}

Alternatively, you can click the link below to verify your account:
{verification_link}

Enter the code in the app or click the link to verify your account. This code and link will expire in 30 minutes.

If you didn't request this, you can safely ignore this email.

Best regards,
The PriceAdjustPro Team
                        """
                        
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [user_obj.email],
                            fail_silently=False,
                        )
                        print(f"Verification code sent to {user_obj.email}")
                    except Exception as email_error:
                        print(f"Failed to send verification email: {str(email_error)}")
                    
                    return JsonResponse({
                        'message': 'Email verification required. Please check your email for a code.',
                        'verification_required': True,
                        'verified': False,
                        'email': user_obj.email
                    }, status=403)

            print(f"Authentication result: {user}")
            if user is not None:
                print(f"User {user.username} authenticated successfully")
                
                # Get account type and ensure profile exists
                try:
                    from receipt_parser.models import UserProfile
                    profile, created = UserProfile.objects.get_or_create(
                        user=user, 
                        defaults={'account_type': 'free', 'is_email_verified': False}
                    )
                    
                    # Check if email is verified
                    if not profile.is_email_verified:
                        print(f"User {user.username} is not verified")
                        
                        # Invalidate old tokens and create a new one
                        from receipt_parser.models import EmailVerificationToken
                        EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)
                        verification_token = EmailVerificationToken.create_token(user)
                        
                        # Send verification email with 6-digit code and link
                        try:
                            from django.utils.http import urlsafe_base64_encode
                            from django.utils.encoding import force_bytes
                            from django.urls import reverse
                            from django.contrib.sites.shortcuts import get_current_site
                            
                            current_site = get_current_site(request)
                            uid = urlsafe_base64_encode(force_bytes(user.pk))
                            verification_link = f"{request.scheme}://{current_site.domain}{reverse('verify_email', kwargs={'uidb64': uid, 'token': verification_token.token})}"
                            
                            subject = 'Verify your PriceAdjustPro account'
                            message = f"""
Hi {user.first_name or user.email},

Please verify your email address to log in to PriceAdjustPro.

Your verification code is:
{verification_token.code}

Alternatively, you can click the link below to verify your account:
{verification_link}

Enter the code in the app or click the link to verify your account. This code and link will expire in 30 minutes.

If you didn't request this, you can safely ignore this email.

Best regards,
The PriceAdjustPro Team
                            """
                            
                            send_mail(
                                subject,
                                message,
                                settings.DEFAULT_FROM_EMAIL,
                                [user.email],
                                fail_silently=False,
                            )
                            print(f"Verification code sent to {user.email}")
                        except Exception as email_error:
                            print(f"Failed to send verification email: {str(email_error)}")
                        
                        return JsonResponse({
                            'message': 'Email verification required. Please check your email for a code.',
                            'verification_required': True,
                            'verified': False,
                            'email': user.email
                        }, status=403)
                        
                except Exception as profile_error:
                    print(f"Error handling profile for {user.username}: {profile_error}")
                    # Fallback if profile creation fails
                    class DummyProfile:
                        is_paid_account = False
                        is_email_verified = True
                    profile = DummyProfile()
                
                # User is verified, proceed with login
                login(request, user)
                
                # Check for new price adjustments on login (runs in background-ish, non-blocking)
                try:
                    from receipt_parser.models import Receipt, LineItem
                    from receipt_parser.utils import check_current_user_for_price_adjustments
                    from datetime import timedelta
                    
                    # Only check receipts from last 30 days (Costco's PA window)
                    thirty_days_ago = timezone.now() - timedelta(days=30)
                    recent_receipts = Receipt.objects.filter(
                        user=user,
                        transaction_date__gte=thirty_days_ago
                    ).prefetch_related('items')
                    
                    alerts_created = 0
                    for receipt in recent_receipts:
                        for item in receipt.items.all():
                            # Skip items already on sale
                            if item.on_sale or (item.instant_savings and item.instant_savings > 0):
                                continue
                            alerts_created += check_current_user_for_price_adjustments(item, receipt)
                    
                    if alerts_created > 0:
                        print(f"Login PA check: Created {alerts_created} new price adjustment alerts for {user.username}")
                except Exception as pa_error:
                    print(f"Login PA check error (non-fatal): {str(pa_error)}")
                
                # Set session cookie attributes based on remember_me preference
                session_duration = settings.SESSION_COOKIE_AGE if remember_me else None
                request.session.set_expiry(session_duration if session_duration else 0)
                
                # Ensure CSRF token is set
                csrf_token = get_token(request)
                
                # Get account type from user profile
                account_type = 'paid' if profile.is_paid_account else 'free'
                is_paid_account = profile.is_paid_account
                
                response = JsonResponse({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
                    'account_type': account_type,
                    'is_paid_account': is_paid_account,
                    'is_email_verified': True,  # User must be verified to reach this point
                    'remember_me': remember_me,
                    # Mobile clients can store this and use:
                    # Authorization: Bearer <sessionid>
                    'sessionid': request.session.session_key,
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
                
                # Also set session cookie explicitly if needed
                if request.session.session_key:
                    session_cookie_kwargs = {
                        'secure': not settings.DEBUG,
                        'httponly': settings.SESSION_COOKIE_HTTPONLY,
                        'samesite': settings.SESSION_COOKIE_SAMESITE,
                        'domain': settings.SESSION_COOKIE_DOMAIN if not settings.DEBUG else None,
                    }
                    if session_duration:
                        session_cookie_kwargs['max_age'] = session_duration
                    
                    response.set_cookie(
                        settings.SESSION_COOKIE_NAME,
                        request.session.session_key,
                        **session_cookie_kwargs
                    )
                
                print(f"Login response prepared for {user.username}")
                print(f"Session key after login: {request.session.session_key}")
                print(f"Session data after login: {dict(request.session)}")
                return response
                
            print(f"Login failed: Invalid credentials for {username_or_email}")
            return JsonResponse({'error': 'Invalid credentials'}, status=401)
        except json.JSONDecodeError:
            print("Login error: Invalid JSON")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            import traceback
            print(f"Login error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'error': 'Login failed', 'details': str(e)}, status=500)
    
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
            
            # Web form: email, password1, password2
            # iOS app: first_name, last_name, email, password
            
            email = data.get('email')
            password = data.get('password')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            
            # Fallback to web form format
            if not password and 'password1' in data:
                password = data.get('password1')
                password2 = data.get('password2')
                if password != password2:
                    print("Registration error: Passwords do not match")
                    return JsonResponse({'error': 'Passwords do not match'}, status=400)

            if not email or not password:
                print("Registration error: Missing required fields (email, password)")
                return JsonResponse({'error': 'Email and password are required'}, status=400)
                
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                print(f"Registration error: Email {email} already registered")
                return JsonResponse({'error': 'Email already registered. Note: Emails are case sensitive.'}, status=400)

            # Use email as username
            username = email
            
            print(f"Creating user with email: {email}")
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            print(f"User {username} created successfully")
            
            # Create user profile and verification token
            try:
                from receipt_parser.models import UserProfile, EmailVerificationToken
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'account_type': 'free', 'is_email_verified': False}
                )
                
                # Create verification token
                verification_token = EmailVerificationToken.create_token(user)
                
                # Set user as inactive until verified (like in DropShipHQ)
                user.is_active = False
                user.save()
                
                # Send verification email with 6-digit code and link
                try:
                    from django.utils.http import urlsafe_base64_encode
                    from django.utils.encoding import force_bytes
                    from django.urls import reverse
                    from django.contrib.sites.shortcuts import get_current_site
                    
                    current_site = get_current_site(request)
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    # Link points to the web verification view
                    verification_link = f"{request.scheme}://{current_site.domain}{reverse('verify_email', kwargs={'uidb64': uid, 'token': verification_token.token})}"
                    
                    subject = 'Verify your PriceAdjustPro account'
                    message = f"""
Hi {user.first_name or user.email},

Welcome to PriceAdjustPro! Please verify your email address to get started.

Your verification code is:
{verification_token.code}

Alternatively, you can click the link below to verify your account:
{verification_link}

Enter the code in the app or click the link to verify your account. This code and link will expire in 30 minutes.

If you didn't create an account, you can safely ignore this email.

Best regards,
The PriceAdjustPro Team
                    """
                    
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=False,
                    )
                    print(f"Verification code sent to {user.email}")
                except Exception as email_error:
                    print(f"Failed to send verification email: {str(email_error)}")
                    # We still continue since the account was created
            except Exception as e:
                print(f"Error handling profile/token for {user.username}: {str(e)}")
                class DummyProfile:
                    is_paid_account = False
                profile = DummyProfile()
            
            # Don't auto-login since verification is now required
            # login(request, user)
            
            account_type = 'paid' if getattr(profile, 'is_paid_account', False) else 'free'
            
            return JsonResponse({
                'message': 'Account created successfully! Please check your email for your verification code.',
                'email': user.email,
                'username': user.username,
                'verification_required': True,
                'verified': False,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_email_verified': False,
                    'account_type': account_type,
                    'receipt_count': 0,
                    'receipt_limit': 5 if account_type == 'free' else 999999,
                }
            })
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
            
            # Try multiple ways to get the password
            password = None
            
            # 1. Try JSON body first
            try:
                if request.body:
                    data = json.loads(request.body)
                    password = data.get('password')
                    print(f"Parsed JSON data: {data}")
                else:
                    print("No request body provided")
                    data = {}
            except json.JSONDecodeError:
                print("Failed to parse JSON from request body")
                data = {}
            
            # 2. Try query parameters
            if not password and request.GET:
                password = request.GET.get('password')
                if password:
                    print(f"Found password in query parameters")
            
            # 3. Try HTTP headers
            if not password:
                password = request.META.get('HTTP_X_PASSWORD') or request.META.get('HTTP_PASSWORD')
                if password:
                    print(f"Found password in HTTP headers")
            
            # 4. Try form data (though unlikely for DELETE)
            if not password and hasattr(request, 'POST') and request.POST:
                password = request.POST.get('password')
                if password:
                    print(f"Found password in POST data")
            
            print(f"Final password status: {'[PRESENT]' if password else '[MISSING]'}")
            
            if not password:
                print(f"Delete account: Missing password everywhere. Body: {request.body}, GET: {request.GET}, Headers: {[k for k in request.META.keys() if 'PASSWORD' in k.upper()]}")
                return JsonResponse({
                    'error': 'Password is required for account deletion',
                    'details': 'Please include password in request body as JSON: {"password": "your_password"} or as query parameter ?password=your_password or in header X-Password'
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
                logger.info(f"Deleting account for user: {user.email} (ID: {user.id})")
                
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
                            logger.info(f"Cancelled Stripe subscription for user {user.email}")
                        except Exception as stripe_error:
                            logger.warning(f"Failed to cancel Stripe subscription: {str(stripe_error)}")
                except ImportError:
                    # UserSubscription model might not exist in all deployments
                    pass
                except Exception as sub_error:
                    logger.warning(f"Error handling subscription cancellation: {str(sub_error)}")
                
                # Delete the user account (this will cascade delete all related data)
                email = user.email
                user.delete()
                
                logger.info(f"Successfully deleted account for {email}. Removed {receipts_count} receipts, {alerts_count} alerts, and {files_deleted} files.")
                
                return JsonResponse({
                    'message': 'Account successfully deleted',
                    'deleted_data': {
                        'receipts': receipts_count,
                        'alerts': alerts_count,
                        'files': files_deleted
                    }
                })
                
            except Exception as delete_error:
                logger.error(f"Error during account deletion for user {user.email}: {str(delete_error)}")
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
    print(f"Session key: {request.session.session_key}")
    print(f"Cookies received: {list(request.COOKIES.keys())}")
    print(f"Session data: {dict(request.session)}")
    user = request.user if request.user.is_authenticated else None
    if user is None:
        user = get_request_user_via_bearer_session(request)

    if user is not None:
        # Get account type from user profile
        try:
            from receipt_parser.models import UserProfile
            profile = UserProfile.objects.get(user=user)
            account_type = 'paid' if profile.is_paid_account else 'free'
            is_paid_account = profile.is_paid_account
            is_email_verified = profile.is_email_verified
        except UserProfile.DoesNotExist:
            # Create profile if it doesn't exist
            profile = UserProfile.objects.create(user=user, account_type='free')
            account_type = 'free'
            is_paid_account = False
            is_email_verified = profile.is_email_verified
        
        user_data = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'account_type': account_type,
            'is_paid_account': is_paid_account,
            'is_email_verified': is_email_verified,
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
            'email': request.user.email,
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
Hello {user.email},

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
                print(f"Email backend: {settings.EMAIL_BACKEND}")
                print(f"Mailgun configured: {bool(settings.MAILGUN_API_KEY)}")
                
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

def api_admin_hijack(request, user_id):
    """Simple admin hijack functionality."""
    print(f"Hijack request: method={request.method}, user={request.user}, target_user_id={user_id}")
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Check if user is superuser
    if not request.user.is_authenticated or not request.user.is_superuser:
        print(f"Permission denied: authenticated={request.user.is_authenticated}, superuser={request.user.is_superuser}")
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if int(user_id) == request.user.pk:
        return JsonResponse({'error': 'Cannot hijack yourself'}, status=400)
    
    try:
        from django.contrib.auth.models import User
        target_user = User.objects.get(pk=user_id)
        
        # Store original admin user info in session
        request.session['original_admin_user_id'] = request.user.pk
        request.session['original_admin_username'] = request.user.username
        request.session['hijack_active'] = True
        
        # Login as target user
        from django.contrib.auth import logout, login
        print(f"Logging out {request.user.username} and logging in as {target_user.username}")
        logout(request)
        login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')
        
        print(f"Hijack successful: now logged in as {request.user.username}")
        # Redirect to the user's dashboard (React app handles routing)
        from django.shortcuts import redirect
        return redirect('/')
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# API URLs
api_urlpatterns = [
    path('auth/login-start/', login_start, name='api_login_start'),
    path('auth/verify-otp/', verify_otp, name='api_verify_otp'),
    path('auth/resend-otp/', api_resend_otp, name='api_resend_otp'),
    path('auth/login/', api_login, name='api_login'),
    path('auth/logout/', api_logout, name='api_logout'),
    path('auth/register/', api_register, name='api_register'),
    path('auth/user/', api_user, name='api_user'),
    path('auth/password-reset/', api_password_reset, name='api_password_reset'),
    path('auth/password-reset-confirm/', api_password_reset_confirm, name='api_password_reset_confirm'),
    path('auth/delete-account/', api_delete_account, name='api_delete_account'),
    path('admin-hijack/<int:user_id>/', api_admin_hijack, name='api_admin_hijack'),
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
    
    # Legacy Web URLs (for templates)
    path('web/', include('receipt_parser.urls')),
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

