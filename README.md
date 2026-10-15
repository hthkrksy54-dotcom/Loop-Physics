<p><img src="docs/developed-with-youtube-sentence-case-dark.png" alt="Developed with YouTube" width="210"></p>

# ytauto – Quiet Thoughts

**ytauto** is a private, internal tool that produces calm educational video essays about philosophy and
psychology and uploads them to the owner's own YouTube channel
**[Quiet Thoughts](https://www.youtube.com/@quietthoughts-20)** using the YouTube Data API v3
(`videos.insert`, `thumbnails.set`, `captions.insert`). It has a single user (the channel owner), no public
sign-in and no viewer data.

**[Privacy Policy](PRIVACY.md)** · **[Terms of Service](TERMS.md)** ·
[YouTube Terms of Service](https://www.youtube.com/t/terms) ·
[Google Privacy Policy](https://policies.google.com/privacy) ·
[Revoke access](https://security.google.com/settings/security/permissions)

**How it works:** a scheduled GitHub Actions workflow (`.github/workflows/produce.yml`) renders a video,
authenticates with the owner's OAuth refresh token (stored as an encrypted GitHub secret) and uploads the
video, thumbnail and captions to the owner's channel. See [docs/architecture.png](docs/architecture.png).

---

# ytauto – autonome YouTube-Videos über Philosophie & Psychologie

Ruhige Video-Essays auf **Deutsch** und **Englisch**, vollautomatisch und **ohne laufende Kosten**.

```
Thema → Skript → Faktencheck → Sprecherstimme → Musik → Visuals → Untertitel → Video + Short + Thumbnail → Upload
```

| Baustein | Lösung | Kosten |
|---|---|---|
| Skripte | eigene Skripte im Repo, danach Gemini Free Tier (Reserve: Groq) mit Fakten-Review | 0 € |
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
