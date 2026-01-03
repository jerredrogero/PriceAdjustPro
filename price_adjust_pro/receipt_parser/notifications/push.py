from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from receipt_parser.models import PushDelivery, PushDevice, PriceAdjustmentAlert
from receipt_parser.notifications.apns import send_apns

logger = logging.getLogger(__name__)


DEFAULT_THROTTLE_MINUTES = 10


def _format_money(value: Decimal) -> str:
    return f"{value:.2f}"


def build_price_adjustment_summary_payload(*, count: int, total_savings: Decimal):
    return {
        "aps": {
            "alert": {
                "title": "Price Adjustments Available",
                "body": f"You have {count} new price adjustments worth ${_format_money(total_savings)}",
            },
            "sound": "default",
            # Badge can be managed client-side; keep simple for MVP
        },
        "type": "price_adjustments",
        "count": count,
        "total_savings": _format_money(total_savings),
    }


def send_price_adjustment_summary_to_user(
    *,
    user_id: int,
    latest_alert_id: int,
    count: int,
    total_savings: Decimal,
    throttle_minutes: int = DEFAULT_THROTTLE_MINUTES,
):
    """
    Fan out a summary push to all enabled devices for a user.

    Dedupes per-device via PushDelivery and throttles via a time window.
    """
    devices = PushDevice.objects.filter(user_id=user_id, is_enabled=True, price_adjustment_alerts_enabled=True)
    if not devices.exists():
        return 0

    payload = build_price_adjustment_summary_payload(count=count, total_savings=total_savings)
    kind = "price_adjustment_summary"
    dedupe_key = f"latest_alert:{latest_alert_id}"

    sent = 0
    now = timezone.now()
    throttle_after = now - timedelta(minutes=throttle_minutes)

    for device in devices:
        # Throttle: if we sent any summary recently to this device, skip unless dedupe key is new
        recently_sent = PushDelivery.objects.filter(device=device, kind=kind, created_at__gte=throttle_after).exists()
        if recently_sent:
            continue

        delivery = None
        try:
            with transaction.atomic():
                delivery = PushDelivery.objects.create(
                    device=device,
                    kind=kind,
                    dedupe_key=dedupe_key,
                    payload_snapshot=payload,
                )
        except IntegrityError:
            # already sent (dedupe)
            continue

        res = send_apns(token=device.apns_token, payload=payload)
        # Persist the APNs result for debugging (no schema changes needed).
        try:
            if delivery is not None:
                delivery.payload_snapshot = {
                    **(delivery.payload_snapshot or {}),
                    "apns_result": {
                        "success": bool(res.success),
                        "status_code": res.status_code,
                        "reason": res.reason,
                    },
                }
                delivery.save(update_fields=["payload_snapshot"])
        except Exception:
            logger.exception("Failed to record APNs result on PushDelivery (device_id=%s)", device.id)

        if not res.success:
            # Only disable on definitive "token is no longer valid" responses.
            # Do NOT disable on recoverable errors like sandbox/prod mismatch or topic mismatch,
            # otherwise the device will keep flipping back to disabled during setup.
            reason_l = (res.reason or "").lower()
            should_disable = (res.status_code == 410) or ("unregistered" in reason_l)
            if should_disable:
                device.is_enabled = False
                device.save(update_fields=["is_enabled", "updated_at"])

            logger.warning(
                "APNs send failed (user_id=%s device_id=%s status=%s reason=%s disabled=%s)",
                user_id,
                device.id,
                res.status_code,
                res.reason,
                should_disable,
            )
        else:
            sent += 1

    return sent


def summarize_new_alerts_for_user(*, user_id: int, alert_ids: list[int]):
    qs = PriceAdjustmentAlert.objects.filter(user_id=user_id, id__in=alert_ids)
    total = Decimal("0.00")
    for a in qs:
        total += (a.original_price - a.lower_price)
    return {"count": qs.count(), "total_savings": total}


