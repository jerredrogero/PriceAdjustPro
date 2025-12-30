from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from receipt_parser.models import PriceAdjustmentAlert
from receipt_parser.notifications.push import send_price_adjustment_summary_to_user

def push_summaries_for_official_sale_item(*, official_sale_item_id: int, window_minutes: int = 10):
    """
    Push summaries for alerts created very recently for a specific official sale item.

    Call this immediately after `create_official_price_alerts(...)` so we only notify
    for alerts created during that processing run.
    """
    recent_cutoff = timezone.now() - timedelta(minutes=window_minutes)

    # Find users who now have alerts for this official item created recently
    qs = PriceAdjustmentAlert.objects.filter(
        data_source="official_promo",
        official_sale_item_id=official_sale_item_id,
        created_at__gte=recent_cutoff,
    ).values_list("user_id", "id", "original_price", "lower_price")

    by_user_ids = defaultdict(list)
    totals = defaultdict(lambda: Decimal("0.00"))
    for user_id, alert_id, original_price, lower_price in qs:
        by_user_ids[user_id].append(alert_id)
        totals[user_id] += (original_price - lower_price)

    users_pushed = 0
    for user_id, alert_ids in by_user_ids.items():
        latest_alert_id = max(alert_ids)
        sent = send_price_adjustment_summary_to_user(
            user_id=user_id,
            latest_alert_id=latest_alert_id,
            count=len(alert_ids),
            total_savings=totals[user_id],
        )
        if sent:
            users_pushed += 1

    return {"users_pushed": users_pushed}


