# Generated by Django 5.1 on 2025-05-25 18:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('receipt_parser', '0007_allow_null_sale_price_and_add_discount_only'),
    ]

    operations = [
        migrations.AlterField(
            model_name='receipt',
            name='file',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
