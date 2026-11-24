from __future__ import annotations

from typing import Any

from .supabase import SupabaseClient


class ReleaseService:
    def __init__(self, client: SupabaseClient):
        self.client = client

    def latest(self, platform: str = "windows-x64") -> dict[str, Any] | None:
        rows = self.client.rest(
            "GET",
            "app_releases",
            authenticated=False,
            params={
                "select": "id,version,platform,download_url,storage_object_path,sha256,release_notes,published_at",
                "platform": f"eq.{platform}",
                "is_active": "eq.true",
                "order": "published_at.desc",
                "limit": 1,
            },
        )
        return rows[0] if rows else None
