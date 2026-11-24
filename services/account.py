from __future__ import annotations

import re
import unicodedata
from typing import Any

from .supabase import SupabaseClient


def normalize_church_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^0-9a-z]+", " ", value.casefold()).strip()


class AccountService:
    def __init__(self, client: SupabaseClient):
        self.client = client

    def profile(self) -> dict[str, Any] | None:
        rows = self.client.rest(
            "GET",
            "profiles",
            params={"select": "*", "id": f"eq.{self.client.session.user_id}", "limit": 1},
        )
        return rows[0] if rows else None

    def organizations(self, query: str = "") -> list[dict[str, Any]]:
        if not query.strip():
            return self.client.rest(
                "GET",
                "church_organizations",
                params={
                    "select": "id,name,status,created_by",
                    "status": "eq.active",
                    "order": "name.asc",
                    "limit": 100,
                },
            )
        return self.client.rpc(
            "search_church_organizations",
            {"p_query": query.strip(), "p_limit": 50},
        )

    def create_or_find_organization(self, name: str) -> dict[str, Any]:
        return self.client.rpc("get_or_create_church_organization", {"p_name": name.strip()})

    def hierarchy_levels(self, organization_id: str) -> list[dict[str, Any]]:
        return self.client.rest(
            "GET",
            "church_hierarchy_levels",
            params={
                "select": "id,organization_id,label,sort_order",
                "organization_id": f"eq.{organization_id}",
                "order": "sort_order.asc",
                "limit": 100,
            },
        )

    def add_hierarchy_level(self, organization_id: str, label: str, sort_order: int) -> dict[str, Any]:
        return self.client.rpc(
            "add_church_hierarchy_level",
            {
                "p_organization_id": organization_id,
                "p_label": label.strip(),
                "p_sort_order": sort_order,
            },
        )

    def nodes(
        self,
        organization_id: str,
        level_id: str,
        parent_id: str | None,
    ) -> list[dict[str, Any]]:
        return self.client.rest(
            "GET",
            "church_nodes",
            params={
                "select": "id,name,organization_id,level_id,parent_id,status",
                "organization_id": f"eq.{organization_id}",
                "level_id": f"eq.{level_id}",
                "parent_id": "is.null" if parent_id is None else f"eq.{parent_id}",
                "status": "eq.active",
                "order": "name.asc",
                "limit": 500,
            },
        )

    def create_or_find_node(
        self,
        organization_id: str,
        level_id: str,
        parent_id: str | None,
        name: str,
    ) -> dict[str, Any]:
        return self.client.rpc(
            "get_or_create_church_node",
            {
                "p_organization_id": organization_id,
                "p_level_id": level_id,
                "p_parent_id": parent_id,
                "p_name": name.strip(),
                "p_external_code": None,
            },
        )

    def complete_profile(self, church_node_id: str, display_name: str) -> dict[str, Any]:
        return self.client.rpc(
            "complete_church_profile",
            {
                "p_church_node_id": church_node_id,
                "p_display_name": display_name.strip(),
            },
        )

    def church_path(self, node_id: str) -> list[dict[str, Any]]:
        path = []
        current = node_id
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            rows = self.client.rest(
                "GET",
                "church_nodes",
                params={"select": "id,name,parent_id,level_id,organization_id", "id": f"eq.{current}", "limit": 1},
            )
            if not rows:
                break
            path.append(rows[0])
            current = rows[0].get("parent_id")
        return list(reversed(path))

