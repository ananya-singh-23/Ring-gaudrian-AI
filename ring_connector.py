"""Opt-in, server-side Ring Partner API client and webhook verification.

Live access remains disabled unless a Ring application is explicitly approved
and credentials plus a user access token are configured server-side.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import base64
from typing import Any, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from event_schema import ring_webhook_to_event

API_BASE_URL = "https://api.amazonvision.com"
OAUTH_TOKEN_URL = "https://oauth.ring.com/oauth/token"
DOCUMENTED_EVENT_TYPES = {
    "motion_detected", "button_press", "device_added", "device_removed",
    "device_online", "device_offline", "subscription_activated",
    "subscription_deactivated", "app_integration_added", "app_integration_removed",
}


class RingConfigurationError(RuntimeError):
    """Raised when live Ring access is not fully configured."""


class RingApiError(RuntimeError):
    """Raised for Ring API transport and response errors without exposing secrets."""


def ring_status(env: Optional[Mapping[str, str]] = None) -> str:
    """Describe live integration readiness without displaying credential values."""
    values = env if env is not None else os.environ
    approved = values.get("RING_APP_APPROVED", "").lower() == "true"
    required = ("RING_CLIENT_ID", "RING_CLIENT_SECRET", "RING_HMAC_SIGNING_KEY", "RING_ACCESS_TOKEN")
    if not approved:
        return "Disabled — Ring app approval is not confirmed. Local simulated mode is active."
    missing = [key for key in required if not values.get(key)]
    if missing:
        return "Disabled — approved app credentials/access token are not fully configured."
    return "Configured — credentials are present; live Ring access has not been verified yet."


def verify_webhook_signature(raw_body: bytes, signature: str, signing_key: str) -> bool:
    """Verify Ring's documented sha256=hex HMAC against the exact raw body bytes."""
    if not raw_body or not signature or not signing_key or not signature.startswith("sha256="):
        return False
    expected = hmac.new(signing_key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    supplied = signature[len("sha256="):]
    return hmac.compare_digest(expected, supplied)


def parse_verified_webhook(raw_body: bytes, signature: str, signing_key: str,
                           device_name: str) -> Dict[str, Any]:
    """Reject unauthenticated/malformed callbacks before normalizing their event."""
    if not verify_webhook_signature(raw_body, signature, signing_key):
        raise RingApiError("Webhook rejected: signature verification failed")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RingApiError("Webhook rejected: invalid JSON payload") from exc
    try:
        event_type = ((payload.get("data") or {}).get("type"))
        if event_type not in DOCUMENTED_EVENT_TYPES:
            raise ValueError("Unsupported Ring webhook event type")
        return ring_webhook_to_event(payload, device_name)
    except (TypeError, ValueError) as exc:
        raise RingApiError("Webhook rejected: event payload is incomplete") from exc


class RingApiClient:
    """Small server-side client for the documented Users and device APIs."""

    def __init__(self, access_token: str, timeout: float = 10.0):
        if not access_token:
            raise RingConfigurationError("A Ring user access token is required")
        self._access_token = access_token
        self._timeout = timeout

    @staticmethod
    def _token_request(form: Mapping[str, str], timeout: float = 10.0) -> Dict[str, Any]:
        request = Request(
            OAUTH_TOKEN_URL,
            data=urlencode(form).encode("ascii"),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            status = getattr(exc, "code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise RingApiError(f"Ring OAuth token request failed{suffix}") from None

    @classmethod
    def exchange_authorization_code(cls, code: str, env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
        """Exchange a Ring authorization code using documented server-side credentials.

        Account-link endpoints, redirects, and nonce/PKCE setup must be configured
        in the Ring Developer Portal according to the approved app's linking flow.
        """
        values = env if env is not None else os.environ
        if values.get("RING_APP_APPROVED", "").lower() != "true":
            raise RingConfigurationError("Ring integration disabled until app approval is confirmed")
        client_id, client_secret = values.get("RING_CLIENT_ID"), values.get("RING_CLIENT_SECRET")
        if not code or not client_id or not client_secret:
            raise RingConfigurationError("Authorization code and approved Ring client credentials are required")
        return cls._token_request({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        })

    @classmethod
    def refresh_tokens(cls, refresh_token: str, env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
        """Refresh Ring OAuth tokens through the documented server endpoint."""
        values = env if env is not None else os.environ
        if values.get("RING_APP_APPROVED", "").lower() != "true":
            raise RingConfigurationError("Ring integration disabled until app approval is confirmed")
        client_id, client_secret = values.get("RING_CLIENT_ID"), values.get("RING_CLIENT_SECRET")
        if not refresh_token or not client_id or not client_secret:
            raise RingConfigurationError("Refresh token and approved Ring client credentials are required")
        return cls._token_request({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        })

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "RingApiClient":
        values = env if env is not None else os.environ
        if values.get("RING_APP_APPROVED", "").lower() != "true":
            raise RingConfigurationError("Ring integration disabled until app approval is confirmed")
        missing = [name for name in ("RING_CLIENT_ID", "RING_CLIENT_SECRET", "RING_HMAC_SIGNING_KEY", "RING_ACCESS_TOKEN")
                   if not values.get(name)]
        if missing:
            raise RingConfigurationError("Ring credentials and access token are not fully configured")
        return cls(values["RING_ACCESS_TOKEN"])

    def _get(self, path: str) -> Dict[str, Any]:
        request = Request(
            f"{API_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self._access_token}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            # Do not include the request, headers, body, or token in the exception text.
            status = getattr(exc, "code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise RingApiError(f"Ring API request failed{suffix}") from None

    def get_user(self) -> Dict[str, Any]:
        """Get the authenticated user's documented profile (`GET /v1/users/me`)."""
        return self._get("/v1/users/me")

    def list_devices(self) -> Dict[str, Any]:
        """Discover devices shared with this authorized Ring account."""
        return self._get("/v1/devices")

    def _integration_request(self, method: str, payload: Mapping[str, str]) -> Dict[str, Any]:
        body = json.dumps(dict(payload)).encode("utf-8")
        request = Request(
            f"{API_BASE_URL}/v1/accounts/me/app-integrations",
            data=body,
            headers={"Authorization": f"Bearer {self._access_token}",
                     "Content-Type": "application/json", "Accept": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                data = response.read()
                return json.loads(data.decode("utf-8")) if data else {}
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            status = getattr(exc, "code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise RingApiError(f"Ring account-link request failed{suffix}") from None

    @staticmethod
    def one_way_nonce(time_value: str, account_id: str, signing_key: str) -> str:
        """Compute the documented one-way account-link nonce.

        Ring defines this as URL-safe Base64(HMAC-SHA256(UTF8 key,
        UTF8 ``<timestamp_ms>:<account_id>``)), without Base64 padding.
        """
        if not time_value or not account_id or not signing_key:
            raise RingConfigurationError("Ring timestamp, account ID, and HMAC key are required")
        message = f"{time_value}:{account_id}".encode("utf-8")
        digest = hmac.new(signing_key.encode("utf-8"), message, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def confirm_one_way_account_link(self, account_identifier: str, nonce: str) -> Dict[str, Any]:
        """Perform required POST nonce verification followed by PATCH completion."""
        if not account_identifier or not nonce:
            raise RingConfigurationError("Signed-in partner account identifier and Ring nonce are required")
        self._integration_request("POST", {"account_identifier": account_identifier, "nonce": nonce})
        return self._integration_request("PATCH", {
            "account_identifier": account_identifier,
            "status": "completed",
        })

    def complete_partner_initiated_account_link(self, account_identifier: str) -> Dict[str, Any]:
        """Finalize partner-initiated OAuth linking with the documented PATCH call."""
        if not account_identifier:
            raise RingConfigurationError("Signed-in partner account identifier is required")
        return self._integration_request("PATCH", {
            "account_identifier": account_identifier,
            "status": "completed",
        })
