"""Connection check: which parts of the pipeline are configured and working."""
from __future__ import annotations

import json

import requests

from . import generate, instagram, tts, youtube


def _llm() -> bool:
    ok_any = False
    messages = [
        {"role": "system", "content": "Reply with JSON only."},
        {"role": "user", "content": 'Return exactly {"ok": true}.'},
    ]
    for name, fn in generate.PROVIDERS.items():
        try:
            answer = generate._parse_json(fn(messages, 1000))
            print(f"[OK]   Skript-KI {name}: antwortet ({json.dumps(answer)})")
            ok_any = True
        except generate.NotConfigured:
            print(f"[--]   Skript-KI {name}: nicht eingetragen")
        except Exception as err:  # report and continue with the next provider
            print(f"[FEHLER] Skript-KI {name}: {str(err)[:200]}")
    return ok_any


def _voice(cfg: dict) -> bool:
    ok = True
    for lang, c in cfg.items():
        try:
            speech = tts.synthesize("Test.", c["voice"], c["rate"], c["pitch"], attempts=2)
            print(f"[OK]   Stimme {lang} ({c['voice']}): {speech.duration:.1f} s Audio")
        except Exception as err:
            print(f"[FEHLER] Stimme {lang}: {str(err)[:200]}")
            ok = False
    return ok


def _youtube(cfg: dict) -> bool:
    ok = True
    for lang, c in cfg.items():
        secret = c["youtube"]["refresh_token_secret"]
        if not youtube.configured(secret):
            print(f"[--]   YouTube {lang}: noch nicht verbunden ({secret} fehlt) – Videos gehen als GitHub-Release raus")
            continue
        try:
            token = youtube.access_token(secret)
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            items = r.json().get("items", []) if r.status_code == 200 else []
            if not items:
                print(f"[FEHLER] YouTube {lang}: Token gültig, aber kein Kanal gefunden ({r.status_code}: {r.text[:150]})")
                ok = False
                continue
            title = items[0]["snippet"]["title"]
            note = "" if title == c["channel_name"] else f" – Achtung: config erwartet „{c['channel_name']}“"
            paused = "" if c["youtube"].get("upload_enabled") else " – Upload pausiert bis zur API-Freigabe (Videos gehen bis dahin als Release raus)"
            print(f"[OK]   YouTube {lang}: verbunden mit Kanal „{title}“{note}{paused}")
        except Exception as err:
            print(f"[FEHLER] YouTube {lang}: {str(err)[:200]}")
            ok = False
    return ok


def _instagram(cfg: dict) -> bool:
    ok = True
    for lang, c in cfg.items():
        if not (c.get("instagram") or {}).get("enabled"):
            continue
        if not instagram.configured(c):
            print(f"[--]   Instagram {lang}: noch nicht verbunden (Secret IG_TOKEN_KEY oder Token-Datei fehlt)")
            continue
        try:
            token = instagram.fresh_token(c)
            me = requests.get(f"{instagram.GRAPH}/me", params={"fields": "username,account_type", "access_token": token}, timeout=30)
            if not me.ok:
                raise RuntimeError(f"{me.status_code}: {me.text[:150]}")
            data = instagram.load_token(c)
            print(f"[OK]   Instagram {lang}: verbunden mit @{me.json()['username']} ({me.json().get('account_type')}), "
                  f"Token gültig bis {data.get('expires_at', '?')[:10]}")
        except Exception as err:
            print(f"[FEHLER] Instagram {lang}: {str(err)[:200]}")
            ok = False
    return ok


def run(cfg: dict) -> int:
    print("Verbindungstest ytauto\n")
    llm_ok = _llm()
    if not llm_ok:
        print("       (Kein Problem, solange Claude die Skripte wöchentlich schreibt.)")
    voice_ok = _voice(cfg)
    yt_ok = _youtube(cfg)
    ig_ok = _instagram(cfg)
    return 0 if (voice_ok and yt_ok and ig_ok) else 1
