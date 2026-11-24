from __future__ import annotations

import streamlit as st

from services.github_releases import GitHubReleaseService
from ui import configured_client, finish_oauth


st.set_page_config(page_title="Herald", page_icon="🎵", layout="wide")

st.title("Herald cloud song repository")
st.caption("An authenticated community catalog for church presentation teams.")

client = configured_client()
if client:
    finish_oauth(client)
    if client.session:
        st.success(f"Signed in as {client.session.user.get('email') or client.session.user_id}.")

st.write(
    "Browse the shared song pool, keep a current Herald installer, and collaborate "
    "with other churches through ideas, bug reports, and feedback."
)

left, right = st.columns(2)
with left:
    st.subheader("For your presentation team")
    st.write("• Sign in and complete your church profile")
    st.write("• Search, inspect, upload, and download Herald songs")
    st.write("• Your uploader and moderator permissions remain database-enforced")
with right:
    st.subheader("Latest Windows release")
    try:
        secrets = dict(st.secrets)
    except Exception:
        secrets = {}
    release = GitHubReleaseService.from_environment(secrets=secrets).latest()
    st.metric("Version", release["version"])
    if release["available"]:
        if release.get("published_at"):
            st.caption(f"Published {release['published_at']}")
        st.page_link("pages/4_Download.py", label="View release download", icon=":material/download:")
    else:
        st.caption("The first public release has not been published yet.")

st.divider()
st.caption(
    "The song pool is private to authenticated accounts. Upload only songs you are permitted to use. "
    "The portal uses the public anon key and signed-in user JWT only."
)
