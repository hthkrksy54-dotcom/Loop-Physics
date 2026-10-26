"""Second channel: one satisfying physics simulation Short per run (config/sims.json, state/sims.json).

Three posts a day (SLOTS). New concepts always go first: the built-in kinds that were never posted, then the
concepts the concept designer builds twice a day (ytauto/concepts/, see docs/concept-designer.md). In between, the
concepts that already ran come back in a fresh variant (new seed: other numbers, colours, melody), weighted by how
well they performed – standouts much more often, weak ones rarely – and never one of the last three again.

Each run renders the video, archives it as a GitHub release (with copy-paste YouTube metadata), posts it as an
Instagram Reel + Story, sends new concepts and standouts to TikTok as drafts and – once uploads are enabled –
publishes it as a YouTube Short.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import re
import statistics
from collections import Counter
from pathlib import Path

from cryptography.fernet import Fernet

from . import gdrive, instagram, publish, sims, tiktok, youtube

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sims.json"
STATE = ROOT / "state" / "sims.json"
TUNING = ROOT / "config" / "sims_tuning.json"  # written daily by trends.py
MUSIC = ROOT / "config" / "sims_music.json"  # viral-song research of the concept designer (twice a day)
OUT = ROOT / "out" / "sims"
STORY_EVERY = 2  # a story for every Reel would crowd the account's stories
SLOTS = [(4, 40), (10, 40), (22, 40)]  # UTC; 16:40 had the fewest views (median 17.–24.10.) and was dropped
# to save GitHub Actions minutes – the schedule in sims.yml runs at these times (+1 min) and half an hour later
SLOT_WINDOW = dt.timedelta(minutes=100)  # a missed or failed slot is retried until the next one is near
STANDOUT = 1.6  # views at least this many times the channel median: a standout, comes back much more often
TIKTOK_PENDING = 4  # one day of videos may wait in the TikTok inbox (TikTok holds 5); the heartbeat tops them up
EXPERIMENTS = ("Loop Physics experiments", "A brand-new simulation concept every time.")
TIKTOK_TAGS = ["satisfying", "oddlysatisfying", "physics", "simulation"]
TIKTOK_KIND_TAG = {"race": "marblerace", "battle": "ballbattle", "escape": "ballescape", "polygon": "ballescape",
                   "territory": "pongwars", "chaos": "doublependulum", "pendulum": "pendulumwave",
                   "harmonograph": "harmonograph", "plinko": "plinko", "stringart": "stringart",
                   "grow": "bouncingball", "multiply": "bouncingball"}


TIKTOK_WHAT = {  # what happens in the video, in one line – no sound references (the owner may pick a trending sound)
    "escape": "One ball, {n} spinning rings, one gap in each – it has to find every exit to break free.",
    "polygon": "One ball, {n} nested polygons turning in opposite directions – and only one gap in each.",
    "grow": "The ball gets a little bigger with every bounce – until there is no room left in the circle.",
    "battle": "Coloured balls share one set of spinning rings – every ring that breaks opens the way for all of them.",
    "plinko": "Balls drop through a triangle of pegs, left or right at every peg – and pile up into a bell curve.",
    "stringart": "A ball speeds up inside a shape and every bounce leaves a line to the last one – the pattern draws itself.",
    "multiply": "Every bounce of the white ball adds a new ball – until the circle is a cloud of colour.",
    "pendulum": "{k} pendulums, each swinging a little faster than the one before – waves and snakes appear, "
                "until they all line up again.",
    "territory": "Every ball flies through its own colour and paints every square it bounces off – "
                 "whoever owns most of the board at the end wins.",
    "chaos": "{k} double pendulums that start only {delta}° apart. For a while they move as one – then chaos takes over.",
    "harmonograph": "Four slowly fading pendulums steer one pen, slightly out of tune – so the drawing turns into a rosette.",
    "race": "All balls race down the same track of pegs, spinners, funnels and bumpers – first over the line wins.",
    "blade_duel": "Two balls, two spinning blades, one arena. Every hit takes HP from the other ball and upgrades "
                  "the attacker.",
    "brick_core": "One ball, one wall of numbered bricks. Green rings add balls, the gold ×2 ring doubles the swarm – "
                  "and in the middle waits the core.",
    "domino_scale": "A marble taps one tiny domino. Every domino is a bit bigger than the one before – until the wave "
                    "reaches the giant at the end.",
}
SOUND_WORDS = r"melod|song|tune|note|sound|music|plays|cracks"


def _what_happens(kind: str, seed: int) -> str:
    """One line about this video; new concepts fall back to their own description without the sound sentences."""
    cls = sims.KINDS[kind]
    sim = cls(seed)
    params = {"n": getattr(sim, "n", ""), "k": getattr(sim, "K", ""),
              "delta": sims._decimal(sim.delta) if isinstance(getattr(sim, "delta", None), float) else ""}
    text = TIKTOK_WHAT.get(kind)
    if not text:
        source = cls.body or BODIES.get(kind) or (cls.__doc__ or "").strip().split("\n\n")[0].replace("\n", " ")
        text = " ".join(x for x in re.split(r"(?<=[.!?])\s+", source) if x and not re.search(SOUND_WORDS, x, re.I))
    try:
        return text.format(**params) if text else ""
    except (KeyError, IndexError, ValueError):  # a placeholder this concept doesn't have
        return ""


def sound_tips() -> list[str]:
    """Trending TikTok sounds the designer found – for the owner to pick when posting a draft (licensed by TikTok,
    never mixed into our own videos)."""
    return [str(t) for t in (load(MUSIC, {}).get("tiktok_sounds") or [])][:6]


def tiktok_caption(kind: str, meta: dict, seed: int = 0) -> str:
    """TikTok text made for this video: the on-screen question, what happens, a question for the comments that
    fits this concept, and a few tags. No sound references – on TikTok the owner may swap in a trending sound."""
    cls = sims.KINDS[kind]
    own = [q for q in (cls.questions or QUESTIONS.get(kind) or []) if not re.search(SOUND_WORDS, q, re.I)]
    question = random.Random(seed * 17 + len(kind)).choice(own) if own else "Which moment was the most satisfying?"
    if meta.get("quiz"):  # song quiz: the owner keeps the original sound, so the question may be about it
        question = QUIZ_QUESTION
    kind_tag = TIKTOK_KIND_TAG.get(kind) or (cls.trend_words[0].replace(" ", "") if cls.trend_words else "")
    tags = [t for t in ([kind_tag] if kind_tag else []) + TIKTOK_TAGS if not re.search(r"asmr|music", t)]
    lines = [meta["onscreen"], _what_happens(kind, seed), f"💬 {question}", " ".join(f"#{t}" for t in tags)]
    return "\n".join(x for x in lines if x)
COVER_AT = {"stringart": 0.9, "plinko": 0.85, "multiply": 0.85, "grow": 0.75, "pendulum": 0.55,
            "escape": 0.3, "polygon": 0.3, "battle": 0.3, "harmonograph": 0.97, "chaos": 0.7, "territory": 0.6,
            "race": 0.4}  # share of the run that makes the best cover frame
NOVELTY = 1.6  # new formats get a boost until they have a few runs (and numbers) of their own

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
    "territory": [
        "{onscreen}",
        "Pick a color – who owns the board at the end?",
        "Every bounce steals a square – which color wins?",
        "Pong wars: which color takes over?",
    ],
    "chaos": [
        "{onscreen}",
        "They start {delta}° apart – watch what happens",
        "The butterfly effect in {k} pendulums",
        "Same start, completely different ending",
    ],
    "harmonograph": [
        "{onscreen}",
        "Two pendulums and a pen drew this",
        "A pendulum drew this – with {song}",
        "Watch a pendulum draw a masterpiece",
    ],
    "race": [
        "{onscreen}",
        "Pick a color before it starts",
        "Marble race: who crosses the line first?",
        "Pegs, spinners, bumpers – which color wins?",
    ],
}
BODIES = {  # what happens and what the sound does, per format (default: the melody)
    "pendulum": "Each pendulum swings a little faster than the one above it and rings its own note – "
                "waves and snakes appear, until they all line up again.",
    "territory": "Every ball flies through its own colour and bounces off the others – and every square it "
                 "bounces off turns into its colour. Whoever owns most of the board at the end wins. "
                 "Every bounce plays the next note of {song}.",
    "chaos": "Double pendulums that start only {delta}° apart. For a while they move as one – then chaos takes "
             "over. Every pendulum rings its own note when it swings through the middle.",
    "harmonograph": "A harmonograph: two slowly fading pendulums move the pen left and right, two move it up "
                    "and down. Every turn of the pen plays the next note of {song}.",
    "race": "All balls race down the same track of pegs, spinners, funnels and bumpers. The camera follows "
            "the leader – and every bounce of the leader plays the next note of {song}.",
}
RANGES = [(58, 68), (62, 74), (66, 80)]  # run lengths (s): every video is longer than a minute (TikTok rewards)
STORY_CLIP = 28  # Instagram stories take at most 60 s: long videos get a teaser cut for the story
QUESTIONS = {
    "escape": ["How many seconds did you guess?", "Which ring was the hardest one?", "Did you recognise the melody?"],
    "grow": ["At what percent did you start holding your breath?", "Did you recognise the melody?",
             "Should the next one be bigger or faster?"],
    "battle": ["Which color did you pick?", "Did your color win?", "Which color should go first next time?"],
    "polygon": ["How many seconds did you guess?", "Rings or polygons – which is harder?"],
    "plinko": ["Did you expect such a clean bell curve?", "Which slot would you bet on?"],
    "stringart": ["What does the pattern remind you of?", "More bounces next time?"],
    "multiply": ["How many balls should the next one have?", "At which number did it get chaotic for you?"],
    "pendulum": ["Which pattern was your favourite?", "Did you see the snake?", "Could you watch this on loop?"],
    "territory": ["Which color did you pick?", "Did your color win?", "Two colors or four – which is better?"],
    "chaos": ["When did you first see them split?", "Which pendulum was your favourite?",
              "Could you watch this on loop?"],
    "harmonograph": ["What does the drawing remind you of?", "Would you hang this on your wall?"],
    "race": ["Which color did you pick?", "Did your color win?", "Which obstacle was the craziest?"],
}
COMPOSERS = {"fur_elise": "Beethoven", "ode_to_joy": "Beethoven", "mountain_king": "Grieg", "twinkle": "Mozart",
             "canon": "Pachelbel", "nachtmusik": "Mozart", "turkish_march": "Mozart", "minuet": "Bach",
             "blue_danube": "Strauss", "lullaby": "Brahms", "morning_mood": "Grieg", "moonlight": "Beethoven",
             "toccata": "Bach", "funeral_march": "Chopin",
             "carol_bells": "Leontovych", "sugar_plum": "Tchaikovsky",
             "jingle_bells": "Pierpont"}
TAGS = ["satisfying", "oddly satisfying", "physics simulation", "bouncing ball", "satisfying video",
        "simulation", "relaxing", "asmr", "classical music"]


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def score(rec: dict) -> int:
    """Views of one post: Instagram + YouTube."""
    return (rec.get("stats") or {}).get("views", 0) + rec.get("yt_views", 0)


def performance(state: dict, now: dt.datetime | None = None) -> tuple[float, dict[str, tuple[float, int, int]]]:
    """Channel median views (posts older than 12 h, last 40) and per kind: (median / channel median, posts, best)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    aged = [v for v in state.get("videos", []) if (v.get("stats") or v.get("yt_views"))
            and now - dt.datetime.fromisoformat(v["date"]) > dt.timedelta(hours=12)]
    base = statistics.median([score(v) for v in aged[-40:]]) if aged else 0
    out = {}
    for k in {v["kind"] for v in aged}:
        vs = [score(v) for v in aged if v["kind"] == k]
        out[k] = (round(statistics.median(vs) / base, 2) if base else 0.0, len(vs), max(vs))
    return base, out


def melody_weights(state: dict, now: dt.datetime | None = None) -> dict[str, dict]:
    """How much each melody is wanted now: our own views with it (lift over the channel median), how often it shows
    up in viral satisfying Shorts (trends.py, daily), the designer's viral-song research (config/sims_music.json,
    twice a day) – and a little less if it ran recently. Melodies without data stay neutral, so new ones get tried."""
    now = now or dt.datetime.now(dt.timezone.utc)
    videos = state.get("videos", [])
    aged = [v for v in videos if (v.get("stats") or v.get("yt_views"))
            and now - dt.datetime.fromisoformat(v["date"]) > dt.timedelta(hours=12)]
    base = statistics.median([score(v) for v in aged[-40:]]) if aged else 0
    trend = load(TUNING, {}).get("melody_trend") or {}
    music = load(MUSIC, {})
    until = music.get("seasonal_until") or {}
    boost = {m: f for m, f in (music.get("boost") or {}).items() if until.get(m, "9999") > now.date().isoformat()}
    recent = Counter(v["melody"] for v in videos[-8:])
    out = {}
    for m in sims.MELODIES:
        mine = [min(4.0, score(v) / base) for v in aged if v["melody"] == m] if base else []
        lift = statistics.mean(mine) if mine else 1.0
        w = (max(0.25, lift) ** 0.8) * (1 + 3 * trend.get(m, 0.0)) * float(boost.get(m, 1.0)) / (1 + recent[m])
        out[m] = {"posts": len(mine), "lift": round(lift, 2), "trend": trend.get(m, 0.0),
                  "boost": float(boost.get(m, 1.0)), "recent": recent[m], "weight": round(w, 3)}
    return out


def standouts(state: dict) -> list[str]:
    """Kinds that performed notably well – the only ones that may be posted again (best first)."""
    base, perf = performance(state)
    if not base or sum(n for _, n, _ in perf.values()) < 5:
        return []
    return sorted((k for k, (r, _, _) in perf.items() if r >= STANDOUT), key=lambda k: -perf[k][0])


def concept_queue(cfg: dict, state: dict) -> list[str]:
    """Concepts that were never posted: built-in kinds first, then designed concepts, oldest first."""
    posted = {v["kind"] for v in state.get("videos", [])}
    broken = set(state.get("broken", {}))
    builtin = [k for k in cfg["kinds"] if k in sims.KINDS and not sims.KINDS[k].concept]
    designed = sorted((k for k, c in sims.KINDS.items() if c.concept), key=lambda k: sims.KINDS[k].concept.get("created", ""))
    return [k for k in builtin + designed if k not in posted and k not in broken]


def plan(cfg: dict, state: dict) -> tuple[str, int, str, str]:
    """Next kind (a new concept if one is ready, else a performance-weighted variant of one that already ran),
    a fresh seed with a good length, a melody weighted by what goes viral (melody_weights), and why this kind was
    chosen."""
    videos = state.get("videos", [])
    tuning = load(TUNING, {})
    broken = set(state.get("broken", {}))
    queue = concept_queue(cfg, state)
    if queue:
        kind, why = queue[0], "new"
    else:
        _, perf = performance(state)
        stars = set(standouts(state))
        recent = [v["kind"] for v in videos[-3:]]
        used = Counter(v["kind"] for v in videos[-12:])
        pool = [k for k in dict.fromkeys(v["kind"] for v in videos) if k in sims.KINDS and k not in broken]
        cands = [k for k in pool if k not in recent] or [k for k in pool if k != (recent or [None])[-1]] or pool
        weights = [max(0.15, perf.get(k, (1.0,))[0]) ** 1.5 * (3 if k in stars else 1) / (1 + used[k])
                   * (2 if sims.KINDS[k].full_frame and perf.get(k, (1.0, 0))[1] < 4 else 1)  # the owner wants more
                   for k in cands]                                                            # 3D until views decide
        kind = random.Random(len(videos) * 7919).choices(cands, weights=weights)[0]
        why = "standout" if kind in stars else "rotation"
    start = max((v["seed"] for v in videos if v["kind"] == kind), default=-1) + 1
    ranges = sims.KINDS[kind].run_ranges or RANGES
    lo, hi = ranges[len(videos) % len(ranges)]
    a, b = min(r[0] for r in ranges), max(r[1] for r in ranges)
    for args in ((lo, hi, 60), (a - 2, b + 6, 150), (a - 12, b + 9, 300)):  # some vary a lot; render() stretches short ones
        try:
            seed = sims.pick_seed(kind, start, *args)
            break
        except RuntimeError:
            continue
    else:
        raise RuntimeError(f"{kind}: no seed with a usable length")
    last_tune = videos[-1]["melody"] if videos else None
    mw = melody_weights(state)
    tunes = [m for m in sims.MELODIES if m != last_tune] or list(sims.MELODIES)
    melody = random.Random(len(videos) * 104729 + seed).choices(tunes, weights=[mw[m]["weight"] for m in tunes])[0]
    return kind, seed, melody, why


def last_slot(now: dt.datetime) -> dt.datetime:
    day = now.replace(second=0, microsecond=0)
    times = [day.replace(hour=h, minute=m) - dt.timedelta(days=d) for d in (0, 1) for h, m in SLOTS]
    return max(t for t in times if t <= now)


def next_slot(now: dt.datetime) -> dt.datetime:
    day = now.replace(second=0, microsecond=0)
    times = [day.replace(hour=h, minute=m) + dt.timedelta(days=d) for d in (0, 1) for h, m in SLOTS]
    return min(t for t in times if t > now)


def slot_due(state: dict, now: dt.datetime | None = None) -> bool:
    """Is a posting slot open that has no post yet?"""
    now = now or dt.datetime.now(dt.timezone.utc)
    slot = last_slot(now)
    if now - slot > SLOT_WINDOW:
        return False
    videos = state.get("videos", [])
    return not videos or dt.datetime.fromisoformat(videos[-1]["date"]) < slot - dt.timedelta(minutes=45)


def _fmt(template: str, params: dict) -> str:
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        return params["onscreen"]


def rewards_length(rec: dict) -> bool:
    """A finished video of full length: over a minute (TikTok's Creator Rewards), or as long as its concept wants
    (short-format experiments are shorter on purpose and go to TikTok too). Old short videos stay out."""
    cls = sims.KINDS.get(rec.get("kind"))
    return rec.get("duration", 0) >= (cls.min_video if cls else sims.MIN_VIDEO) - 0.5


def tiktok_waiting(state: dict) -> int:
    """Drafts of over-a-minute videos still waiting in the owner's TikTok inbox (older short ones don't block)."""
    return sum(1 for r in state.get("videos", []) if rewards_length(r)
               and (r.get("tiktok") or {}).get("status") not in (None, "PUBLISH_COMPLETE", "FAILED"))


def tiktok_backlog(cfg: dict, state: dict, max_pending: int = TIKTOK_PENDING, files: dict[str, Path] | None = None) -> int:
    """Send over-a-minute videos that are not on TikTok yet as drafts – best performers first – while at most
    max_pending of them wait in the owner's inbox. Videos come from `files` ("kind-seed" -> path) or the release."""
    import time

    import requests

    videos = state.get("videos", [])
    pending = tiktok_waiting(state)
    todo = sorted((r for r in videos if not r.get("tiktok") and not r.get("tiktok_skip")
                   and (rewards_length(r) or files)), key=lambda r: -score(r))
    repo = os.environ.get("GITHUB_REPOSITORY", "hthkrksy54-dotcom/Yt")
    sent = 0
    for r in todo:
        if pending >= max_pending:
            break
        name = f"{r['kind']}-{r['seed']}"
        path = (files or {}).get(name)
        if not path:
            if not r.get("release"):
                continue
            tag = r["release"].rsplit("/", 1)[1]
            res = requests.get(f"https://github.com/{repo}/releases/download/{tag}/loop-physics-{tag[5:]}.mp4", timeout=300)
            if res.status_code == 404:
                r["tiktok_skip"] = "video no longer archived"
                continue
            res.raise_for_status()
            path = OUT / f"tiktok-{name}.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(res.content)
        try:
            draft = tiktok.send_draft(cfg, Path(path), wait=60)
        except tiktok.TikTokError as err:
            print(f"  tiktok: {name} not sent: {err}", flush=True)
            if re.search(r"spam|pending|rate|too_many|limit", str(err), re.I):
                break  # TikTok wants fewer drafts at once: the next heartbeat goes on
            r["tiktok_skip"] = str(err)[:200]
            continue
        r["tiktok"] = {**draft, "caption": tiktok_caption(r["kind"], metadata(r["kind"], r["seed"], r["melody"], cfg,
                                                                             r.get("quiz", False)), r["seed"])}
        print(f"  tiktok: {name} sent as a draft ({draft['status']})", flush=True)
        pending += 1
        sent += 1
        time.sleep(12)  # TikTok allows 6 upload starts per minute
    return sent


QUIZ_QUESTION = "Which song is this? 🎵 Write it in the comments!"
QUIZ_START = "2026-10-20"


def song_quiz(kind: str, state: dict) -> bool:
    """Song quiz experiment: a share of the videos (config/sims_music.json → song_quiz_share) hides the melody's name
    and asks the viewers to name the song in the comments. Only kinds whose hits play the melody take part."""
    if sims.KINDS[kind].credit is not sims.Sim.credit:
        return False
    share = load(MUSIC, {}).get("song_quiz_share", 0.5)
    return random.Random(f"quiz-{len(state.get('videos', []))}").random() < share


def follower_report(state: dict) -> str:
    """Followers now and gained over the last 7 days (daily counts from the trend check)."""
    hist = state.get("followers") or []
    parts = []
    for key, name in (("instagram", "Instagram"), ("youtube", "YouTube")):
        pts = [h for h in hist if h.get(key) is not None]
        if not pts:
            continue
        week = [h for h in pts if h["date"] >= (dt.date.fromisoformat(pts[-1]["date"]) - dt.timedelta(days=7)).isoformat()]
        days = (dt.date.fromisoformat(week[-1]["date"]) - dt.date.fromisoformat(week[0]["date"])).days
        parts.append(f"{name} {pts[-1][key]} ({week[-1][key] - week[0][key]:+d} in {days} d)")
    return "followers    " + (" · ".join(parts) if parts else "– (daily counts start with the next trend check)")


def quiz_report(state: dict) -> str:
    """Song quiz vs not (videos with melody since the start of the test): views factor and comments per post."""
    base, _ = performance(state)
    now = dt.datetime.now(dt.timezone.utc)
    rows = {True: [], False: []}
    for v in state.get("videos", []):
        cls = sims.KINDS.get(v["kind"])
        if (v["date"] < QUIZ_START or not cls or cls.credit is not sims.Sim.credit or not base
                or not (v.get("stats") or v.get("yt_views"))
                or now - dt.datetime.fromisoformat(v["date"]) < dt.timedelta(hours=12)):
            continue
        rows[bool(v.get("quiz"))].append((score(v) / base, (v.get("stats") or {}).get("comments", 0)))

    def side(rs: list) -> str:
        if not rs:
            return "– (0)"
        return (f"×{statistics.median(r for r, _ in rs):.2f} views, "
                f"{sum(c for _, c in rs) / len(rs):.1f} comments ({len(rs)})")
    share = load(MUSIC, {}).get("song_quiz_share", 0.5)
    return f"song quiz    with {side(rows[True])} vs without {side(rows[False])} · share {share:.0%}"


def onscreen(lines: list[str]) -> str:
    """The on-screen title as one line: 'Which color' + 'wins the race?', 'Every hit upgrades it – Who wins…'."""
    out = lines[0] if lines else ""
    for line in lines[1:]:
        sep = " – " if line[:1].isupper() and not re.search(r"[?!.,:;–-]$", out) else " "
        out += sep + line
    return out


def metadata(kind: str, seed: int, melody: str, cfg: dict, quiz: bool = False,
             prev: str | None = None, next_id: str | None = None) -> dict:
    """Title, YouTube description, Instagram caption and tags. prev/next_id: YouTube ids of the neighbouring
    episodes of a numbered series, linked in the description so one episode leads to the next."""
    rnd = random.Random(seed * 31 + len(kind))
    song_full = sims.MELODIES[melody][0]
    song = song_full.split(" – ")[0]
    if quiz:  # song quiz: the name stays out of every visible text – the comments name it
        song = song_full = "a famous melody"
    cls = sims.KINDS[kind]
    sim = cls(seed)
    params = {"n": getattr(sim, "n", ""), "k": getattr(sim, "K", ""), "song": song, "onscreen": onscreen(sim.title()),
              "delta": sims._decimal(sim.delta) if isinstance(getattr(sim, "delta", None), float) else ""}
    tuning = load(TUNING, {})
    title = _fmt(rnd.choice(cls.titles or TITLES.get(kind, ["{onscreen}"])), params)
    addons = [a for a in tuning.get("title_addons") or []
              if "?" not in a and not (kind in ("pendulum", "chaos", "harmonograph") and "bounce" in a.lower())
              and not re.search(r"guess|name|song|melod", a, re.I)]  # the song name is on screen (or it is the quiz)
    if quiz:
        title = f"{params['onscreen']} – Can you name the song?"
        title = title if len(title) <= 95 else "Can you name the song? Watch till the end"
    elif addons and rnd.random() < 0.5:  # half the time: the on-screen question plus a trending add-on
        with_addon = f"{params['onscreen']} – {rnd.choice(addons)}"
        title = with_addon if len(with_addon) <= 95 else title
    generic = [q for q in tuning.get("questions") or []
               if not re.search(r"\b(rings?|pendulums?|plinko|colou?rs?|polygons?|balls? wins?|escap\w*|marbles?|races?)\b",
                                q, re.I) and not re.search(r"song|melod", q, re.I)]  # the description names the song
    question = rnd.choice((cls.questions or QUESTIONS.get(kind, ["Did you recognise the melody?"])) + generic[:3])
    if quiz:
        question = QUIZ_QUESTION
    tags_line = " ".join(["#satisfying"] + [f"#{t}" for t in (tuning.get("hashtags") or []) if t != "satisfying"][:3]) \
        if tuning.get("hashtags") else cfg["instagram"].get("hashtags", "")
    composer = "" if quiz else COMPOSERS.get(melody, "")
    what = cls.body or BODIES.get(kind) or (
        TIKTOK_WHAT[kind] + " Every bounce plays the next note of {song}." if kind in TIKTOK_WHAT
        else "Every bounce plays the next note of {song}.")
    what = _fmt(what, {**params, "song": song_full})
    body = what + ("" if re.search(r"simulated", what, re.I) else
                   "\nPhysics, picture and sound are all generated in code – no two runs are the same.")
    music = ("🎵 The melody is a public-domain classic, played note by note by the simulation – no recording is used."
             if quiz else f"🎵 Music: {song_full} (public domain), played note by note by the simulation – "
                          "no recording is used.")  # says so up front, for any false copyright claim
    # the first line is what search and the expanded Short show: the question in the video, in plain words
    lead = params["onscreen"].rstrip() + ("" if re.search(r"[?!.]$", params["onscreen"].rstrip()) else ".")
    lead += (" Name the song before the finale." if quiz else
                                 f" A satisfying physics simulation to {song}." if song else "")
    series = re.match(r"([A-Z][A-Za-z ]{1,20}) #(\d+)", what) if cls.experiment == "series" else None
    episodes = [f"◀ Previous episode: https://youtube.com/shorts/{prev}" if prev else "",
                f"▶ Next episode: https://youtube.com/shorts/{next_id}" if next_id else ""]
    follow = (f"🔔 Subscribe so you don't miss {series.group(1)} #{int(series.group(2)) + 1}." if series and not next_id
              else f"🔔 Subscribe to {cfg['channel_name']} – a new simulation every few hours, each one built to a finale.")
    description = "\n\n".join(x for x in [
        lead,
        body,
        "\n".join(e for e in episodes if e),
        music,
        f"💬 {question}",
        follow,
        " ".join(["#satisfying", "#physics", "#simulation"] + ([f"#{composer.lower()}"] if composer else [])
                 + ["#shorts"]),
    ] if x)
    caption = "\n\n".join([
        title,
        body,
        f"💬 {question}",
        ("📩 Send this to someone who'll know the song." if quiz
         else "📩 Send this to someone who can't stop watching these."),
        f"Follow {cfg['handle']} – a new simulation every few hours."
        + (f"\n▶ YouTube: {cfg['youtube']['channel_url']}" if cfg["youtube"].get("channel_url") else ""),
        (tags_line + (f" #{composer.lower()}" if composer else "")).strip(),
    ])
    return {"title": title[:95], "description": description, "caption": caption[:2150], "question": question,
            "onscreen": params["onscreen"], "quiz": quiz,
            "tags": list(dict.fromkeys(TAGS + [t for t in (song.lower(), composer.lower()) if t]
                                       + (tuning.get("hashtags") or [])[:4]))}


def neighbours(records: list[dict], kind: str, seed: int) -> tuple[str | None, str | None]:
    """YouTube ids of the episodes before and after this one in a numbered series (episode = seed + 1)."""
    if sims.KINDS[kind].experiment != "series":
        return None, None
    ids = {r["seed"]: r["youtube_id"] for r in records if r["kind"] == kind and r.get("youtube_id")}
    return ids.get(seed - 1), ids.get(seed + 1)


def describe(token: str, rec: dict, records: list[dict], cfg: dict) -> str:
    """Give one upload the current description (with links to its neighbouring episodes); title and tags stay
    as they are on YouTube. Returns the new description."""
    import requests

    api, h = "https://www.googleapis.com/youtube/v3", {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{api}/videos", params={"part": "snippet", "id": rec["youtube_id"]}, headers=h, timeout=30)
    r.raise_for_status()
    items = r.json().get("items") or []
    if not items:
        raise RuntimeError(f"{rec['youtube_id']} not found on the channel")
    sn = items[0]["snippet"]
    prev, nxt = neighbours(records, rec["kind"], rec["seed"])
    desc = metadata(rec["kind"], rec["seed"], rec["melody"], cfg, rec.get("quiz", False), prev, nxt)["description"]
    keep = {k: sn[k] for k in ("tags", "defaultLanguage", "defaultAudioLanguage") if sn.get(k)}  # PUT drops what it lacks
    r = requests.put(f"{api}/videos", params={"part": "snippet"}, headers={**h, "Content-Type": "application/json"},
                     data=json.dumps({"id": rec["youtube_id"], "snippet": {
                         "title": sn["title"], "categoryId": sn["categoryId"], "description": desc, **keep}}),
                     timeout=60)
    if not r.ok:
        raise RuntimeError(f"videos.update failed ({r.status_code}): {r.text[:200]}")
    return desc


def youtube_describe(last: int = 4) -> None:
    """The newest `last` uploads get the current description template (run once after the template changes)."""
    cfg, state = load(CONFIG, {}), load(STATE, {"videos": []})
    token = _youtube_token(cfg)
    if not token:
        raise SystemExit("YouTube token or client credentials missing")
    records = state.get("videos", [])
    for rec in [r for r in records if r.get("youtube_id")][-last:]:
        print(f"== https://youtube.com/shorts/{rec['youtube_id']} ({rec['kind']}-{rec['seed']})\n"
              f"{describe(token, rec, records, cfg)}\n", flush=True)


def _youtube_token(cfg: dict) -> str | None:
    path = ROOT / cfg["youtube"]["token_file"]
    if not (path.exists() and os.environ.get("IG_TOKEN_KEY") and os.environ.get("YT_CLIENT_ID")):
        return None
    data = json.loads(Fernet(os.environ["IG_TOKEN_KEY"].strip().encode()).decrypt(path.read_bytes().strip()))
    return youtube.access_token_from(data["refresh_token"])


def story_clip(video: Path) -> Path | None:
    """The first STORY_CLIP seconds as a teaser for the Instagram story (stories take at most 60 s)."""
    import subprocess

    out = video.with_name(video.stem + "-story.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-t", str(STORY_CLIP), "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-af", f"afade=t=out:st={STORY_CLIP - 1.5}:d=1.5", "-movflags", "+faststart", str(out)]
    if subprocess.run(cmd).returncode != 0:
        print("  warning: story clip failed – no story this time", flush=True)
        return None
    return out


def backfill_reels() -> int:
    """Post the videos whose Reel failed (Instagram not reachable) as Reels now, oldest first, without stories,
    while their release – the public video URL – still exists. Returns how many went out."""
    cfg, state = load(CONFIG, {}), load(STATE, {"videos": []})
    if not instagram.configured(cfg):
        print("[sims] Instagram not connected – no Reels to catch up", flush=True)
        return 0
    repo = os.environ.get("GITHUB_REPOSITORY", "hthkrksy54-dotcom/Yt")
    now = dt.datetime.now(dt.timezone.utc)
    todo = [r for r in state["videos"] if not r.get("instagram_id") and r.get("release")
            and now - dt.datetime.fromisoformat(r["date"]) < dt.timedelta(days=9)]  # releases are kept 10 days
    posted = 0
    for rec in todo:
        tag = rec["release"].rsplit("/", 1)[1]
        try:
            meta = metadata(rec["kind"], rec["seed"], rec["melody"], cfg, rec.get("quiz", False))
            cls = sims.KINDS.get(rec["kind"])
            share = cls.cover_at if cls and cls.cover_at is not None else COVER_AT.get(rec["kind"], 0.5)
            rec.update(instagram.post_reel(
                cfg, f"https://github.com/{repo}/releases/download/{tag}/loop-physics-{tag[5:]}.mp4",
                meta["caption"], story=False, label=meta["title"],
                thumb_offset_ms=int(1000 * (rec["duration"] - sims.OUTRO) * share)))
        except Exception as err:  # noqa: BLE001 – the next one may still work
            print(f"  warning: reel for {tag} failed: {err}", flush=True)
            continue
        posted += 1
        save(STATE, state)
        print(f"  reel {posted}/{len(todo)}: {rec.get('instagram_url')} ({rec['kind']})", flush=True)
    print(f"[sims] caught up {posted} of {len(todo)} missing Reels", flush=True)
    return posted


def planned_run() -> bool:
    """Started by the schedule or the timer (posts only in an open slot), not by hand."""
    return os.environ.get("GITHUB_EVENT_NAME") == "schedule" or os.environ.get("IN_SOURCE") in ("timer", "watchdog")


def run(upload: bool = True) -> dict:
    cfg = load(CONFIG, {})
    state = load(STATE, {"videos": []})
    ig_error = None
    if upload and instagram.configured(cfg):
        try:  # a blocked or expired token: the video still goes out everywhere else, the run ends red
            instagram._user(instagram.fresh_token(cfg))
        except instagram.InstagramError as err:
            ig_error = f"Instagram access for @{cfg['instagram']['account']} is not working: {err}"
            print(f"  warning: {ig_error}", flush=True)
        if not ig_error:
            try:
                used, total = instagram.publishing_quota(cfg)
            except instagram.InstagramError as err:
                print(f"  warning: {err}", flush=True)
                used, total = 0, 100
            if used >= total - 3:
                print(f"[sims] Instagram publishing limit nearly used ({used}/{total} in 24 h) – skipping this hour",
                      flush=True)
                return {}
    if planned_run() and not slot_due(state):
        print("[sims] no open posting slot – nothing to post", flush=True)
        return {}
    for attempt in range(3):  # a concept that fails is set aside and the next one goes out instead
        kind, seed, melody, why = plan(cfg, state)
        stamp = dt.datetime.now(dt.timezone.utc)
        name = f"{stamp:%Y%m%d}-{kind}-{seed}"
        quiz = song_quiz(kind, state)
        try:
            meta = metadata(kind, seed, melody, cfg, quiz, neighbours(state.get("videos", []), kind, seed)[0])
            print(f"[sims] {name} ({why}): {meta['title']} ({sims.MELODIES[melody][0]}{', song quiz' if quiz else ''})",
                  flush=True)
            result = sims.render(kind, seed, OUT / f"{name}.mp4", melody, cfg.get("handle", ""), quiz=quiz)
            break
        except Exception as err:  # noqa: BLE001
            state.setdefault("broken", {})[kind] = f"{stamp:%Y-%m-%d %H:%M} {type(err).__name__}: {err}"[:300]
            save(STATE, state)
            print(f"  warning: {kind} failed and is set aside: {err}", flush=True)
    else:
        raise SystemExit("[sims] no concept could be rendered")
    cls = sims.KINDS[kind]
    record = {"date": stamp.isoformat(timespec="seconds"), "kind": kind, "seed": seed, "melody": melody,
              "timbre": result.get("timbre"), "title": meta["title"], "duration": round(result["duration"], 1),
              "why": why, "quiz": quiz}
    if quiz:
        record["tiktok_note"] = "Song-Rätsel: Originalton behalten (keinen anderen Sound wählen) – die Frage dreht sich um die Melodie."
    if cls.concept:
        record["concept"] = cls.concept.get("idea", "")
    if not upload:
        print(f"  rendered {result['video']} ({result['duration']:.1f}s)", flush=True)
        return record

    body = "\n".join(["### Title", "```", meta["title"], "```", "### Description", "```", meta["description"], "```",
                      "### Tags", "```", ", ".join(meta["tags"]), "```"])
    files = [(result["video"], f"loop-physics-{name}.mp4", "video/mp4")]
    clip = story_clip(Path(result["video"])) if result["duration"] > 59.5 else None
    if clip:
        files.append((clip, f"loop-physics-{name}-story.mp4", "video/mp4"))
    rel = publish.github_release(f"sims-{name}", f"[Loop Physics] {meta['title']}", body, files)
    if drive := gdrive.save(cfg["channel_name"], meta["title"], files, body):
        record["drive"] = drive
    video_url = rel.get("assets", {}).get(f"loop-physics-{name}.mp4")
    story_url = rel.get("assets", {}).get(f"loop-physics-{name}-story.mp4")
    if rel:
        record["release"] = rel["release"]
    if ig_error:
        record.setdefault("warnings", []).append(f"instagram: {ig_error}"[:300])
    elif video_url and instagram.configured(cfg):
        try:
            story = len(state.get("videos", [])) % STORY_EVERY == 0
            share = cls.cover_at if cls.cover_at is not None else COVER_AT.get(kind, 0.5)
            cover_ms = int(1000 * (result["duration"] - sims.OUTRO) * share)
            record.update(instagram.post_reel(cfg, video_url, meta["caption"], story=story and bool(story_url or not clip),
                                              label=meta["title"], thumb_offset_ms=cover_ms, story_url=story_url))
        except Exception as err:  # one platform failing must not lose the run
            record.setdefault("warnings", []).append(f"instagram: {err}")
            print(f"  warning: instagram failed: {err}", flush=True)
    if tiktok.configured(cfg) and tiktok_waiting(state) < TIKTOK_PENDING:  # every video, like the Reel
        try:  # a draft in the owner's TikTok inbox: one tap to post (TikTok wants the creator to confirm)
            cap = tiktok_caption(kind, meta, seed)
            record["tiktok"] = {**tiktok.send_draft(cfg, Path(result["video"])), "caption": cap}
            print(f"  tiktok: draft {record['tiktok']['status']}", flush=True)
        except Exception as err:  # noqa: BLE001
            record.setdefault("warnings", []).append(f"tiktok: {err}")
            print(f"  warning: tiktok failed: {err}", flush=True)
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
    prev = neighbours(state["videos"], kind, seed)[0]
    if prev and record.get("youtube_id"):  # the episode before now links on to this one
        try:
            describe(token, next(r for r in state["videos"] if r.get("youtube_id") == prev), state["videos"], cfg)
            print(f"  youtube: previous episode {prev} now links here", flush=True)
        except Exception as err:  # noqa: BLE001
            print(f"  warning: link from the previous episode failed: {err}", flush=True)
    if record.get("tiktok"):
        tiktok.write_queue(state["videos"], cfg["channel_name"], tips=sound_tips())
    removed = publish.cleanup_releases("sims-", keep_days=10)  # Instagram keeps its own copy
    if removed:
        print(f"  removed {removed} old releases", flush=True)
    if _youtube_token(cfg):
        try:  # give videos the owner uploaded by hand our title, description, tags and playlist
            youtube_polish(apply=True)
        except (Exception, SystemExit) as err:
            print(f"  warning: youtube polish failed: {err}", flush=True)
    if ig_error:  # everything else is done and saved – fail loudly so the problem gets noticed
        raise SystemExit(f"[sims] posted without Instagram – {ig_error}")
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
    "territory": ("Which color conquers the board?", "Pong-wars style territory battles – pick your colour."),
    "chaos": ("Chaos – the butterfly effect", "Double pendulums that start a hair apart and end up worlds apart."),
    "harmonograph": ("Pendulum drawings", "A harmonograph draws a new figure every time."),
    "race": ("Marble races", "Pick a colour – the first ball over the finish line wins."),
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
        recent = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=4)
        free = [r for r in records if not r.get("youtube_id") and abs(r.get("duration", 0) - secs) <= 1.5
                and dt.datetime.fromisoformat(r["date"]) > recent]
        near = sorted(free, key=lambda r: abs(r.get("duration", 0) - secs))
        rec = rec or next((r for r in free if f"{r['kind']}-{r['seed']}" in fname), None) \
            or next((r for r in free if r["kind"] in fname), None) \
            or next((r for r in free if _norm(r["title"]) == title), None) \
            or (free[0] if len(free) == 1 else None) \
            or (near[0] if len(near) > 1 and abs(near[0]["duration"] - secs) < 0.8  # clearly the closest length
                and abs(near[1]["duration"] - secs) - abs(near[0]["duration"] - secs) >= 0.5 else None)
        print(f"  {v['id']} {secs:3d}s views={v['statistics'].get('viewCount', 0):>5} file={fname[:38]!r:40} "
              f"title={v['snippet']['title'][:45]!r} -> {rec['kind'] + '-' + str(rec['seed']) if rec else 'NO MATCH'}",
              flush=True)
        if rec and v["id"] not in taken:
            matches.append((v, rec))
            rec["youtube_id"] = v["id"]
            taken.add(v["id"])
    views = {v["id"]: int(v["statistics"].get("viewCount", 0)) for v in videos}
    for r in records:  # own views per post, for spotting standouts
        if r.get("youtube_id") in views:
            r["yt_views"] = views[r["youtube_id"]]
    if not apply:
        for pl in get("playlists", part="snippet,contentDetails", mine="true", maxResults=50).get("items", []):
            print(f"  playlist {pl['id']} {pl['contentDetails']['itemCount']} videos: {pl['snippet']['title']}", flush=True)
        print(f"dry run: {len(matches)} uploads would be updated", flush=True)
        return

    existing = {p["snippet"]["title"]: p["id"] for p in get("playlists", part="snippet", mine="true",
                                                            maxResults=50).get("items", [])}
    for v, rec in matches:
        meta = metadata(rec["kind"], rec["seed"], rec["melody"], cfg, rec.get("quiz", False))
        send("PUT", "videos", "snippet", {"id": v["id"], "snippet": {
            "title": meta["title"], "description": meta["description"], "tags": meta["tags"],
            "categoryId": cfg["youtube"]["category_id"], "defaultLanguage": cfg["youtube"]["default_language"]}})
        cls = sims.KINDS.get(rec["kind"])
        name, about = PLAYLISTS.get(rec["kind"]) or (cls and cls.playlist) or EXPERIMENTS
        if name not in existing:
            existing[name] = send("POST", "playlists", "snippet,status", {
                "snippet": {"title": name, "description": f"{about} A brand-new concept twice a day on Loop Physics.",
                            "defaultLanguage": "en"}, "status": {"privacyStatus": "public"}})["id"]
            time.sleep(8)  # new playlists take a moment before YouTube accepts items
        have = requests.get(f"{api}/playlistItems", headers=h, timeout=30,
                            params={"part": "id", "playlistId": existing[name], "videoId": v["id"]})
        if not (have.ok and have.json().get("items")):
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
