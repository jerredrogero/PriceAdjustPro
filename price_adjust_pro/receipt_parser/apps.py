from django.apps import AppConfig


class ReceiptParserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'receipt_parser'

    def ready(self):
        # Register AVIF support through pillow_heif
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            # pillow_heif not available, AVIF support will be limited
            pass
