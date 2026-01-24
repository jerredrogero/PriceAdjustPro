from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailOTP
import logging

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 30

def issue_email_otp(user) -> tuple[EmailOTP, str]:
    """
    Generate a new OTP, hash it, save it, and email the plain code to the user.
    """
    code = EmailOTP.generate_code()
    
    # Invalidate any existing unused OTPs for this user
    EmailOTP.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
    
    otp = EmailOTP.objects.create(
        user=user,
        code_hash=EmailOTP.hash_code(code),
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
        last_sent_at=timezone.now(),
    )

    subject = "Your PriceAdjustPro verification code"
    message = f"Your verification code is: {code}\n\nIt expires in {OTP_TTL_MINUTES} minutes.\n\nIf you didn't request this, you can safely ignore this email."
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"OTP sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send OTP email to {user.email}: {str(e)}")
        # We still return the otp object, but the user won't get the email
        # In a real app, you might want to handle this differently
        
    return otp, code
