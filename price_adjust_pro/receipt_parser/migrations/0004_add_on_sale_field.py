# Generated by Django 5.1 on 2025-05-23 22:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('receipt_parser', '0003_alter_costcoitem_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lineitem',
            name='on_sale',
            field=models.BooleanField(default=False, help_text='Mark this item as on sale if the parsing missed it'),
        ),
    ]
