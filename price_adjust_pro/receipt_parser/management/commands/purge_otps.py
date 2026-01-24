from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from receipt_parser.models import EmailOTP

class Command(BaseCommand):
    help = 'Purges used and expired OTP records older than 24 hours'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=1)
        
        # Delete used OTPs older than 1 day
        used_deleted, _ = EmailOTP.objects.filter(
            used_at__isnull=False, 
            used_at__lt=cutoff
        ).delete()
        
        # Delete expired OTPs older than 1 day
        expired_deleted, _ = EmailOTP.objects.filter(
            used_at__isnull=True, 
            expires_at__lt=cutoff
        ).delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully purged {used_deleted} used and {expired_deleted} expired OTP records.'
            )
        )
