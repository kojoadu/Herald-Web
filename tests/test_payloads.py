from __future__ import annotations

import pytest

from models.payloads import SongDraft, ValidationError


def test_song_payload_preserves_herald_shape():
    value = SongDraft.from_export(
        {
            "id": "8a4eea56-8d78-4e2d-9eaa-8e9c5fd7b5ca",
            "title": "Amazing Grace",
            "sections": [{"type": "Verse", "number": 1, "text": "Amazing grace"}],
            "arrangement": ["V1"],
        }
    )

    assert value.content["sections"][0]["text"] == "Amazing grace"
    assert value.title == "Amazing Grace"


def test_song_payload_rejects_empty_title():
    with pytest.raises(ValidationError, match="Title"):
        SongDraft.from_export(
            {
                "id": "8a4eea56-8d78-4e2d-9eaa-8e9c5fd7b5ca",
                "title": " ",
                "sections": [],
                "arrangement": [],
            }
        )
