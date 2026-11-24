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

    def sign_up(self, email: str, password: str, display_name: str, redirect_url: str) -> dict:
        return self.client.auth(
            "POST",
            "signup",
            {
                "email": email.strip(),
                "password": password,
                "data": {"display_name": display_name.strip()},
                "redirect_to": redirect_url,
            },
        )

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
