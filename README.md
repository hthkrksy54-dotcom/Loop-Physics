# ytauto – autonome YouTube-Videos über Philosophie & Psychologie

Ruhige Video-Essays auf **Deutsch** und **Englisch**, vollautomatisch und **ohne laufende Kosten**.

```
Thema → Skript → Faktencheck → Sprecherstimme → Musik → Visuals → Untertitel → Video + Short + Thumbnail → Upload
```

| Baustein | Lösung | Kosten |
|---|---|---|
| Skripte | eigene Skripte im Repo, danach GitHub Models (Reserve: Gemini Free Tier) mit Fakten-Review | 0 € |
| Stimme | Microsoft-Neural-Stimmen über `edge-tts` (DE: Florian, EN: Andrew) | 0 € |
| Musik | prozedural erzeugte Ambient-Musik, keine Lizenzfragen | 0 € |
| Visuals | ruhige, langsam fließende Farbfelder, Garamond-Typografie (OFL-Schriften) | 0 € |
| Schnitt | ffmpeg (1080p, Kapitel, Untertitel, Lautheit −15 LUFS) | 0 € |
| Shorts | automatische Hochkant-Version (ca. 50 s) pro Thema | 0 € |
| Upload | YouTube Data API: Video, Thumbnail, Untertitel, Short | 0 € |
| Ausführung | GitHub Actions, Mo/Mi/Fr (öffentliches Repo = unbegrenzte Minuten) | 0 € |

**Einrichtung:** siehe [SETUP.md](SETUP.md). Die YouTube-Kanäle musst du einmal selbst anlegen.

## Lokal ausprobieren

```bash
sudo apt-get install ffmpeg
pip install -r requirements.txt
python -m ytauto render --lang de --topic dichotomy-of-control   # Ergebnis in out/de/…
```

## Aufbau

- `config/channels.json`: Kanalnamen, Stimmen, Sprechtempo, Upload-Einstellungen
- `content/topics.json`: Themen-Backlog (Reihenfolge = Veröffentlichungsreihenfolge)
- `content/scripts/<de|en>/<id>.json`: Skripte (handgeschrieben oder generiert)
- `state/published.json`: was schon veröffentlicht wurde (schreibt die Pipeline selbst)
- `ytauto/`: Pipeline (`tts`, `music`, `visuals`, `render`, `generate`, `youtube`, `publish`)
- `.github/workflows/produce.yml`: Zeitplan und Ablauf
