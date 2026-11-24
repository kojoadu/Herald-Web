from __future__ import annotations

import streamlit as st

from services.feedback import FeedbackService
from services.moderation import ModerationService
from services.supabase import SupabaseError
from ui import configured_client, current_profile, require_auth, show_error


st.set_page_config(page_title="Moderation · Herald", page_icon="🛡️", layout="wide")
st.title("Moderation")
client = require_auth(configured_client())
profile = current_profile(client)
if not profile or profile.get("role") != "moderator":
    st.error("Moderator access is required. Database RLS and RPC checks are authoritative.")
    st.stop()

service = ModerationService(client)
reports_tab, feedback_tab = st.tabs(["Song reports", "Feedback status"])
with reports_tab:
    report_filter = st.selectbox("Report status", ("open", "reviewing", "resolved", "dismissed"), key="report_filter")
    try:
        reports = service.reports(report_filter)
    except SupabaseError as exc:
        show_error(exc)
        reports = []
    if not reports:
        st.info("No reports in this queue.")
    for report in reports:
        with st.expander(f"{report['reason']} · {report['song_id']}"):
            st.write(report.get("details") or "No details.")
            status = st.selectbox(
                "Resolution",
                ("reviewing", "resolved", "dismissed"),
                key=f"report_status_{report['id']}",
            )
            note = st.text_area("Resolution note", max_chars=4000, key=f"report_note_{report['id']}")
            if st.button("Save", key=f"report_save_{report['id']}"):
                try:
                    service.resolve_report(str(report["id"]), status, note)
                    st.success("Report updated.")
                    st.rerun()
                except (ValueError, SupabaseError) as exc:
                    show_error(exc)

with feedback_tab:
    try:
        feedback = FeedbackService(client).list()
    except SupabaseError as exc:
        show_error(exc)
        feedback = []
    for item in feedback:
        columns = st.columns([4, 2, 1])
        columns[0].write(item["title"])
        status = columns[1].selectbox(
            "Status",
            ModerationService.FEEDBACK_STATUSES,
            index=ModerationService.FEEDBACK_STATUSES.index(item["status"]),
            label_visibility="collapsed",
            key=f"feedback_status_{item['id']}",
        )
        if columns[2].button("Save", key=f"feedback_save_{item['id']}"):
            try:
                service.set_feedback_status(str(item["id"]), status)
                st.success("Status updated.")
                st.rerun()
            except (ValueError, SupabaseError) as exc:
                show_error(exc)
