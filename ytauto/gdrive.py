"""Copy of every finished video in the owner's Google Drive: Kanal-Videos/<channel>/<date – title>/.

Uses the same OAuth client as YouTube with a refresh token for the scope drive.file (the app only sees the
folders and files it created itself) from the GitHub secret GDRIVE_REFRESH_TOKEN. Video folders older than
KEEP_DAYS are deleted so the free 15 GB never fill up. Drive must never block a run: save() only warns.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import youtube

SECRET = "GDRIVE_REFRESH_TOKEN"
ROOT_FOLDER = "Kanal-Videos"
KEEP_DAYS = 14
API = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"
CHUNK = 16 * 1024 * 1024


class DriveError(RuntimeError):
    pass


def configured() -> bool:
    return youtube.configured(SECRET)


def folder_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _children(token: str, parent: str, extra: str = "") -> list[dict]:
    files, page = [], None
    while True:
        r = requests.get(API, headers=_headers(token), timeout=30, params={
            "q": f"'{parent}' in parents and trashed = false{extra}", "pageSize": 1000, "pageToken": page,
            "fields": "nextPageToken, files(id, name, mimeType, createdTime)"})
        if not r.ok:
            raise DriveError(f"list failed ({r.status_code}): {r.text[:300]}")
        files += r.json().get("files", [])
        page = r.json().get("nextPageToken")
        if not page:
            return files


def _folder(token: str, name: str, parent: str = "root") -> str:
    """The id of the folder `name` in `parent`, created on first use."""
    quoted = name.replace("\\", "\\\\").replace("'", "\\'")
    found = _children(token, parent, f" and mimeType = '{FOLDER}' and name = '{quoted}'")
    if found:
        return found[0]["id"]
    r = requests.post(API, headers=_headers(token), params={"fields": "id"}, timeout=30,
                      json={"name": name, "mimeType": FOLDER, "parents": [parent]})
    if not r.ok:
        raise DriveError(f"creating folder {name} failed ({r.status_code}): {r.text[:300]}")
    return r.json()["id"]


def channel_folder(token: str, channel: str) -> str:
    return _folder(token, channel, _folder(token, ROOT_FOLDER))


def _upload(token: str, data: bytes, name: str, parent: str, ctype: str) -> str:
    init = requests.post(UPLOAD, params={"uploadType": "resumable", "fields": "id"}, timeout=60,
                         headers={**_headers(token), "Content-Type": "application/json; charset=UTF-8",
                                  "X-Upload-Content-Type": ctype, "X-Upload-Content-Length": str(len(data))},
                         data=json.dumps({"name": name, "parents": [parent]}))
    if not init.ok:
        raise DriveError(f"upload of {name} failed to start ({init.status_code}): {init.text[:300]}")
    session, size, offset, failures = init.headers["Location"], len(data), 0, 0
    while True:
        chunk = data[offset:offset + CHUNK]
        rng = f"bytes {offset}-{offset + len(chunk) - 1}/{size}" if chunk else f"bytes */{size}"
        try:
            r = requests.put(session, headers={**_headers(token), "Content-Range": rng}, data=chunk, timeout=300)
        except requests.RequestException:
            r = None
        if r is not None and r.status_code in (200, 201):
            return r.json()["id"]
        if r is not None and r.status_code == 308:
            got = r.headers.get("Range")
            offset, failures = (int(got.split("-")[1]) + 1 if got else 0), 0
            continue
        failures += 1
        if failures > 5 or (r is not None and 400 <= r.status_code < 500 and r.status_code != 429):
            raise DriveError(f"upload of {name} failed: {None if r is None else (r.status_code, r.text[:300])}")
        time.sleep(2 ** failures)
        q = requests.put(session, headers={**_headers(token), "Content-Range": f"bytes */{size}"}, timeout=60)
        if q.status_code in (200, 201):
            return q.json()["id"]
        got = q.headers.get("Range")
        offset = int(got.split("-")[1]) + 1 if got else 0


def cleanup(token: str, channel_id: str, keep_days: int = KEEP_DAYS) -> int:
    """Delete video folders older than keep_days (permanently, so the space is free right away)."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=keep_days)
    removed = 0
    for f in _children(token, channel_id):
        if dt.datetime.fromisoformat(f["createdTime"].replace("Z", "+00:00")) < cutoff:
            r = requests.delete(f"{API}/{f['id']}", headers=_headers(token), timeout=60)
            removed += r.status_code == 204
    return removed


def save(channel: str, title: str, files: list[tuple], texts: str) -> str | None:
    """Upload a video's files (same list as for the GitHub release; Instagram story teasers are left out) and its
    copy-paste texts into a new folder; returns the folder URL, or None when Drive is not set up or fails."""
    if not configured():
        return None
    try:
        token = youtube.access_token(SECRET)
        channel_id = channel_folder(token, channel)
        stamp = dt.datetime.now(ZoneInfo("Europe/Berlin"))  # the owner's time
        name = f"{stamp:%Y-%m-%d %H.%M} – {title}"[:120].replace("/", "-")
        folder = _folder(token, name, channel_id)
        for path, asset, ctype in files:
            if not asset.endswith("-story.mp4"):
                _upload(token, Path(path).read_bytes(), asset, folder, ctype)
        _upload(token, texts.encode(), "Texte zum Kopieren.txt", folder, "text/plain")
        removed = cleanup(token, channel_id)
        print(f"  drive: {folder_url(folder)}" + (f" (removed {removed} folders older than {KEEP_DAYS} days)"
                                                   if removed else ""), flush=True)
        return folder_url(folder)
    except Exception as err:  # noqa: BLE001 – Drive must never block a run
        print(f"  warning: google drive failed: {err}", flush=True)
        return None
