from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import uuid


MAX_SONG_BYTES = 1_048_576
SECTION_TYPES = {"Verse", "PreChorus", "Chorus", "Bridge", "Tag", "Intro", "Ending", "Other"}


class ValidationError(ValueError):
    """A user-supplied payload is not a valid Herald payload."""


def _text(value: object, name: str, *, minimum: int = 0, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be text.")
    value = value.strip()
    if not minimum <= len(value) <= maximum:
        raise ValidationError(f"{name} must contain {minimum} to {maximum} characters.")
    return value


def _optional_text(value: object, name: str, maximum: int) -> str | None:
    if value is None:
        return None
    value = _text(value, name, maximum=maximum)
    return value or None


@dataclass(frozen=True)
class SongDraft:
    song_id: str
    title: str
    author: str | None
    ccli_number: str | None
    content: dict

    @classmethod
    def from_export(cls, value: object) -> "SongDraft":
        if not isinstance(value, dict):
            raise ValidationError("The song export must be a JSON object.")
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_SONG_BYTES:
            raise ValidationError("The song export is too large (maximum 1 MiB).")

        title = _text(value.get("title"), "Title", minimum=1, maximum=240)
        raw_sections = value.get("sections")
        if not isinstance(raw_sections, list) or not raw_sections:
            raise ValidationError("The song must contain at least one section.")
        if len(raw_sections) > 500:
            raise ValidationError("The song has too many sections.")

        sections = []
        total_text = 0
        for index, section in enumerate(raw_sections, start=1):
            if not isinstance(section, dict):
                raise ValidationError(f"Section {index} must be an object.")
            section_type = section.get("type", "Verse")
            if section_type not in SECTION_TYPES:
                raise ValidationError(f"Section {index} has an unknown type.")
            lyrics = section.get("text")
            if not isinstance(lyrics, str) or len(lyrics) > 100_000:
                raise ValidationError(f"Section {index} lyrics are invalid or too long.")
            total_text += len(lyrics)
            number = section.get("number")
            if number is not None and (isinstance(number, bool) or not isinstance(number, int) or number < 1):
                raise ValidationError(f"Section {index} number must be a positive integer.")
            custom_label = section.get("customLabel")
            if custom_label is not None and not isinstance(custom_label, str):
                raise ValidationError(f"Section {index} custom label must be text.")
            sections.append(
                {
                    "type": section_type,
                    "number": number,
                    "customLabel": custom_label,
                    "text": lyrics,
                }
            )
        if total_text == 0:
            raise ValidationError("The song must contain lyrics.")

        raw_id = value.get("id")
        try:
            song_id = str(uuid.UUID(str(raw_id))) if raw_id else str(uuid.uuid4())
        except ValueError as exc:
            raise ValidationError("The song ID is not a valid UUID.") from exc

        arrangement = value.get("arrangement", [])
        if not isinstance(arrangement, list) or any(not isinstance(item, str) for item in arrangement):
            raise ValidationError("Arrangement must be a list of section keys.")

        content = deepcopy(value)
        content["id"] = song_id
        content["title"] = title
        content["sections"] = sections
        content["arrangement"] = arrangement
        return cls(
            song_id=song_id,
            title=title,
            author=_optional_text(value.get("author"), "Author", 240),
            ccli_number=_optional_text(value.get("ccliNumber"), "CCLI number", 40),
            content=content,
        )


@dataclass(frozen=True)
class FeedbackDraft:
    title: str
    body: str
    category: str

    def __post_init__(self) -> None:
        title = _text(self.title, "Title", minimum=3, maximum=200)
        body = _text(self.body, "Description", minimum=3, maximum=8000)
        if self.category not in {"idea", "bug", "question", "praise"}:
            raise ValidationError("Category is invalid.")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "body", body)


def parse_song_export(data: bytes | str) -> SongDraft:
    try:
        text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Choose a valid UTF-8 Herald song JSON export.") from exc
    return SongDraft.from_export(value)


def song_as_download(content: dict) -> bytes:
    draft = SongDraft.from_export(content)
    return (json.dumps(draft.content, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
