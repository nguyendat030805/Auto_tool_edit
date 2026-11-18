"""Check GitHub Releases for a newer published application version."""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APP_VERSION = "1.0.0"
GITHUB_REPOSITORY = "nguyendat030805/Auto_tool_edit"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest"
_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")


def _version_tuple(value: str) -> tuple[int, int, int]:
    """Parse a stable MAJOR.MINOR[.PATCH] version into comparable numbers."""
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Định dạng phiên bản không hợp lệ: {value}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def check_for_update() -> dict[str, object]:
    """Return latest release information without blocking on long network waits."""
    result: dict[str, object] = {
        "current_version": APP_VERSION,
        "latest_version": None,
        "update_available": False,
        "release_url": RELEASES_PAGE_URL,
        "download_url": None,
        "error": None,
    }
    request = Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Auto-tool-edit-updater",
        },
    )

    try:
        with urlopen(request, timeout=4) as response:
            release = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            result["error"] = "Repository chưa có bản phát hành công khai nào."
        else:
            result["error"] = f"GitHub trả về lỗi HTTP {exc.code}."
        return result
    except (URLError, TimeoutError, OSError) as exc:
        result["error"] = f"Không kết nối được GitHub: {exc}"
        return result
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        result["error"] = f"Phản hồi phiên bản từ GitHub không hợp lệ: {exc}"
        return result

    try:
        version = str(release["tag_name"])
        current = _version_tuple(APP_VERSION)
        latest = _version_tuple(version)
    except (KeyError, TypeError, ValueError) as exc:
        result["error"] = f"Thông tin phiên bản trên GitHub không hợp lệ: {exc}"
        return result

    release_url = release.get("html_url")
    if isinstance(release_url, str) and release_url.startswith("https://github.com/"):
        result["release_url"] = release_url

    assets = release.get("assets", [])
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if asset.get("name", "").lower() in {"app.exe", "app.zip"}:
                download_url = asset.get("browser_download_url")
                if isinstance(download_url, str) and download_url.startswith("https://"):
                    result["download_url"] = download_url
                    break

    result["latest_version"] = version.removeprefix("v")
    result["update_available"] = latest > current
    return result
