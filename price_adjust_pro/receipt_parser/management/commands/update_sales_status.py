from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from receipt_parser.models import CostcoPromotion

class Command(BaseCommand):
    help = 'Update sales status and deactivate expired promotions'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
    
    def handle(self, *args, **options):
        current_date = date.today()
        dry_run = options['dry_run']
        
        self.stdout.write(f"Checking promotions as of {current_date}")
        
        # Find expired promotions that are still marked as processed
        expired_promotions = CostcoPromotion.objects.filter(
            sale_end_date__lt=current_date,
            is_processed=True
        )
        
        # Find future promotions that should become active today
        newly_active_promotions = CostcoPromotion.objects.filter(
            sale_start_date__lte=current_date,
            sale_end_date__gte=current_date,
            is_processed=False
        )
        
        # Find currently active promotions
        active_promotions = CostcoPromotion.objects.filter(
            sale_start_date__lte=current_date,
            sale_end_date__gte=current_date,
            is_processed=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n📊 Status Report:"
                f"\n• {active_promotions.count()} currently active promotions"
                f"\n• {expired_promotions.count()} expired promotions to deactivate"
                f"\n• {newly_active_promotions.count()} promotions ready to activate"
            )
        )
        
        if expired_promotions.exists():
            self.stdout.write(f"\n🔴 Expired Promotions:")
            for promo in expired_promotions:
                items_count = promo.sale_items.count()
                self.stdout.write(
                    f"  • {promo.title} (ended {promo.sale_end_date}, {items_count} items)"
                )
                
                if not dry_run:
                    # Don't actually deactivate - just mark for reference
                    # We keep them processed so the data is still available
                    pass
        
        if newly_active_promotions.exists():
            self.stdout.write(f"\n🟢 Promotions Ready to Activate:")
            for promo in newly_active_promotions:
                pages_count = promo.pages.count()
                processed_pages = promo.pages.filter(is_processed=True).count()
                self.stdout.write(
                    f"  • {promo.title} (starts {promo.sale_start_date}, "
                    f"{processed_pages}/{pages_count} pages processed)"
                )
                
                if processed_pages == pages_count and pages_count > 0:
                    if not dry_run:
                        promo.is_processed = True
                        promo.processed_date = timezone.now()
                        promo.save()
                        self.stdout.write(
                            self.style.SUCCESS(f"    ✅ Activated {promo.title}")
                        )
                    else:
                        self.stdout.write(f"    📝 Would activate {promo.title}")
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ⚠️  Cannot activate - only {processed_pages}/{pages_count} pages processed"
                        )
                    )
        
        if active_promotions.exists():
            self.stdout.write(f"\n✅ Currently Active Promotions:")
            total_items = 0
            for promo in active_promotions:
                items_count = promo.sale_items.count()
                total_items += items_count
                days_remaining = (promo.sale_end_date - current_date).days
                self.stdout.write(
                    f"  • {promo.title} ({items_count} items, {days_remaining} days left)"
                )
            
            self.stdout.write(
                self.style.SUCCESS(f"\n🎯 Total: {total_items} items currently on sale")
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n📝 DRY RUN - No changes made. Remove --dry-run to apply changes.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Sales status updated successfully!")
            ) 