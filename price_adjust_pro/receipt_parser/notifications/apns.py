from __future__ import annotations

import functools
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)


class ApnsSendResult:
    def __init__(self, *, success: bool, status_code: int | None = None, reason: str | None = None):
        self.success = success
        self.status_code = status_code
        self.reason = reason


def _load_p8_key() -> str | None:
    raw = (getattr(settings, "APNS_PRIVATE_KEY_P8", "") or "").strip()
    if raw:
        # Allow env var with '\n' escapes
        return raw.replace("\\n", "\n")

    path = (getattr(settings, "APNS_PRIVATE_KEY_P8_PATH", "") or "").strip()
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            logger.warning("APNS_PRIVATE_KEY_P8_PATH could not be read: %s", e)

    return None


@functools.lru_cache(maxsize=1)
def _get_apns_client():
    """
    Lazily build an APNs client.

    Uses provider token auth (.p8). We import `apns2` at runtime so tests can run
    without the dependency installed.
    """
    p8 = _load_p8_key()
    if not p8:
        return None

    team_id = getattr(settings, "APNS_TEAM_ID", "") or ""
    key_id = getattr(settings, "APNS_KEY_ID", "") or ""
    if not team_id or not key_id:
        return None

    use_sandbox = bool(getattr(settings, "APNS_USE_SANDBOX", False))

    from apns2.client import APNsClient  # type: ignore

    # apns2 supports passing the private key bytes/str directly
    return APNsClient(credentials=p8, use_sandbox=use_sandbox, use_alternative_port=False, team_id=team_id, key_id=key_id)


def send_apns(*, token: str, payload: dict, topic: str | None = None) -> ApnsSendResult:
    """
    Send a push to a single APNs token.

    If APNs is not configured, returns a non-success result (and logs).
    """
    client = _get_apns_client()
    if client is None:
        logger.info("APNs not configured; skipping send")
        return ApnsSendResult(success=False, reason="apns_not_configured")

    bundle_id = topic or getattr(settings, "APNS_BUNDLE_ID", "") or ""
    if not bundle_id:
        logger.warning("APNS_BUNDLE_ID missing; skipping send")
        return ApnsSendResult(success=False, reason="missing_topic")

    try:
        from apns2.payload import Payload  # type: ignore

        aps = payload.get("aps") or {}
        alert = aps.get("alert")
        sound = aps.get("sound")
        badge = aps.get("badge")
        content_available = 1 if aps.get("content-available") else 0

        # Anything outside "aps" is custom data
        custom = {k: v for k, v in payload.items() if k != "aps"}

        apns_payload = Payload(
            alert=alert,
            sound=sound,
            badge=badge,
            content_available=bool(content_available),
            custom=custom or None,
        )

        # Priority defaults: use apns2 default behavior
        res = client.send_notification(token, apns_payload, topic=bundle_id)

        # apns2 returns NotificationResponse
        if getattr(res, "is_successful", False):
            return ApnsSendResult(success=True, status_code=200)
        return ApnsSendResult(
            success=False,
            status_code=getattr(res, "status", None),
            reason=getattr(res, "description", None) or getattr(res, "reason", None),
        )
    except Exception as e:
        logger.exception("APNs send failed: %s", e)
        return ApnsSendResult(success=False, reason="exception")


