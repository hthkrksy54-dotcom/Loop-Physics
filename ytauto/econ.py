"""Third channel: Real Numbers – money and the economy explained with real data, in a keynote-style look
(black stage, crisp type, gradient figures, charts that draw themselves – see studio.py).

A script (content/econ/scripts/<id>.json) is a list of chapters; every chapter is a list of beats: one or two
sentences of narration ("say"), optionally what the stage shows from then on ("show": a scene from studio.SCENES
with its arguments; data can come straight from the World Bank) and a "mark" that points at something in the
current scene while the sentence is spoken (a year on a line chart, a row of a bar chart). This module turns a
script into the long video (1920x1080, 8–15 min), a vertical Short over one minute (TikTok rewards), a thumbnail,
captions and the upload texts.

  python -m ytauto econ render <id> [--short-only]
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import wave
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import requests

from . import gdrive, instagram, music, publish, render, studio, tiktok, tts, youtube
from .tts import SAMPLE_RATE

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "econ.json"
STATE = ROOT / "state" / "econ.json"
SCRIPTS = ROOT / "content" / "econ" / "scripts"
DATA = ROOT / "content" / "econ" / "data"
OUT = ROOT / "out" / "econ"
CAPTION = render.Format(1920, 1080, 0, 0, body_size=54, margin=120, max_chars=58, max_words=11)
CAPTION_V = render.Format(1080, 1920, 0, 0, body_size=66, margin=90, max_chars=26, max_words=6)


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


# ---------------------------------------------------------------- data


def worldbank(indicator: str, country: str) -> list[tuple[int, float]]:
    """Yearly values of a World Bank indicator (CC BY 4.0), cached in the repo so every render is reproducible."""
    path = DATA / f"wb-{indicator}-{country}.json"
    if not path.exists():
        r = requests.get(f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}",
                         params={"format": "json", "date": "1960:2100", "per_page": 5000}, timeout=60)
        r.raise_for_status()
        body = r.json()
        rows = body[1] if len(body) > 1 and body[1] else []
        points = sorted((int(x["date"]), float(x["value"])) for x in rows if x["value"] is not None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"indicator": indicator, "country": country, "source": "World Bank",
                                    "points": points}) + "\n", encoding="utf-8")
    return [tuple(p) for p in load(path, {})["points"]]


def series(spec: dict) -> list[tuple[float, float]]:
    """A data series from a spec: {"wb": indicator, "country"} | {"points": [...]} | {"compound": {...}};
    optional "from"/"to" years and "rebase": [year, value] (scale so that year has that value)."""
    if "wb" in spec:
        pts = worldbank(spec["wb"], spec["country"])
    elif "compound" in spec:
        c = spec["compound"]
        pts = [(y, c["start"] * (1 + c["rate"] / 100) ** y) for y in range(0, c["years"] + 1)]
    else:
        pts = [tuple(p) for p in spec["points"]]
    lo, hi = spec.get("from", -1e9), spec.get("to", 1e9)
    pts = [(x, y) for x, y in pts if lo <= x <= hi]
    if "rebase" in spec:
        year, value = spec["rebase"]
        base = dict(pts).get(year)
        pts = [(x, y / base * value) for x, y in pts]
    return pts


def _bars_items(show: dict) -> list[tuple[str, float]]:
    if "items" in show:
        return [(str(a), float(b)) for a, b in show["items"]]
    d = show["data"]
    items = []
    for name, code in d["countries"].items():
        pts = [(x, y) for x, y in worldbank(d["wb"], code) if d["mean"][0] <= x <= d["mean"][1]]
        items.append((name, sum(y for _, y in pts) / len(pts)))
    return sorted(items, key=lambda kv: kv[1]) if d.get("sort", True) else items


def _sub(show: dict) -> str:
    """The small grey line under a chart heading: where the numbers come from."""
    if "sub" in show:
        return show["sub"]
    if show["type"] == "line" and "wb" in show["series"][0]:
        s = show["series"][0]
        pts = series(s)
        return f"{studio.COUNTRIES.get(s['country'], s['country'])} · {int(pts[0][0])}–{int(pts[-1][0])} · World Bank"
    if show["type"] == "bars" and "data" in show:
        a, b = show["data"]["mean"]
        return f"Yearly average {a}–{b} · World Bank"
    return show.get("source", "") if show["type"] in ("bars", "coins", "columns") else ""


def _scene(L: studio.Layout, show: dict, dur: float, marks: list) -> list:
    kind = show["type"]
    color = show.get("color") or (show["series"][0].get("color") if kind == "line" else None)
    kw = {"color": color} if color else {}
    if kind == "line":
        data = [{"label": s.get("label", ""), "color": s.get("color"), "points": series(s)} for s in show["series"]]
        return studio.line(L, data, show.get("heading", ""), show.get("unit", ""), show.get("log", False), _sub(show),
                           dur, marks, **kw)
    if kind == "bars":
        return studio.bars(L, _bars_items(show), show.get("heading", ""), show.get("unit", ""), show.get("highlight"),
                           show.get("suffix", ""), _sub(show), marks, **kw)
    if kind in ("coins", "columns"):
        return studio.columns(L, show["stacks"], show.get("heading", ""), sub=_sub(show), **kw)
    if kind == "compare":
        return studio.compare(L, tuple(show["left"]), tuple(show["right"]), show.get("heading", ""), **kw)
    if kind == "number":
        return studio.number(L, show["big"], show.get("caption", ""), **kw)
    if kind == "note":
        return studio.note(L, show["text"], show.get("source", ""), **kw)
    if kind == "title":
        return studio.title(L, show["heading"], show.get("kicker", ""), **kw)
    raise ValueError(f"unknown scene type {kind!r}")


# ---------------------------------------------------------------- timeline


@dataclass
class Cut:
    start: float
    end: float
    scene: studio.Scene


@dataclass
class Timeline:
    layout: studio.Layout
    voice: str
    rate: str
    pitch: str
    t: float = 0.0
    cuts: list[Cut] = field(default_factory=list)
    audio: list[tuple[float, np.ndarray]] = field(default_factory=list)
    captions: list[tuple[float, float, str]] = field(default_factory=list)
    chapters: list[tuple[float, str]] = field(default_factory=list)
    foley: list[tuple[float, str]] = field(default_factory=list)

    def show(self, show: dict, dur: float, marks: list | None = None) -> None:
        self.foley.append((self.t, "swell" if show["type"] == "title" else "whoosh"))
        parts = _scene(self.layout, show, dur, marks or [])
        self.cuts.append(Cut(self.t, self.t + dur, studio.scene(self.layout, parts, dur)))
        self.t += dur

    def beats(self, beats: list[dict], caption_fmt: render.Format) -> None:
        """Narrate the beats; every "show" starts a new scene that lasts until the next one, every "mark"
        points at something in the current scene while its sentence is spoken."""
        speeches = [tts.synthesize(b["say"], self.voice, self.rate, self.pitch) for b in beats]
        i = 0
        while i < len(beats):
            j = i + 1
            while j < len(beats) and not beats[j].get("show"):
                j += 1
            dur = sum(sp.duration + 0.5 for sp in speeches[i:j]) + 0.3
            start = self.t
            show = beats[i].get("show") or {"type": "note", "text": beats[i]["say"][:120]}
            t = start + 0.25
            marks = []
            for b, sp in zip(beats[i:j], speeches[i:j]):
                if b.get("mark"):
                    marks.append((t - start, b["mark"]))
                self.audio.append((t, sp.audio))
                chunks = render._chunk(tts.align_tokens(b["say"], sp.words), caption_fmt)
                for k, c in enumerate(chunks):  # one line at a time: never two captions on screen
                    end = min(c.end + 0.15, chunks[k + 1].start - 0.02) if k + 1 < len(chunks) else c.end + 0.3
                    self.captions.append((t + c.start, t + end, c.text))
                t += sp.duration + 0.5
            self.show(show, dur, marks)
            i = j


def build_long(script: dict, cfg: dict) -> Timeline:
    tl = Timeline(studio.Layout(1920, 1080), cfg["voice"], cfg["rate"], cfg["pitch"])
    chapters = script["chapters"]
    tl.chapters.append((0.0, "Intro"))
    tl.beats(chapters[0]["beats"], CAPTION)  # the hook comes before the title
    tl.show({"type": "title", "heading": script["title_card"], "kicker": cfg["channel_name"]}, 3.6)
    for k, ch in enumerate(chapters[1:], 1):
        tl.chapters.append((tl.t, ch["heading"]))
        tl.show({"type": "title", "heading": ch["heading"], "kicker": f"Chapter {k}"}, 2.8)
        tl.beats(ch["beats"], CAPTION)
    tl.show({"type": "title", "heading": cfg["outro"], "kicker": cfg["channel_name"]}, 5.0)
    return tl


def build_short(script: dict, cfg: dict) -> Timeline:
    tl = Timeline(studio.Layout(1080, 1920), cfg["voice"], cfg["rate"], cfg["pitch"])
    sh = script["short"]
    tl.show({"type": "title", "heading": sh["hook"], "kicker": cfg["channel_name"], "color": "red"}, 2.2)
    for p in tl.cuts[0].scene.parts:  # the hook is already on screen in the first frame
        if hasattr(p, "t0"):
            p.t0 -= 1.4
    tl.beats(sh["beats"], CAPTION_V)
    tl.show({"type": "title", "heading": "Full story on the channel", "kicker": cfg["channel_name"]}, 2.6)
    if tl.t < 61.5:  # TikTok only rewards videos over a minute
        cut = tl.cuts[-1]
        cut.end += 61.5 - tl.t
        cut.scene.dur = cut.end - cut.start
        tl.t = 61.5
    return tl


# ---------------------------------------------------------------- sound


def _sfx(kind: str, rng: np.random.Generator) -> np.ndarray:
    """A soft air whoosh for a scene change; a slow swell with a low boom for title cards."""
    peak = 0.95 if kind == "swell" else 0.32
    n = int(SAMPLE_RATE * (peak + 0.9))
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    noise = rng.standard_normal(n).astype(np.float32)
    body = np.convolve(noise, np.ones(28, np.float32) / 28, mode="same")
    env = np.where(t < peak, (t / peak) ** 2.2, np.exp(-(t - peak) * 7)).astype(np.float32)
    sig = body * env * (0.5 if kind == "swell" else 0.32)
    if kind == "swell":
        tb = np.clip(t - peak, 0, None)
        sig += (np.sin(2 * np.pi * 52 * tb) * np.exp(-tb * 3.2) * (t >= peak) * 0.16).astype(np.float32)
    return sig.astype(np.float32)


def _audio(tl: Timeline, seed: int) -> np.ndarray:
    total = tl.t + 0.5
    voice = np.zeros(int(total * SAMPLE_RATE) + 1, np.float32)
    for start, a in tl.audio:
        i = int(start * SAMPLE_RATE)
        voice[i:i + len(a)] += a[: len(voice) - i]
    bgm = music.pulse(total, seed) * 0.6
    mix = render._mix(voice, bgm)
    rng = np.random.default_rng(seed)
    for t, kind in tl.foley[1:]:
        s = _sfx(kind, rng)
        i = max(0, int((t - (0.75 if kind == "swell" else 0.12)) * SAMPLE_RATE))
        mix[i:i + len(s)] += s[: len(mix) - i, None]
    return np.clip(mix, -1, 1)


# ---------------------------------------------------------------- video


def _ass(tl: Timeline, fmt: render.Format) -> str:
    """Captions for the Short: white, slightly tight, with a soft dark halo, above the app's buttons."""
    L = tl.layout
    margin_v = int(L.h - 1470) if L.vertical else 70
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {L.w}\nPlayResY: {L.h}\n"
            "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Cap,Inter Display SemiBold,{fmt.body_size},&H00F7F5F5,&H00F7F5F5,&H5A000000,&H00000000,0,0,0,0,"
            f"100,100,-1,0,1,6,0,2,{fmt.margin},{fmt.margin},{margin_v},1\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    return head + "\n".join(f"Dialogue: 0,{render._ass_time(s)},{render._ass_time(e)},Cap,,0,0,0,,"
                            f"{{\\blur8}}{render._esc(t)}" for s, e, t in tl.captions) + "\n"


def _srt(tl: Timeline) -> str:
    def stamp(t: float) -> str:
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{stamp(s)} --> {stamp(e)}\n{t}\n" for i, (s, e, t) in enumerate(tl.captions, 1))


def encode(tl: Timeline, out: Path, seed: int, fmt: render.Format, burn: bool) -> float:
    """Draw every frame, mix the sound, encode. burn=True burns the captions in (Shorts); the long video gets a
    clean picture and an .srt file next to it (YouTube captions)."""
    work = out.parent / f"work-{out.stem}"
    work.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".srt").write_text(_srt(tl), encoding="utf-8")
    if burn:
        (work / "subs.ass").write_text(_ass(tl, fmt), encoding="utf-8")
    stereo = _audio(tl, seed)
    with wave.open(str(work / "audio.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((stereo * 32767).astype("<i2").tobytes())
    L = tl.layout
    stage = studio.Stage(L.w, L.h)
    fps = studio.FPS
    vf = (f"ass=subs.ass:fontsdir={studio.FONT_DIR}," if burn else "") + "format=yuv420p"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{L.w}x{L.h}",
           "-framerate", str(fps), "-i", "pipe:0", "-i", "audio.wav", "-vf", vf,
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
           "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-tune", "animation", "-x264-params", "aq-mode=3",
           "-g", str(fps * 4), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out.resolve())]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=work)
    frames = int(math.ceil(tl.t * fps))
    k = 0
    try:
        for cut in tl.cuts:
            while k < frames and k / fps < cut.end:
                proc.stdin.write(stage.draw(cut.scene, k / fps - cut.start).tobytes())
                k += 1
                if k % (fps * 60) == 0:
                    print(f"  render {out.name}: {k / fps / 60:.0f}/{tl.t / 60:.1f} min", flush=True)
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return tl.t


def thumbnail(script: dict, out: Path) -> Path:
    """1280x720: the big figure in its gradient on black, one short line above – readable on a phone."""
    th = script["thumbnail"]
    L = studio.Layout(1280, 720)
    parts = studio.number(L, th["big"], "", th.get("color", "red"))
    for p in parts:
        p.y += 70
    lines, size = studio.fit(th["text"], "display", 96, L.w - 160, 1, 50)
    parts.append(studio.El(studio.text(lines, "display", size, studio.WHITE), L.w / 2, 120, 0))
    img = studio.Stage(L.w, L.h).draw(studio.Scene(parts, 60.0, 0), 20.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=94)
    return out


def describe(script: dict, cfg: dict, chapters: list[tuple[float, str]]) -> str:
    def stamp(t: float) -> str:
        return f"{int(t // 60):02d}:{int(t % 60):02d}"
    parts = [script["description"].strip(), "Chapters:\n" + "\n".join(f"{stamp(t)} {h}" for t, h in chapters),
             "Data & sources:\n" + "\n".join(f"• {s}" for s in script["sources"]),
             cfg["disclosure"], cfg["not_advice"], " ".join(script.get("hashtags", cfg["hashtags"]))]
    return "\n\n".join(parts)


def render_script(script_id: str, short_only: bool = False) -> dict:
    cfg = load(CONFIG, {})
    script = load(SCRIPTS / f"{script_id}.json", None)
    if not script:
        raise SystemExit(f"no script {script_id}")
    seed = zlib.crc32(script_id.encode()) & 0xFFFF
    out = OUT / script_id
    result: dict = {"id": script_id}
    if not short_only:
        tl = build_long(script, cfg)
        result["video"] = out / "video.mp4"
        result["duration"] = encode(tl, result["video"], seed, CAPTION, burn=cfg.get("burn_captions_long", False))
        result["captions"] = result["video"].with_suffix(".srt")
        result["chapters"] = tl.chapters
        result["description"] = describe(script, cfg, tl.chapters)
        result["thumbnail"] = thumbnail(script, out / "thumbnail.jpg")
    if script.get("short"):
        ts = build_short(script, cfg)
        result["short"] = out / "short.mp4"
        result["short_duration"] = encode(ts, result["short"], seed + 1, CAPTION_V, burn=True)
    return result


def words(script: dict) -> int:
    return sum(len(b["say"].split()) for ch in script["chapters"] for b in ch["beats"])


# ---------------------------------------------------------------- quality gate

REQUIRED = {"line": ["series"], "bars": [], "coins": ["stacks"], "columns": ["stacks"], "compare": ["left", "right"],
            "number": ["big"], "note": ["text"], "title": ["heading"]}
WPS = 2.3        # spoken words per second incl. pauses, long video (measured on the first episode)
WPS_SHORT = 2.1  # the Short has more, shorter beats


def check(script_id: str, preview: bool = True) -> bool:
    """Validate a script before it enters the queue: structure, lengths, data, marks – and draw a preview sheet
    (one still per scene) to look at: out/econ/<id>/preview-long.png and preview-short.png."""
    problems: list[str] = []
    info: list[str] = []
    try:
        script = json.loads((SCRIPTS / f"{script_id}.json").read_text(encoding="utf-8"))
    except Exception as err:  # noqa: BLE001
        print(f"FAIL {script_id}: cannot read script – {err}")
        return False
    for key in ("id", "order", "title", "title_card", "description", "tags", "hashtags", "sources", "thumbnail",
                "chapters", "short"):
        if key not in script:
            problems.append(f"missing key {key!r}")
    if problems:
        return _verdict(script_id, problems, info)
    if script["id"] != script_id:
        problems.append("id must equal the file name")
    if len(script["title"]) > 100:
        problems.append(f"title longer than 100 characters ({len(script['title'])})")
    if len(script["thumbnail"].get("text", "")) > 24 or len(script["thumbnail"].get("big", "")) > 14:
        problems.append("thumbnail: text max 24 characters, big max 14 characters")
    if not script["sources"]:
        problems.append("no sources listed")
    if len(script["chapters"]) < 5:
        problems.append("at least 5 chapters (the first one is the hook before the title card)")
    n_long = words(script)
    n_short = sum(len(b["say"].split()) for b in script["short"].get("beats", []))
    info.append(f"long: {n_long} words ≈ {n_long / WPS / 60 + 0.6:.1f} min · short: {n_short} words ≈ "
                f"{n_short / WPS_SHORT + 5:.0f} s")
    if n_long < 1150:
        problems.append(f"long script too short ({n_long} words) – needs ≥ 1150 words for 8+ minutes")
    if n_long > 2100:
        problems.append(f"long script too long ({n_long} words) – keep it under 2100 words (≤ 15 minutes)")
    if n_short < 130:
        problems.append(f"short too short ({n_short} words) – needs ≥ 130 words to run over a minute")
    if len(script["short"].get("hook", "")) > 40:
        problems.append("short hook longer than 40 characters")
    groups = {"long": [ch["beats"] for ch in script["chapters"]], "short": [script["short"].get("beats", [])]}
    for name, chapters in groups.items():
        for ci, beats in enumerate(chapters):
            if beats and not beats[0].get("show"):
                problems.append(f"{name} chapter {ci}: the first beat needs a 'show'")
            current = None
            for bi, b in enumerate(beats):
                if not b.get("say"):
                    problems.append(f"{name} chapter {ci} beat {bi}: empty 'say'")
                sh = b.get("show")
                if sh:
                    current = sh
                    err = _check_show(sh)
                    if err:
                        problems.append(f"{name} chapter {ci} beat {bi}: {err}")
                if b.get("mark") and current:
                    err = _check_mark(current, b["mark"])
                    if err:
                        problems.append(f"{name} chapter {ci} beat {bi}: {err}")
    if preview and not problems:
        info += _preview(script)
    return _verdict(script_id, problems, info)


def _check_show(sh: dict) -> str | None:
    kind = sh.get("type")
    if kind not in REQUIRED:
        return f"unknown scene type {kind!r} (use {', '.join(REQUIRED)})"
    missing = [k for k in REQUIRED[kind] if k not in sh]
    if missing:
        return f"{kind} needs {', '.join(missing)}"
    color = sh.get("color")
    if color and color not in studio.GRADIENTS:
        return f"unknown color {color!r} (use {', '.join(studio.GRADIENTS)})"
    try:
        if kind == "line":
            for s in sh["series"]:
                pts = series(s)
                if len(pts) < 3:
                    return f"line series has only {len(pts)} points"
        if kind == "bars":
            if "items" not in sh and "data" not in sh:
                return "bars need 'items' or 'data'"
            if not _bars_items(sh):
                return "bars without items"
    except Exception as err:  # noqa: BLE001
        return f"data failed: {type(err).__name__}: {err}"
    return None


def _check_mark(sh: dict, mark: dict) -> str | None:
    if sh["type"] == "line":
        if "x" not in mark:
            return "a line-chart mark needs 'x' (a year on the chart)"
        xs = [x for x, _ in series(sh["series"][0])]
        if not xs[0] <= mark["x"] <= xs[-1]:
            return f"mark x={mark['x']} is outside the chart ({xs[0]}–{xs[-1]})"
    elif sh["type"] == "bars":
        names = mark.get("items") or mark.get("item")
        names = [names] if isinstance(names, str) else names or []
        known = {n for n, _ in _bars_items(sh)}
        bad = [n for n in names if n not in known]
        if not names or bad:
            return f"bar mark needs 'item'/'items' from the bars ({', '.join(sorted(known))})"
    else:
        return f"marks only work on line and bars scenes (current scene: {sh['type']})"
    return None


def _preview(script: dict) -> list[str]:
    from PIL import Image

    out = OUT / script["id"]
    out.mkdir(parents=True, exist_ok=True)
    notes = []
    for name, L, chapters, tw in (("long", studio.Layout(1920, 1080), [c["beats"] for c in script["chapters"]], 480),
                                   ("short", studio.Layout(1080, 1920), [script["short"]["beats"]], 270)):
        stills = []
        stage = studio.Stage(L.w, L.h)
        for beats in chapters:
            i = 0
            while i < len(beats):
                j = i + 1
                while j < len(beats) and not beats[j].get("show"):
                    j += 1
                durs = [len(b["say"].split()) / WPS + 0.5 for b in beats[i:j]]
                dur = sum(durs) + 0.3
                marks, t = [], 0.25
                for b, d in zip(beats[i:j], durs):
                    if b.get("mark"):
                        marks.append((t, b["mark"]))
                    t += d
                sc = studio.scene(L, _scene(L, beats[i]["show"], dur, marks), dur)
                stills.append(stage.draw(sc, max(0.5, dur - 0.8)).resize((tw, int(tw * L.h / L.w))))
                i = j
        cols = 6 if name == "long" else 8
        rows = math.ceil(len(stills) / cols)
        th = stills[0].height
        sheet = Image.new("RGB", (cols * (tw + 6), rows * (th + 6)), (64, 64, 64))
        for k, im in enumerate(stills):
            sheet.paste(im, ((k % cols) * (tw + 6), (k // cols) * (th + 6)))
        path = out / f"preview-{name}.png"
        sheet.save(path)
        notes.append(f"preview: {path} ({len(stills)} scenes, each shortly before it ends)")
    thumb = thumbnail(script, out / "thumbnail.jpg")
    notes.append(f"thumbnail: {thumb}")
    return notes


def _verdict(script_id: str, problems: list[str], info: list[str]) -> bool:
    for line in info:
        print(f"  {line}")
    for p in problems:
        print(f"  ✗ {p}")
    print(f"{'PASS' if not problems else 'FAIL'} {script_id}")
    return not problems


# ---------------------------------------------------------------- publishing

TIKTOK_QUEUE = ROOT / "state" / "tiktok_econ.md"


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def queue(state: dict) -> list[str]:
    """Scripts not published yet, in their "order" (the writer appends new ones at the end)."""
    done = {r["id"] for r in state.get("videos", [])}
    scripts = [(load(p, {}).get("order", 999), p.stem) for p in SCRIPTS.glob("*.json")]
    return [sid for _, sid in sorted(scripts) if sid not in done]


def _texts(script: dict, cfg: dict, result: dict) -> dict:
    tags = list(dict.fromkeys(script.get("tags", []) + ["economics", "money", "explained", "data visualization"]))
    hashtags = " ".join(script.get("hashtags", cfg["hashtags"]))
    sh = script.get("short", {})
    short_title = f"{sh.get('hook', script['title_card'])} #Shorts"[:95]
    short_desc = "\n\n".join([sh.get("hook", ""), f"The full story: {script['title']}",
                                cfg["disclosure"], cfg["not_advice"], hashtags + " #Shorts"])
    caption = "\n\n".join([sh.get("hook", script["title_card"]), script["description"].split(". ")[0] + ".",
                            "Full video on YouTube – follow for more money, explained with real numbers.",
                            hashtags + " #economics #finance"])
    return {"title": script["title"][:100], "description": result.get("description", ""), "tags": tags,
            "short_title": short_title, "short_description": short_desc, "caption": caption[:2150],
            "tiktok": "\n".join([sh.get("hook", script["title_card"]), "Full video on YouTube.",
                                 hashtags + " #economics #learnontiktok"])}


def produce(upload: bool = True, script_id: str | None = None) -> dict:
    """Render the next script and publish it: release archive, Instagram Reel + story, TikTok draft, YouTube."""
    import datetime as dt

    from .simchannel import story_clip

    cfg, state = load(CONFIG, {}), load(STATE, {"videos": []})
    script_id = script_id or next(iter(queue(state)), None)
    if not script_id:
        print("[econ] no script waiting – the writer adds new ones (docs/econ-writer.md); nothing to do", flush=True)
        return {}
    script = load(SCRIPTS / f"{script_id}.json", {})
    print(f"[econ] {script_id}: {script['title']}", flush=True)
    result = render_script(script_id)
    texts = _texts(script, cfg, result)
    stamp = dt.datetime.now(dt.timezone.utc)
    record = {"id": script_id, "date": stamp.isoformat(timespec="seconds"), "title": script["title"],
              "duration": round(result["duration"], 1), "short_duration": round(result.get("short_duration", 0), 1)}
    if not upload:
        print(f"  rendered {result['video']} and {result.get('short')}", flush=True)
        return record
    name = f"{stamp:%Y%m%d}-{script_id}"
    body = "\n".join(["### Title", "```", texts["title"], "```", "### Description", "```", texts["description"], "```",
                      "### Tags", "```", ", ".join(texts["tags"]), "```", "### Short – title", "```",
                      texts["short_title"], "```", "### Short – description", "```", texts["short_description"], "```"])
    slug = re.sub(r"[^a-z0-9]+", "-", cfg["channel_name"].lower()).strip("-")
    files = [(result["video"], f"{slug}-{name}.mp4", "video/mp4"),
             (result["thumbnail"], f"{slug}-{name}-thumbnail.jpg", "image/jpeg"),
             (result["captions"], f"{slug}-{name}-captions.srt", "application/x-subrip")]
    clip = None
    if result.get("short"):
        files.append((result["short"], f"{slug}-{name}-short.mp4", "video/mp4"))
        clip = story_clip(Path(result["short"]))
        if clip:
            files.append((clip, f"{slug}-{name}-story.mp4", "video/mp4"))
    rel = publish.github_release(f"econ-{name}", f"[{cfg['channel_name']}] {texts['title']}", body, files)
    if drive := gdrive.save(cfg["channel_name"], texts["title"], files, body):
        record["drive"] = drive
    assets = rel.get("assets", {})
    if rel:
        record["release"] = rel["release"]
    short_url = assets.get(f"{slug}-{name}-short.mp4")
    if short_url and instagram.configured(cfg):
        try:
            record.update(instagram.post_reel(cfg, short_url, texts["caption"], story=True, label=script["title"],
                                              thumb_offset_ms=3000,
                                              story_url=assets.get(f"{slug}-{name}-story.mp4")))
        except Exception as err:  # noqa: BLE001 – one platform failing must not lose the run
            record.setdefault("warnings", []).append(f"instagram: {err}")
            print(f"  warning: instagram failed: {err}", flush=True)
    if result.get("short") and tiktok.configured(cfg):
        try:
            record["tiktok"] = {**tiktok.send_draft(cfg, Path(result["short"])), "caption": texts["tiktok"]}
        except Exception as err:  # noqa: BLE001
            record.setdefault("warnings", []).append(f"tiktok: {err}")
            print(f"  warning: tiktok failed: {err}", flush=True)
    if cfg["youtube"].get("upload_enabled"):
        try:
            token = _youtube_token(cfg)
            meta = {"title": texts["title"], "description": texts["description"], "tags": texts["tags"],
                    "categoryId": cfg["youtube"]["category_id"], "defaultLanguage": cfg["youtube"]["default_language"]}
            vid = youtube.upload_video(token, Path(result["video"]), meta,
                                       {"privacyStatus": "public", "selfDeclaredMadeForKids": False})
            youtube.set_thumbnail(token, vid, Path(result["thumbnail"]))
            record["youtube_id"] = vid
            if result.get("short"):
                record["youtube_short_id"] = youtube.upload_video(
                    token, Path(result["short"]), {**meta, "title": texts["short_title"],
                                                   "description": texts["short_description"]},
                    {"privacyStatus": "public", "selfDeclaredMadeForKids": False})
        except Exception as err:  # noqa: BLE001
            record.setdefault("warnings", []).append(f"youtube: {err}")
            print(f"  warning: youtube failed: {err}", flush=True)
    state.setdefault("videos", []).append(record)
    save(STATE, state)
    if record.get("tiktok"):
        tiktok.write_queue(state["videos"], cfg["channel_name"], TIKTOK_QUEUE)
    publish.cleanup_releases("econ-", keep_days=21)
    print(f"[econ] published {script_id}", flush=True)
    return record


def _youtube_token(cfg: dict) -> str:
    import os

    from cryptography.fernet import Fernet
    secret = cfg["youtube"].get("refresh_token_secret")
    if secret and os.environ.get(secret):  # GitHub secret first, else the encrypted token file
        return youtube.access_token(secret)
    data = json.loads(Fernet(os.environ["IG_TOKEN_KEY"].strip().encode()).decrypt(
        (ROOT / cfg["youtube"]["token_file"]).read_bytes().strip()))
    return youtube.access_token_from(data["refresh_token"])


YT_API = "https://www.googleapis.com/youtube/v3"


def _release_texts(tag: str) -> dict:
    """Title, description, tags and the Short's texts exactly as prepared in the episode's GitHub release."""
    import os

    repo = os.environ.get("GITHUB_REPOSITORY", "hthkrksy54-dotcom/Yt")
    gh = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=gh, timeout=30)
    body = r.json().get("body", "") if r.ok else ""
    keys = {"Title": "title", "Description": "description", "Tags": "tags", "Short – title": "short_title",
            "Short – description": "short_description"}
    texts = {keys[k]: v for k, v in re.findall(r"### (.+?)\n```\n(.*?)\n```", body, re.S) if k in keys}
    if "tags" in texts:
        texts["tags"] = [t.strip() for t in texts["tags"].split(",") if t.strip()]
    return texts


def youtube_sync() -> bool:
    """Find the videos and Shorts the owner uploaded by hand (any privacy status, so a private or scheduled
    upload is finished before it goes live) and give them our title, description, tags, thumbnail and captions,
    once each. Matched by file name (the files from Drive or the release), else by length. Returns True if the
    state changed."""
    import datetime as dt
    import tempfile

    cfg, state = load(CONFIG, {}), load(STATE, {"videos": []})
    if not youtube.configured(cfg["youtube"].get("refresh_token_secret", "")):
        print("[econ] YouTube not connected – nothing to sync", flush=True)
        return False
    token = _youtube_token(cfg)
    h = {"Authorization": f"Bearer {token}"}
    ch = requests.get(f"{YT_API}/channels", params={"part": "contentDetails", "mine": "true"}, headers=h, timeout=30)
    uploads_id = ch.json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = requests.get(f"{YT_API}/playlistItems", headers=h, timeout=30,
                         params={"part": "contentDetails", "playlistId": uploads_id, "maxResults": 50}).json()
    ids = [i["contentDetails"]["videoId"] for i in items.get("items", [])]
    uploads = requests.get(f"{YT_API}/videos", headers=h, timeout=30, params={
        "part": "snippet,contentDetails,fileDetails", "id": ",".join(ids)}).json().get("items", []) if ids else []
    for v in uploads:
        m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", v["contentDetails"]["duration"])
        d, hh, mm, ss = (int(x or 0) for x in m.groups()) if m else (0, 0, 0, 0)
        v["seconds"] = ((d * 24 + hh) * 60 + mm) * 60 + ss
        v["file"] = (v.get("fileDetails", {}).get("fileName") or "").casefold()

    def put(video_id: str, title: str, description: str, tags: list[str]) -> bool:
        body = {"id": video_id, "snippet": {"title": title, "description": description, "tags": tags,
                                            "categoryId": cfg["youtube"]["category_id"],
                                            "defaultLanguage": cfg["youtube"]["default_language"],
                                            "defaultAudioLanguage": cfg["youtube"]["default_language"]}}
        r = requests.put(f"{YT_API}/videos", params={"part": "snippet"}, data=json.dumps(body), timeout=60,
                         headers={**h, "Content-Type": "application/json"})
        if not r.ok:
            print(f"  could not update {video_id} ({r.status_code}): {r.text[:200]}", flush=True)
        return r.ok

    def asset(name: str, suffix: str) -> Path | None:  # a file of the current episode's release
        r = requests.get(f"{rec['release'].replace('/releases/tag/', '/releases/download/')}/{name}", timeout=120)
        if not r.ok:
            return None
        fh = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        fh.write(r.content)
        fh.close()
        return Path(fh.name)

    slug = re.sub(r"[^a-z0-9]+", "-", cfg["channel_name"].lower()).strip("-")
    taken = {r.get(k) for r in state["videos"] for k in ("youtube_id", "youtube_short_id")} - {None}
    changed = False
    for rec in state["videos"]:
        if not rec.get("release"):
            continue
        tag = rec["release"].rsplit("/", 1)[1]
        base = f"{slug}-{tag.removeprefix('econ-')}"
        made = dt.datetime.fromisoformat(rec["date"]) - dt.timedelta(hours=1)
        for key, short, length in (("youtube_id", False, rec.get("duration")),
                                   ("youtube_short_id", True, rec.get("short_duration"))):
            if rec.get(key):
                continue
            free = [v for v in uploads if v["id"] not in taken and dt.datetime.fromisoformat(
                v["snippet"]["publishedAt"].replace("Z", "+00:00")) >= made]
            by_file = [v for v in free if base in v["file"] and (f"{base}-short" in v["file"]) == short]
            by_length = [v for v in free if length and abs(v["seconds"] - length) <= 2]
            pick = by_file[:1] or (by_length if len(by_length) == 1 else [])
            if pick:
                rec[key] = pick[0]["id"]
                taken.add(pick[0]["id"])
                changed = True
                print(f"[econ] found upload of {rec['id']} ({'Short' if short else 'video'}): "
                      f"https://youtu.be/{pick[0]['id']}", flush=True)
        long_id, short_id = rec.get("youtube_id"), rec.get("youtube_short_id")
        short_state = "linked" if long_id else "plain"  # the Short links the full video once that is up too
        if not ((long_id and not rec.get("texts_set")) or (short_id and rec.get("short_texts_set") != short_state)
                or (long_id and not (rec.get("thumbnail_set") or rec.get("thumbnail_error")))
                or (long_id and not (rec.get("captions_set") or rec.get("captions_error")))):
            continue
        texts = _release_texts(tag)
        if not texts.get("title"):
            print(f"  [econ] no texts for {rec['id']} (release {tag} gone?) – left as uploaded", flush=True)
            continue
        if long_id and not rec.get("texts_set") and put(long_id, texts["title"], texts["description"], texts["tags"]):
            rec["texts_set"] = changed = True
            print(f"  set title, description and tags: https://youtu.be/{long_id}", flush=True)
        if short_id and rec.get("short_texts_set") != short_state:
            desc = texts.get("short_description", "")
            if long_id:
                desc = desc.replace(f"The full story: {texts['title']}",
                                    f"The full story: {texts['title']}\n▶ https://youtu.be/{long_id}", 1)
            if put(short_id, texts.get("short_title", texts["title"]), desc, texts["tags"]):
                rec["short_texts_set"], changed = short_state, True
                print(f"  set Short title and description: https://youtube.com/shorts/{short_id}", flush=True)
        if long_id and not (rec.get("thumbnail_set") or rec.get("thumbnail_error")):
            path = asset(f"{base}-thumbnail.jpg", ".jpg")
            error = youtube.set_thumbnail(token, long_id, path) if path else "thumbnail missing in the release"
            rec["thumbnail_error" if error else "thumbnail_set"], changed = (error[:200] if error else True), True
            print(f"  {error or 'thumbnail set'}", flush=True)
        if long_id and not (rec.get("captions_set") or rec.get("captions_error")):
            path = asset(f"{base}-captions.srt", ".srt")
            error = youtube.add_captions(token, long_id, path, "en", "English") if path else "captions missing"
            rec["captions_error" if error else "captions_set"], changed = (error[:200] if error else True), True
            print(f"  {error or 'captions added'}", flush=True)
    if changed:
        save(STATE, state)
    return changed


def backfill_reel(every_day: bool = True) -> bool:
    """Post the Short of the oldest episode that has no Reel yet – made before Instagram was connected, or its
    Reel failed – as Reel + story, at most one a day and only while its release (the video's public URL) exists."""
    import datetime as dt

    cfg, state = load(CONFIG, {}), load(STATE, {"videos": []})
    if not instagram.configured(cfg):
        print("[econ] Instagram not connected – no Reel to catch up", flush=True)
        return False
    now = dt.datetime.now(dt.timezone.utc)
    if every_day and any(r.get("reel_backfill") == now.date().isoformat() for r in state["videos"]):
        print("[econ] already caught up one Reel today", flush=True)
        return False
    todo = [r for r in state["videos"] if not r.get("instagram_id") and r.get("release")
            and now - dt.datetime.fromisoformat(r["date"]) < dt.timedelta(days=20)]  # releases are kept 21 days
    if not todo:
        print("[econ] every episode has its Reel", flush=True)
        return False
    rec = todo[0]
    script = load(SCRIPTS / f"{rec['id']}.json", {})
    slug = re.sub(r"[^a-z0-9]+", "-", cfg["channel_name"].lower()).strip("-")
    tag = rec["release"].rsplit("/", 1)[1]
    files = f"{rec['release'].replace('/releases/tag/', '/releases/download/')}/{slug}-{tag.removeprefix('econ-')}"
    print(f"[econ] catching up the Reel of {rec['id']}", flush=True)
    rec.update(instagram.post_reel(cfg, f"{files}-short.mp4", _texts(script, cfg, {})["caption"], story=True,
                                   label=script["title"], thumb_offset_ms=3000, story_url=f"{files}-story.mp4"))
    rec["reel_backfill"] = now.date().isoformat()
    save(STATE, state)
    print(f"  reel: {rec.get('instagram_url')} ({len(todo) - 1} still waiting)", flush=True)
    return True
