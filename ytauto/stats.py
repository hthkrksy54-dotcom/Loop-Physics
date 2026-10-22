"""All channels at a glance: views, followers, likes and comments, per account and in total.

YouTube: subscribers and views from the channel, likes and comments summed over every upload. Instagram: followers,
plus views (insights), likes and comments summed over every post. TikTok can't be read: the connected scopes only allow
uploading drafts (user.info.stats / video.list would be needed). Nothing is stored; the table goes to the job summary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
YT = "https://www.googleapis.com/youtube/v3"


def _cfg(name: str) -> dict:
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def youtube(token: str, name: str) -> dict:
    h = {"Authorization": f"Bearer {token}"}

    def get(path: str, **params) -> dict:
        r = requests.get(f"{YT}/{path}", params=params, headers=h, timeout=30)
        r.raise_for_status()
        return r.json()

    ch = get("channels", part="snippet,statistics,contentDetails", mine="true")["items"][0]
    if ch["snippet"]["title"] != name:  # never count another channel by accident
        raise RuntimeError(f"token belongs to '{ch['snippet']['title']}', not '{name}'")
    ids, page = [], None
    while True:
        res = get("playlistItems", part="contentDetails", maxResults=50,
                  playlistId=ch["contentDetails"]["relatedPlaylists"]["uploads"], **({"pageToken": page} if page else {}))
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        page = res.get("nextPageToken")
        if not page:
            break
    likes = comments = 0
    for k in range(0, len(ids), 50):
        for v in get("videos", part="statistics", id=",".join(ids[k:k + 50])).get("items", []):
            likes += int(v["statistics"].get("likeCount", 0))
            comments += int(v["statistics"].get("commentCount", 0))
    st = ch["statistics"]
    return {"views": int(st.get("viewCount", 0)), "followers": int(st.get("subscriberCount", 0)), "likes": likes,
            "comments": comments, "posts": len(ids)}


def instagram(cfg: dict) -> dict:
    from . import instagram as ig

    token = ig.load_token(cfg)["token"]  # read only: no refresh, so nothing has to be saved
    me = requests.get(f"{ig.GRAPH}/me", params={"fields": "followers_count,media_count", "access_token": token},
                      timeout=30).json()
    out = {"views": 0, "followers": int(me.get("followers_count", 0)), "likes": 0, "comments": 0, "posts": 0}
    url, params = f"{ig.GRAPH}/me/media", {"fields": "id,like_count,comments_count", "limit": 100, "access_token": token}
    while url:
        res = requests.get(url, params=params, timeout=30).json()
        for m in res.get("data", []):
            out["posts"] += 1
            out["likes"] += int(m.get("like_count", 0))
            out["comments"] += int(m.get("comments_count", 0))
            r = requests.get(f"{ig.GRAPH}/{m['id']}/insights", params={"metric": "views", "access_token": token},
                             timeout=30)
            if r.ok:
                out["views"] += sum(int(d["values"][0]["value"]) for d in r.json().get("data", []))
        url, params = (res.get("paging") or {}).get("next"), None
    return out


def run() -> int:
    from . import econ, simchannel
    from . import youtube as yt

    qt, rn, lp = _cfg("channels.json")["en"], _cfg("econ.json"), _cfg("sims.json")
    rows: list[tuple[str, str, dict | str]] = []
    for name, token in [(qt["channel_name"], lambda: yt.access_token(qt["youtube"]["refresh_token_secret"])),
                        (rn["channel_name"], lambda: econ._youtube_token(rn)),
                        (lp["channel_name"], lambda: simchannel._youtube_token(lp))]:
        try:
            tok = token()
            if not tok:
                raise RuntimeError("no token")
            rows.append(("YouTube", name, youtube(tok, name)))
        except Exception as err:
            rows.append(("YouTube", name, f"nicht abrufbar ({str(err)[:80]})"))
    for c in (qt, rn, lp):
        try:
            rows.append(("Instagram", c["channel_name"], instagram(c)))
        except Exception as err:
            rows.append(("Instagram", c["channel_name"], f"nicht abrufbar ({str(err)[:80]})"))
    keys = ("views", "followers", "likes", "comments", "posts")
    total = {k: sum(r[k] for _, _, r in rows if isinstance(r, dict)) for k in keys}
    fmt = lambda n: f"{n:,}".replace(",", ".")
    lines = ["| Plattform | Kanal | Aufrufe | Abos/Follower | Likes | Kommentare | Beiträge |", "|---|---|---:|---:|---:|---:|---:|"]
    for platform, name, r in rows:
        lines.append(f"| {platform} | {name} | " + (" | ".join(fmt(r[k]) for k in keys) if isinstance(r, dict)
                                                   else f"{r} | | | | "))
    for platform in ("YouTube", "Instagram"):
        sub = [r for p, _, r in rows if p == platform and isinstance(r, dict)]
        lines.append(f"| **{platform} gesamt** | | " + " | ".join(f"**{fmt(sum(r[k] for r in sub))}**" for k in keys))
    lines.append("| **Alles zusammen** | | " + " | ".join(f"**{fmt(total[k])}**" for k in keys))
    lines.append("\nTikTok: nicht abrufbar – die Verbindung darf nur Entwürfe hochladen.")
    text = "\n".join(lines)
    print(text, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("## Statistik\n\n" + text + "\n")
    return 0
