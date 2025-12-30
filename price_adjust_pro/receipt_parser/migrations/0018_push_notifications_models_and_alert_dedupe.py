from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("receipt_parser", "0017_add_verification_code"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="priceadjustmentalert",
            name="dedupe_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Stable key to dedupe alerts across repeated matching runs",
                max_length=128,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="priceadjustmentalert",
            constraint=models.UniqueConstraint(
                condition=Q(("dedupe_key__isnull", False)),
                fields=("user", "dedupe_key"),
                name="uniq_price_adjustment_alert_user_dedupe_key",
            ),
        ),
        migrations.CreateModel(
            name="PushDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_id", models.CharField(help_text="Client-generated stable device identifier", max_length=128)),
                ("apns_token", models.CharField(help_text="APNs device token (hex string)", max_length=256)),
                (
                    "platform",
                    models.CharField(
                        choices=[("ios", "iOS")],
                        default="ios",
                        max_length=16,
                    ),
                ),
                ("app_version", models.CharField(blank=True, max_length=32, null=True)),
                ("is_enabled", models.BooleanField(default=True)),
                ("price_adjustment_alerts_enabled", models.BooleanField(default=True)),
                ("sale_alerts_enabled", models.BooleanField(default=True)),
                ("receipt_processing_alerts_enabled", models.BooleanField(default=True)),
                ("price_drop_alerts_enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="push_devices", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Push Device",
                "verbose_name_plural": "Push Devices",
            },
        ),
        migrations.AddIndex(
            model_name="pushdevice",
            index=models.Index(fields=["user", "device_id"], name="receipt_pars_user_id_a1ed7a_idx"),
        ),
        migrations.AddIndex(
            model_name="pushdevice",
            index=models.Index(fields=["user", "is_enabled"], name="receipt_pars_user_id_0e0b2c_idx"),
        ),
        migrations.AddIndex(
            model_name="pushdevice",
            index=models.Index(fields=["platform"], name="receipt_pars_platform_8a3cc9_idx"),
        ),
        migrations.AddIndex(
            model_name="pushdevice",
            index=models.Index(fields=["last_seen_at"], name="receipt_pars_last_se_8d7f3c_idx"),
        ),
        migrations.AddConstraint(
            model_name="pushdevice",
            constraint=models.UniqueConstraint(fields=("user", "device_id"), name="uniq_push_device_user_device_id"),
        ),
        migrations.CreateModel(
            name="PushDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=64)),
                ("dedupe_key", models.CharField(db_index=True, max_length=255)),
                ("payload_snapshot", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "device",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="receipt_parser.pushdevice"),
                ),
            ],
            options={
                "verbose_name": "Push Delivery",
                "verbose_name_plural": "Push Deliveries",
            },
        ),
        migrations.AddIndex(
            model_name="pushdelivery",
            index=models.Index(fields=["kind", "created_at"], name="receipt_pars_kind_e0aab0_idx"),
        ),
        migrations.AddIndex(
            model_name="pushdelivery",
            index=models.Index(fields=["device", "kind", "created_at"], name="receipt_pars_device__4b8f02_idx"),
        ),
        migrations.AddConstraint(
            model_name="pushdelivery",
            constraint=models.UniqueConstraint(fields=("device", "kind", "dedupe_key"), name="uniq_push_delivery_device_kind_key"),
        ),
    ]


