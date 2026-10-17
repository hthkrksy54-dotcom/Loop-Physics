"""TikTok: every new video goes to the owner's TikTok inbox as a draft (Content Posting API, "upload" mode).

TikTok only lets audited apps post publicly, and its rules want the creator to confirm each post, so the pipeline
does everything up to that tap: it uploads the finished video, TikTok sends the owner a notification, and the
owner posts the draft in the app (caption ready to copy in state/tiktok.md). About 15 seconds per video.

Credentials (client key/secret of the owner's TikTok developer app) and the access/refresh tokens live together,
encrypted with IG_TOKEN_KEY, in the token file named in the channel config (`tiktok.token_file`). The access token
lasts 24 h and is refreshed on every run; the refresh token lasts a year and is renewed with it.

One-time setup (locally, with IG_TOKEN_KEY set):
  python -m ytauto tiktok url --key CLIENT_KEY            -> open the link, allow, copy the address you land on
  python -m ytauto tiktok connect --key CLIENT_KEY --secret CLIENT_SECRET --redirect "<address shown on the callback page>"
  python -m ytauto tiktok check                           -> shows the connected account
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import urllib.parse
from pathlib import Path

import requests
from cryptography.fernet import Fernet, InvalidToken

API = "https://open.tiktokapis.com/v2"
AUTH = "https://www.tiktok.com/v2/auth/authorize/"
REDIRECT = "https://hthkrksy54-dotcom.github.io/Yt/tiktok-callback.html"
SCOPES = "user.info.basic,video.upload"  # drafts only; video.publish would need direct posting
ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "state" / "tiktok.md"
SINGLE_CHUNK_MAX = 64 * 1024 * 1024   # up to 64 MB a video goes up in one piece
CHUNK = 10 * 1024 * 1024              # bigger files: 10 MB chunks, the last one takes the rest
MAX_WAITING = 5                       # TikTok holds at most 5 unposted drafts per account a day


class TikTokError(RuntimeError):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _path(cfg: dict) -> Path:
    return ROOT / cfg["tiktok"]["token_file"]


def configured(cfg: dict) -> bool:
    tt = cfg.get("tiktok") or {}
    return bool(tt.get("enabled") and os.environ.get("IG_TOKEN_KEY") and _path(cfg).exists())


def _fernet() -> Fernet:
    return Fernet(os.environ["IG_TOKEN_KEY"].strip().encode())


def _load(cfg: dict) -> dict:
    try:
        return json.loads(_fernet().decrypt(_path(cfg).read_bytes().strip()))
    except InvalidToken as err:
        raise TikTokError("IG_TOKEN_KEY does not match the stored TikTok token") from err


def _save(cfg: dict, data: dict) -> None:
    _path(cfg).parent.mkdir(parents=True, exist_ok=True)
    _path(cfg).write_bytes(_fernet().encrypt(json.dumps(data).encode()) + b"\n")


def _store(cfg: dict, data: dict, tok: dict) -> dict:
    now = _now()
    data.update(access_token=tok["access_token"], refresh_token=tok.get("refresh_token", data.get("refresh_token")),
                open_id=tok.get("open_id", data.get("open_id")), scope=tok.get("scope", data.get("scope")),
                expires_at=(now + dt.timedelta(seconds=int(tok.get("expires_in", 86400)))).isoformat(timespec="seconds"),
                refresh_expires_at=(now + dt.timedelta(seconds=int(tok.get("refresh_expires_in", 31536000))))
                .isoformat(timespec="seconds"))
    _save(cfg, data)
    return data


def _oauth(data: dict, **form) -> dict:
    r = requests.post(f"{API}/oauth/token/", timeout=30, headers={"Content-Type": "application/x-www-form-urlencoded"},
                      data={"client_key": data["client_key"], "client_secret": data["client_secret"], **form})
    tok = r.json() if r.content else {}
    if not r.ok or "access_token" not in tok:
        raise TikTokError(f"token request failed ({r.status_code}): {tok.get('error_description') or r.text[:300]}")
    return tok


def auth_url(client_key: str, state: str = "ytauto") -> str:
    return AUTH + "?" + urllib.parse.urlencode({"client_key": client_key, "scope": SCOPES, "response_type": "code",
                                                "redirect_uri": REDIRECT, "state": state})


def connect(cfg: dict, client_key: str, client_secret: str, redirect: str, channel: str | None = None,
            taken: set[str] = frozenset()) -> dict:
    """Exchange the code from the address the owner landed on for tokens and store everything encrypted.
    `channel` must match the link's state, and an account already connected to another channel (`taken`
    open_ids) is refused, so a browser still logged in to the wrong account can't mix the channels up."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(redirect.strip()).query)
    if "error" in query:
        raise TikTokError(f"TikTok refused: {query.get('error_description', query['error'])}")
    state = (query.get("state") or [None])[0]
    if channel and state not in (None, "ytauto", channel):
        raise TikTokError(f"this address belongs to the link for '{state}', not '{channel}' – nothing stored")
    code = (query.get("code") or [redirect.strip()])[0]
    data = {"client_key": client_key.strip(), "client_secret": client_secret.strip()}
    tok = _oauth(data, code=code, grant_type="authorization_code", redirect_uri=REDIRECT)
    if tok.get("open_id") in taken:
        raise TikTokError("this TikTok account is already connected to another channel – log in with the "
                          "channel's own account (private window) and try again; nothing stored")
    return _store(cfg, data, tok)


def open_id(cfg: dict) -> str | None:
    """The connected account's id (no network), or None."""
    try:
        return _load(cfg).get("open_id") if _path(cfg).exists() else None
    except TikTokError:
        return None


def fresh_token(cfg: dict) -> str:
    """A valid access token (refreshed when it has less than an hour left)."""
    data = _load(cfg)
    if dt.datetime.fromisoformat(data["expires_at"]) - _now() > dt.timedelta(hours=1):
        return data["access_token"]
    if dt.datetime.fromisoformat(data["refresh_expires_at"]) < _now():
        raise TikTokError("refresh token expired – connect TikTok again (python -m ytauto tiktok url)")
    data = _store(cfg, data, _oauth(data, grant_type="refresh_token", refresh_token=data["refresh_token"]))
    print("  tiktok: access token refreshed", flush=True)
    return data["access_token"]


def _call(token: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    r = requests.post(f"{API}/{path}", params=params, timeout=60, json=body or {},
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"})
    res = r.json() if r.content else {}
    err = res.get("error") or {}
    if not r.ok or err.get("code") not in (None, "ok"):
        raise TikTokError(f"{path}: {err.get('code', r.status_code)} – {err.get('message') or r.text[:300]}")
    return res.get("data") or {}


def account(cfg: dict) -> dict:
    token = fresh_token(cfg)
    r = requests.get(f"{API}/user/info/", params={"fields": "open_id,display_name,avatar_url"}, timeout=30,
                     headers={"Authorization": f"Bearer {token}"})
    res = r.json() if r.content else {}
    if not r.ok or (res.get("error") or {}).get("code") not in (None, "ok"):
        raise TikTokError(f"user info failed ({r.status_code}): {r.text[:300]}")
    return res["data"]["user"]


def send_draft(cfg: dict, video: Path, wait: int = 180) -> dict:
    """Upload the video into the owner's TikTok inbox; returns {"publish_id", "status"}."""
    token = fresh_token(cfg)
    size = video.stat().st_size
    if size <= SINGLE_CHUNK_MAX:
        chunk, count = size, 1
    else:
        chunk, count = CHUNK, size // CHUNK
    init = _call(token, "post/publish/inbox/video/init/", {"source_info": {
        "source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}})
    with video.open("rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1  # the last chunk takes the rest
            f.seek(start)
            part = f.read(end - start + 1)
            r = requests.put(init["upload_url"], data=part, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                "Content-Range": f"bytes {start}-{end}/{size}"})
            if r.status_code not in (200, 201, 206):
                raise TikTokError(f"upload of chunk {i + 1}/{count} failed ({r.status_code}): {r.text[:200]}")
    status = "UPLOADED"
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(8)
        try:
            status = _call(token, "post/publish/status/fetch/", {"publish_id": init["publish_id"]}).get("status", status)
        except TikTokError as err:
            print(f"  tiktok: status check failed: {err}", flush=True)
            break
        if status in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE", "FAILED"):
            break
    if status == "FAILED":
        raise TikTokError(f"TikTok could not process the upload (publish_id {init['publish_id']})")
    return {"publish_id": init["publish_id"], "status": status}


def send_url(cfg: dict, url: str, wait: int = 60) -> dict:
    """send_draft for a video that only exists online (a release asset)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "video.mp4"
        with requests.get(url, stream=True, timeout=300) as r:
            if not r.ok:
                raise TikTokError(f"video download failed ({r.status_code})")
            with path.open("wb") as f:
                for part in r.iter_content(1 << 20):
                    f.write(part)
        return send_draft(cfg, path, wait=wait)


def waiting(records: list[dict]) -> int:
    """Drafts still waiting in the owner's inbox."""
    return sum(1 for r in records if (r.get("tiktok") or {}).get("status") not in (None, "PUBLISH_COMPLETE", "FAILED"))


def backlog(cfg: dict, todo: list[tuple[dict, str, str]], records: list[dict], max_pending: int = MAX_WAITING) -> int:
    """Send (record, video URL, caption) items as drafts while fewer than `max_pending` wait in the inbox –
    the owner posts them one tap each, so the inbox never fills up. Returns how many were sent."""
    sent = 0
    for rec, url, text in todo:
        if waiting(records) >= max_pending:
            break
        try:
            rec["tiktok"] = {**send_url(cfg, url), "caption": text}
        except (TikTokError, requests.RequestException) as err:
            print(f"  tiktok: {rec.get('id')} not sent: {err}", flush=True)
            if re.search(r"spam|pending|rate|too_many|limit", str(err), re.I):
                break  # TikTok wants fewer drafts at once: the next run goes on
            rec["tiktok_skip"] = str(err)[:200]
            continue
        sent += 1
        print(f"  tiktok: {rec.get('id')} sent as a draft ({rec['tiktok']['status']})", flush=True)
        time.sleep(12)  # TikTok allows 6 upload starts per minute
    return sent


def refresh(cfg: dict, records: list[dict]) -> bool:
    """Ask TikTok which recent drafts the owner has posted meanwhile; returns True if anything changed."""
    open_ = [r for r in records[-12:] if r.get("tiktok") and r["tiktok"].get("status") not in ("PUBLISH_COMPLETE", "FAILED")]
    if not open_:
        return False
    token, changed = fresh_token(cfg), False
    for r in open_:
        try:
            res = _call(token, "post/publish/status/fetch/", {"publish_id": r["tiktok"]["publish_id"]})
        except TikTokError as err:
            name = r.get("id") or f"{r['kind']}-{r['seed']}"
            print(f"  tiktok: status of {name} unknown: {err}", flush=True)
            continue
        ids = res.get("publicaly_available_post_id") or []
        print(f"  tiktok: {r.get('id') or r.get('kind')}: {res.get('status')}", flush=True)
        if res.get("status") and res["status"] != r["tiktok"].get("status"):
            r["tiktok"]["status"], changed = res["status"], True
        if ids and not r["tiktok"].get("url"):
            handle = (cfg.get("tiktok") or {}).get("account", "")
            r["tiktok"]["url"], changed = f"https://www.tiktok.com/@{handle}/video/{ids[0]}", True
    return changed


def lead(text: str, sentences: int = 2, limit: int = 240) -> str:
    """The first sentences of a video description – what this video is about – without the "In this video essay
    we…" / "With World Bank data we…" sentences that only describe the method."""
    out: list[str] = []
    for x in re.split(r"(?<=[.!?])\s+", text.split("\n\n")[0].strip()):
        if re.match(r"(In this|With |Using |Here we|We )", x):
            if out:
                break  # what follows belongs to the method sentence
            continue
        if out and len(" ".join(out + [x])) > limit:
            break
        out.append(x)
        if len(out) == sentences:
            break
    return " ".join(out)


def question_from(*texts: str) -> str | None:
    """The last question asked in the video's own words (e.g. the closing line of a Short)."""
    for text in reversed(texts):
        found = [x for x in re.split(r"(?<=[.!?])\s+", text or "") if x.endswith("?")]
        if found:
            return found[-1]
    return None


def caption(title: str, question: str, tags: list[str]) -> str:
    return "\n".join([title, question, " ".join(f"#{t}" for t in tags)])


def write_queue(records: list[dict], channel: str, path: Path | None = None) -> None:
    """state/tiktok.md (or `path`): the latest drafts with their caption to copy – the owner's 15-second checklist."""
    sent = [r for r in records if r.get("tiktok")]
    waiting = sorted((r for r in sent if r["tiktok"].get("status") != "PUBLISH_COMPLETE"), key=lambda r: r["date"], reverse=True)
    posted = sorted((r for r in sent if r["tiktok"].get("status") == "PUBLISH_COMPLETE"), key=lambda r: r["date"], reverse=True)
    recent = waiting + posted[:5]
    lines = [f"# TikTok – {channel}: Entwürfe zum Posten", "",
             "1. Beschreibung unten kopieren (Kopier-Symbol rechts im Kasten).",
             "2. In TikTok auf die Benachrichtigung tippen (oder Profil → Posteingang/Entwürfe) → **Weiter**.",
             "3. Beschreibung einfügen, nach Wunsch einen angesagten Sound wählen → **Posten**.", "",
             "Welcher Text zu welchem Entwurf gehört: Die erste Zeile ist der Satz, der am Anfang im Video steht.", ""]
    for r in recent:
        tt = r["tiktok"]
        when = dt.datetime.fromisoformat(r["date"]).strftime("%d.%m. %H:%M UTC")
        state = {"SEND_TO_USER_INBOX": "im Posteingang", "PUBLISH_COMPLETE": "gepostet",
                 "FAILED": "fehlgeschlagen"}.get(tt.get("status", ""), "wird verarbeitet")
        links = ([f"[auf TikTok]({tt['url']})"] if tt.get("url") else []) + \
                ([f"[Video]({r['release']})"] if r.get("release") else [])
        title = tt.get("caption", r["title"]).split("\n")[0]
        lines += [f"## {when} – {title}", "", f"Status: **{state}**" + "".join(f" · {x}" for x in links), "",
                  "```text", tt.get("caption", ""), "```", ""]
    if not recent:
        lines.append("_Noch keine Entwürfe._")
    path = path or QUEUE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
