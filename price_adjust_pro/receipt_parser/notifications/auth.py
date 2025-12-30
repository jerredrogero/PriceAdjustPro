from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone


def get_request_user_via_bearer_session(request):
    """
    Authenticate via `Authorization: Bearer <session_key>`.

    This is a pragmatic bridge for mobile clients that don't want to deal with
    cookie jars + CSRF. It maps the bearer token to an existing Django session.
    """
    auth = request.META.get("HTTP_AUTHORIZATION", "") or ""
    if not auth.lower().startswith("bearer "):
        return None

    session_key = auth.split(" ", 1)[1].strip()
    if not session_key:
        return None

    try:
        session = Session.objects.get(session_key=session_key, expire_date__gt=timezone.now())
    except Session.DoesNotExist:
        return None

    decoded = session.get_decoded()
    user_id = decoded.get("_auth_user_id")
    if not user_id:
        return None

    User = get_user_model()
    return User.objects.filter(pk=user_id, is_active=True).first()


