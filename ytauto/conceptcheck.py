"""Quality gate for Loop Physics concepts: python -m ytauto concept-check <kind> [--full] | --all

Checks what makes a concept postable – it imports, describes itself, is deterministic, finds seeds with a good
length, makes sound, ends with a finale, fits its text on screen and paints fast enough – and writes a contact
sheet (out/concepts/<kind>.png) to look at. With --full it also renders the whole video and checks its loudness.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw

from . import concepts, simchannel, sims

OUT = Path(__file__).resolve().parent.parent / "out" / "concepts"
RANGES = [(58, 66), (62, 72), (66, 78), (72, 86)]  # every video must run longer than a minute (TikTok rewards)
SOUND = {"bounce", "land", "tone", "clack", "break"}


def check(kind: str, full: bool = False, quiet: bool = False) -> bool:
    problems: list[str] = []
    info: list[str] = []

    def say(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    if kind not in sims.KINDS:
        broken = {k: v for k, v in concepts.BROKEN.items() if k == kind or kind in v}
        say(f"FAIL {kind}: not found" + (f" – import error:\n{next(iter(broken.values()))}" if broken else ""))
        return False
    cls = sims.KINDS[kind]

    # 1) self-description (designed concepts)
    if cls.concept:
        for key in ("created", "idea", "finale"):
            if not cls.concept.get(key):
                problems.append(f"concept['{key}'] missing")
        try:
            dt.datetime.fromisoformat(cls.concept.get("created", ""))
        except ValueError:
            problems.append("concept['created'] is not an ISO time")
        if not cls.titles or len(cls.titles) < 2:
            problems.append("needs at least 2 titles")
        if not cls.questions:
            problems.append("needs at least 1 question")
        if not cls.body:
            problems.append("needs a body text")
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,30}", kind):
            problems.append("kind must be lowercase letters/digits/underscore")

    # 2) seeds with a good length, determinism
    t0 = time.time()
    seeds = {}
    for lo, hi in RANGES:
        try:
            seeds[(lo, hi)] = sims.pick_seed(kind, 0, lo, hi, tries=40)
        except RuntimeError:
            pass
        except Exception as err:  # noqa: BLE001
            problems.append(f"simulation crashed: {type(err).__name__}: {err}")
            break
    search = time.time() - t0
    if len(seeds) < 2:
        problems.append(f"only {len(seeds)} of {len(RANGES)} length ranges reachable within 40 seeds "
                        f"(runs must end between 58 and 86 s – videos are longer than a minute)")
    if search > 240:
        problems.append(f"seed search too slow ({search:.0f}s) – simulate() must be much faster")
    if not seeds:
        return _verdict(kind, problems, info, say)
    seed = next(iter(seeds.values()))
    a, b = sims.simulate(kind, seed), sims.simulate(kind, seed)
    if a.end != b.end or len(a.events) != len(b.events):
        problems.append("not deterministic (use self.rnd for physics, never random/time/global state)")
    sounds = sum(1 for _, k, _ in a.events if k in SOUND)
    if sounds < 12:
        problems.append(f"only {sounds} sound events – the melody needs bounce/land/tone events")
    if not any(k == "finale" for _, k, _ in a.events):
        problems.append("no finale event (call self.finish())")
    info.append(f"seeds {', '.join(f'{lo}-{hi}s: {s}' for (lo, hi), s in seeds.items())} · "
                f"{sounds} sound events · run {a.end:.1f}s")

    # 3) texts fit, metadata renders
    sim = cls(seed)
    painter = sims.Painter(sim, sim.credit("Für Elise – Beethoven"), "@loop_physics")
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    for line in sim.title():
        if d.textlength(line, font=painter.f_title) > sims.W - 60:
            problems.append(f"title line too wide: {line!r} (max ~24 characters)")
    if len(sim.title()) > 2:
        problems.append("title() must have at most 2 lines")
    try:
        meta = simchannel.metadata(kind, seed, "fur_elise", simchannel.load(simchannel.CONFIG, {}))
        info.append(f"title: {meta['title']}")
        if len(meta["title"]) > 95:
            problems.append("YouTube title longer than 95 characters")
    except Exception as err:  # noqa: BLE001
        problems.append(f"metadata failed: {type(err).__name__}: {err}")

    # 4) paint: sample the run, measure the time per frame, save a contact sheet
    end = a.end
    shots_at = [f * end for f in (0.03, 0.2, 0.4, 0.6, 0.8, 0.95, 0.995)] + [end + 1.0]
    dt_ = 1 / (sims.FPS * sims.SUBSTEPS)
    shots, ms, every = [], [], max(1, int(sims.FPS * 0.25))
    frame = 0
    try:
        while shots_at:
            for _ in range(sims.SUBSTEPS):
                sim.step(dt_)
            frame += 1
            if frame % every == 0 or sim.t >= shots_at[0]:
                t1 = time.time()
                img = painter.frame(every / sims.FPS)
                ms.append(1000 * (time.time() - t1))
                if sim.t >= shots_at[0]:
                    shots.append(img.resize((270, 480)))
                    shots_at.pop(0)
    except Exception as err:  # noqa: BLE001
        problems.append(f"drawing crashed: {type(err).__name__}: {err}")
    if shots:
        OUT.mkdir(parents=True, exist_ok=True)
        sheet = Image.new("RGB", (270 * len(shots), 480))
        for i, im in enumerate(shots):
            sheet.paste(im, (270 * i, 0))
        sheet.save(OUT / f"{kind}.png")
        info.append(f"contact sheet: {OUT / f'{kind}.png'} (8 moments, the last one after the finale)")
    if ms:
        avg = sum(ms) / len(ms)
        info.append(f"paint {avg:.0f} ms/frame (max {max(ms):.0f})")
        if avg > 180:
            problems.append(f"painting too slow: {avg:.0f} ms/frame (limit 180)")

    # 5) the real video
    if full and not problems:
        melody = list(sims.MELODIES)[seed % len(sims.MELODIES)]
        t1 = time.time()
        res = sims.render(kind, seed, OUT / f"{kind}-{seed}.mp4", melody, "@loop_physics")
        took = time.time() - t1
        loud = subprocess.run(["ffmpeg", "-i", str(res["video"]), "-af", "ebur128", "-f", "null", "-"],
                              capture_output=True, text=True).stderr
        m = re.findall(r"I:\s+(-?[\d.]+) LUFS", loud)
        lufs = float(m[-1]) if m else math.nan
        info.append(f"video: {res['video']} ({res['duration']:.1f}s, {lufs:.1f} LUFS, rendered in {took:.0f}s"
                    f"{', slow motion' if res.get('slowmo') else ''})")
        if res["duration"] < sims.MIN_VIDEO:
            problems.append(f"video only {res['duration']:.1f}s – must be at least {sims.MIN_VIDEO:.0f}s")
        if res.get("stretch", 1) > 1.01:
            info.append(f"note: played {res['stretch']:.2f}× slower to reach {sims.MIN_VIDEO:.0f}s – aim for longer runs")
        if not -17 <= lufs <= -11:
            problems.append(f"loudness {lufs} LUFS outside -17…-11")
        if took > 1500:
            problems.append(f"render took {took:.0f}s – must stay well under the 60 min job limit")
    return _verdict(kind, problems, info, say)


def _verdict(kind: str, problems: list[str], info: list[str], say) -> bool:
    for line in info:
        say(f"  {line}")
    for p in problems:
        say(f"  ✗ {p}")
    say(f"{'PASS' if not problems else 'FAIL'} {kind}")
    return not problems


def listing(cfg: dict, state: dict) -> str:
    """Every concept with its status and numbers – what exists, what is queued, what performs."""
    base, perf = simchannel.performance(state)
    stars = set(simchannel.standouts(state))
    queue = simchannel.concept_queue(cfg, state)
    posted = {}
    for v in state.get("videos", []):
        posted[v["kind"]] = posted.get(v["kind"], 0) + 1
    lines = [f"channel median: {base:.0f} views per post (Instagram + YouTube, posts older than 12 h)",
             f"queue (next posts, oldest first): {', '.join(queue) or 'EMPTY – build a new concept!'}", ""]
    for kind, cls in sims.KINDS.items():
        r, n, best = perf.get(kind, (0.0, 0, 0))
        status = ("queued" if kind in queue else "broken" if kind in state.get("broken", {}) else
                  f"posted {posted.get(kind, 0)}x")
        idea = cls.concept.get("idea") if cls.concept else (cls.__doc__ or "").strip().split("\n")[0]
        lines.append(f"{kind:14} {status:11} {('×%.1f' % r) if n else '–':>5} {'STANDOUT' if kind in stars else '':8} "
                     f"{idea[:110]}")
    for name, err in concepts.BROKEN.items():
        lines.append(f"{name:14} IMPORT ERROR {err.strip().splitlines()[-1][:100]}")
    return "\n".join(lines)
