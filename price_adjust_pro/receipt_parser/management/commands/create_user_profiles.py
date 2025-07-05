from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from receipt_parser.models import UserProfile


class Command(BaseCommand):
    help = 'Create UserProfile objects for all existing users who do not have one'

    def handle(self, *args, **options):
        users_without_profile = User.objects.filter(profile__isnull=True)
        created_count = 0
        
        for user in users_without_profile:
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={'account_type': 'free'}
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created profile for user: {user.username}')
        
        if created_count == 0:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {created_count} user profiles')
            ) 