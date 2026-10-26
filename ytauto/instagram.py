"""Instagram Reels publishing (Instagram API with Instagram Login, own account in development mode).

The long-lived access token lives encrypted in the repo (state/…token) so the workflow can refresh it
every week and commit the new one; the decryption key is the GitHub secret IG_TOKEN_KEY.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from cryptography.fernet import Fernet, InvalidToken

GRAPH = "https://graph.instagram.com"
ROOT = Path(__file__).resolve().parent.parent
REFRESH_AFTER_DAYS = 7
AUDIENCE_TZ = ZoneInfo("America/New_York")  # the English channels post their Reels in the US morning


class InstagramError(RuntimeError):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _token_path(cfg: dict) -> Path:
    return ROOT / cfg["instagram"]["token_file"]


def configured(cfg: dict) -> bool:
    ig = cfg.get("instagram") or {}
    return bool(ig.get("enabled") and os.environ.get("IG_TOKEN_KEY") and _token_path(cfg).exists())


def _fernet() -> Fernet:
    return Fernet(os.environ["IG_TOKEN_KEY"].strip().encode())


def reel_due(cfg: dict, now: dt.datetime | None = None) -> dt.datetime | None:
    """When the Reel of a video made now should go out: None = right away (US daytime, or no `reel_hour` set),
    else the next `reel_hour`:00 New York time – videos made at 4:00 in Germany wait for the US morning."""
    hour = (cfg.get("instagram") or {}).get("reel_hour")
    ny = (now or _now()).astimezone(AUDIENCE_TZ)
    if hour is None or hour <= ny.hour < 20:
        return None
    due = ny.replace(hour=hour, minute=0, second=0, microsecond=0)
    if ny.hour >= 20:
        due += dt.timedelta(days=1)
    return due.astimezone(dt.timezone.utc)


def reel_waiting(rec: dict, now: dt.datetime | None = None) -> bool:
    """The record's Reel is held back until its time."""
    return bool(rec.get("reel_due")) and dt.datetime.fromisoformat(rec["reel_due"]) > (now or _now())


def save_token(cfg: dict, data: dict) -> None:
    _token_path(cfg).parent.mkdir(parents=True, exist_ok=True)
    _token_path(cfg).write_bytes(_fernet().encrypt(json.dumps(data).encode()) + b"\n")


def load_token(cfg: dict) -> dict:
    try:
        return json.loads(_fernet().decrypt(_token_path(cfg).read_bytes().strip()))
    except InvalidToken as err:
        raise InstagramError("IG_TOKEN_KEY does not match the stored token") from err


def connect(cfg: dict, token: str) -> dict:
    """Store a new long-lived token (from the Meta app: Instagram API setup → Generate token) for this channel."""
    token = token.strip()
    r = requests.get(f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token}, timeout=30)
    if not r.ok:
        raise InstagramError(f"token rejected ({r.status_code}): {r.text[:200]}")
    me = r.json()
    want = (cfg.get("instagram") or {}).get("account")
    if want and me.get("username") != want:  # a token of another channel's account must never be stored here
        raise InstagramError(f"token belongs to @{me.get('username')}, not @{want} – nothing stored")
    data = {"token": token, "user_id": str(me.get("user_id") or me.get("id")), "username": me.get("username", ""),
            "refreshed_at": "2000-01-01T00:00:00+00:00",  # refresh on first use: starts the 60 days now
            "expires_at": (_now() + dt.timedelta(days=60)).isoformat(timespec="seconds")}
    save_token(cfg, data)
    return {k: v for k, v in data.items() if k != "token"}


def fresh_token(cfg: dict) -> str:
    """Return a valid token, refreshing it (60-day validity) once a week."""
    data = load_token(cfg)
    refreshed = dt.datetime.fromisoformat(data["refreshed_at"])
    if _now() - refreshed > dt.timedelta(days=REFRESH_AFTER_DAYS):
        r = requests.get(
            f"{GRAPH}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": data["token"]},
            timeout=30,
        )
        if r.ok and r.json().get("access_token"):
            data.update(
                token=r.json()["access_token"],
                refreshed_at=_now().isoformat(timespec="seconds"),
                expires_at=(_now() + dt.timedelta(seconds=int(r.json().get("expires_in", 5184000)))).isoformat(timespec="seconds"),
            )
            save_token(cfg, data)
            print("  instagram: access token refreshed", flush=True)
        else:
            print(f"  instagram: token refresh failed ({r.status_code}): {r.text[:200]}", flush=True)
    return data["token"]


def hashtags(script: dict, cfg: dict, limit: int = 5) -> str:
    """A few precise hashtags beat long lists; Instagram mostly searches the caption text now."""
    tags: list[str] = []
    for t in ((script.get("hashtags") or "") + " " + cfg["instagram"].get("hashtags", "")).split():
        t = t if t.startswith("#") else f"#{t}"
        if t.lower() not in {x.lower() for x in tags} and t.lower() != "#shorts":
            tags.append(t)
    return " ".join(tags[:limit])


def _youtube_line(cfg: dict, youtube_url: str | None) -> str:
    channel = cfg["instagram"].get("youtube_channel", cfg["channel_name"])
    if youtube_url:
        return f"▶ Full video essay on YouTube: {youtube_url}\nYouTube: {channel}"
    return f"▶ Full video essay on YouTube (link in bio)\nYouTube: {channel}"


def caption(script: dict, cfg: dict, youtube_url: str | None = None) -> str:
    short = script["short"]
    title = short["title"].replace("#Shorts", "").strip()
    parts = [title, short["text"].strip()]
    if script.get("question"):
        parts.append(f"💬 {script['question']}")
    parts += [_youtube_line(cfg, youtube_url), cfg["words"]["disclosure"], hashtags(script, cfg)]
    return "\n\n".join(parts)[:2150]


def carousel_caption(script: dict, cfg: dict, youtube_url: str | None = None) -> str:
    data = script["carousel"]
    intro = script["description"].split(". ")[0].strip().rstrip(".") + "."
    parts = [data["cover"], intro, "Save this for a quiet moment, and share it with someone who needs it."]
    if script.get("question"):
        parts.append(f"💬 {script['question']}")
    parts += [_youtube_line(cfg, youtube_url), hashtags(script, cfg)]
    return "\n\n".join(parts)[:2150]


def _user(token: str) -> str:
    me = requests.get(f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token}, timeout=30)
    if not me.ok:
        raise InstagramError(f"token check failed ({me.status_code}): {me.text[:200]}")
    return me.json()["user_id"]


def _container(uid: str, token: str, fields: dict, tries: int = 3) -> str:
    for attempt in range(tries):
        create = requests.post(f"{GRAPH}/{uid}/media", data={**fields, "access_token": token}, timeout=60)
        if create.ok:
            return create.json()["id"]
        # 2207052 = Instagram could not fetch the media; a release asset uploaded seconds ago may not be served yet
        if '"error_subcode":2207052' not in create.text or attempt == tries - 1:
            raise InstagramError(f"container failed ({create.status_code}): {create.text[:300]}")
        print(f"  media fetch failed, retrying in 30 s ({attempt + 1}/{tries - 1})", flush=True)
        time.sleep(30)


def _wait(container: str, token: str, tries: int = 60) -> None:
    for _ in range(tries):  # Instagram fetches and processes the media asynchronously
        st = requests.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": token}, timeout=30).json()
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise InstagramError(f"processing failed: {st}")
        time.sleep(10)
    raise InstagramError("processing timed out")


def _publish(uid: str, token: str, container: str) -> tuple[str, str | None]:
    pub = requests.post(f"{GRAPH}/{uid}/media_publish", data={"creation_id": container, "access_token": token}, timeout=60)
    if not pub.ok:
        raise InstagramError(f"publish failed ({pub.status_code}): {pub.text[:300]}")
    media_id = pub.json()["id"]
    link = requests.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": token}, timeout=30).json()
    return media_id, link.get("permalink")


def _log_story(cfg: dict, entry: dict) -> None:
    """Every story we post, with the highlight it belongs in (highlights have no API; the owner files them)."""
    path = ROOT / cfg["instagram"].get("story_log", "state/instagram_stories.json")
    log = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    log.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def story_log(cfg: dict) -> list[dict]:
    path = ROOT / cfg["instagram"].get("story_log", "state/instagram_stories.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def live_stories(cfg: dict) -> list[dict]:
    """Stories currently visible on the account (last 24 hours)."""
    token = fresh_token(cfg)
    r = requests.get(f"{GRAPH}/{_user(token)}/stories", params={"fields": "id,timestamp", "access_token": token}, timeout=30)
    if not r.ok:
        raise InstagramError(f"stories lookup failed ({r.status_code}): {r.text[:200]}")
    return r.json().get("data", [])


def post_reel(cfg: dict, video_url: str, text: str, story: bool = True, highlight: str | None = None, label: str = "",
              cover_url: str | None = None, thumb_offset_ms: int = 1500, story_url: str | None = None) -> dict:
    """Publish a Reel (and the same clip, or `story_url` – stories take at most 60 s – as a Story)."""
    token = fresh_token(cfg)
    uid = _user(token)
    # already live? (a run that posted it but lost its state to a push race) – adopt it instead of posting twice
    r = requests.get(f"{GRAPH}/{uid}/media", params={"fields": "id,caption,permalink,timestamp", "limit": 12,
                                                     "access_token": token}, timeout=30)
    for m in (r.json().get("data", []) if r.ok else []):
        if " ".join((m.get("caption") or "").split()) == " ".join(text.split()) and \
                _now() - dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) < dt.timedelta(days=3):
            print(f"  instagram reel already live: {m.get('permalink')} – not posted again", flush=True)
            return {"instagram_id": m["id"], "instagram_url": m.get("permalink")}
    fields = {"media_type": "REELS", "video_url": video_url, "caption": text, "share_to_feed": "true"}
    try:
        if not cover_url:
            raise InstagramError("no cover image")
        container = _container(uid, token, {**fields, "cover_url": cover_url})
        _wait(container, token)
    except InstagramError as err:  # never lose the Reel over its cover: fall back to a frame of the video
        if cover_url:
            print(f"  cover image not used ({err}) – using a video frame", flush=True)
        container = _container(uid, token, {**fields, "thumb_offset": str(int(thumb_offset_ms))})
        _wait(container, token)
    media_id, link = _publish(uid, token, container)
    print(f"  instagram reel: {link or media_id}", flush=True)
    result = {"instagram_id": media_id, "instagram_url": link}
    if story:  # the same clip as a Story brings followers back to the new Reel
        try:
            result["instagram_story_id"] = post_story(cfg, video_url=story_url or video_url, kind="reel",
                                                      highlight=highlight, label=label)
        except InstagramError as err:
            print(f"  warning: story failed: {err}", flush=True)
    return result


def post_story(cfg: dict, video_url: str | None = None, image_url: str | None = None,
               kind: str = "story", highlight: str | None = None, label: str = "") -> str:
    token = fresh_token(cfg)
    uid = _user(token)
    fields = {"media_type": "STORIES"}
    fields.update({"video_url": video_url} if video_url else {"image_url": image_url})
    container = _container(uid, token, fields)
    _wait(container, token)
    media_id, _ = _publish(uid, token, container)
    print(f"  instagram story: {media_id} ({kind}{' → ' + highlight if highlight else ''})", flush=True)
    _log_story(cfg, {"id": media_id, "date": _now().isoformat(timespec="seconds"), "kind": kind,
                     "highlight": highlight, "label": label})
    return media_id


def post_carousel(cfg: dict, image_urls: list[str], text: str) -> dict:
    token = fresh_token(cfg)
    uid = _user(token)
    children = []
    for url in image_urls[:10]:
        child = _container(uid, token, {"image_url": url, "is_carousel_item": "true"})
        _wait(child, token, tries=30)
        children.append(child)
    container = _container(uid, token, {"media_type": "CAROUSEL", "children": ",".join(children), "caption": text})
    _wait(container, token, tries=30)
    media_id, link = _publish(uid, token, container)
    print(f"  instagram carousel: {link or media_id}", flush=True)
    return {"carousel_id": media_id, "carousel_url": link}


def publishing_quota(cfg: dict) -> tuple[int, int]:
    """(posts used in the last 24 h, allowed) – Instagram caps API publishing per account."""
    token = fresh_token(cfg)
    r = requests.get(f"{GRAPH}/{_user(token)}/content_publishing_limit", params={"fields": "quota_usage,config",
                                                                               "access_token": token}, timeout=30)
    if not r.ok:
        raise InstagramError(f"quota lookup failed ({r.status_code}): {r.text[:200]}")
    data = (r.json().get("data") or [{}])[0]
    return int(data.get("quota_usage", 0)), int((data.get("config") or {}).get("quota_total", 50))
