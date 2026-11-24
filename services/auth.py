from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

from .supabase import AuthSession, SupabaseClient


class AuthService:
    def __init__(self, client: SupabaseClient):
        self.client = client

    def sign_in(self, email: str, password: str) -> AuthSession:
        payload = self.client.auth(
            "POST",
            "token?grant_type=password",
            {"email": email.strip(), "password": password},
        )
        session = AuthSession.from_payload(payload)
        self.client.session = session
        return session

    def sign_up(
        self,
        email: str,
        password: str,
        display_name: str,
        redirect_url: str = "",
    ) -> AuthSession | None:
        email = email.strip()
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Enter a display name.")
        if not email or "@" not in email:
            raise ValueError("Enter a valid email address.")
        if not password:
            raise ValueError("Enter a password.")

        redirect_url = redirect_url.strip()
        payload = self.client.auth(
            "POST",
            "signup",
            {
                "email": email,
                "password": password,
                "data": {"display_name": display_name},
            },
            params={"redirect_to": redirect_url} if redirect_url else None,
        )
        session_payload = payload.get("session") if isinstance(payload, dict) else None
        if isinstance(session_payload, dict):
            payload = session_payload
        if isinstance(payload, dict) and payload.get("access_token") and payload.get("refresh_token"):
            self.client.session = AuthSession.from_payload(payload)
            return self.client.session
        return None

    def oauth_url(self, provider: str, redirect_url: str) -> tuple[str, str]:
        if provider not in {"google", "azure"}:
            raise ValueError("Unsupported OAuth provider.")
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        query = urlencode(
            {
                "provider": provider,
                "redirect_to": redirect_url,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return (
            f"{self.client.project_url}/auth/v1/authorize?{query}",
            verifier,
        )

    def exchange_oauth_code(self, code: str, verifier: str) -> AuthSession:
        payload = self.client.auth(
            "POST",
            "token?grant_type=pkce",
            {"auth_code": code, "code_verifier": verifier},
        )
        session = AuthSession.from_payload(payload)
        self.client.session = session
        return session

    def current_user(self) -> dict:
        if self.client.session is None:
            return {}
        self.client._ensure_session()
        return self.client.session.user
