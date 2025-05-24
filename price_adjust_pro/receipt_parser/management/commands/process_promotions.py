from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from receipt_parser.models import CostcoPromotion
from receipt_parser.utils import process_official_promotion

class Command(BaseCommand):
    help = 'Process official Costco promotional booklets and create price adjustment alerts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--promotion-id',
            type=int,
            help='Process a specific promotion by ID'
        )
        parser.add_argument(
            '--all-unprocessed',
            action='store_true',
            help='Process all unprocessed promotions'
        )
        parser.add_argument(
            '--active-only',
            action='store_true',
            help='Only process promotions with active sale dates'
        )
    
    def handle(self, *args, **options):
        if options['promotion_id']:
            # Process specific promotion
            try:
                promotion = CostcoPromotion.objects.get(id=options['promotion_id'])
                self.stdout.write(f"Processing promotion: {promotion.title}")
                
                results = process_official_promotion(promotion.id)
                
                if 'error' in results:
                    raise CommandError(f"Failed to process promotion: {results['error']}")
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully processed '{promotion.title}':\n"
                        f"  - Pages processed: {results['pages_processed']}\n"
                        f"  - Items extracted: {results['items_extracted']}\n"
                        f"  - Alerts created: {results['alerts_created']}\n"
                        f"  - Errors: {len(results['errors'])}"
                    )
                )
                
                if results['errors']:
                    self.stdout.write(
                        self.style.WARNING("Errors encountered:")
                    )
                    for error in results['errors']:
                        self.stdout.write(f"  - {error}")
                        
            except CostcoPromotion.DoesNotExist:
                raise CommandError(f"Promotion with ID {options['promotion_id']} does not exist")
                
        elif options['all_unprocessed']:
            # Process all unprocessed promotions
            queryset = CostcoPromotion.objects.filter(is_processed=False)
            
            if options['active_only']:
                today = timezone.now().date()
                queryset = queryset.filter(
                    sale_start_date__lte=today,
                    sale_end_date__gte=today
                )
            
            if not queryset.exists():
                self.stdout.write(
                    self.style.WARNING("No unprocessed promotions found")
                )
                return
            
            self.stdout.write(f"Found {queryset.count()} unprocessed promotion(s)")
            
            total_pages = 0
            total_items = 0
            total_alerts = 0
            processed_count = 0
            
            for promotion in queryset:
                self.stdout.write(f"\nProcessing: {promotion.title}")
                
                try:
                    results = process_official_promotion(promotion.id)
                    
                    if 'error' in results:
                        self.stdout.write(
                            self.style.ERROR(f"Failed: {results['error']}")
                        )
                        continue
                    
                    total_pages += results['pages_processed']
                    total_items += results['items_extracted']
                    total_alerts += results['alerts_created']
                    processed_count += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ {results['pages_processed']} pages, "
                            f"{results['items_extracted']} items, "
                            f"{results['alerts_created']} alerts"
                        )
                    )
                    
                    if results['errors']:
                        self.stdout.write(
                            self.style.WARNING(f"  ⚠ {len(results['errors'])} errors")
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing {promotion.title}: {str(e)}")
                    )
            
            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n=== SUMMARY ===\n"
                    f"Promotions processed: {processed_count}\n"
                    f"Total pages: {total_pages}\n"
                    f"Total items extracted: {total_items}\n"
                    f"Total alerts created: {total_alerts}"
                )
            )
            
        else:
            # Show available options
            unprocessed_count = CostcoPromotion.objects.filter(is_processed=False).count()
            total_count = CostcoPromotion.objects.count()
            
            self.stdout.write(
                "Costco Promotion Processing Tool\n"
                f"Total promotions: {total_count}\n"
                f"Unprocessed: {unprocessed_count}\n\n"
                "Usage:\n"
                "  --promotion-id ID    Process specific promotion\n"
                "  --all-unprocessed    Process all unprocessed promotions\n"
                "  --active-only        Only process active promotions"
            )
            
            if unprocessed_count > 0:
                self.stdout.write("\nUnprocessed promotions:")
                for promo in CostcoPromotion.objects.filter(is_processed=False):
                    status = "ACTIVE" if promo.sale_start_date <= timezone.now().date() <= promo.sale_end_date else "INACTIVE"
                    self.stdout.write(f"  {promo.id}: {promo.title} ({status})") 