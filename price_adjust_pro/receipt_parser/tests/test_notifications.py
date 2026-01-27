import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from receipt_parser.models import PushDevice, PushDelivery, PriceAdjustmentAlert
from receipt_parser.notifications.push import send_price_adjustment_summary_to_user


class PushDeviceUpsertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1@example.com", password="pw", email="u1@example.com")

    def test_requires_auth(self):
        resp = self.client.post(
            "/api/notifications/devices/",
            data=json.dumps(
                {
                    "device_id": "00000000-0000-0000-0000-000000000000",
                    "apns_token": "a" * 64,
                    "platform": "ios",
                    "app_version": "1.2.3",
                    "preferences": {
                        "price_adjustment_alerts_enabled": True,
                        "sale_alerts_enabled": True,
                        "receipt_processing_alerts_enabled": True,
                        "price_drop_alerts_enabled": True,
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_creates_device(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            "/api/notifications/devices/",
            data=json.dumps(
                {
                    "device_id": "00000000-0000-0000-0000-000000000000",
                    "apns_token": "b" * 64,
                    "platform": "ios",
                    "app_version": "1.2.3",
                    "preferences": {
                        "price_adjustment_alerts_enabled": True,
                        "sale_alerts_enabled": False,
                        "receipt_processing_alerts_enabled": True,
                        "price_drop_alerts_enabled": False,
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PushDevice.objects.filter(user=self.user).count(), 1)
        d = PushDevice.objects.get(user=self.user)
        self.assertEqual(d.device_id, "00000000-0000-0000-0000-000000000000")
        self.assertEqual(d.apns_token, "b" * 64)
        self.assertTrue(d.price_adjustment_alerts_enabled)
        self.assertFalse(d.sale_alerts_enabled)

    def test_upsert_does_not_duplicate(self):
        self.client.force_login(self.user)
        payload = {
            "device_id": "device-1",
            "apns_token": "c" * 64,
            "platform": "ios",
            "app_version": "1.0.0",
            "preferences": {
                "price_adjustment_alerts_enabled": True,
                "sale_alerts_enabled": True,
                "receipt_processing_alerts_enabled": True,
                "price_drop_alerts_enabled": True,
            },
        }
        r1 = self.client.post("/api/notifications/devices/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(r1.status_code, 200)
        payload["apns_token"] = "d" * 64
        payload["preferences"]["sale_alerts_enabled"] = False
        r2 = self.client.post("/api/notifications/devices/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(PushDevice.objects.filter(user=self.user, device_id="device-1").count(), 1)
        d = PushDevice.objects.get(user=self.user, device_id="device-1")
        self.assertEqual(d.apns_token, "d" * 64)
        self.assertFalse(d.sale_alerts_enabled)


class AlertDedupeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u2@example.com", password="pw", email="u2@example.com")

    def test_alert_dedupe_key_unique(self):
        purchase_date = timezone.now()
        k = PriceAdjustmentAlert.build_dedupe_key(
            user_id=self.user.id,
            item_code="123",
            purchase_date=purchase_date,
            original_store_number="0001",
            data_source="official_promo",
            official_sale_item_id=1,
        )
        PriceAdjustmentAlert.objects.create(
            user=self.user,
            item_code="123",
            item_description="X",
            original_price=Decimal("10.00"),
            lower_price=Decimal("9.00"),
            original_store_city="A",
            original_store_number="0001",
            cheaper_store_city="All",
            cheaper_store_number="ALL",
            purchase_date=purchase_date,
            data_source="official_promo",
            official_sale_item_id=1,
            dedupe_key=k,
        )
        with self.assertRaises(Exception):
            PriceAdjustmentAlert.objects.create(
                user=self.user,
                item_code="123",
                item_description="X",
                original_price=Decimal("10.00"),
                lower_price=Decimal("9.00"),
                original_store_city="A",
                original_store_number="0001",
                cheaper_store_city="All",
                cheaper_store_number="ALL",
                purchase_date=purchase_date,
                data_source="official_promo",
                official_sale_item_id=1,
                dedupe_key=k,
            )


class PushDeliveryDedupeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u3@example.com", password="pw", email="u3@example.com")
        self.device = PushDevice.objects.create(
            user=self.user,
            device_id="d1",
            apns_token="e" * 64,
            platform="ios",
            is_enabled=True,
            price_adjustment_alerts_enabled=True,
        )

    def test_push_delivery_dedupe(self):
        # Patch APNs sender at the module import site
        import receipt_parser.notifications.push as push_mod

        def fake_send_apns(*, token, payload, topic=None):
            class R:
                success = True
                reason = None

            return R()

        push_mod.send_apns = fake_send_apns

        sent1 = send_price_adjustment_summary_to_user(
            user_id=self.user.id,
            latest_alert_id=100,
            count=1,
            total_savings=Decimal("1.00"),
            throttle_minutes=0,
        )
        sent2 = send_price_adjustment_summary_to_user(
            user_id=self.user.id,
            latest_alert_id=100,
            count=1,
            total_savings=Decimal("1.00"),
            throttle_minutes=0,
        )
        self.assertEqual(sent1, 1)
        self.assertEqual(sent2, 0)
        self.assertEqual(PushDelivery.objects.filter(device=self.device, kind="price_adjustment_summary").count(), 1)


