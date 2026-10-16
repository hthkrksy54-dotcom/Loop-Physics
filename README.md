<p><img src="docs/developed-with-youtube-sentence-case-dark.png" alt="Developed with YouTube" width="210"></p>

# ytauto – Quiet Thoughts & Loop Physics

**ytauto** is a private, internal tool of a single channel owner. It produces original videos and publishes them to
the owner's own YouTube channels using the YouTube Data API v3:

- **[Quiet Thoughts](https://www.youtube.com/@quietthoughts-20)** – calm educational video essays about philosophy
  and psychology (`videos.insert`, `thumbnails.set`, `captions.insert`).
- **[Loop Physics](https://www.youtube.com/@LoopPhysics-420)** – generated, oddly satisfying physics simulations
  (`videos.insert`, `videos.update` and `playlistItems` for the owner's own videos, `channels.update` and
  `channelBanners.insert` for the owner's own channel, and a daily trend check with `search.list`/`videos.list`
  whose public data is only aggregated in memory, never stored).

It has a single user (the channel owner), no public sign-in and no viewer data.

**[Privacy Policy](PRIVACY.md)** · **[Terms of Service](TERMS.md)** ·
[YouTube Terms of Service](https://www.youtube.com/t/terms) ·
[Google Privacy Policy](https://policies.google.com/privacy) ·
[Revoke access](https://security.google.com/settings/security/permissions)

**How it works:** scheduled GitHub Actions workflows (`.github/workflows/produce.yml`, `sims.yml`, `trends.yml`)
render the videos, authenticate with the owner's OAuth refresh tokens (stored encrypted) and publish to the
owner's channels. See [docs/architecture.png](docs/architecture.png).

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
| Ausführung | GitHub Actions, täglich ein Video (öffentliches Repo = unbegrenzte Minuten) | 0 € |
| Instagram | jeder Short als Reel + Story (@quiet_thoughts_yt), Caption mit Frage + 3–5 Hashtags, Token verschlüsselt, verlängert sich selbst | 0 € |
| Karussells | Di/Do/Sa: Zitat-Karussell aus einem veröffentlichten Video + Zitat-Story ([Workflow](.github/workflows/carousel.yml)) | 0 € |
| Stories | täglich eine frische Story (Zitat-Karte, sonntags Wochenrückblick), wenn nicht schon Reel/Karussell eine gepostet hat; jede Story wird mit ihrem Highlight protokolliert ([Workflow](.github/workflows/stories.yml)) | 0 € |
| Highlights | keine API bei Instagram – sonntags kommt eine Liste, welche Stories in welches Highlight gehören (`python -m ytauto highlights`) | 0 € |
| Upload-Wächter | stündlich: erkennt Videos, die du von Hand hochlädst, korrigiert Shorts, postet das passende Reel | 0 € |

**Einrichtung:** siehe [SETUP.md](SETUP.md). Die YouTube-Kanäle musst du einmal selbst anlegen.

## Loop Physics – jeder Post ein neues Konzept

| Baustein | Lösung |
|---|---|
| Takt | 2 Posts täglich um 11:30 und 18:30 UTC ([Workflow](.github/workflows/sims.yml)); dazwischen alle ~2 h ein Herzschlag, der YouTube-Uploads nachpflegt und liegengebliebene Workflows startet |
| Neue Konzepte | 2× täglich baut ein automatischer Konzept-Designer (geplante Claude-Session) nach [docs/concept-designer.md](docs/concept-designer.md) ein neues Konzept aus aktuellen viralen Trends – eine Datei in `ytauto/concepts/`, mit Qualitätsprüfung (`python -m ytauto concept-check`) |
| Keine Wiederholungen | gepostet wird immer das älteste noch nie gepostete Konzept; nur Ausreißer nach oben (≥ 1,6× Median-Aufrufe aus Instagram + YouTube) dürfen erneut laufen, und nur wenn kein neues bereitliegt |
| Robustheit | kaputte Konzepte werden übersprungen und vermerkt; verpasste Slots werden bis 6 h später nachgeholt; Übersicht mit `python -m ytauto concepts` |
| Trends | täglicher Trend-Check ([Bericht](docs/loop-physics-trends.md)) |

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
