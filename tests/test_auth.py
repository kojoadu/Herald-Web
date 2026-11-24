from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.auth import AuthService
from services.supabase import AuthSession, SupabaseClient


def client_with_auth_payload(payload: dict) -> tuple[SupabaseClient, Mock]:
    client = SupabaseClient("https://example.supabase.co", "anon", session_factory=Mock)
    client.auth = Mock(return_value=payload)
    return client, client.auth


def test_sign_up_saves_session_when_email_confirmation_is_disabled():
    client, auth = client_with_auth_payload(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "user": {"id": "user"},
        }
    )

    session = AuthService(client).sign_up(
        " person@example.com ",
        "password",
        " Person ",
        " https://app.example.com/Account ",
    )

    assert isinstance(session, AuthSession)
    assert client.session is session
    auth.assert_called_once_with(
        "POST",
        "signup",
        {
            "email": "person@example.com",
            "password": "password",
            "data": {"display_name": "Person"},
        },
        params={"redirect_to": "https://app.example.com/Account"},
    )


def test_sign_up_handles_nested_session_response():
    client, _ = client_with_auth_payload(
        {
            "session": {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "user": {"id": "user"},
            }
        }
    )

    session = AuthService(client).sign_up("person@example.com", "password", "Person")

    assert isinstance(session, AuthSession)
    assert client.session is session


def test_sign_up_waits_for_email_confirmation_without_session():
    client, auth = client_with_auth_payload(
        {"user": {"id": "user", "email": "person@example.com"}}
    )

    session = AuthService(client).sign_up("person@example.com", "password", "Person")

    assert session is None
    assert client.session is None
    assert auth.call_args.kwargs["params"] is None


@pytest.mark.parametrize(
    ("email", "display_name", "message"),
    [
        ("invalid", "Person", "valid email"),
        ("person@example.com", " ", "display name"),
    ],
)
def test_sign_up_validates_required_account_fields(email, display_name, message):
    client, auth = client_with_auth_payload({})

    with pytest.raises(ValueError, match=message):
        AuthService(client).sign_up(email, "password", display_name)

    auth.assert_not_called()
