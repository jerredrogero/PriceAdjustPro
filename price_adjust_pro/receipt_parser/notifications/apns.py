from __future__ import annotations

import functools
import logging
import time
import base64
import binascii

from django.conf import settings

logger = logging.getLogger(__name__)


class ApnsSendResult:
    def __init__(self, *, success: bool, status_code: int | None = None, reason: str | None = None):
        self.success = success
        self.status_code = status_code
        self.reason = reason


def _load_p8_key() -> str | None:
    raw = (getattr(settings, "APNS_PRIVATE_KEY_P8", "") or "").strip()
    raw_b64 = (getattr(settings, "APNS_PRIVATE_KEY_P8_BASE64", "") or "").strip()
    if raw_b64 and not raw:
        raw = raw_b64

    if raw:
        # Render env vars are sometimes pasted with wrapping quotes or escaped newlines.
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1].strip()

        # Allow env var with '\n' escapes
        raw = raw.replace("\\r\\n", "\n").replace("\\n", "\n")

        # Normalize Windows newlines
        raw = raw.replace("\r\n", "\n")

        # Some platforms prefer storing the .p8 as base64.
        # If it doesn't look like PEM yet, try base64 decode.
        if "BEGIN PRIVATE KEY" not in raw and "BEGIN EC PRIVATE KEY" not in raw:
            try:
                decoded = base64.b64decode(raw.encode("utf-8"), validate=True)
                decoded_text = decoded.decode("utf-8", errors="strict").strip()
                if "BEGIN PRIVATE KEY" in decoded_text or "BEGIN EC PRIVATE KEY" in decoded_text:
                    return decoded_text.replace("\r\n", "\n")
            except (binascii.Error, UnicodeDecodeError):
                pass

        return raw

    path = (getattr(settings, "APNS_PRIVATE_KEY_P8_PATH", "") or "").strip()
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            logger.warning("APNS_PRIVATE_KEY_P8_PATH could not be read: %s", e)

    return None


@functools.lru_cache(maxsize=1)
def _get_signing_key():
    """
    Lazily load the APNs provider token signing key (.p8).
    """
    p8 = _load_p8_key()
    if not p8:
        return None
    try:
        from cryptography.hazmat.primitives import serialization  # type: ignore
    except Exception as e:
        logger.exception("cryptography is required for APNs provider token auth: %s", e)
        return None
    try:
        return serialization.load_pem_private_key(p8.encode("utf-8"), password=None)
    except Exception as e:
        logger.exception("Failed to parse APNS_PRIVATE_KEY_P8: %s", e)
        return None


def _apns_host() -> str:
    use_sandbox = bool(getattr(settings, "APNS_USE_SANDBOX", False))
    return "https://api.sandbox.push.apple.com" if use_sandbox else "https://api.push.apple.com"


@functools.lru_cache(maxsize=1)
def _get_http_client():
    try:
        import httpx  # type: ignore
    except Exception as e:
        logger.exception("httpx is required for APNs HTTP/2: %s", e)
        return None
    # HTTP/2 is required by APNs
    return httpx.Client(http2=True, timeout=10.0)


@functools.lru_cache(maxsize=1)
def _provider_token_cache():
    # store {"token": str, "iat": int}
    return {"token": None, "iat": 0}


def _get_provider_token() -> str | None:
    """
    Build (and cache) APNs provider token JWT.

    APNs recommends rotating at least every 60 minutes; we refresh every 50.
    """
    team_id = (getattr(settings, "APNS_TEAM_ID", "") or "").strip()
    key_id = (getattr(settings, "APNS_KEY_ID", "") or "").strip()
    if not team_id or not key_id:
        return None

    cache = _provider_token_cache()
    now = int(time.time())
    if cache.get("token") and (now - int(cache.get("iat") or 0) < 50 * 60):
        return cache["token"]

    signing_key = _get_signing_key()
    if signing_key is None:
        return None

    try:
        import jwt  # type: ignore
    except Exception as e:
        logger.exception("PyJWT is required for APNs provider token auth: %s", e)
        return None

    try:
        token = jwt.encode(
            {"iss": team_id, "iat": now},
            signing_key,
            algorithm="ES256",
            headers={"kid": key_id},
        )
        cache["token"] = token
        cache["iat"] = now
        return token
    except Exception as e:
        logger.exception("Failed to create APNs provider token JWT: %s", e)
        return None


def send_apns(*, token: str, payload: dict, topic: str | None = None) -> ApnsSendResult:
    """
    Send a push to a single APNs token.

    If APNs is not configured, returns a non-success result (and logs).
    """
    http_client = _get_http_client()
    if http_client is None:
        return ApnsSendResult(success=False, reason="http2_client_missing")

    provider_token = _get_provider_token()
    if not provider_token:
        logger.info("APNs not configured; skipping send")
        return ApnsSendResult(success=False, reason="apns_not_configured")

    bundle_id = topic or getattr(settings, "APNS_BUNDLE_ID", "") or ""
    if not bundle_id:
        logger.warning("APNS_BUNDLE_ID missing; skipping send")
        return ApnsSendResult(success=False, reason="missing_topic")

    try:
        import json as _json

        aps = payload.get("aps") or {}
        has_alert = bool(aps.get("alert"))
        push_type = "alert" if has_alert else "background"

        url = f"{_apns_host()}/3/device/{token}"
        headers = {
            "authorization": f"bearer {provider_token}",
            "apns-topic": bundle_id,
            "apns-push-type": push_type,
        }

        res = http_client.post(url, headers=headers, content=_json.dumps(payload).encode("utf-8"))
        if 200 <= res.status_code < 300:
            return ApnsSendResult(success=True, status_code=res.status_code)

        reason = None
        try:
            body = res.json()
            reason = body.get("reason") if isinstance(body, dict) else None
        except Exception:
            reason = (res.text or "").strip() or None

        return ApnsSendResult(success=False, status_code=res.status_code, reason=reason)
    except Exception as e:
        logger.exception("APNs send failed: %s", e)
        return ApnsSendResult(success=False, reason="exception")


