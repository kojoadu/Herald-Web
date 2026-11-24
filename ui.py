from __future__ import annotations

import streamlit as st

from services.supabase import AuthSession, SupabaseClient, SupabaseError
from services.account import AccountService
from services.auth import AuthService


SESSION_KEY = "herald_auth_session"


def configured_client() -> SupabaseClient | None:
    secrets = {}
    try:
        secrets = dict(st.secrets)
    except Exception:
        pass
    try:
        client = SupabaseClient.from_environment(secrets=secrets)
    except ValueError as exc:
        st.warning(str(exc))
        st.info("Set SUPABASE_URL and SUPABASE_ANON_KEY in the server environment or Streamlit secrets.")
        return None
    saved = st.session_state.get(SESSION_KEY)
    if saved and isinstance(saved, dict):
        try:
            client.session = AuthSession.from_payload(saved)
        except SupabaseError:
            st.session_state.pop(SESSION_KEY, None)
    return client


def save_session(client: SupabaseClient) -> None:
    if client.session is None:
        st.session_state.pop(SESSION_KEY, None)
    else:
        st.session_state[SESSION_KEY] = client.session.as_dict()


def finish_oauth(client: SupabaseClient) -> None:
    code = st.query_params.get("code")
    error = st.query_params.get("error_description") or st.query_params.get("error")
    if error:
        st.error(str(error))
        st.query_params.clear()
        return
    verifier = st.session_state.get("oauth_verifier")
    if code and verifier:
        try:
            AuthService(client).exchange_oauth_code(str(code), str(verifier))
            save_session(client)
            st.session_state.pop("oauth_verifier", None)
            st.query_params.clear()
            st.rerun()
        except SupabaseError as exc:
            st.error(str(exc))
            st.query_params.clear()


def require_auth(client: SupabaseClient | None) -> SupabaseClient:
    if client is None:
        st.stop()
    finish_oauth(client)
    if client.session is None:
        st.warning("Sign in on the Account page to continue.")
        st.page_link("pages/1_Account.py", label="Go to Account", icon=":material/person:")
        st.stop()
    try:
        client.refresh()
        save_session(client)
    except SupabaseError as exc:
        st.session_state.pop(SESSION_KEY, None)
        client.session = None
        st.error(f"Your session expired. Please sign in again. {exc}")
        st.stop()
    return client


def current_profile(client: SupabaseClient) -> dict | None:
    try:
        return AccountService(client).profile()
    except SupabaseError as exc:
        st.error(str(exc))
        st.stop()


def show_error(exc: Exception) -> None:
    st.error(str(exc))


def song_lyrics(content: dict) -> str:
    lines = []
    for section in content.get("sections", []):
        if not isinstance(section, dict):
            continue
        label = str(section.get("customLabel") or section.get("type") or "Section")
        number = section.get("number")
        if number is not None and label.casefold() != "other":
            label = f"{label} {number}"
        lines.append(f"[{label}]")
        lines.append(str(section.get("text") or ""))
        lines.append("")
    return "\n".join(lines).rstrip()
