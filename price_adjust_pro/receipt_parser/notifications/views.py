from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from receipt_parser.models import PushDevice
from receipt_parser.notifications.auth import get_request_user_via_bearer_session
from receipt_parser.serializers import PushDeviceSerializer, PushDeviceUpsertSerializer

logger = logging.getLogger(__name__)


@csrf_exempt
def api_upsert_push_device(request):
    """
    GET/POST /api/notifications/devices/

    Auth:
    - Cookie session (request.user.is_authenticated)
    - OR Authorization: Bearer <django_session_key>
    """
    if request.method not in ("GET", "POST"):
        return JsonResponse({"error": "Method not allowed"}, status=405)

    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    if user is None:
        user = get_request_user_via_bearer_session(request)

    if user is None:
        # WARNING level so this shows up in production logs without extra config.
        logger.warning(
            "Push device upsert: auth required (ua=%s, has_auth=%s, cookies=%s)",
            request.META.get("HTTP_USER_AGENT", "")[:120],
            bool(request.META.get("HTTP_AUTHORIZATION")),
            ",".join(sorted(list(request.COOKIES.keys())))[:200],
        )
        return JsonResponse({"error": "Authentication required"}, status=401)

    if request.method == "GET":
        devices = PushDevice.objects.filter(user=user).order_by("-updated_at")[:20]
        return JsonResponse({"devices": PushDeviceSerializer(devices, many=True).data}, status=200)

    try:
        body = request.body.decode("utf-8") if isinstance(request.body, (bytes, bytearray)) else (request.body or "")
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        logger.warning("Push device upsert: invalid JSON (user_id=%s)", getattr(user, "id", None))
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    logger.warning(
        "Push device upsert: received (user_id=%s, keys=%s)",
        getattr(user, "id", None),
        sorted(list(data.keys())) if isinstance(data, dict) else "non-dict",
    )

    serializer = PushDeviceUpsertSerializer(data=data)
    if not serializer.is_valid():
        logger.warning(
            "Push device upsert: validation failed (user_id=%s) errors=%s",
            getattr(user, "id", None),
            serializer.errors,
        )
        return JsonResponse({"error": "Validation failed", "details": serializer.errors}, status=400)

    vd = serializer.validated_data
    prefs = vd["preferences"]

    device, _created = PushDevice.objects.update_or_create(
        user=user,
        device_id=vd["device_id"],
        defaults={
            "apns_token": vd["apns_token"],
            "platform": vd["platform"],
            "app_version": vd.get("app_version") or None,
            "is_enabled": True,
            "last_seen_at": timezone.now(),
            "price_adjustment_alerts_enabled": prefs["price_adjustment_alerts_enabled"],
            "sale_alerts_enabled": prefs["sale_alerts_enabled"],
            "receipt_processing_alerts_enabled": prefs["receipt_processing_alerts_enabled"],
            "price_drop_alerts_enabled": prefs["price_drop_alerts_enabled"],
        },
    )

    logger.warning(
        "Push device upsert: success (user_id=%s device_id=%s platform=%s)",
        getattr(user, "id", None),
        device.device_id,
        device.platform,
    )
    return JsonResponse(PushDeviceSerializer(device).data, status=200)


