<p><img src="docs/developed-with-youtube-sentence-case-dark.png" alt="Developed with YouTube" width="210"></p>

# ytauto – Quiet Thoughts, Loop Physics & Real Numbers

**ytauto** is a private, internal tool of a single channel owner. It produces original videos and publishes them to
the owner's own YouTube channels using the YouTube Data API v3:

- **[Quiet Thoughts](https://www.youtube.com/@quietthoughts-20)** – calm educational video essays about philosophy
  and psychology (`videos.insert`, `thumbnails.set`, `captions.insert`).
- **[Loop Physics](https://www.youtube.com/@LoopPhysics-420)** – generated, oddly satisfying physics simulations
  (`videos.insert`, `videos.update` and `playlistItems` for the owner's own videos, `channels.update` and
  `channelBanners.insert` for the owner's own channel, and a daily trend check with `search.list`/`videos.list`
  whose public data is only aggregated in memory, never stored).
- **[Real Numbers](https://www.youtube.com/@realnumbersdaily)** – data-driven explainers about money and the economy,
  charts drawn in code from public World Bank data (`videos.insert`, `thumbnails.set`, `captions.insert`, and
  `videos.update` to give the owner's own uploads their prepared title, description and tags).

A copy of each video goes to the owner's own Google Drive (Drive API, scope `drive.file`: only files the tool
created itself).

It has a single user (the channel owner), no public sign-in and no viewer data.

**[Privacy Policy](PRIVACY.md)** · **[Terms of Service](TERMS.md)** ·
[YouTube Terms of Service](https://www.youtube.com/t/terms) ·
[Google Privacy Policy](https://policies.google.com/privacy) ·
[Revoke access](https://security.google.com/settings/security/permissions)

**How it works:** scheduled GitHub Actions workflows (`.github/workflows/produce.yml`, `sims.yml`, `econ.yml`, `sync.yml`, `trends.yml`)
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
| Ausführung | GitHub Actions, täglich ein Video um 4 Uhr deutscher Zeit, Sommer wie Winter (öffentliches Repo = unbegrenzte Minuten) | 0 € |
| Instagram | jeder Short als Reel + Story (@quiet_thoughts_yt) um 10 Uhr New Yorker Zeit (das Video entsteht schon um 4 Uhr deutscher Zeit, der Upload-Wächter postet das Reel zur Zeit), Caption mit Frage + 3–5 Hashtags, Token verschlüsselt, verlängert sich selbst | 0 € |
| TikTok | jeder Short zusammen mit dem Reel als Entwurf in den TikTok-Posteingang (höchstens 5 warten gleichzeitig – mehr lässt TikTok nicht zu –, der Upload-Wächter füllt stündlich nach), Beschreibungen zum Kopieren in [state/tiktok_quiet.md](state/tiktok_quiet.md); verbinden mit dem Workflow [TikTok verbinden](.github/workflows/tiktok-connect.yml) | 0 € |
| Karussells | Di/Do/Sa: Zitat-Karussell aus einem veröffentlichten Video + Zitat-Story ([Workflow](.github/workflows/carousel.yml)) | 0 € |
| Stories | täglich eine frische Story (Zitat-Karte, sonntags Wochenrückblick), wenn nicht schon Reel/Karussell eine gepostet hat; jede Story wird mit ihrem Highlight protokolliert ([Workflow](.github/workflows/stories.yml)) | 0 € |
| Highlights | keine API bei Instagram – sonntags kommt eine Liste, welche Stories in welches Highlight gehören (`python -m ytauto highlights`) | 0 € |
| Upload-Wächter | stündlich: erkennt Videos, die du von Hand hochlädst, korrigiert Shorts, postet das passende Reel | 0 € |
| Google Drive | jedes Video aller drei Kanäle zusätzlich unter „Kanal-Videos/<Kanal>“, mit Texten zum Kopieren, 14 Tage lang ([gdrive.py](ytauto/gdrive.py)) | 0 € |

**Einrichtung:** siehe [SETUP.md](SETUP.md). Die YouTube-Kanäle musst du einmal selbst anlegen.

## Loop Physics – zweimal täglich ein neues Konzept

| Baustein | Lösung |
|---|---|
| Takt | 4 Videos am Tag, alle 6 Stunden: 4:40, 10:40, 16:40 und 22:40 UTC (deutsche Sommerzeit 6:40, 12:40, 18:40, 0:40; US-Ostküste 0:40, 6:40, 12:40, 18:40) ([Workflow](.github/workflows/sims.yml)); zwischen den Slots pflegt der Workflow YouTube-Uploads nach, füllt TikTok-Entwürfe auf und startet liegengebliebene Workflows |
| Neue Konzepte | jede Nacht um ca. 3:15 baut ein automatischer Konzept-Designer (geplante Claude-Session) nach [docs/concept-designer.md](docs/concept-designer.md) bis zu zwei neue Konzepte aus aktuellen viralen Trends – eine Datei in `ytauto/concepts/`, mit Qualitätsprüfung (`python -m ytauto concept-check`: u. a. Ton = Bild – jede Note auf einem sichtbaren Treffer, keine stummen Treffer-Massen, keine Pausen über 3,5 s). Tempo-Experiment: mindestens eines pro Nacht ist schnell (`tempo = "fast"`, viele/schnelle Bälle, 4+ hörbare Treffer pro Sekunde); `python -m ytauto concepts` vergleicht schnell vs. normal |
| Melodien | gewählt nach Viralität: eigene Aufrufe pro Melodie (z. B. Für Elise), Melodien in viralen Satisfying-Shorts (täglicher Trend-Check) und die nächtliche Song-Recherche des Konzept-Designers ([config/sims_music.json](config/sims_music.json): Boosts, saisonale Stücke, neue gemeinfreie Melodien); angesagte, urheberrechtlich geschützte Sounds stehen als Vorschlag oben in [state/tiktok.md](state/tiktok.md) – nur zum Auswählen in TikTok; Übersicht: `python -m ytauto melodies` |
| Ende | nach dem Finale wird „LIKE & SUBSCRIBE“ eingeblendet |
| Länge | jedes Video über 1 Minute (ca. 61–90 s), damit es bei TikTok für Creator Rewards zählt; Instagram-Stories bekommen einen 28-s-Teaser |
| Auswahl | neue Konzepte haben immer Vorrang; dazwischen kommen bereits gelaufene Konzepte als neue Variante zurück, gewichtet nach Aufrufen (Instagram + YouTube) – Ausreißer nach oben (≥ 1,6× Median) deutlich öfter, nie eins der letzten drei |
| TikTok | jedes Video zusammen mit dem Reel als Entwurf in den TikTok-Posteingang (höchstens 4 warten gleichzeitig, TikTok hält höchstens 5), Beschreibungen zum Kopieren in [state/tiktok.md](state/tiktok.md) |
| Robustheit | kaputte Konzepte werden übersprungen und vermerkt; verpasste Slots werden bis 6 h später nachgeholt; Übersicht mit `python -m ytauto concepts` |
| Trends | täglicher Trend-Check ([Bericht](docs/loop-physics-trends.md)) |

## Real Numbers – Alltagsgeld, erklärt mit echten Zahlen

| Baustein | Lösung |
|---|---|
| Ausrichtung | allgemeine Geld-Tipps für die breite Masse nach dem Vorbild von Finanzbär (und Finanzfluss): Meilensteine, Geldfresser, Sparen, Schulden, Rente, Index-Fonds allgemein, Psychologie des Geldes – keine Einzelaktien, keine Produkte; jedes Video sagt nach dem Hook „not financial advice“, Titel- und Endkarten zeigen es, ab und zu ein gesprochenes „Like & Abo“ ([Themen](content/econ/topics.md)) |
| Format | täglich um 4 Uhr deutscher Zeit ein Video mit 8–15 Minuten (1920x1080) plus ein Short über 1 Minute (Englisch, Zielgruppe USA/UK) ([Workflow](.github/workflows/econ.yml)) |
| Look | Keynote-Stil, komplett im Code gezeichnet ([studio.py](ytauto/studio.py)): schwarze Bühne, Inter-Typografie (OFL), große Zahlen mit Farbverlauf, die hochzählen, Diagramme, die sich selbst zeichnen, Markierungen im Takt der Sprache, langsame Kamerafahrt |
| Daten | Weltbank-Indikatoren (CC BY 4.0), im Repo zwischengespeichert, Quellen in jeder Beschreibung |
| Skripte | montags ab ca. 14:00 schreibt ein automatischer Skript-Autor (geplante Claude-Session) die 7 Folgen der Woche nach [docs/econ-writer.md](docs/econ-writer.md), Themen aus [content/econ/topics.md](content/econ/topics.md); Qualitätsprüfung mit Vorschaubildern: `python -m ytauto econ check <id>` |
| Ton | Sprecherstimme über `edge-tts` (15 % schneller als normal), moderne Hintergrundmusik (prozedural, Pads + Arpeggio + Puls), keine Soundeffekte, −14 LUFS |
| Veröffentlichung | Release mit Video, Short, Thumbnail und Untertiteln (.srt); Short als Instagram-Reel + Story um 11 Uhr New Yorker Zeit und als TikTok-Entwurf gleich morgens, sobald die Konten verbunden sind; YouTube-Upload nach Freigabe |
| TikTok | jeder Short zusammen mit dem Reel als Entwurf in den TikTok-Posteingang (höchstens 5 warten gleichzeitig – mehr lässt TikTok nicht zu –, stündlich nachgefüllt), Beschreibungen zum Kopieren in [state/tiktok_econ.md](state/tiktok_econ.md); verbinden mit dem Workflow [TikTok verbinden](.github/workflows/tiktok-connect.yml) |
| Reels nachholen | täglich 0:40 UTC höchstens ein Reel für eine Folge ohne Reel (vor der Instagram-Verbindung entstanden oder fehlgeschlagen) ([Workflow](.github/workflows/econ-reels.yml)) |
| Upload-Wächter | stündlich: erkennt Video und Short, die du von Hand hochlädst (auch privat oder geplant), und setzt Titel, Beschreibung, Tags, Thumbnail und Untertitel; der Short verlinkt das ganze Video |

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
