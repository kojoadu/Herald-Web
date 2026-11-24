from __future__ import annotations

import json

import streamlit as st

from models import parse_song_export, song_as_download
from models.payloads import ValidationError
from services.catalog import CatalogService
from services.moderation import ModerationService
from services.supabase import SupabaseError
from ui import configured_client, require_auth, show_error, song_lyrics


st.set_page_config(page_title="Song catalog · Herald", page_icon="🎶", layout="wide")
st.title("Song catalog")
client = require_auth(configured_client())
catalog = CatalogService(client)

search_tab, upload_tab = st.tabs(["Search and download", "Upload"])
with search_tab:
    query = st.text_input("Search title, author, or CCLI number")
    try:
        songs = catalog.search(query)
    except SupabaseError as exc:
        show_error(exc)
        st.stop()
    if not songs:
        st.info("No published songs match your search.")
        st.stop()
    selected = st.selectbox(
        "Song",
        songs,
        format_func=lambda song: f"{song['title']} — {song.get('author') or 'Unknown author'}",
    )
    st.subheader(selected["title"])
    metadata = st.columns(3)
    metadata[0].caption(f"Author: {selected.get('author') or '—'}")
    metadata[1].caption(f"CCLI: {selected.get('ccli_number') or '—'}")
    metadata[2].caption(f"Revision: {selected['revision']}")
    st.text(song_lyrics(selected["content"]))
    try:
        download = song_as_download(selected["content"])
        st.download_button(
            "Download Herald song JSON",
            data=download,
            file_name=f"{selected['title'].strip().replace(' ', '_')}.json",
            mime="application/json",
        )
    except ValidationError as exc:
        show_error(exc)
    with st.expander("Report this song"):
        reason = st.selectbox("Reason", ("copyright", "incorrect", "inappropriate", "duplicate", "other"))
        details = st.text_area("Details", max_chars=4000)
        if st.button("Submit report"):
            try:
                ModerationService(client).report_song(str(selected["id"]), reason, details)
                st.success("Report submitted to moderators.")
            except (ValueError, SupabaseError) as exc:
                show_error(exc)

with upload_tab:
    st.info("Upload only material you own or have permission to use.")
    uploaded = st.file_uploader("Herald song JSON", type=["json"])
    rights = st.checkbox("I have permission to upload this song.")
    existing_song_id = st.text_input("Existing cloud song ID (for an edit; otherwise leave blank)")
    if uploaded and rights and st.button("Upload song", type="primary"):
        try:
            draft = parse_song_export(uploaded.getvalue())
            expected_revision = 0
            if existing_song_id.strip():
                current = catalog.get(existing_song_id.strip())
                if not current:
                    raise ValueError("The existing song could not be found.")
                expected_revision = int(current["revision"])
                draft_content = draft.content
                draft_content["id"] = current["id"]
                draft = type(draft)(current["id"], draft.title, draft.author, draft.ccli_number, draft_content)
            result = catalog.upload(draft, expected_revision)
            st.success(f"Uploaded {result['title']} at revision {result['revision']}.")
        except (ValidationError, ValueError, SupabaseError) as exc:
            show_error(exc)
    with st.expander("Expected JSON shape"):
        st.code(
            json.dumps(
                {
                    "id": "optional UUID",
                    "title": "Amazing Grace",
                    "author": "John Newton",
                    "ccliNumber": "22025",
                    "sections": [
                        {"type": "Verse", "number": 1, "customLabel": None, "text": "Amazing grace…"}
                    ],
                    "arrangement": ["V1"],
                },
                indent=2,
            ),
            language="json",
        )
