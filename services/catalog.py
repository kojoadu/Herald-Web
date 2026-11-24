from __future__ import annotations

from typing import Any
import uuid

from models import SongDraft

from .supabase import SupabaseClient


class CatalogService:
    COLUMNS = "id,owner_id,title,author,ccli_number,content,revision,status,created_at,updated_at"

    def __init__(self, client: SupabaseClient):
        self.client = client

    def search(self, query: str = "", *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        params: dict[str, Any] = {
            "select": self.COLUMNS,
            "status": "eq.published",
            "order": "title.asc",
            "limit": limit,
            "offset": max(0, offset),
        }
        query = query.strip()
        if query:
            terms = " ".join(query.split())
            escaped = self._or_value(terms)
            params["or"] = f"(title.ilike.*{escaped}*,author.ilike.*{escaped}*,ccli_number.ilike.*{escaped}*)"
        return self.client.rest("GET", "cloud_songs", params=params)

    def get(self, song_id: str) -> dict[str, Any] | None:
        rows = self.client.rest(
            "GET",
            "cloud_songs",
            params={"select": self.COLUMNS, "id": f"eq.{song_id}", "limit": 1},
        )
        return rows[0] if rows else None

    def upload(self, draft: SongDraft, expected_revision: int = 0) -> dict[str, Any]:
        uuid.UUID(draft.song_id)
        if expected_revision < 0:
            raise ValueError("Expected revision cannot be negative.")
        return self.client.rpc(
            "upsert_cloud_song",
            {
                "p_song_id": draft.song_id,
                "p_expected_revision": expected_revision,
                "p_title": draft.title,
                "p_author": draft.author,
                "p_ccli_number": draft.ccli_number,
                "p_content": draft.content,
            },
        )

    @staticmethod
    def _or_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace(",", "\\,").replace("(", "\\(").replace(")", "\\)")
