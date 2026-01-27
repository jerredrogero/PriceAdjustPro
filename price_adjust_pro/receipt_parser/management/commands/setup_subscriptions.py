from django.core.management.base import BaseCommand
from django.utils import timezone
from receipt_parser.models import SubscriptionProduct
from decimal import Decimal


class Command(BaseCommand):
    help = 'Set up subscription products in the database'

    def handle(self, *args, **options):
        # Monthly subscription
        monthly_product, created = SubscriptionProduct.objects.get_or_create(
            stripe_product_id='prod_ScaEJwnoEX6k5a',
            defaults={
                'stripe_price_id': 'price_1QR5AQLpUWBjzjCjqpfNUvNr',  # You'll need to get this from Stripe
                'name': 'PriceAdjustPro Monthly',
                'description': 'Monthly subscription to PriceAdjustPro - Track your Costco receipts and never miss a price adjustment again!',
                'price': Decimal('4.99'),
                'currency': 'usd',
                'billing_interval': 'month',
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created monthly subscription product: {monthly_product.name}')
            )
        else:
            # Update price if it exists
            monthly_product.price = Decimal('4.99')
            monthly_product.save()
            self.stdout.write(
                self.style.WARNING(f'Monthly subscription product already exists: {monthly_product.name} (Price updated to 4.99)')
            )

        # Yearly subscription
        yearly_product, created = SubscriptionProduct.objects.get_or_create(
            stripe_product_id='prod_ScaGa23kaHXo9w',
            defaults={
                'stripe_price_id': 'price_1QR5AQLpUWBjzjCjqpfNUvNs',  # You'll need to get this from Stripe
                'name': 'PriceAdjustPro Yearly',
                'description': 'Yearly subscription to PriceAdjustPro - Save with our annual plan!',
                'price': Decimal('49.99'),
                'currency': 'usd',
                'billing_interval': 'year',
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created yearly subscription product: {yearly_product.name}')
            )
        else:
            # Update price if it exists
            yearly_product.price = Decimal('49.99')
            yearly_product.save()
            self.stdout.write(
                self.style.WARNING(f'Yearly subscription product already exists: {yearly_product.name} (Price updated to 49.99)')
            )

        self.stdout.write(
            self.style.SUCCESS('Subscription products setup completed!')
        )
        
        # Display current products
        self.stdout.write('\nCurrent subscription products:')
        for product in SubscriptionProduct.objects.all():
            status = '✓ Active' if product.is_active else '✗ Inactive'
            self.stdout.write(f'  - {product.name}: ${product.price}/{product.billing_interval} {status}') 