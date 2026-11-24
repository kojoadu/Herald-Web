from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
import time
from typing import Any, Callable, Mapping
from urllib.parse import urljoin

import requests


class SupabaseError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class AuthenticationRequired(SupabaseError):
    pass


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    expires_at: int
    user: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AuthSession":
        token = payload.get("access_token")
        refresh = payload.get("refresh_token")
        user = payload.get("user")
        if not isinstance(token, str) or not token or not isinstance(refresh, str) or not isinstance(user, dict):
            raise SupabaseError("Supabase returned an incomplete authentication session.")
        expires_at = payload.get("expires_at")
        if not isinstance(expires_at, int):
            expires_at = int(time.time()) + int(payload.get("expires_in", 3600))
        return cls(token, refresh, expires_at, dict(user))

    @property
    def user_id(self) -> str:
        value = self.user.get("id")
        if not isinstance(value, str) or not value:
            raise SupabaseError("The authentication session has no user ID.")
        return value

    @property
    def expires_soon(self) -> bool:
        return self.expires_at <= int(time.time()) + 60

    def as_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "user": self.user,
        }


class SupabaseClient:
    """Small bearer-token client for Supabase GoTrue and PostgREST."""

    def __init__(
        self,
        project_url: str,
        anon_key: str,
        *,
        session: AuthSession | None = None,
        session_factory: Callable[[], requests.Session] = requests.Session,
        timeout: float = 30,
    ):
        project_url = project_url.rstrip("/")
        if not project_url.startswith("https://") and not project_url.startswith("http://localhost"):
            raise ValueError("SUPABASE_URL must be an HTTPS URL.")
        if not anon_key:
            raise ValueError("SUPABASE_ANON_KEY is required; never use a service-role key.")
        self.project_url = project_url
        self.anon_key = anon_key
        self.session = session
        self.http = session_factory()
        self.timeout = timeout

    @classmethod
    def from_environment(cls, *, secrets: Mapping[str, Any] | None = None) -> "SupabaseClient":
        source = secrets or {}
        project_url = os.environ.get("SUPABASE_URL") or str(source.get("SUPABASE_URL", ""))
        anon_key = os.environ.get("SUPABASE_ANON_KEY") or str(source.get("SUPABASE_ANON_KEY", ""))
        return cls(project_url, anon_key)

    def _headers(self, *, authenticated: bool) -> dict[str, str]:
        headers = {"apikey": self.anon_key, "Accept": "application/json"}
        if authenticated:
            self._ensure_session()
            assert self.session is not None
            headers["Authorization"] = f"Bearer {self.session.access_token}"
        return headers

    def _ensure_session(self) -> None:
        if self.session is None:
            raise AuthenticationRequired("Sign in to access the Herald cloud.")
        if self.session.expires_soon:
            self.refresh()

    def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        json_body: Any = None,
        params: Mapping[str, Any] | None = None,
        retried: bool = False,
    ) -> Any:
        url = urljoin(f"{self.project_url}/", path.lstrip("/"))
        response = self.http.request(
            method,
            url,
            headers=self._headers(authenticated=authenticated),
            json=json_body,
            params=params,
            timeout=self.timeout,
        )
        if authenticated and response.status_code == 401 and not retried and self.session is not None:
            self.refresh(force=True)
            return self._request(
                method,
                path,
                authenticated=True,
                json_body=json_body,
                params=params,
                retried=True,
            )
        return self._decode(response)

    @staticmethod
    def _decode(response: requests.Response) -> Any:
        if response.ok:
            if not response.content:
                return None
            try:
                return response.json()
            except ValueError as exc:
                raise SupabaseError("Supabase returned invalid JSON.") from exc
        detail = ""
        code = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("message") or payload.get("msg") or payload.get("error_description") or "")
                code = payload.get("code") if isinstance(payload.get("code"), str) else None
        except ValueError:
            detail = response.text[:500]
        raise SupabaseError(
            detail or f"Supabase request failed ({response.status_code}).",
            status_code=response.status_code,
            code=code,
        )

    def auth(self, method: str, endpoint: str, body: Any = None, **kwargs: Any) -> Any:
        return self._request(
            method,
            f"auth/v1/{endpoint}",
            authenticated=False,
            json_body=body,
            **kwargs,
        )

    def rest(
        self,
        method: str,
        relation: str,
        *,
        body: Any = None,
        params: Mapping[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        return self._request(
            method,
            f"rest/v1/{relation}",
            authenticated=authenticated,
            json_body=body,
            params=params,
        )

    def rpc(self, name: str, arguments: Mapping[str, Any], *, authenticated: bool = True) -> Any:
        return self.rest("POST", f"rpc/{name}", body=dict(arguments), authenticated=authenticated)

    def refresh(self, *, force: bool = False) -> AuthSession:
        if self.session is None or not self.session.refresh_token:
            raise AuthenticationRequired("Sign in before refreshing a session.")
        if not force and not self.session.expires_soon:
            return self.session
        payload = self.auth(
            "POST",
            "token?grant_type=refresh_token",
            {"refresh_token": self.session.refresh_token},
        )
        self.session = AuthSession.from_payload(payload)
        return self.session

    def sign_out(self) -> None:
        if self.session is None:
            return
        self._request("POST", "auth/v1/logout", authenticated=True)
        self.session = None


def jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT claims for display/expiry only; Supabase still verifies every request."""
    try:
        segment = token.split(".")[1]
        padded = segment + "=" * (-len(segment) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        return value if isinstance(value, dict) else {}
    except (IndexError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
