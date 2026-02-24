from django.core.management.base import BaseCommand
from receipt_parser.models import SubscriptionProduct
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds the database with test Stripe subscription products'

    def handle(self, *args, **options):
        products = [
            {
                'stripe_product_id': 'prod_test_monthly',
                'stripe_price_id': 'price_1T4OHjCBOzePXFXgdFkskMkE',
                'name': 'Premium Monthly',
                'description': 'Monthly premium subscription for PriceAdjustPro',
                'price': Decimal('4.99'),
                'billing_interval': 'month',
                'is_active': True,
                'is_test_mode': True
            },
            {
                'stripe_product_id': 'prod_test_yearly',
                'stripe_price_id': 'price_1T4OI1CBOzePXFXgm6GxGlgd',
                'name': 'Premium Yearly',
                'description': 'Yearly premium subscription for PriceAdjustPro',
                'price': Decimal('49.99'),
                'billing_interval': 'year',
                'is_active': True,
                'is_test_mode': True
            }
        ]

        for prod_data in products:
            # First, update any existing products with this price ID to be in test mode
            # This handles the migration from the old schema where is_test_mode didn't exist
            SubscriptionProduct.objects.filter(stripe_price_id=prod_data['stripe_price_id']).update(is_test_mode=True)
            
            obj, created = SubscriptionProduct.objects.update_or_create(
                stripe_price_id=prod_data['stripe_price_id'],
                is_test_mode=True,
                defaults=prod_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created product: {obj.name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Successfully updated product: {obj.name}'))

        self.stdout.write(self.style.SUCCESS('Database seeding complete.'))
