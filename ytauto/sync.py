"""Watch the channel for videos the owner uploaded by hand and finish the job around them.

While YouTube uploads via the API are paused (pending Google's audit), the owner uploads each video
manually. This runs hourly and, for every produced video that now appears on the channel:
  * records the YouTube IDs,
  * fixes a Short that was uploaded with the long video's title/description,
  * posts the matching Instagram Reel with a link to the YouTube video.
"""
from __future__ import annotations

import json
import re

import requests

from . import instagram, publish, social, youtube

API = "https://www.googleapis.com/youtube/v3"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _seconds(iso: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def _uploads(token: str, limit: int = 50) -> list[dict]:
    h = {"Authorization": f"Bearer {token}"}
    ch = requests.get(f"{API}/channels", params={"part": "contentDetails", "mine": "true"}, headers=h, timeout=30).json()
    playlist = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = requests.get(
        f"{API}/playlistItems", params={"part": "contentDetails", "playlistId": playlist, "maxResults": limit}, headers=h, timeout=30
    ).json().get("items", [])
    ids = [i["contentDetails"]["videoId"] for i in items]
    if not ids:
        return []
    videos = requests.get(
        f"{API}/videos", params={"part": "snippet,status,contentDetails", "id": ",".join(ids)}, headers=h, timeout=30
    ).json().get("items", [])
    for v in videos:
        v["seconds"] = _seconds(v["contentDetails"]["duration"])
    return videos


def _matches(video: dict, script: dict) -> bool:
    sn = video["snippet"]
    title, desc = _norm(sn.get("title")), _norm(sn.get("description"))
    short_title = _norm(script.get("short", {}).get("title", "").replace("#Shorts", ""))
    return (
        title == _norm(script["title"])
        or (short_title and short_title in title)
        or desc.startswith(_norm(script["description"])[:80])
        or (script.get("short") and desc.startswith(_norm(script["short"]["text"])[:80]))
    )


def _fix_short(token: str, video: dict, script: dict, cfg: dict, long_id: str | None) -> bool:
    """Give a Short uploaded with the long video's metadata its own title and description."""
    want_title, want_desc = publish.short_metadata(script, cfg, long_id)
    sn = video["snippet"]
    if _norm(sn.get("title")) == _norm(want_title) and (not long_id or long_id in sn.get("description", "")):
        return False
    body = {
        "id": video["id"],
        "snippet": {
            "title": want_title,
            "description": want_desc,
            "tags": publish.tags(script),
            "categoryId": sn.get("categoryId", cfg["youtube"].get("category_id", "27")),
            "defaultLanguage": cfg["youtube"]["default_language"],
            "defaultAudioLanguage": cfg["youtube"]["default_language"],
        },
    }
    r = requests.put(
        f"{API}/videos", params={"part": "snippet"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, data=json.dumps(body), timeout=60,
    )
    if not r.ok:
        print(f"  could not update short {video['id']} ({r.status_code}): {r.text[:200]}", flush=True)
        return False
    print(f"  fixed short metadata: https://youtube.com/shorts/{video['id']}", flush=True)
    return True


def run(lang: str, cfg: dict, state: dict, load_script) -> bool:
    """Returns True if state changed."""
    secret = cfg["youtube"]["refresh_token_secret"]
    if not youtube.configured(secret):
        print(f"[{lang}] YouTube not connected – nothing to sync", flush=True)
        return False
    token = youtube.access_token(secret)
    uploads = [v for v in _uploads(token) if v["status"].get("privacyStatus") == "public"]
    changed = False
    for rec in state.get(lang, []):
        script = load_script(rec["id"])
        if script is None:
            continue
        mine = [v for v in uploads if _matches(v, script)]
        longs = [v for v in mine if v["seconds"] > 180]
        shorts = [v for v in mine if v["seconds"] <= 180]
        if longs and rec.get("youtube_id") != longs[-1]["id"]:
            rec["youtube_id"] = longs[-1]["id"]
            changed = True
            print(f"[{lang}] found upload of '{rec['id']}': https://youtu.be/{rec['youtube_id']}", flush=True)
        for s in shorts:
            if rec.get("youtube_short_id") != s["id"]:
                rec["youtube_short_id"] = s["id"]
                changed = True
            if rec.get("youtube_id") and _fix_short(token, s, script, cfg, rec["youtube_id"]):
                changed = True
        # Post the Reel once the long video is live, so the caption can link to it.
        if rec.get("youtube_id") and not rec.get("instagram_id") and instagram.configured(cfg) and script.get("short"):
            short_url = rec.get("short_url") or (
                f"https://github.com/{_repo()}/releases/download/video-{lang}-{rec['id']}/{lang}-{rec['id']}-short.mp4"
            )
            try:
                rec.update(instagram.post_reel(cfg, short_url, instagram.caption(script, cfg, f"https://youtu.be/{rec['youtube_id']}"),
                                               highlight=social.highlight_for(script), label=script["short"]["title"]))
                changed = True
            except Exception as err:
                print(f"  warning: instagram reel for '{rec['id']}' failed: {err}", flush=True)
    return changed


def _repo() -> str:
    import os

    return os.environ.get("GITHUB_REPOSITORY", "hthkrksy54-dotcom/Yt")
