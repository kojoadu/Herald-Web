from __future__ import annotations

from typing import Any

from models import FeedbackDraft

from .supabase import SupabaseClient


class FeedbackService:
    def __init__(self, client: SupabaseClient):
        self.client = client

    def list(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "select": "id,author_id,title,body,category,status,vote_count,created_at,updated_at",
            "order": "vote_count.desc,created_at.desc",
            "limit": max(1, min(limit, 200)),
            "offset": max(0, offset),
        }
        if status:
            params["status"] = f"eq.{status}"
        return self.client.rest("GET", "feedback_items", params=params)

    def get(self, feedback_id: str) -> dict[str, Any] | None:
        rows = self.client.rest(
            "GET",
            "feedback_items",
            params={"select": "*", "id": f"eq.{feedback_id}", "limit": 1},
        )
        return rows[0] if rows else None

    def create(self, draft: FeedbackDraft) -> dict[str, Any]:
        rows = self.client.rest(
            "POST",
            "feedback_items",
            body={
                "author_id": self.client.session.user_id,
                "title": draft.title,
                "body": draft.body,
                "category": draft.category,
                "status": "open",
                "vote_count": 0,
            },
            params={"select": "*"},
        )
        return rows[0] if isinstance(rows, list) and rows else rows

    def toggle_vote(self, feedback_id: str) -> dict[str, Any]:
        rows = self.client.rpc("toggle_feedback_vote", {"p_feedback_id": feedback_id})
        if not rows:
            raise ValueError("Supabase did not return the vote state.")
        return rows[0] if isinstance(rows, list) else rows

    def my_votes(self, feedback_ids: list[str]) -> set[str]:
        if not feedback_ids:
            return set()
        values = ",".join(feedback_ids)
        rows = self.client.rest(
            "GET",
            "feedback_votes",
            params={
                "select": "feedback_id",
                "user_id": f"eq.{self.client.session.user_id}",
                "feedback_id": f"in.({values})",
            },
        )
        return {str(row["feedback_id"]) for row in rows}

    def comments(self, feedback_id: str) -> list[dict[str, Any]]:
        return self.client.rest(
            "GET",
            "feedback_comments",
            params={
                "select": "id,feedback_id,author_id,body,is_deleted,created_at,updated_at",
                "feedback_id": f"eq.{feedback_id}",
                "order": "created_at.asc",
                "limit": 500,
            },
        )

    def add_comment(self, feedback_id: str, body: str) -> dict[str, Any]:
        body = body.strip()
        if not 1 <= len(body) <= 4000:
            raise ValueError("Comment must contain 1 to 4000 characters.")
        rows = self.client.rest(
            "POST",
            "feedback_comments",
            body={
                "feedback_id": feedback_id,
                "author_id": self.client.session.user_id,
                "body": body,
                "is_deleted": False,
            },
            params={"select": "*"},
        )
        return rows[0] if isinstance(rows, list) and rows else rows

    def delete_own_comment(self, comment_id: str) -> None:
        self.client.rest(
            "PATCH",
            "feedback_comments",
            body={"is_deleted": True},
            params={"id": f"eq.{comment_id}", "author_id": f"eq.{self.client.session.user_id}"},
        )
