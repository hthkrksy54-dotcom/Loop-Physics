"""Text-to-speech via Microsoft Edge neural voices (edge-tts, free, no API key).

Returns decoded mono PCM plus word timings, so captions can be aligned exactly.
"""
from __future__ import annotations

import asyncio
import os
import re
import ssl
import subprocess
import time
from dataclasses import dataclass

import edge_tts
import edge_tts.communicate as _communicate
import numpy as np

SAMPLE_RATE = 48000


def _use_env_ca_bundle() -> None:
    # edge-tts pins certifi's bundle; behind a TLS-inspecting proxy we need the system one.
    ca = os.environ.get("SSL_CERT_FILE")
    if ca and os.path.exists(ca):
        _communicate._SSL_CTX = ssl.create_default_context(cafile=ca)


_use_env_ca_bundle()


@dataclass
class Word:
    start: float  # seconds, relative to the clip
    end: float
    text: str


@dataclass
class Speech:
    audio: np.ndarray  # float32 mono at SAMPLE_RATE
    words: list[Word]

    @property
    def duration(self) -> float:
        return len(self.audio) / SAMPLE_RATE


def _decode_mp3(data: bytes) -> np.ndarray:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"],
        input=data,
        capture_output=True,
        check=True,
    )
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


async def _stream(text: str, voice: str, rate: str, pitch: str) -> tuple[bytes, list[Word]]:
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    audio = bytearray()
    words: list[Word] = []
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start = chunk["offset"] / 1e7
            words.append(Word(start, start + chunk["duration"] / 1e7, chunk["text"]))
    if not audio:
        raise RuntimeError("edge-tts returned no audio")
    return bytes(audio), words


def synthesize(text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz", attempts: int = 5) -> Speech:
    text = re.sub(r"\s+", " ", text).strip()
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            data, words = asyncio.run(_stream(text, voice, rate, pitch))
            return Speech(_decode_mp3(data), words)
        except Exception as err:  # network hiccups are common; retry with backoff
            last_err = err
            time.sleep(2 ** (i + 1))
    raise RuntimeError(f"TTS failed after {attempts} attempts: {last_err}")


_TRAILING = "\"'“”„«»‚‘’)]….,;:!?—–-"


def align_tokens(text: str, words: list[Word]) -> list[Word]:
    """Map edge-tts boundary words (no punctuation) back onto the original text.

    Returns display tokens carrying original spelling and punctuation with the
    boundary timings. Unmatched spans are attached to the neighbouring token.
    """
    text = re.sub(r"\s+", " ", text).strip()
    tokens: list[Word] = []
    cursor = 0
    pending_start = 0
    for w in words:
        idx = text.find(w.text, cursor, cursor + 80 + len(w.text))
        if idx < 0:
            # Spoken form differs from written form (numbers, abbreviations): keep timing only.
            if tokens:
                tokens[-1] = Word(tokens[-1].start, w.end, tokens[-1].text)
            continue
        end = idx + len(w.text)
        while end < len(text) and text[end] in _TRAILING:
            end += 1
        piece = text[pending_start:end].strip()
        if piece:
            tokens.append(Word(w.start, w.end, piece))
        cursor = pending_start = end
    rest = text[pending_start:].strip()
    if rest:
        if tokens:
            tokens[-1] = Word(tokens[-1].start, tokens[-1].end, tokens[-1].text + " " + rest)
        else:
            tokens.append(Word(0.0, 0.5, rest))
    return tokens
