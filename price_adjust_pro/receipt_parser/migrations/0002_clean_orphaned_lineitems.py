from django.db import migrations

def delete_orphaned_lineitems(apps, schema_editor):
    LineItem = apps.get_model('receipt_parser', 'LineItem')
    LineItem.objects.filter(receipt__isnull=True).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('receipt_parser', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(delete_orphaned_lineitems),
    ] 