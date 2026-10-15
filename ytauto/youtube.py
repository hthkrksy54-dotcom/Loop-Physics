"""Minimal YouTube Data API v3 client: OAuth refresh, resumable upload, thumbnail, captions."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
CAPTION_URL = "https://www.googleapis.com/upload/youtube/v3/captions"
CHUNK = 16 * 1024 * 1024


class YouTubeError(RuntimeError):
    pass


def configured(refresh_secret: str) -> bool:
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", refresh_secret))


def access_token(refresh_secret: str) -> str:
    return access_token_from(os.environ[refresh_secret])


def access_token_from(refresh_token: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["YT_CLIENT_ID"],
            "client_secret": os.environ["YT_CLIENT_SECRET"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise YouTubeError(f"token refresh failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()["access_token"]


def upload_video(token: str, path: Path, snippet: dict, status: dict) -> str:
    size = path.stat().st_size
    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        data=json.dumps({"snippet": snippet, "status": status}),
        timeout=60,
    )
    if init.status_code != 200:
        raise YouTubeError(f"upload init failed ({init.status_code}): {init.text[:500]}")
    session = init.headers["Location"]

    offset, failures = 0, 0
    with path.open("rb") as fh:
        while offset < size:
            fh.seek(offset)
            chunk = fh.read(CHUNK)
            end = offset + len(chunk) - 1
            try:
                r = requests.put(
                    session,
                    headers={"Authorization": f"Bearer {token}", "Content-Range": f"bytes {offset}-{end}/{size}"},
                    data=chunk,
                    timeout=300,
                )
            except requests.RequestException:
                r = None
            if r is not None and r.status_code in (200, 201):
                return r.json()["id"]
            if r is not None and r.status_code == 308:
                rng = r.headers.get("Range")
                offset = int(rng.split("-")[1]) + 1 if rng else 0
                failures = 0
                continue
            failures += 1
            if failures > 6 or (r is not None and 400 <= r.status_code < 500 and r.status_code != 429):
                raise YouTubeError(f"upload failed: {None if r is None else (r.status_code, r.text[:300])}")
            time.sleep(2 ** failures)
            # Ask the server how much it already has.
            q = requests.put(session, headers={"Authorization": f"Bearer {token}", "Content-Range": f"bytes */{size}"}, timeout=60)
            if q.status_code in (200, 201):
                return q.json()["id"]
            rng = q.headers.get("Range")
            offset = int(rng.split("-")[1]) + 1 if rng else 0
    raise YouTubeError("upload ended without a video id")


def set_thumbnail(token: str, video_id: str, path: Path) -> str | None:
    r = requests.post(
        THUMB_URL,
        params={"videoId": video_id, "uploadType": "media"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
        data=path.read_bytes(),
        timeout=60,
    )
    if r.status_code != 200:
        # Custom thumbnails need a phone-verified channel; not fatal.
        return f"thumbnail skipped ({r.status_code}): {r.text[:200]}"
    return None


def add_captions(token: str, video_id: str, srt: Path, language: str, name: str) -> str | None:
    boundary = "ytauto-boundary"
    meta = json.dumps({"snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}})
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
        f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n"
    ).encode() + srt.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    r = requests.post(
        CAPTION_URL,
        params={"uploadType": "multipart", "part": "snippet"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/related; boundary={boundary}"},
        data=body,
        timeout=60,
    )
    if r.status_code != 200:
        return f"captions skipped ({r.status_code}): {r.text[:200]}"
    return None
