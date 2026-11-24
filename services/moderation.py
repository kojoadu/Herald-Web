from __future__ import annotations

from typing import Any

from .supabase import SupabaseClient


class ModerationService:
    FEEDBACK_STATUSES = ("open", "planned", "in_progress", "completed", "closed")
    REPORT_STATUSES = ("open", "reviewing", "resolved", "dismissed")

    def __init__(self, client: SupabaseClient):
        self.client = client

    def reports(self, status: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "select": "id,song_id,reporter_id,reason,details,status,resolution_note,created_at,updated_at",
            "order": "created_at.asc",
            "limit": 200,
        }
        if status:
            params["status"] = f"eq.{status}"
        return self.client.rest("GET", "song_reports", params=params)

    def resolve_report(self, report_id: str, status: str, note: str) -> dict[str, Any]:
        if status not in self.REPORT_STATUSES[1:]:
            raise ValueError("Invalid report status.")
        if len(note) > 4000:
            raise ValueError("Resolution note is too long.")
        return self.client.rpc(
            "set_song_report_resolution",
            {
                "p_report_id": report_id,
                "p_status": status,
                "p_resolution_note": note.strip() or None,
            },
        )

    def set_feedback_status(self, feedback_id: str, status: str) -> dict[str, Any]:
        if status not in self.FEEDBACK_STATUSES:
            raise ValueError("Invalid feedback status.")
        return self.client.rpc(
            "set_feedback_status",
            {"p_feedback_id": feedback_id, "p_status": status},
        )

    def report_song(self, song_id: str, reason: str, details: str) -> dict[str, Any]:
        if reason not in {"copyright", "incorrect", "inappropriate", "duplicate", "other"}:
            raise ValueError("Invalid report reason.")
        if len(details) > 4000:
            raise ValueError("Report details are too long.")
        rows = self.client.rest(
            "POST",
            "song_reports",
            body={
                "song_id": song_id,
                "reporter_id": self.client.session.user_id,
                "reason": reason,
                "details": details.strip(),
                "status": "open",
            },
            params={"select": "*"},
        )
        return rows[0] if isinstance(rows, list) and rows else rows
