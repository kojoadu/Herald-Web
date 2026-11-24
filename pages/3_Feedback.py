from __future__ import annotations

import streamlit as st

from models import FeedbackDraft
from models.payloads import ValidationError
from services.feedback import FeedbackService
from services.supabase import SupabaseError
from ui import configured_client, require_auth, show_error


st.set_page_config(page_title="Feedback · Herald", page_icon="💬", layout="wide")
st.title("Community feedback")
client = require_auth(configured_client())
service = FeedbackService(client)

create_tab, browse_tab = st.tabs(["Submit", "Browse and discuss"])
with create_tab:
    with st.form("new_feedback"):
        title = st.text_input("Title", max_chars=200)
        category = st.selectbox("Category", ("idea", "bug", "question", "praise"))
        body = st.text_area("Description", max_chars=8000)
        submitted = st.form_submit_button("Submit feedback", type="primary")
    if submitted:
        try:
            item = service.create(FeedbackDraft(title, body, category))
            st.success(f"Created feedback: {item['title']}")
        except (ValidationError, SupabaseError) as exc:
            show_error(exc)

with browse_tab:
    status = st.selectbox(
        "Status",
        ("all", "open", "planned", "in_progress", "completed", "closed"),
        index=0,
    )
    try:
        items = service.list(status=None if status == "all" else status)
        my_votes = service.my_votes([str(item["id"]) for item in items])
    except SupabaseError as exc:
        show_error(exc)
        st.stop()
    if not items:
        st.info("No feedback items match this filter.")
        st.stop()
    selected = st.selectbox(
        "Discussion",
        items,
        format_func=lambda item: f"{item['title']}  ·  {item['vote_count']} votes  ·  {item['status']}",
    )
    st.subheader(selected["title"])
    st.caption(f"{selected['category']} · {selected['status']} · {selected['vote_count']} votes")
    st.write(selected["body"])
    voted = str(selected["id"]) in my_votes
    if st.button("Remove my upvote" if voted else "Upvote", key=f"vote_{selected['id']}"):
        try:
            result = service.toggle_vote(str(selected["id"]))
            st.success(f"{result['vote_count']} votes · {'voted' if result['voted'] else 'vote removed'}")
            st.rerun()
        except SupabaseError as exc:
            show_error(exc)
    st.divider()
    st.subheader("Comments")
    try:
        comments = service.comments(str(selected["id"]))
    except SupabaseError as exc:
        show_error(exc)
        comments = []
    for comment in comments:
        st.markdown(comment["body"])
        st.caption(f"{comment['created_at']} · {comment['author_id']}")
        if comment["author_id"] == client.session.user_id:
            if st.button("Delete", key=f"delete_{comment['id']}"):
                try:
                    service.delete_own_comment(str(comment["id"]))
                    st.rerun()
                except SupabaseError as exc:
                    show_error(exc)
    with st.form(f"comment_{selected['id']}"):
        body = st.text_area("Add a comment", max_chars=4000)
        submitted = st.form_submit_button("Post comment")
    if submitted:
        try:
            service.add_comment(str(selected["id"]), body)
            st.rerun()
        except (ValueError, SupabaseError) as exc:
            show_error(exc)
