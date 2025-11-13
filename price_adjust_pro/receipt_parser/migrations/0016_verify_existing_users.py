# Migration to mark existing users as email verified
# This is needed because we're implementing email verification after users already exist

from django.db import migrations
from django.utils import timezone


def verify_existing_users(apps, schema_editor):
    """
    Mark all existing users as email verified.
    This is a one-time migration when implementing email verification.
    """
    UserProfile = apps.get_model('receipt_parser', 'UserProfile')
    User = apps.get_model('auth', 'User')
    
    # Get all user profiles
    profiles = UserProfile.objects.all()
    
    print(f"Verifying {profiles.count()} existing user profiles...")
    
    for profile in profiles:
        if not profile.is_email_verified:
            profile.is_email_verified = True
            profile.email_verified_at = timezone.now()
            profile.save()
    
    # Also verify any users without profiles (shouldn't happen but just in case)
    users_without_profiles = User.objects.exclude(
        id__in=UserProfile.objects.values_list('user_id', flat=True)
    )
    
    for user in users_without_profiles:
        UserProfile.objects.create(
            user=user,
            is_email_verified=True,
            email_verified_at=timezone.now(),
            account_type='free'
        )
    
    print(f"Successfully verified all existing users")


def reverse_verify(apps, schema_editor):
    """
    Reverse the migration by unmarking users.
    Note: This will lock out existing users, so use with caution.
    """
    UserProfile = apps.get_model('receipt_parser', 'UserProfile')
    
    # We'll keep the verification status since reversing would lock everyone out
    print("Reverse migration: Keeping verification status to avoid locking users out")


class Migration(migrations.Migration):

    dependencies = [
        ('receipt_parser', '0015_userprofile_email_verified_at_and_more'),
    ]

    operations = [
        migrations.RunPython(verify_existing_users, reverse_verify),
    ]

