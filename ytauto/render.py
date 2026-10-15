"""Turns a script into a finished video: narration, captions, music, visuals, encode."""
from __future__ import annotations

import re
import subprocess
import wave
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import music, tts, visuals
from .tts import SAMPLE_RATE, Word

FPS = 24
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


@dataclass
class Format:
    width: int
    height: int
    bg_width: int
    bg_height: int
    body_size: int
    margin: int
    max_chars: int
    max_words: int

    @property
    def vertical(self) -> bool:
        return self.height > self.width


LONG = Format(1920, 1080, 384, 216, body_size=78, margin=250, max_chars=80, max_words=14)
SHORT = Format(1080, 1920, 216, 384, body_size=96, margin=80, max_chars=44, max_words=8)


def _ass_color(rgb) -> str:
    r, g, b = rgb
    return f"&H00{b:02X}{g:02X}{r:02X}"


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_time(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _esc(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def _split_balanced(sentence: list[Word], fmt: Format) -> list[list[Word]]:
    """Split one long sentence into k pieces of similar length, preferring punctuation."""
    lengths = [len(w.text) + 1 for w in sentence]
    total = sum(lengths)
    k = max(-(-total // fmt.max_chars), -(-len(sentence) // fmt.max_words))
    if k <= 1:
        return [sentence]
    cum, acc = [], 0
    for n in lengths:
        acc += n
        cum.append(acc)
    cuts, prev = [], 0
    for j in range(1, k):
        target = total * j / k
        best, best_cost = None, None
        for i in range(prev + 1, len(sentence) - 1):
            cost = abs(cum[i] - target)
            if sentence[i].text.rstrip("\"'“”„«»‚‘’)").endswith((",", ";", ":", "—", "–")):
                cost -= fmt.max_chars * 0.3
            if i - prev < 2:
                cost += fmt.max_chars
            if best_cost is None or cost < best_cost:
                best, best_cost = i, cost
        if best is None:
            break
        cuts.append(best)
        prev = best
    pieces, start = [], 0
    for c in cuts:
        pieces.append(sentence[start : c + 1])
        start = c + 1
    pieces.append(sentence[start:])
    return [p for p in pieces if p]


def _chunk(tokens: list[Word], fmt: Format) -> list[Word]:
    """Group word tokens into calm, readable on-screen phrases (sentence-aware)."""
    sentences: list[list[Word]] = [[]]
    for tok in tokens:
        sentences[-1].append(tok)
        if tok.text.rstrip("\"'“”„«»‚‘’)").endswith((".", "!", "?", "…")):
            sentences.append([])
    chunks: list[Word] = []
    for sentence in sentences:
        for piece in _split_balanced(sentence, fmt) if sentence else []:
            chunks.append(Word(piece[0].start, piece[-1].end, " ".join(w.text for w in piece)))
    return chunks


@dataclass
class Timeline:
    fmt: Format
    palette: dict
    t: float = 0.0
    events: list[str] = field(default_factory=list)
    voice: list[tuple[int, np.ndarray]] = field(default_factory=list)
    captions: list[tuple[float, float, str]] = field(default_factory=list)
    chapters: list[tuple[float, str]] = field(default_factory=list)

    def pause(self, seconds: float) -> None:
        self.t += seconds

    def _event(self, start: float, end: float, style: str, text: str, fade=(400, 300)) -> None:
        self.events.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{{\\fad({fade[0]},{fade[1]})}}{text}"
        )

    def _add_voice(self, speech: tts.Speech) -> None:
        self.voice.append((int(self.t * SAMPLE_RATE), speech.audio))

    def speak(self, text: str, voice: str, rate: str, pitch: str) -> None:
        speech = tts.synthesize(text, voice, rate, pitch)
        tokens = tts.align_tokens(text, speech.words)
        chunks = _chunk(tokens, self.fmt)
        self._add_voice(speech)
        for i, c in enumerate(chunks):
            start = self.t + c.start - 0.12
            nxt = self.t + chunks[i + 1].start - 0.12 if i + 1 < len(chunks) else self.t + speech.duration + 0.3
            end = min(self.t + c.end + 0.6, nxt - 0.04)
            self._event(start, end, "Body", _esc(c.text), fade=(220, 160))
            self.captions.append((start, end, c.text))
        self.t += speech.duration

    def quote(self, text: str, author: str, voice: str, rate: str, pitch: str, marks: str = "“”") -> None:
        speech = tts.synthesize(text, voice, rate, pitch)
        accent = _ass_color(self.palette["accent"])
        small = int(self.fmt.body_size * 0.62)
        body = f"{marks[0]}{_esc(text)}{marks[1]}\\N{{\\fs{small // 2}}} \\N{{\\fs{small}\\i0\\c{accent}\\fsp3}}— {_esc(author).upper()}"
        start = self.t
        self._add_voice(speech)
        self.t += speech.duration + 1.2
        self._event(start - 0.3, self.t, "Quote", body, fade=(600, 500))
        self.captions.append((start, self.t - 1.0, f"{marks[0]}{text}{marks[1]} — {author}"))

    def card(self, small: str, big: str, seconds: float, chapter: str | None = None) -> None:
        if chapter is not None:
            self.chapters.append((self.t, chapter))
        accent = _ass_color(self.palette["accent"])
        cx, cy = self.fmt.width // 2, self.fmt.height // 2
        gap = int(self.fmt.body_size * 1.3)
        if small:
            spaced = "  ".join(small.upper()) if len(small) < 24 else small.upper()
            self._event(self.t, self.t + seconds, "Small", f"{{\\pos({cx},{cy - gap})\\c{accent}}}{_esc(spaced)}", fade=(700, 600))
        self._event(self.t + 0.2, self.t + seconds, "Title", f"{{\\pos({cx},{cy + gap // 4})}}{_esc(big)}", fade=(800, 600))
        self.t += seconds

    def ass(self) -> str:
        f = self.fmt
        cream = _ass_color((244, 236, 220))
        title_size = int(f.body_size * (1.45 if not f.vertical else 1.25))
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {f.width}
PlayResY: {f.height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Body,EB Garamond,{f.body_size},{cream},{cream},&H64000000,&H96000000,0,0,0,0,100,100,0.5,0,1,0,2.2,5,{f.margin},{f.margin},0,1
Style: Quote,EB Garamond,{int(f.body_size * 1.08)},{cream},{cream},&H64000000,&H96000000,0,1,0,0,100,100,0.5,0,1,0,2.2,5,{f.margin},{f.margin},0,1
Style: Title,Cormorant Garamond Medium,{title_size},{cream},{cream},&H64000000,&H96000000,0,0,0,0,100,100,1,0,1,0,2.5,5,{f.margin // 2},{f.margin // 2},0,1
Style: Small,EB Garamond,{int(f.body_size * 0.68)},{cream},{cream},&H64000000,&H96000000,0,0,0,0,100,100,3,0,1,0,1.5,5,{f.margin},{f.margin},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        return header + "\n".join(self.events) + "\n"

    def srt(self) -> str:
        out = []
        for i, (s, e, text) in enumerate(self.captions, 1):
            out.append(f"{i}\n{_srt_time(s)} --> {_srt_time(e)}\n{text}\n")
        return "\n".join(out)

    def voice_track(self, total: float) -> np.ndarray:
        track = np.zeros(int(total * SAMPLE_RATE) + 1, dtype=np.float32)
        for start, audio in self.voice:
            end = min(len(track), start + len(audio))
            track[start:end] += audio[: end - start]
        return track


def _mix(voice: np.ndarray, bgm: np.ndarray) -> np.ndarray:
    n = min(len(voice), len(bgm))
    voice, bgm = voice[:n], bgm[:n]
    # Duck the music under speech, smoothly.
    win = int(0.5 * SAMPLE_RATE)
    env = np.convolve(np.abs(voice), np.ones(win, dtype=np.float32) / win, mode="same")
    active = np.clip(env / (np.percentile(env[env > 0], 60) if np.any(env > 0) else 1), 0, 1)
    active = np.convolve(active, np.ones(win, dtype=np.float32) / win, mode="same")
    gain = 0.30 - 0.15 * active
    peak = float(np.max(np.abs(voice))) or 1.0
    v = voice / peak * 0.8
    mix = bgm * gain[:, None] + v[:, None]
    return np.clip(mix, -1, 1).astype(np.float32)


def _write_wav(path: Path, stereo: np.ndarray) -> None:
    pcm = (stereo * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


def encode(tl: Timeline, out: Path, seed: int, workdir: Path) -> float:
    total = tl.t
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "subs.ass").write_text(tl.ass(), encoding="utf-8")
    bgm = music.generate(total, seed)
    _write_wav(workdir / "audio.wav", _mix(tl.voice_track(total), bgm))

    f = tl.fmt
    bg = visuals.Background(f.bg_width, f.bg_height, tl.palette, seed)
    fonts = str(visuals.FONT_DIR)
    vf = (
        f"scale={f.width}:{f.height}:flags=bicubic,"
        f"noise=alls=3:allf=t,vignette=angle=0.6,"
        f"fade=t=in:st=0:d=1.5,fade=t=out:st={max(0, total - 2.5):.2f}:d=2.5,"
        f"ass=subs.ass:fontsdir={fonts},format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{f.bg_width}x{f.bg_height}", "-r", str(FPS), "-i", "pipe:0",
        "-i", "audio.wav",
        "-vf", vf,
        "-af", "loudnorm=I=-15:TP=-1.5:LRA=11,aresample=48000",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-tune", "film", "-g", str(FPS * 4),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest",
        str(out.resolve()),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=workdir)
    n_frames = int(total * FPS) + 1
    try:
        for i in range(n_frames):
            proc.stdin.write(bg.frame(i / FPS).tobytes())
            if i % (FPS * 60) == 0:
                print(f"  render {out.name}: {i / FPS / 60:.0f}/{total / 60:.1f} min", flush=True)
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return total


def seed_for(script: dict) -> int:
    return zlib.crc32(script["id"].encode()) & 0x7FFFFFFF


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def render_long(script: dict, lang_cfg: dict, outdir: Path) -> dict:
    seed = seed_for(script)
    palette = visuals.palette_for(seed)
    tl = Timeline(LONG, palette)
    v, rate, pitch = lang_cfg["voice"], lang_cfg["rate"], lang_cfg["pitch"]
    words = lang_cfg["words"]

    tl.pause(1.6)
    sections = script["sections"]
    tl.chapters.append((0.0, words["intro"]))
    for p in _paragraphs(sections[0]["text"]):
        tl.speak(p, v, rate, pitch)
        tl.pause(0.7)
    tl.pause(0.5)
    tl.card(script.get("label", ""), script["title_card"] if "title_card" in script else script["title"], 4.5)
    tl.pause(0.6)

    for i, sec in enumerate(sections[1:]):
        tl.card(ROMAN[i % len(ROMAN)], sec["heading"], 3.4, chapter=sec["heading"])
        tl.pause(0.5)
        if sec.get("quote"):
            q = sec["quote"]
            if q.get("lead"):
                tl.speak(q["lead"], v, rate, pitch)
                tl.pause(0.5)
            tl.quote(q["text"], q["author"], v, lang_cfg.get("quote_rate", rate), pitch, words.get("quote_marks", "“”"))
            tl.pause(0.4)
        for p in _paragraphs(sec["text"]):
            tl.speak(p, v, rate, pitch)
            tl.pause(0.75)
        tl.pause(0.6)

    tl.card(lang_cfg["channel_name"], words["outro"], 7.0)
    tl.pause(1.0)

    outdir.mkdir(parents=True, exist_ok=True)
    video = outdir / "video.mp4"
    duration = encode(tl, video, seed, outdir / "work_long")
    (outdir / "captions.srt").write_text(tl.srt(), encoding="utf-8")
    thumb = outdir / "thumbnail.jpg"
    visuals.thumbnail(thumb, script["thumbnail_text"], script.get("label", ""), palette, seed)
    return {"video": video, "thumbnail": thumb, "captions": outdir / "captions.srt", "chapters": tl.chapters, "duration": duration}


def render_short(script: dict, lang_cfg: dict, outdir: Path) -> dict | None:
    short = script.get("short")
    if not short:
        return None
    seed = seed_for(script) + 7
    palette = visuals.palette_for(seed_for(script))
    tl = Timeline(SHORT, palette)
    v, rate, pitch = lang_cfg["voice"], lang_cfg["rate"], lang_cfg["pitch"]
    tl.pause(0.4)
    for p in _paragraphs(short["text"]):
        tl.speak(p, v, rate, pitch)
        tl.pause(0.5)
    tl.card("", lang_cfg["channel_name"], 2.0)
    outdir.mkdir(parents=True, exist_ok=True)
    video = outdir / "short.mp4"
    duration = encode(tl, video, seed, outdir / "work_short")
    return {"video": video, "duration": duration}
