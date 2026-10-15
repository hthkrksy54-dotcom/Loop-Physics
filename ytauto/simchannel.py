"""Second channel: one satisfying physics simulation Short per run (config/sims.json, state/sims.json).

Each run picks the next format and melody, renders the video, archives it as a GitHub release (with
copy-paste YouTube metadata), posts it as an Instagram Reel + Story and – once uploads are enabled –
publishes it as a YouTube Short.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
from collections import Counter
from pathlib import Path

from cryptography.fernet import Fernet

from . import instagram, publish, sims, youtube

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sims.json"
STATE = ROOT / "state" / "sims.json"
OUT = ROOT / "out" / "sims"

TITLES = {
    "escape": [
        "Can the ball escape all {n} rings?",
        "{n} rings, one ball – wait for the ending",
        "Will this ball break out of {n} spinning rings?",
        "Every bounce plays {song} – can it escape?",
    ],
    "grow": [
        "Every bounce makes the ball bigger",
        "This ball grows with every bounce – wait for it",
        "Every bounce = bigger ball + one note of {song}",
        "How many bounces until it fills the circle?",
    ],
}
QUESTIONS = {
    "escape": ["How many seconds did you guess?", "Which ring was the hardest one?", "Did you recognise the melody?"],
    "grow": ["At what percent did you start holding your breath?", "Did you recognise the melody?",
             "Should the next one be bigger or faster?"],
}
COMPOSERS = {"fur_elise": "Beethoven", "ode_to_joy": "Beethoven", "mountain_king": "Grieg", "twinkle": "Mozart",
             "canon": "Pachelbel"}
TAGS = ["satisfying", "oddly satisfying", "physics simulation", "bouncing ball", "satisfying video",
        "simulation", "relaxing", "asmr", "classical music"]


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plan(cfg: dict, state: dict) -> tuple[str, int, str]:
    """Next format (least used, never twice in a row), a fresh seed for it, and the least used melody."""
    videos = state.get("videos", [])
    kinds = [k for k in cfg["kinds"] if k in sims.KINDS]
    used = Counter(v["kind"] for v in videos)
    last = videos[-1]["kind"] if videos else None
    kind = min(kinds, key=lambda k: (k == last and len(kinds) > 1, used[k], kinds.index(k)))
    start = max((v["seed"] for v in videos if v["kind"] == kind), default=-1) + 1
    seed = sims.pick_seed(kind, start)
    tunes = Counter(v["melody"] for v in videos)
    last_tune = videos[-1]["melody"] if videos else None
    melody = min(sims.MELODIES, key=lambda m: (m == last_tune, tunes[m], m))
    return kind, seed, melody


def metadata(kind: str, seed: int, melody: str, cfg: dict) -> dict:
    rnd = random.Random(seed * 31 + len(kind))
    song_full = sims.MELODIES[melody][0]
    song = song_full.split(" – ")[0]
    params = {"n": getattr(sims.KINDS[kind](seed), "n", ""), "song": song}
    title = rnd.choice(TITLES.get(kind, ["{song}"])).format(**params)
    question = rnd.choice(QUESTIONS.get(kind, ["Did you recognise the melody?"]))
    composer = COMPOSERS.get(melody, "")
    body = (f"Every bounce plays the next note of {song_full}.\n"
            "Physics, picture and sound are all generated in code – no two runs are the same.")
    description = "\n\n".join([
        body,
        f"💬 {question}",
        f"New simulation every day on {cfg['channel_name']}.",
        "#satisfying #physics #simulation #shorts",
    ])
    caption = "\n\n".join([
        title,
        body,
        f"💬 {question}",
        f"Follow {cfg['handle']} for a new one every day.",
        (cfg["instagram"].get("hashtags", "") + (f" #{composer.lower()}" if composer else "")).strip(),
    ])
    return {"title": title[:95], "description": description, "caption": caption[:2150],
            "tags": TAGS + [t for t in (song.lower(), composer.lower()) if t]}


def _youtube_token(cfg: dict) -> str | None:
    path = ROOT / cfg["youtube"]["token_file"]
    if not (path.exists() and os.environ.get("IG_TOKEN_KEY") and os.environ.get("YT_CLIENT_ID")):
        return None
    data = json.loads(Fernet(os.environ["IG_TOKEN_KEY"].strip().encode()).decrypt(path.read_bytes().strip()))
    return youtube.access_token_from(data["refresh_token"])


def run(upload: bool = True) -> dict:
    cfg = load(CONFIG, {})
    state = load(STATE, {"videos": []})
    kind, seed, melody = plan(cfg, state)
    meta = metadata(kind, seed, melody, cfg)
    stamp = dt.datetime.now(dt.timezone.utc)
    name = f"{stamp:%Y%m%d}-{kind}-{seed}"
    print(f"[sims] {name}: {meta['title']} ({sims.MELODIES[melody][0]})", flush=True)
    result = sims.render(kind, seed, OUT / f"{name}.mp4", melody, cfg.get("handle", ""))
    record = {"date": stamp.isoformat(timespec="seconds"), "kind": kind, "seed": seed, "melody": melody,
              "title": meta["title"], "duration": round(result["duration"], 1)}
    if not upload:
        print(f"  rendered {result['video']} ({result['duration']:.1f}s)", flush=True)
        return record

    body = "\n".join(["### Title", "```", meta["title"], "```", "### Description", "```", meta["description"], "```",
                      "### Tags", "```", ", ".join(meta["tags"]), "```"])
    rel = publish.github_release(f"sims-{name}", f"[Loop Physics] {meta['title']}", body,
                                 [(result["video"], f"loop-physics-{name}.mp4", "video/mp4")])
    video_url = rel.get("assets", {}).get(f"loop-physics-{name}.mp4")
    if rel:
        record["release"] = rel["release"]
    if video_url and instagram.configured(cfg):
        try:
            record.update(instagram.post_reel(cfg, video_url, meta["caption"], story=True, label=meta["title"]))
        except Exception as err:  # one platform failing must not lose the run
            record.setdefault("warnings", []).append(f"instagram: {err}")
            print(f"  warning: instagram failed: {err}", flush=True)
    if cfg["youtube"].get("upload_enabled"):
        try:
            token = _youtube_token(cfg)
            if token:
                vid = youtube.upload_video(token, Path(result["video"]), {
                    "title": meta["title"], "description": meta["description"], "tags": meta["tags"],
                    "categoryId": cfg["youtube"]["category_id"],
                    "defaultLanguage": cfg["youtube"]["default_language"],
                }, {"privacyStatus": "public", "selfDeclaredMadeForKids": False})
                record["youtube_id"] = vid
                print(f"  youtube: https://youtube.com/shorts/{vid}", flush=True)
        except Exception as err:
            record.setdefault("warnings", []).append(f"youtube: {err}")
            print(f"  warning: youtube failed: {err}", flush=True)
    state.setdefault("videos", []).append(record)
    save(STATE, state)
    return record
