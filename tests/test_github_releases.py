from __future__ import annotations

import requests

from services.github_releases import GitHubReleaseService


class Response:
    def __init__(self, payload=None, text="", error: Exception | None = None):
        self.payload = payload
        self.text = text
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


def test_latest_release_selects_stable_asset_names_and_checksums():
    checksums = (
        f"{'a' * 64}  Herald-Setup.exe\n"
        f"{'b' * 64}  Herald-win-x64.zip\n"
    )
    session = Session(
        [
            Response(
                payload={
                    "tag_name": "v0.2.0",
                    "name": "Herald v0.2.0",
                    "body": "Release notes",
                    "published_at": "2026-11-24T12:00:00Z",
                    "html_url": "https://github.test/release",
                    "assets": [
                        {
                            "name": "Herald-Setup.exe",
                            "browser_download_url": "https://github.test/Herald-Setup.exe",
                        },
                        {
                            "name": "Herald-win-x64.zip",
                            "browser_download_url": "https://github.test/Herald-win-x64.zip",
                        },
                        {
                            "name": "SHA256SUMS.txt",
                            "browser_download_url": "https://github.test/SHA256SUMS.txt",
                        },
                    ],
                }
            ),
            Response(text=checksums),
        ]
    )

    release = GitHubReleaseService(session_factory=lambda: session).latest()

    assert release["version"] == "0.2.0"
    assert release["installer_url"].endswith("Herald-Setup.exe")
    assert release["portable_url"].endswith("Herald-win-x64.zip")
    assert release["checksums"]["Herald-Setup.exe"] == "a" * 64
    assert release["is_fallback"] is False


def test_latest_release_falls_back_to_stable_download_url_on_api_error():
    error = requests.HTTPError("rate limited")
    session = Session([Response(error=error)])

    release = GitHubReleaseService(
        session_factory=lambda: session,
        download_url="https://downloads.example.test/Herald-Setup.exe",
    ).latest()

    assert release["is_fallback"] is True
    assert release["installer_url"] == "https://downloads.example.test/Herald-Setup.exe"
    assert release["portable_url"] is None
    assert release["checksums_url"] is None


def test_fallback_uses_official_latest_installer_url_by_default():
    service = GitHubReleaseService()

    release = service.fallback()

    assert release["installer_url"] == (
        "https://github.com/kojoadu/Herald-Web/releases/download/"
        "Presentation/Herald-win-Setup.exe"
    )
    assert release["release_url"] == (
        "https://github.com/kojoadu/Herald-Web/releases/tag/Presentation"
    )


def test_missing_release_is_not_shown_as_downloadable():
    error = requests.HTTPError("not found")
    error.response = type("Response", (), {"status_code": 404})()
    session = Session([Response(error=error)])

    release = GitHubReleaseService(session_factory=lambda: session).latest()

    assert release["available"] is True
    assert release["is_fallback"] is True
    assert release["installer_url"].endswith("Presentation/Herald-win-Setup.exe")
