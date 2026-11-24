from __future__ import annotations

import streamlit as st

from services.releases import ReleaseService
from services.supabase import SupabaseError
from ui import configured_client, show_error


st.set_page_config(page_title="Download · Herald", page_icon="⬇️", layout="centered")
st.title("Download Herald for Windows")
client = configured_client()
if client is None:
    st.stop()
try:
    release = ReleaseService(client).latest()
except SupabaseError as exc:
    show_error(exc)
    st.stop()
if not release:
    st.info("No active Windows release is currently published.")
    st.stop()

st.metric("Latest version", release["version"])
if release.get("published_at"):
    st.caption(f"Published {release['published_at']}")
if release.get("release_notes"):
    st.subheader("Release notes")
    st.markdown(release["release_notes"])
download_url = release.get("download_url")
if download_url:
    st.link_button("Download Windows x64", download_url, type="primary")
else:
    st.warning("This release references a storage object; a signed-download flow has not been configured.")
st.subheader("Verify the download")
st.code(release["sha256"], language=None)
st.caption("SHA-256 checksum. Compare it with the hash of the downloaded installer.")
