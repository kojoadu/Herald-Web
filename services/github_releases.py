from __future__ import annotations

import os
from typing import Any, Mapping

import requests


DEFAULT_REPOSITORY = "kojoadu/Herald-Releases"


class GitHubReleaseError(RuntimeError):
    pass


class GitHubReleaseService:
    def __init__(
        self,
        repository: str = DEFAULT_REPOSITORY,
        *,
        download_url: str | None = None,
        releases_url: str | None = None,
        session_factory=requests.Session,
        timeout: float = 15,
    ):
        parts = repository.strip().split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError("HERALD_GITHUB_REPOSITORY must use owner/repository format.")
        self.repository = repository
        self.timeout = timeout
        self.http = session_factory()
        self.releases_url = releases_url or f"https://github.com/{repository}/releases/latest"
        self._download_override = download_url
        self.download_url = download_url or (
            f"https://github.com/{repository}/releases/latest/download/Herald-Setup.exe"
        )

    @classmethod
    def from_environment(
        cls,
        *,
        secrets: Mapping[str, Any] | None = None,
    ) -> "GitHubReleaseService":
        source = secrets or {}

        def value(name: str, default: str | None = None) -> str | None:
            return os.environ.get(name) or (
                str(source[name]).strip() if source.get(name) else default
            )

        return cls(
            value("HERALD_GITHUB_REPOSITORY", DEFAULT_REPOSITORY) or DEFAULT_REPOSITORY,
            download_url=value("HERALD_DOWNLOAD_URL"),
            releases_url=value("HERALD_RELEASES_URL"),
        )

    def latest(self) -> dict[str, Any]:
        url = f"https://api.github.com/repos/{self.repository}/releases/latest"
        try:
            response = self.http.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "Herald-Web",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise GitHubReleaseError("GitHub returned an invalid release response.")
            return self._parse_release(payload)
        except requests.HTTPError as exc:
            if getattr(exc.response, "status_code", None) == 404 and not self._download_override:
                return self.unavailable()
            return self.fallback()
        except (requests.RequestException, ValueError, GitHubReleaseError):
            return self.fallback()

    def fallback(self) -> dict[str, Any]:
        return {
            "tag": "Latest",
            "version": "Latest",
            "name": "Herald for Windows",
            "release_notes": "",
            "published_at": None,
            "release_url": self.releases_url,
            "installer_url": self.download_url,
            "portable_url": (
                f"https://github.com/{self.repository}/releases/latest/download/"
                "Herald-win-x64.zip"
            ),
            "checksums_url": (
                f"https://github.com/{self.repository}/releases/latest/download/"
                "SHA256SUMS.txt"
            ),
            "checksums": {},
            "is_fallback": True,
            "available": True,
        }

    def unavailable(self) -> dict[str, Any]:
        return {
            "tag": "",
            "version": "Not published",
            "name": "Herald for Windows",
            "release_notes": "",
            "published_at": None,
            "release_url": self.releases_url,
            "installer_url": None,
            "portable_url": None,
            "checksums_url": None,
            "checksums": {},
            "is_fallback": False,
            "available": False,
        }

    def _parse_release(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            assets = []
        by_name = {
            str(asset.get("name", "")).casefold(): str(asset.get("browser_download_url", ""))
            for asset in assets
            if isinstance(asset, dict) and asset.get("browser_download_url")
        }
        installer_url = by_name.get("herald-setup.exe") or self.download_url
        portable_url = by_name.get("herald-win-x64.zip")
        checksums_url = by_name.get("sha256sums.txt")
        if not installer_url:
            raise GitHubReleaseError("The latest release has no Windows installer asset.")

        tag = str(payload.get("tag_name") or "")
        return {
            "tag": tag,
            "version": tag.removeprefix("v") or str(payload.get("name") or "Latest"),
            "name": str(payload.get("name") or "Herald"),
            "release_notes": str(payload.get("body") or ""),
            "published_at": payload.get("published_at"),
            "release_url": str(
                payload.get("html_url") or f"https://github.com/{self.repository}/releases/latest"
            ),
            "installer_url": installer_url,
            "portable_url": portable_url,
            "checksums_url": checksums_url,
            "checksums": self._read_checksums(checksums_url),
            "is_fallback": False,
            "available": True,
        }

    def _read_checksums(self, url: str | None) -> dict[str, str]:
        if not url:
            return {}
        try:
            response = self.http.get(
                url,
                headers={"User-Agent": "Herald-Web"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = response.text
        except requests.RequestException:
            return {}

        checksums = {}
        for line in text.splitlines():
            value, separator, filename = line.partition("  ")
            if separator and len(value) == 64:
                checksums[filename.strip()] = value.lower()
        return checksums
