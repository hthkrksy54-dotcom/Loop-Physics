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

TITLES = {  # {onscreen} = the question shown in the video, {n} = rings/polygons, {song} = melody
    "escape": [
        "{onscreen}",
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
    "battle": [
        "{onscreen}",
        "Pick a color before it starts",
        "Four balls, one way out – who wins?",
        "Every bounce plays {song} – which color wins?",
    ],
    "polygon": [
        "{onscreen}",
        "One ball vs. {n} spinning polygons",
        "Every bounce plays {song} – can it break out?",
    ],
    "plinko": [
        "{onscreen}",
        "Watch randomness turn into a perfect curve",
        "Hundreds of balls, one bell curve",
    ],
    "stringart": [
        "{onscreen}",
        "Every bounce draws a line – wait for the pattern",
        "A bouncing ball draws this – with {song}",
    ],
    "multiply": [
        "{onscreen}",
        "One ball becomes chaos – every bounce adds another",
        "Every bounce adds a ball – wait for the ending",
        "Every bounce plays {song} and adds a ball",
    ],
    "pendulum": [
        "{onscreen}",
        "Watch these pendulums fall back in sync",
        "Pure physics: every pendulum swings a little faster",
        "Wait for the moment they all line up",
    ],
}
BODIES = {  # what the sound does, per format (default: the melody)
    "pendulum": "Each pendulum swings a little faster than the one above it and rings its own note – "
                "waves and snakes appear, until they all line up again.",
}
RANGES = [(28, 40), (35, 48), (42, 56)]  # alternate short, medium and long runs
QUESTIONS = {
    "escape": ["How many seconds did you guess?", "Which ring was the hardest one?", "Did you recognise the melody?"],
    "grow": ["At what percent did you start holding your breath?", "Did you recognise the melody?",
             "Should the next one be bigger or faster?"],
    "battle": ["Which color did you pick?", "Did your color win?", "Which color should race next time?"],
    "polygon": ["How many seconds did you guess?", "Rings or polygons – which is harder?"],
    "plinko": ["Did you expect such a clean bell curve?", "Which slot would you bet on?"],
    "stringart": ["What does the pattern remind you of?", "More bounces next time?"],
    "multiply": ["How many balls should the next one have?", "At which number did it get chaotic for you?"],
    "pendulum": ["Which pattern was your favourite?", "Did you see the snake?", "Could you watch this on loop?"],
}
COMPOSERS = {"fur_elise": "Beethoven", "ode_to_joy": "Beethoven", "mountain_king": "Grieg", "twinkle": "Mozart",
             "canon": "Pachelbel", "nachtmusik": "Mozart", "turkish_march": "Mozart", "minuet": "Bach",
             "blue_danube": "Strauss", "lullaby": "Brahms", "morning_mood": "Grieg", "moonlight": "Beethoven"}
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
    lo, hi = RANGES[len(videos) % len(RANGES)]
    try:
        seed = sims.pick_seed(kind, start, lo, hi, tries=60)
    except RuntimeError:  # some formats can't be that short or long
        seed = sims.pick_seed(kind, start)
    tunes = Counter(v["melody"] for v in videos)
    last_tune = videos[-1]["melody"] if videos else None
    melody = min(sims.MELODIES, key=lambda m: (m == last_tune, tunes[m], m))
    return kind, seed, melody


def metadata(kind: str, seed: int, melody: str, cfg: dict) -> dict:
    rnd = random.Random(seed * 31 + len(kind))
    song_full = sims.MELODIES[melody][0]
    song = song_full.split(" – ")[0]
    sim = sims.KINDS[kind](seed)
    params = {"n": getattr(sim, "n", ""), "song": song, "onscreen": " ".join(sim.title())}
    title = rnd.choice(TITLES.get(kind, ["{onscreen}"])).format(**params)
    question = rnd.choice(QUESTIONS.get(kind, ["Did you recognise the melody?"]))
    composer = COMPOSERS.get(melody, "")
    body = (BODIES.get(kind, f"Every bounce plays the next note of {song_full}.") + "\n"
            "Physics, picture and sound are all generated in code – no two runs are the same.")
    description = "\n\n".join([
        body,
        f"💬 {question}",
        f"A new simulation every few hours on {cfg['channel_name']}.",
        "#satisfying #physics #simulation #shorts",
    ])
    caption = "\n\n".join([
        title,
        body,
        f"💬 {question}",
        f"Follow {cfg['handle']} – a new one every few hours."
        + (f"\n▶ YouTube: {cfg['youtube']['channel_url']}" if cfg["youtube"].get("channel_url") else ""),
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
    if upload and instagram.configured(cfg):
        try:  # a blocked or expired Instagram token must not silently swallow the videos
            instagram._user(instagram.fresh_token(cfg))
        except instagram.InstagramError as err:
            raise SystemExit(f"Instagram access for @{cfg['instagram']['account']} is not working – nothing rendered. {err}")
    kind, seed, melody = plan(cfg, state)
    meta = metadata(kind, seed, melody, cfg)
    stamp = dt.datetime.now(dt.timezone.utc)
    name = f"{stamp:%Y%m%d}-{kind}-{seed}"
    print(f"[sims] {name}: {meta['title']} ({sims.MELODIES[melody][0]})", flush=True)
    result = sims.render(kind, seed, OUT / f"{name}.mp4", melody, cfg.get("handle", ""))
    record = {"date": stamp.isoformat(timespec="seconds"), "kind": kind, "seed": seed, "melody": melody,
              "timbre": result.get("timbre"), "title": meta["title"], "duration": round(result["duration"], 1)}
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


DESCRIPTION = """Oddly satisfying physics simulations – every bounce plays a melody.

Balls breaking out of spinning rings, colour battles, pendulum waves, plinko bell curves, string art and more. \
Every video is generated from scratch – the physics, the picture and the sound. Each collision plays the next \
note of a classical melody (Beethoven, Mozart, Grieg, Bach, Strauss …).

New simulations every few hours. Pick your colour, guess the ending and tell us in the comments.

Instagram: @loop_physics"""
KEYWORDS = ["satisfying", "oddly satisfying", "physics simulation", "bouncing ball", "satisfying video", "simulation",
            "relaxing", "asmr", "classical music", "pendulum wave", "plinko", "marble race", "loop physics"]


def branding() -> None:
    """Set banner, description and keywords of the Loop Physics YouTube channel (works before the API audit)."""
    import requests

    cfg = load(CONFIG, {})
    token = _youtube_token(cfg)
    if not token:
        raise SystemExit("YouTube token or client credentials missing")
    api, h = "https://www.googleapis.com/youtube/v3", {"Authorization": f"Bearer {token}"}
    ch = requests.get(f"{api}/channels", params={"part": "snippet,brandingSettings", "mine": "true"}, headers=h,
                      timeout=30).json()["items"][0]
    if ch["snippet"]["title"] != cfg["channel_name"]:  # never touch another channel by accident
        raise SystemExit(f"token belongs to '{ch['snippet']['title']}', not '{cfg['channel_name']}'")
    banner = requests.post("https://www.googleapis.com/upload/youtube/v3/channelBanners/insert",
                           headers={**h, "Content-Type": "image/jpeg"},
                           data=(ROOT / "docs" / "sims" / "banner.jpg").read_bytes(), timeout=120)
    banner.raise_for_status()
    branding = {"channel": dict(ch.get("brandingSettings", {}).get("channel", {}))}
    branding["channel"].update({
        "description": DESCRIPTION,
        "keywords": " ".join(f'"{k}"' if " " in k else k for k in KEYWORDS),
        "defaultLanguage": cfg["youtube"]["default_language"],
    })
    branding["channel"].pop("title", None)
    branding["image"] = {"bannerExternalUrl": banner.json()["url"]}
    r = requests.put(f"{api}/channels", params={"part": "brandingSettings"},
                     headers={**h, "Content-Type": "application/json"},
                     data=json.dumps({"id": ch["id"], "brandingSettings": branding}), timeout=60)
    if not r.ok:
        raise SystemExit(f"channel update failed ({r.status_code}): {r.text[:300]}")
    print(f"branded {ch['snippet']['title']} ({ch['id']}): banner, description, keywords", flush=True)


PLAYLISTS = {
    "escape": ("Can the ball escape? – Ring escapes", "A ball against spinning rings – every bounce plays a melody."),
    "battle": ("Which color wins? – Color battles", "Pick your colour before it starts."),
    "grow": ("Every bounce makes it bigger", "A ball that grows with every bounce until the circle is full."),
    "polygon": ("Polygon escapes", "Spinning polygons, one ball, one way out."),
    "plinko": ("Plinko – bell curves", "Hundreds of balls turn randomness into a perfect curve."),
    "stringart": ("String art – bounces that draw", "Every bounce leaves a line until a pattern appears."),
    "multiply": ("Every bounce adds a ball", "One ball becomes a cloud of colour."),
    "pendulum": ("Pendulum waves", "Pendulums drift into waves and snakes and fall back in sync."),
}


def _norm(text: str) -> str:
    return " ".join((text or "").replace("#shorts", "").replace("#Shorts", "").split()).casefold()


def youtube_polish(apply: bool = False) -> None:
    """Match the owner's manual uploads to produced simulations, then (apply=True) give them our title,
    description and tags, sort them into one playlist per format and remember their YouTube ids."""
    import re
    import time

    import requests

    cfg, state = load(CONFIG, {}), load(STATE, {"videos": []})
    token = _youtube_token(cfg)
    if not token:
        raise SystemExit("YouTube token or client credentials missing")
    api, h = "https://www.googleapis.com/youtube/v3", {"Authorization": f"Bearer {token}"}

    def get(path: str, **params) -> dict:
        r = requests.get(f"{api}/{path}", params=params, headers=h, timeout=30)
        r.raise_for_status()
        return r.json()

    def send(method: str, path: str, part: str, body: dict) -> dict:
        r = requests.request(method, f"{api}/{path}", params={"part": part}, timeout=60,
                             headers={**h, "Content-Type": "application/json"}, data=json.dumps(body))
        if not r.ok:
            raise SystemExit(f"{path} failed ({r.status_code}): {r.text[:300]}")
        return r.json()

    ch = get("channels", part="snippet,brandingSettings,contentDetails,statistics", mine="true")["items"][0]
    if ch["snippet"]["title"] != cfg["channel_name"]:
        raise SystemExit(f"token belongs to '{ch['snippet']['title']}', not '{cfg['channel_name']}'")
    bs = ch.get("brandingSettings", {})
    print(f"channel {ch['snippet']['title']}: {ch['statistics'].get('subscriberCount')} subscribers, "
          f"{ch['statistics'].get('viewCount')} views | banner set: {bool(bs.get('image', {}).get('bannerExternalUrl'))} | "
          f"description: {bs.get('channel', {}).get('description', '')[:50]!r}", flush=True)

    ids = [i["contentDetails"]["videoId"] for i in get(
        "playlistItems", part="contentDetails", maxResults=50,
        playlistId=ch["contentDetails"]["relatedPlaylists"]["uploads"]).get("items", [])]
    videos = get("videos", part="snippet,contentDetails,fileDetails,statistics", id=",".join(ids))["items"] if ids else []
    records = state.get("videos", [])
    taken = {r["youtube_id"] for r in records if r.get("youtube_id")}
    matches = []
    for v in videos:
        m = re.fullmatch(r"P(?:T)?(?:(\d+)M)?(?:(\d+)S)?", v["contentDetails"]["duration"]) or None
        secs = (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 0
        fname = (v.get("fileDetails", {}).get("fileName") or "").casefold()
        title = _norm(v["snippet"]["title"])
        rec = next((r for r in records if r.get("youtube_id") == v["id"]), None)
        free = [r for r in records if not r.get("youtube_id") and abs(r.get("duration", 0) - secs) <= 1.5]
        rec = rec or next((r for r in free if f"{r['kind']}-{r['seed']}" in fname), None) \
            or next((r for r in free if r["kind"] in fname), None) \
            or next((r for r in free if _norm(r["title"]) == title), None) \
            or (free[0] if len(free) == 1 else None)
        print(f"  {v['id']} {secs:3d}s views={v['statistics'].get('viewCount', 0):>5} file={fname[:38]!r:40} "
              f"title={v['snippet']['title'][:45]!r} -> {rec['kind'] + '-' + str(rec['seed']) if rec else 'NO MATCH'}",
              flush=True)
        if rec and v["id"] not in taken:
            matches.append((v, rec))
            rec["youtube_id"] = v["id"]
            taken.add(v["id"])
    if not apply:
        print(f"dry run: {len(matches)} uploads would be updated", flush=True)
        return

    existing = {p["snippet"]["title"]: p["id"] for p in get("playlists", part="snippet", mine="true",
                                                            maxResults=50).get("items", [])}
    for v, rec in matches:
        meta = metadata(rec["kind"], rec["seed"], rec["melody"], cfg)
        send("PUT", "videos", "snippet", {"id": v["id"], "snippet": {
            "title": meta["title"], "description": meta["description"], "tags": meta["tags"],
            "categoryId": cfg["youtube"]["category_id"], "defaultLanguage": cfg["youtube"]["default_language"]}})
        name, about = PLAYLISTS.get(rec["kind"], (rec["kind"], ""))
        if name not in existing:
            existing[name] = send("POST", "playlists", "snippet,status", {
                "snippet": {"title": name, "description": f"{about} New simulations every few hours on Loop Physics.",
                            "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}})["id"]
        if not get("playlistItems", part="id", playlistId=existing[name], videoId=v["id"]).get("items"):
            for attempt in range(5):  # a brand-new playlist often answers 409 ABORTED for a few seconds
                r = requests.post(f"{api}/playlistItems", params={"part": "snippet"}, timeout=60,
                                  headers={**h, "Content-Type": "application/json"}, data=json.dumps({"snippet": {
                                      "playlistId": existing[name],
                                      "resourceId": {"kind": "youtube#video", "videoId": v["id"]}}}))
                if r.ok:
                    break
                print(f"  playlist add retry {attempt + 1} ({r.status_code})", flush=True)
                time.sleep(4 * (attempt + 1))
            else:
                raise SystemExit(f"playlistItems failed ({r.status_code}): {r.text[:300]}")
        print(f"  updated {v['id']}: {meta['title']!r} -> playlist {name!r}", flush=True)
    save(STATE, state)
