"""The legal notice (Impressum, § 5 DDG / § 18 Abs. 2 MStV) and its link in every YouTube channel description.

IMPRESSUM.md in the repo root is the page itself; once it exists, the hourly sync makes sure each channel's
description ends with the link (and puts it back if the description was edited in YouTube Studio). Instagram and
TikTok bios can't be edited through their APIs – the owner adds the same link there once.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "IMPRESSUM.md"
URL = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'hthkrksy54-dotcom/Yt')}/blob/main/IMPRESSUM.md"
LINE = f"Impressum / Legal notice: {URL}"
API = "https://www.googleapis.com/youtube/v3"


def with_line(description: str) -> str:
    """The description with the link as its last line (exactly once, at most 1,000 characters in all)."""
    rest = re.sub(r"\n*Impressum / Legal notice: \S+\s*$", "", (description or "").rstrip())
    return (rest[:1000 - len(LINE) - 2].rstrip() + "\n\n" + LINE) if rest else LINE


def ensure(token: str, channel_name: str) -> bool:
    """Add the link to the channel's description if it is missing; True if the channel was updated."""
    h = {"Authorization": f"Bearer {token}"}
    ch = requests.get(f"{API}/channels", params={"part": "snippet,brandingSettings", "mine": "true"}, headers=h,
                      timeout=30).json()["items"][0]
    if ch["snippet"]["title"] != channel_name:  # never touch another channel by accident
        raise RuntimeError(f"token belongs to '{ch['snippet']['title']}', not '{channel_name}'")
    settings = {k: v for k, v in ch.get("brandingSettings", {}).get("channel", {}).items() if k != "title"}
    want = with_line(settings.get("description", ""))
    if settings.get("description", "") == want:
        return False
    settings["description"] = want
    r = requests.put(f"{API}/channels", params={"part": "brandingSettings"},
                     headers={**h, "Content-Type": "application/json"},
                     data=json.dumps({"id": ch["id"], "brandingSettings": {"channel": settings}}), timeout=60)
    if not r.ok:
        raise RuntimeError(f"channel update failed ({r.status_code}): {r.text[:200]}")
    print(f"[imprint] link added to the description of {channel_name}", flush=True)
    return True


def run() -> None:
    """All three channels; a channel that can't be reached is reported and skipped."""
    if not PAGE.exists():
        return
    from . import econ, simchannel, youtube

    qt = json.loads((ROOT / "config" / "channels.json").read_text(encoding="utf-8"))["en"]
    rn = json.loads((ROOT / "config" / "econ.json").read_text(encoding="utf-8"))
    lp = json.loads((ROOT / "config" / "sims.json").read_text(encoding="utf-8"))
    channels = [(qt["channel_name"], lambda: youtube.access_token(qt["youtube"]["refresh_token_secret"])),
                (rn["channel_name"], lambda: econ._youtube_token(rn)),
                (lp["channel_name"], lambda: simchannel._youtube_token(lp))]
    for name, token in channels:
        try:
            tok = token()
            if tok:
                ensure(tok, name)
        except Exception as err:
            print(f"[imprint] {name}: {err}", flush=True)
