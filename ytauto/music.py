"""Procedural ambient music: soft pads, sparse bell tones, no samples, no licensing issues."""
from __future__ import annotations

import numpy as np

from .tts import SAMPLE_RATE

# Semitone offsets from the root for a few calm progressions (minor-ish and modal).
PROGRESSIONS = [
    [[0, 3, 7, 10], [-4, 0, 3, 7], [-9, -5, 0, 3], [-2, 2, 5, 9]],    # i7 - VI - III(inv) - VII
    [[0, 4, 7, 11], [-3, 0, 4, 7], [5, 9, 12, 16], [2, 5, 9, 12]],    # Imaj7 - vi - IV - ii
    [[0, 3, 7, 14], [5, 8, 12, 15], [-2, 2, 5, 9], [3, 7, 10, 14]],   # i(add9) - iv - VII - III
    [[0, 7, 12, 16], [-5, 2, 7, 11], [-3, 4, 9, 12], [-7, 0, 5, 9]],  # open voicings, lydian-ish
]
PENTATONIC = [0, 3, 5, 7, 10, 12, 15, 17]


def _midi_to_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    # Gentle 2nd-order-like roll-off applied in the frequency domain.
    n = len(x)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1 / SAMPLE_RATE)
    spec *= 1 / np.sqrt(1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec, n).astype(np.float32)


def _pad_chord(notes: list[int], root_midi: int, length: int, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(length, dtype=np.float32) / SAMPLE_RATE
    out = np.zeros(length, dtype=np.float32)
    for i, n in enumerate(notes):
        f = _midi_to_hz(root_midi + n)
        amp = 0.22 / (1 + 0.35 * i)
        for detune in (-0.0035, 0.0, 0.0041):
            ph = rng.uniform(0, 2 * np.pi)
            out += amp * np.sin(2 * np.pi * f * (1 + detune) * t + ph).astype(np.float32)
            out += 0.25 * amp * np.sin(2 * np.pi * 2 * f * (1 + detune) * t + ph).astype(np.float32)
    # Sub bass on the chord root.
    out += 0.18 * np.sin(2 * np.pi * _midi_to_hz(root_midi + notes[0] - 12) * t).astype(np.float32)
    return out


def generate(duration: float, seed: int) -> np.ndarray:
    """Return stereo float32 array (n, 2) of calm ambient music, peak ~0.5."""
    rng = np.random.default_rng(seed)
    n_total = int(duration * SAMPLE_RATE) + SAMPLE_RATE
    root = int(rng.choice([45, 46, 48, 50, 52, 53]))  # A2..F3
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    chord_len = float(rng.uniform(9.0, 13.0))
    fade = 3.5

    left = np.zeros(n_total, dtype=np.float32)
    right = np.zeros(n_total, dtype=np.float32)
    seg = int((chord_len + fade) * SAMPLE_RATE)
    step = int(chord_len * SAMPLE_RATE)
    env = np.ones(seg, dtype=np.float32)
    fl = int(fade * SAMPLE_RATE)
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fl))).astype(np.float32)
    env[:fl] = ramp
    env[-fl:] = ramp[::-1]

    pos, k = 0, 0
    while pos < n_total:
        notes = prog[k % len(prog)]
        chord = _pad_chord(notes, root, seg, rng) * env
        end = min(n_total, pos + seg)
        pan = 0.5 + 0.15 * np.sin(k * 1.7)
        left[pos:end] += chord[: end - pos] * (1 - pan) * 2
        right[pos:end] += chord[: end - pos] * pan * 2
        pos += step
        k += 1

    # Sparse, soft bell tones from the pentatonic scale.
    t_bell = rng.uniform(4, 12)
    blen = int(5 * SAMPLE_RATE)
    tb = np.arange(blen, dtype=np.float32) / SAMPLE_RATE
    while t_bell < duration - 5:
        f = _midi_to_hz(root + 24 + int(rng.choice(PENTATONIC)))
        bell = (np.sin(2 * np.pi * f * tb) + 0.3 * np.sin(2 * np.pi * 2.01 * f * tb)) * np.exp(-tb * 1.1)
        bell = (bell * np.minimum(1, tb / 0.02) * 0.07).astype(np.float32)
        i = int(t_bell * SAMPLE_RATE)
        p = rng.uniform(0.25, 0.75)
        left[i : i + blen] += bell[: len(left) - i] * (1 - p) * 2
        right[i : i + blen] += bell[: len(right) - i] * p * 2
        t_bell += rng.uniform(6, 16)

    # Slow "breathing" amplitude and gentle low-pass for warmth.
    t = np.arange(n_total, dtype=np.float32) / SAMPLE_RATE
    breathe = (0.85 + 0.15 * np.sin(2 * np.pi * t / 23.0)).astype(np.float32)
    left = _lowpass(left * breathe, 1800)
    right = _lowpass(right * breathe, 1800)

    # Cheap stereo reverb: a few decaying, offset echoes.
    for delay, gain in ((0.113, 0.35), (0.271, 0.25), (0.419, 0.18), (0.733, 0.12)):
        d = int(delay * SAMPLE_RATE)
        left[d:] += right[:-d] * gain
        right[d:] += left[:-d] * gain * 0.9

    stereo = np.stack([left, right], axis=1)[: int(duration * SAMPLE_RATE)]
    # Fade in/out.
    fi = min(len(stereo), 4 * SAMPLE_RATE)
    stereo[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    fo = min(len(stereo), 6 * SAMPLE_RATE)
    stereo[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(stereo))) or 1.0
    return (stereo / peak * 0.5).astype(np.float32)


def _pluck(f: float, n: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    env = np.exp(-t * 7.0) * np.minimum(1, t / 0.004)
    sig = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 10)
           + 0.1 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 16))
    return (sig * env).astype(np.float32)


def _kick(n: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    f = 46 + 70 * np.exp(-t * 28)
    phase = 2 * np.pi * np.cumsum(f) / SAMPLE_RATE
    return (np.sin(phase) * np.exp(-t * 9) * np.minimum(1, t / 0.002)).astype(np.float32)


def pulse(duration: float, seed: int) -> np.ndarray:
    """Modern, minimal underscore for explainers: warm pads, a soft plucked arpeggio and a gentle pulse.
    Arranged in 8-bar sections (intro with pads only, occasional breakdowns). Stereo float32, peak ~0.5."""
    rng = np.random.default_rng(seed)
    sr = SAMPLE_RATE
    n = int(duration * sr) + sr
    bpm = float(rng.choice([92, 96, 100]))
    beat = 60 / bpm
    bar = 4 * beat
    root = int(rng.choice([45, 47, 48, 50]))
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    patterns = [[0, 1, 2, 3, 2, 1, 2, 3], [0, 2, 1, 3, 0, 2, 1, 3], [0, 1, 2, 1, 3, 2, 1, 2], [3, 2, 1, 0, 1, 2, 1, 3]]
    left = np.zeros(n, np.float32)
    right = np.zeros(n, np.float32)
    pads = np.zeros(n, np.float32)
    seg = int(2 * bar * sr)
    fl = int(min(1.2, bar * 0.4) * sr)
    env = np.ones(seg + fl, np.float32)
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fl))).astype(np.float32)
    env[:fl], env[-fl:] = ramp, ramp[::-1]
    k = 0
    while k * seg < n:
        chord = _pad_chord(prog[k % len(prog)], root, seg + fl, rng) * env
        i = k * seg
        pads[i:i + len(chord)] += chord[: n - i]
        k += 1
    duck = np.ones(n, np.float32)
    pl = int(0.9 * sr)
    kl = int(0.45 * sr)
    kick = _kick(kl)
    dl = int(beat * 0.75 * sr)
    bars = int(duration / bar) + 1
    for b in range(bars):
        section = b // 8
        full = section >= 1 and section % 6 != 5 and b < bars - 2
        if section == 0 and b < 4:
            continue
        notes = prog[(b // 2) % len(prog)]
        pat = patterns[(b // 8 + seed) % len(patterns)]
        for s, idx in enumerate(pat):
            t = b * bar + s * beat / 2
            i = int(t * sr)
            if i >= n:
                break
            f = _midi_to_hz(root + 24 + notes[idx % len(notes)])
            vel = (1.0 if s % 4 == 0 else 0.72) * float(rng.uniform(0.85, 1.0)) * (0.55 if not full else 1.0)
            p = _pluck(f, pl) * vel
            side = (left, right) if s % 2 == 0 else (right, left)
            side[0][i:i + pl] += p[: n - i] * 0.8
            j = i + dl
            if j < n:
                side[1][j:j + pl] += p[: n - j] * 0.35
        if full:
            for s in (0, 2):
                i = int((b * bar + s * beat) * sr)
                if i < n:
                    left[i:i + kl] += kick[: n - i] * 0.9
                    right[i:i + kl] += kick[: n - i] * 0.9
                    w = min(int(0.32 * sr), n - i)
                    duck[i:i + w] = np.minimum(duck[i:i + w], 0.62 + 0.38 * np.linspace(0, 1, w) ** 0.6)
    pads *= duck
    left = _lowpass(left, 3200) + pads * 0.9
    right = _lowpass(right, 3200) + pads * 0.9
    for delay, gain in ((0.113, 0.3), (0.271, 0.22), (0.419, 0.15), (0.733, 0.1)):
        d = int(delay * sr)
        left[d:] += right[:-d] * gain
        right[d:] += left[:-d] * gain * 0.9
    stereo = np.stack([left, right], axis=1)[: int(duration * sr)]
    fi = min(len(stereo), 2 * sr)
    stereo[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    fo = min(len(stereo), 5 * sr)
    stereo[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(stereo))) or 1.0
    return (stereo / peak * 0.5).astype(np.float32)
