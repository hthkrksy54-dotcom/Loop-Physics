"""Metadata assembly and publishing (YouTube, or a GitHub Release as fallback)."""
from __future__ import annotations

import os
import re
from pathlib import Path

import requests

from . import youtube


def _clean(text: str) -> str:
    return re.sub(r"[<>]", "", text)


def _stamp(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def description(script: dict, cfg: dict, chapters: list[tuple[float, str]]) -> str:
    w = cfg["words"]
    parts = [script["description"].strip()]
    if len(chapters) >= 3:
        parts.append(f"{w['chapters']}:\n" + "\n".join(f"{_stamp(t)} {title}" for t, title in chapters))
    if script.get("sources"):
        parts.append(f"{w['sources']}:\n" + "\n".join(f"• {s}" for s in script["sources"]))
    notes = []
    if script.get("category") == "psychology":
        notes.append(w["not_advice"])
    notes.append(w["disclosure"])
    parts.append("\n".join(notes))
    parts.append(script.get("hashtags") or w["hashtags"])
    text = _clean("\n\n".join(parts))
    return text[:4900]


def tags(script: dict) -> list[str]:
    out, total = [], 0
    for t in script.get("tags", []):
        t = _clean(t).strip()
        if t and total + len(t) + 3 <= 480:
            out.append(t)
            total += len(t) + 3
    return out


def short_metadata(script: dict, cfg: dict, long_id: str | None) -> tuple[str, str]:
    short = script["short"]
    title = _clean(short["title"]).strip()
    if "#shorts" not in title.lower():
        title = f"{title} #Shorts"
    text = short["text"].split("\n\n")[0]
    link = f"\n\n▶ {'Ganzes Video' if script['lang'] == 'de' else 'Full video'}: https://youtu.be/{long_id}" if long_id else ""
    desc = _clean(f"{text}{link}\n\n{cfg['words']['disclosure']}\n\n{script.get('hashtags') or cfg['words']['hashtags']} #Shorts")
    return title[:100], desc[:4900]


def to_youtube(script: dict, cfg: dict, long: dict, short: dict | None) -> dict:
    yt = cfg["youtube"]
    secret = yt["refresh_token_secret"]
    token = youtube.access_token(secret)
    lang = yt["default_language"]
    snippet = {
        "title": _clean(script["title"])[:100],
        "description": description(script, cfg, long["chapters"]),
        "tags": tags(script),
        "categoryId": yt.get("category_id", "27"),
        "defaultLanguage": lang,
        "defaultAudioLanguage": lang,
    }
    status = {
        "privacyStatus": yt.get("privacy", "public"),
        "selfDeclaredMadeForKids": False,
        "embeddable": True,
        "license": "youtube",
        "containsSyntheticMedia": bool(yt.get("contains_synthetic_media", False)),
    }
    result: dict = {"warnings": []}
    video_id = youtube.upload_video(token, long["video"], snippet, status)
    result["youtube_id"] = video_id
    print(f"  uploaded https://youtu.be/{video_id}", flush=True)
    for warn in (
        youtube.set_thumbnail(token, video_id, long["thumbnail"]),
        youtube.add_captions(token, video_id, long["captions"], lang, cfg["channel_name"]),
    ):
        if warn:
            result["warnings"].append(warn)
            print("  warning:", warn, flush=True)

    if short and yt.get("upload_short", True):
        title, desc = short_metadata(script, cfg, video_id)
        short_snippet = dict(snippet, title=title, description=desc)
        try:
            short_id = youtube.upload_video(token, short["video"], short_snippet, status)
            result["short_id"] = short_id
            print(f"  uploaded short https://youtube.com/shorts/{short_id}", flush=True)
        except youtube.YouTubeError as err:
            # The long video is already live; record it rather than failing the run.
            result["warnings"].append(f"short upload failed: {err}")
            print("  warning: short upload failed:", err, flush=True)
    return result


def github_release(tag: str, name: str, body: str, files: list[tuple[str | Path, str, str]]) -> dict:
    """(Re)create a GitHub release with the given files; returns {"release": url, "assets": {name: url}}.

    Release asset URLs are public, which is what Instagram needs to fetch videos and images.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return {}
    api = f"https://api.github.com/repos/{repo}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    existing = requests.get(f"{api}/releases/tags/{tag}", headers=headers, timeout=30)
    if existing.status_code == 200:
        requests.delete(f"{api}/releases/{existing.json()['id']}", headers=headers, timeout=30)
        requests.delete(f"{api}/git/refs/tags/{tag}", headers=headers, timeout=30)
    rel = requests.post(
        f"{api}/releases",
        headers=headers,
        json={"tag_name": tag, "name": name[:120], "body": body[:120000]},
        timeout=30,
    )
    if rel.status_code not in (200, 201):
        print(f"  release failed ({rel.status_code}): {rel.text[:300]}", flush=True)
        return {}
    upload_url = rel.json()["upload_url"].split("{")[0]
    assets = {}
    for path, asset_name, ctype in files:
        with Path(path).open("rb") as fh:
            up = requests.post(
                upload_url,
                params={"name": asset_name},
                headers={**headers, "Content-Type": ctype},
                data=fh,
                timeout=900,
            )
        if up.status_code in (200, 201):
            assets[asset_name] = up.json().get("browser_download_url")
        else:
            print(f"  asset upload failed for {asset_name} ({up.status_code})", flush=True)
    url = rel.json()["html_url"]
    print(f"  release: {url}", flush=True)
    return {"release": url, "assets": assets}


def to_github_release(script: dict, cfg: dict, long: dict, short: dict | None) -> dict:
    """Archive of every video as a GitHub release (files + copy-paste metadata).

    Also the public source URL Instagram fetches Reels from.
    """
    tag = f"video-{script['lang']}-{script['id']}"
    body = [
        f"## {script['title']}",
        "",
        "### Titel / Title",
        "```",
        script["title"],
        "```",
        "### Beschreibung / Description",
        "```",
        description(script, cfg, long["chapters"]),
        "```",
        "### Tags",
        "```",
        ", ".join(tags(script)),
        "```",
    ]
    if short:
        st, sd = short_metadata(script, cfg, None)
        body += ["### Short", "```", st, "", sd, "```"]
    prefix = f"{script['lang']}-{script['id']}"
    files = [(long["video"], f"{prefix}-video.mp4", "video/mp4"), (long["thumbnail"], f"{prefix}-thumbnail.jpg", "image/jpeg"),
             (long["captions"], f"{prefix}-captions.srt", "text/plain")]
    if short:
        files.append((short["video"], f"{prefix}-short.mp4", "video/mp4"))
    rel = github_release(tag, f"[{script['lang'].upper()}] {script['title']}", "\n".join(body), files)
    if not rel:
        return {}
    result = {"release": rel["release"]}
    if rel["assets"].get(f"{prefix}-short.mp4"):
        result["short_url"] = rel["assets"][f"{prefix}-short.mp4"]
    return result


def release_asset(tag: str, name: str, path: str | Path, asset_name: str, ctype: str) -> str | None:
    """Add one file to a long-lived release (created on first use); returns its public URL."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return None
    api = f"https://api.github.com/repos/{repo}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    rel = requests.get(f"{api}/releases/tags/{tag}", headers=headers, timeout=30)
    if rel.status_code == 404:
        rel = requests.post(f"{api}/releases", headers=headers, json={"tag_name": tag, "name": name}, timeout=30)
    if not rel.ok:
        print(f"  release {tag} unavailable ({rel.status_code}): {rel.text[:200]}", flush=True)
        return None
    release = rel.json()
    for asset in release.get("assets", []):
        if asset["name"] == asset_name:
            requests.delete(f"{api}/releases/assets/{asset['id']}", headers=headers, timeout=30)
    with Path(path).open("rb") as fh:
        up = requests.post(
            release["upload_url"].split("{")[0],
            params={"name": asset_name},
            headers={**headers, "Content-Type": ctype},
            data=fh,
            timeout=300,
        )
    if up.status_code not in (200, 201):
        print(f"  asset upload failed for {asset_name} ({up.status_code})", flush=True)
        return None
    return up.json().get("browser_download_url")
