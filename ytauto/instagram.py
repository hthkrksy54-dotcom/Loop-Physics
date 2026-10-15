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

import requests
from cryptography.fernet import Fernet, InvalidToken

GRAPH = "https://graph.instagram.com"
ROOT = Path(__file__).resolve().parent.parent
REFRESH_AFTER_DAYS = 7


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


def save_token(cfg: dict, data: dict) -> None:
    _token_path(cfg).parent.mkdir(parents=True, exist_ok=True)
    _token_path(cfg).write_bytes(_fernet().encrypt(json.dumps(data).encode()) + b"\n")


def load_token(cfg: dict) -> dict:
    try:
        return json.loads(_fernet().decrypt(_token_path(cfg).read_bytes().strip()))
    except InvalidToken as err:
        raise InstagramError("IG_TOKEN_KEY does not match the stored token") from err


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


def caption(script: dict, cfg: dict) -> str:
    short = script["short"]
    title = short["title"].replace("#Shorts", "").strip()
    tags = []
    for t in (cfg["instagram"].get("hashtags", "") + " " + (script.get("hashtags") or "")).split():
        t = t if t.startswith("#") else f"#{t}"
        if t.lower() not in {x.lower() for x in tags} and t.lower() != "#shorts":
            tags.append(t)
    parts = [
        title,
        short["text"].strip(),
        f"Full video essay on YouTube: {cfg['channel_name']} (link in bio)",
        cfg["words"]["disclosure"],
        " ".join(tags[:15]),
    ]
    return "\n\n".join(parts)[:2150]


def post_reel(cfg: dict, video_url: str, text: str) -> dict:
    token = fresh_token(cfg)
    me = requests.get(f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token}, timeout=30)
    if not me.ok:
        raise InstagramError(f"token check failed ({me.status_code}): {me.text[:200]}")
    uid = me.json()["user_id"]

    create = requests.post(
        f"{GRAPH}/{uid}/media",
        data={"media_type": "REELS", "video_url": video_url, "caption": text, "share_to_feed": "true",
              "thumb_offset": "1500", "access_token": token},
        timeout=60,
    )
    if not create.ok:
        raise InstagramError(f"container failed ({create.status_code}): {create.text[:300]}")
    container = create.json()["id"]

    for _ in range(60):  # up to ~10 minutes for Instagram to fetch and process the video
        st = requests.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": token}, timeout=30).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise InstagramError(f"processing failed: {st}")
        time.sleep(10)
    else:
        raise InstagramError("processing timed out")

    pub = requests.post(f"{GRAPH}/{uid}/media_publish", data={"creation_id": container, "access_token": token}, timeout=60)
    if not pub.ok:
        raise InstagramError(f"publish failed ({pub.status_code}): {pub.text[:300]}")
    media_id = pub.json()["id"]
    link = requests.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": token}, timeout=30).json()
    print(f"  instagram reel: {link.get('permalink', media_id)}", flush=True)
    return {"instagram_id": media_id, "instagram_url": link.get("permalink")}
