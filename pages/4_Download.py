from __future__ import annotations

import streamlit as st

from services.github_releases import GitHubReleaseService


st.set_page_config(page_title="Download · Herald", page_icon="⬇️", layout="centered")
st.title("Download Herald for Windows")
try:
    secrets = dict(st.secrets)
except Exception:
    secrets = {}
release = GitHubReleaseService.from_environment(secrets=secrets).latest()

st.metric("Latest version", release["version"])
if not release["available"]:
    st.info("No public Herald release has been published yet.")
    st.link_button("Open releases page", release["release_url"])
    st.stop()
if release.get("published_at"):
    st.caption(f"Published {release['published_at']}")
if release["is_fallback"]:
    st.info(
        "GitHub's release API is temporarily unavailable. The stable latest-release "
        "installer link is shown below."
    )
if release.get("release_notes"):
    st.subheader("Release notes")
    st.markdown(release["release_notes"])
download_url = release.get("installer_url")
if download_url:
    st.link_button("Download Windows x64", download_url, type="primary")
if release.get("portable_url"):
    st.link_button("Download portable ZIP", release["portable_url"])
st.link_button("View GitHub Release", release["release_url"])

if release.get("checksums"):
    st.subheader("Verify the download")
    for filename, checksum in release["checksums"].items():
        st.write(f"**{filename}**")
        st.code(checksum, language=None)
    st.caption("SHA-256 checksum. Compare it with the hash of the downloaded file.")
elif release.get("checksums_url"):
    st.link_button("Download SHA-256 checksums", release["checksums_url"])
