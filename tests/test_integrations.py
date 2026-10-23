"""Offline tests for canonical event records and the disabled-by-default Ring adapter."""
from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import json
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

import ring_connector
import state
from event_schema import normalize_event, validate_event
from simulator import make_event
from utils import parse_ts


def test_simulator_events_use_canonical_schema_and_keep_legacy_fields():
    event = make_event("front_door", "Front Door", "door_open", details="test")
    assert validate_event(event)
    assert event["source"] == "simulated"
    assert event["simulated"] is True
    assert event["attributes"]["details"] == "test"


def test_legacy_event_is_migrated_to_simulated_source():
    event = normalize_event({
        "id": "old", "device_id": "front_door", "device_name": "Front Door",
        "event_type": "door_open", "timestamp": "2026-10-23T12:00:00Z", "details": "old format",
    })
    assert event["source"] == "simulated"
    assert event["simulated"] is True
    expected = datetime.fromisoformat("2026-10-23T12:00:00+00:00").astimezone().replace(tzinfo=None)
    assert parse_ts(event["timestamp"]) == expected


def test_invalid_timestamps_are_rejected():
    assert not validate_event({
        "id": "bad", "source": "simulated", "device_id": "x", "device_name": "X",
        "event_type": "motion_detected", "timestamp": "not-time", "attributes": {},
    })


def test_ring_webhook_conversion_uses_documented_envelope():
    raw = json.dumps({
        "meta": {"version": "1.1", "request_id": "req-1", "account_id": "private-account"},
        "data": {"id": "event-1", "type": "motion_detected", "subType": "human",
                 "attributes": {"source": "cam-7", "source_type": "devices", "timestamp": 1792771200000}},
    }).encode()
    key = "test-only-key"
    signature = "sha256=" + hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()
    event = ring_connector.parse_verified_webhook(raw, signature, key, "Camera")
    assert event["source"] == "ring"
    assert event["simulated"] is False
    assert event["device_id"] == "cam-7"
    assert event["attributes"]["subType"] == "human"
    assert "private-account" not in json.dumps(event)


def test_webhook_rejects_missing_or_invalid_signature():
    raw = b'{"data":{}}'
    assert not ring_connector.verify_webhook_signature(raw, "", "secret")
    with pytest.raises(ring_connector.RingApiError, match="signature verification failed"):
        ring_connector.parse_verified_webhook(raw, "sha256=bad", "secret", "Camera")


def test_webhook_rejects_unknown_event_even_with_valid_signature():
    raw = json.dumps({"meta": {}, "data": {"id": "x", "type": "unknown_event",
                                            "attributes": {"source": "cam", "timestamp": 1792771200000}}}).encode()
    key = "test-only-key"
    signature = "sha256=" + hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()
    with pytest.raises(ring_connector.RingApiError, match="event payload is incomplete"):
        ring_connector.parse_verified_webhook(raw, signature, key, "Camera")


def test_ring_integration_is_disabled_without_approval_or_credentials():
    assert "Disabled" in ring_connector.ring_status({})
    with pytest.raises(ring_connector.RingConfigurationError):
        ring_connector.RingApiClient.from_env({})
    with pytest.raises(ring_connector.RingConfigurationError):
        ring_connector.RingApiClient.from_env({"RING_APP_APPROVED": "true"})


def test_one_way_nonce_uses_ring_documented_hmac_encoding():
    timestamp, account_id, key = "1751800260000", "account-123", "test-key"
    digest = hmac.new(key.encode(), f"{timestamp}:{account_id}".encode(), hashlib.sha256).digest()
    expected = __import__("base64").urlsafe_b64encode(digest).decode().rstrip("=")
    assert ring_connector.RingApiClient.one_way_nonce(timestamp, account_id, key) == expected


def test_one_way_link_calls_post_then_patch(monkeypatch):
    client = ring_connector.RingApiClient("test-token")
    calls = []

    def fake_request(method, payload):
        calls.append((method, dict(payload)))
        return {"status": "awaiting" if method == "POST" else "completed"}

    monkeypatch.setattr(client, "_integration_request", fake_request)
    result = client.confirm_one_way_account_link("demo-user", "nonce-value")
    assert [method for method, _payload in calls] == ["POST", "PATCH"]
    assert calls[0][1] == {"account_identifier": "demo-user", "nonce": "nonce-value"}
    assert calls[1][1] == {"account_identifier": "demo-user", "status": "completed"}
    assert result["status"] == "completed"


def test_ring_users_and_device_endpoints_are_documented_and_mocked(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data": []}'

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.get_header("Authorization"), timeout))
        return Response()

    monkeypatch.setattr(ring_connector, "urlopen", fake_urlopen)
    client = ring_connector.RingApiClient("test-token")
    assert client.get_user() == {"data": []}
    assert client.list_devices() == {"data": []}
    assert [call[0] for call in calls] == [
        "https://api.amazonvision.com/v1/users/me",
        "https://api.amazonvision.com/v1/devices",
    ]
    assert all(call[1] == "Bearer test-token" for call in calls)


def test_ring_api_failure_is_sanitized(monkeypatch):
    def fail_urlopen(_request, timeout):
        raise ring_connector.URLError("secret-bearing transport details")

    monkeypatch.setattr(ring_connector, "urlopen", fail_urlopen)
    client = ring_connector.RingApiClient("do-not-print-this-token")
    with pytest.raises(ring_connector.RingApiError) as exc:
        client.get_user()
    assert "do-not-print-this-token" not in str(exc.value)
    assert "secret-bearing" not in str(exc.value)


@pytest.mark.parametrize("method,form", [
    ("exchange_authorization_code", {
        "grant_type": "authorization_code", "code": "test-code",
        "client_id": "test-client", "client_secret": "test-secret",
    }),
    ("refresh_tokens", {
        "grant_type": "refresh_token", "refresh_token": "test-refresh",
        "client_id": "test-client", "client_secret": "test-secret",
    }),
])
def test_oauth_exchange_and_refresh_are_server_side_form_posts(monkeypatch, method, form):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"access_token":"new-access","refresh_token":"new-refresh"}'

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.data.decode("ascii"), request.get_header("Content-type")))
        return Response()

    monkeypatch.setattr(ring_connector, "urlopen", fake_urlopen)
    env = {"RING_APP_APPROVED": "true", "RING_CLIENT_ID": "test-client",
           "RING_CLIENT_SECRET": "test-secret", "RING_HMAC_SIGNING_KEY": "test-hmac"}
    if method == "exchange_authorization_code":
        result = ring_connector.RingApiClient.exchange_authorization_code("test-code", env)
    else:
        result = ring_connector.RingApiClient.refresh_tokens("test-refresh", env)
    assert result["access_token"] == "new-access"
    assert calls == [("https://oauth.ring.com/oauth/token", urlencode(form),
                      "application/x-www-form-urlencoded")]


def test_store_normalizes_and_deduplicates_events(monkeypatch):
    fake_session = SimpleNamespace(events=[make_event("front_door", "Front Door", "door_open")])
    monkeypatch.setattr(state, "st", SimpleNamespace(session_state=fake_session))
    monkeypatch.setattr(state, "_save_json", lambda *_args: None)
    existing = fake_session.events[0]
    added = state.add_events([existing, dict(existing, id="new")])
    assert added == 1
    assert len(fake_session.events) == 2
    assert all(event["source"] == "simulated" for event in fake_session.events)


def test_reset_clears_all_sources(monkeypatch):
    fake_session = SimpleNamespace(events=[make_event("front_door", "Front Door", "door_open")])
    monkeypatch.setattr(state, "st", SimpleNamespace(session_state=fake_session))
    monkeypatch.setattr(state, "_save_json", lambda *_args: None)
    state.clear_events()
    assert fake_session.events == []
