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
