from __future__ import annotations

import streamlit as st

from services.releases import ReleaseService
from services.supabase import SupabaseError
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
    if client:
        try:
            release = ReleaseService(client).latest()
            if release:
                st.metric("Version", release["version"])
                if release.get("published_at"):
                    st.caption(f"Published {release['published_at']}")
                st.page_link("pages/4_Download.py", label="View release download", icon=":material/download:")
            else:
                st.info("No active release has been published yet.")
        except SupabaseError as exc:
            st.error(str(exc))
    else:
        st.info("Configure Supabase to check releases.")

st.divider()
st.caption(
    "The song pool is private to authenticated accounts. Upload only songs you are permitted to use. "
    "The portal uses the public anon key and signed-in user JWT only."
)
