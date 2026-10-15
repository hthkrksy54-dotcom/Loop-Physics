# Einrichtung – einmalig, ca. 30–45 Minuten

Alles hier ist **kostenlos**. Die meisten Schritte gehen auch am Handy im Browser.
Danach läuft der Kanal ohne dich: Mo/Mi/Fr entsteht automatisch je ein Video auf Deutsch
und Englisch (plus je ein Short) und wird hochgeladen.

Solange Schritt 2–4 nicht erledigt sind, legt die Pipeline jedes fertige Video als
**GitHub-Release** ab (Repo → *Releases*): MP4, Thumbnail, Untertitel und Titel/Beschreibung
zum Kopieren. Die kannst du in der Zwischenzeit von Hand in der YouTube-App hochladen.

---

## 1. YouTube-Kanäle anlegen (geht nur durch dich)

Google erlaubt nicht, Konten automatisch zu erstellen. Das musst du einmal selbst tun.

1. Melde dich bei YouTube mit deinem Google-Konto an (oder lege ein neues an).
2. Erstelle **zwei Kanäle** (Profilbild → *Einstellungen* → *Kanal hinzufügen oder verwalten* → *Kanal erstellen*):
   - Deutsch: **Leise Gedanken**
   - Englisch: **Quiet Thoughts**

   Die Namen sind Vorschläge. Wenn du andere nimmst, ändere `channel_name` in `config/channels.json`.
3. Verifiziere jeden Kanal per Telefon unter <https://www.youtube.com/verify>.
   Erst danach sind eigene Thumbnails und Videos über 15 Minuten erlaubt.

## 2. Google-Cloud-Projekt (für den automatischen Upload)

1. Öffne <https://console.cloud.google.com/> und lege ein Projekt an, z. B. `ytauto`.
2. *APIs & Dienste* → *Bibliothek* → **YouTube Data API v3** → *Aktivieren*.
3. *Google Auth Platform* (früher „OAuth-Zustimmungsbildschirm“):
   - **Branding:** App-Name `ytauto`, deine E-Mail als Support- und Entwickleradresse.
   - **Zielgruppe:** Typ *Extern*. Dann **„App veröffentlichen“ → In Produktion**.
     Das ist wichtig: Im Testmodus laufen die Zugangsschlüssel nach 7 Tagen ab.
     Die Warnung „App nicht überprüft“ ist bei privater Nutzung normal.
   - **Datenzugriff:** Bereich `https://www.googleapis.com/auth/youtube.force-ssl` hinzufügen.
   - **Clients** → *Client erstellen* → Typ **Webanwendung** → unter
     *Autorisierte Weiterleitungs-URIs* eintragen: `https://developers.google.com/oauthplayground`
   - **Client-ID** und **Clientschlüssel** notieren.

## 3. Zugangsschlüssel (Refresh-Token) pro Kanal holen

Das geht komplett im Browser, auch am Handy:

1. Öffne <https://developers.google.com/oauthplayground>.
2. Zahnrad oben rechts → **Use your own OAuth credentials** anhaken → Client-ID und Clientschlüssel eintragen.
3. Links bei *Step 1* ins Feld unten eintragen:
   `https://www.googleapis.com/auth/youtube.force-ssl` → **Authorize APIs**.
4. Google-Konto wählen, dann **den Kanal „Leise Gedanken“** auswählen.
   Bei „App nicht überprüft“: *Erweitert* → *Weiter zu ytauto* → *Zulassen*.
5. *Step 2* → **Exchange authorization code for tokens** → den **Refresh token** kopieren.
6. Das Ganze für **„Quiet Thoughts“** wiederholen. Vorher oben rechts auf *Step 1* zurück und
   beim Anmelden den anderen Kanal wählen.

## 4. Schlüssel in GitHub hinterlegen

Repo auf GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Wert |
|---|---|
| `YT_CLIENT_ID` | Client-ID aus Schritt 2 |
| `YT_CLIENT_SECRET` | Clientschlüssel aus Schritt 2 |
| `YT_REFRESH_TOKEN_DE` | Refresh-Token von „Leise Gedanken“ |
| `YT_REFRESH_TOKEN_EN` | Refresh-Token von „Quiet Thoughts“ |
| `GEMINI_API_KEY` | **kostenloser** Schlüssel von <https://aistudio.google.com/apikey> (gleiches Google-Konto, keine Kreditkarte). Damit schreibt die Pipeline neue Skripte. |
| `GROQ_API_KEY` *(optional)* | kostenloser Schlüssel von <https://console.groq.com/keys>, Reserve, falls Gemini mal ausfällt |

Für einen einzelnen Kanal einfach nur dessen Token eintragen. Der andere Kanal bleibt dann beim GitHub-Release.

> **Am wichtigsten ist `GEMINI_API_KEY`, und den kannst du sofort eintragen.** Ohne ihn produziert die
> Pipeline nur die fertig geschriebenen Skripte und bleibt danach stehen.

## 5. Freigabe für öffentliche Uploads beantragen (wichtig)

Google sperrt Videos aus **ungeprüften API-Projekten automatisch auf „privat“**.
Die Prüfung (Audit) ist kostenlos, dauert aber einige Tage bis Wochen:

- Formular: <https://support.google.com/youtube/contact/yt_api_form>
  („YouTube API Services – Audit and Quota Extension Form“).
- Angaben: *Internes Tool, lädt ausschließlich eigene Inhalte auf die eigenen zwei Kanäle hoch;
  keine Nutzer außer dem Kanalinhaber.* Projekt-ID aus der Cloud Console angeben.

**Empfehlung:** Trage die `YT_REFRESH_TOKEN_*`-Secrets erst ein, **wenn das Audit genehmigt ist**.
Bis dahin landen die Videos als GitHub-Release, und du lädst sie per App hoch.
Gesperrte private Videos lassen sich später meist nicht mehr öffentlich schalten.

## 6. Testlauf

GitHub → **Actions** → **Produce videos** → **Run workflow**.
Zum Ausprobieren `upload` abhaken. Die Videos liegen dann unter *Artifacts* des Laufs.

---

## Wie die Skripte entstehen

1. Zuerst die fertig geschriebenen Skripte in `content/scripts/<sprache>/`.
2. Danach schreibt ein kostenloses Sprachmodell neue Skripte zu den Themen in `content/topics.json`:
   **Gemini** (Free Tier), als Reserve **Groq**. Jedes Skript geht durch eine zweite Faktenprüfung und wird im
   Repo gespeichert, sodass du es nachlesen kannst.
3. Ist die Themenliste leer, schlägt das Modell selbst neue Themen vor.

Du kannst jederzeit eigene Themen in `content/topics.json` eintragen oder Skripte in `content/scripts/` bearbeiten.

## Geld verdienen (YouTube-Partnerprogramm)

- Voraussetzungen: **1.000 Abonnenten** und **4.000 Wiedergabestunden** in 12 Monaten
  (oder 10 Mio. Shorts-Aufrufe in 90 Tagen). Dann in YouTube Studio → *Verdienen* bewerben.
- YouTube kürzt die Monetarisierung bei massenhaft produzierten, gleichförmigen KI-Videos
  („inauthentic content“). Dagegen hilft diese Pipeline mit sorgfältigen, quellenbelegten Skripten,
  Kapiteln, Quellenangaben und einer moderaten Frequenz (3 Videos pro Woche und Sprache).
  Erhöhe die Frequenz nicht stark.
- Ab und zu ein Blick auf neue Skripte lohnt sich. Pflicht ist er nicht.
