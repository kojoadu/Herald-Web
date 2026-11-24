from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from services.supabase import AuthSession, AuthenticationRequired, SupabaseClient, SupabaseError


class Response:
    def __init__(self, status_code: int = 200, payload=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload
        self.content = b"" if payload is None else json.dumps(payload).encode()
        self.text = self.content.decode()

    def json(self):
        return self._payload


def test_authenticated_rest_includes_anon_key_and_bearer():
    http = Mock()
    http.request.return_value = Response(payload=[])
    session = AuthSession("access", "refresh", 4102444800, {"id": "user"})
    client = SupabaseClient("https://example.supabase.co", "anon", session=session, session_factory=lambda: http)

    assert client.rest("GET", "cloud_songs") == []
    headers = http.request.call_args.kwargs["headers"]
    assert headers["apikey"] == "anon"
    assert headers["Authorization"] == "Bearer access"


def test_rest_requires_session_for_private_song_pool():
    client = SupabaseClient("https://example.supabase.co", "anon", session_factory=Mock)
    with pytest.raises(AuthenticationRequired):
        client.rest("GET", "cloud_songs")


def test_refresh_replaces_expiring_session():
    http = Mock()
    http.request.return_value = Response(
        payload={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "user": {"id": "user"},
        }
    )
    session = AuthSession("old-access", "old-refresh", 1, {"id": "user"})
    client = SupabaseClient("https://example.supabase.co", "anon", session=session, session_factory=lambda: http)

    refreshed = client.refresh(force=True)

    assert refreshed.access_token == "new-access"
    assert "new-refresh" == client.session.refresh_token


def test_supabase_error_is_readable():
    http = Mock()
    http.request.return_value = Response(409, {"message": "Revision conflict"})
    client = SupabaseClient("https://example.supabase.co", "anon", session_factory=lambda: http)

    with pytest.raises(SupabaseError, match="Revision conflict"):
        client.rest("GET", "app_releases", authenticated=False)
