from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("receipt_parser", "0018_push_notifications_models_and_alert_dedupe"),
    ]

    operations = [
        migrations.AlterField(
            model_name="priceadjustmentalert",
            name="original_store_city",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="priceadjustmentalert",
            name="original_store_number",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="priceadjustmentalert",
            name="cheaper_store_city",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="priceadjustmentalert",
            name="cheaper_store_number",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]


