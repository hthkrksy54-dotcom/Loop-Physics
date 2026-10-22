"""Daily trend check for Loop Physics: what is going viral in satisfying Shorts, what works on our own
Instagram, and a tuning file (config/sims_tuning.json) that steers formats, lengths, titles and hashtags.

YouTube data is only aggregated in memory (themes, keywords, lengths, hashtags) – no third-party titles or
statistics are stored, per the YouTube API Services policies. Our own Instagram numbers are kept in state.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import statistics
from collections import Counter

import requests

from . import generate, instagram, simchannel, sims

YT = "https://www.googleapis.com/youtube/v3"
QUERIES = ["satisfying simulation", "satisfying physics", "bouncing ball simulation", "oddly satisfying balls",
           "marble race", "ball escape rings"]
KIND_WORDS = {
    "escape": ["escape", "ring", "rings", "circle", "break out", "spinning", "gap"],
    "polygon": ["hexagon", "polygon", "square", "triangle", "octagon", "pentagon", "shape"],
    "battle": ["color", "colour", "battle", "wins", "team", "country", "countries", "vs", "versus"],
    "grow": ["grow", "grows", "bigger", "size", "fills"],
    "multiply": ["multiply", "duplicate", "clone", "adds", "spawn", "1000", "more balls"],
    "plinko": ["plinko", "galton", "bell curve", "pegs", "probability"],
    "stringart": ["string", "pattern", "draw", "draws", "lines", "art"],
    "pendulum": ["pendulum", "pendulums", "wave", "sync"],
    "territory": ["territory", "pong", "pong wars", "conquer", "conquers", "takes over", "paint", "pixels"],
    "chaos": ["chaos", "chaotic", "butterfly", "butterfly effect", "double pendulum"],
    "harmonograph": ["harmonograph", "spirograph", "drawing", "draws", "spiral"],
    "race": ["race", "marble", "marbles", "marble race", "finish", "track"],
}
STOP = set("the a an and or of to in on at for with is are this that it its you your my me i we be will can how "
           "what why when who which every each one all just new video videos shorts short satisfying oddly".split())
JUNK_TAGS = {"shorts", "short", "viral", "fyp", "foryou", "foryoupage", "trending", "youtube", "subscribe", "like",
             "tiktok", "reels", "reel", "explore", "youtubeshorts", "shortsfeed", "shortvideo", "trend", "funny"}
SPECIFIC = r"\b(rings?|pendulums?|plinko|colou?rs?|polygons?|hexagons?|string|grows?|balls? wins?|escapes?|marbles?|races?)\b"
HOOK_SYSTEM = ("You write short, honest YouTube Shorts / Instagram Reels titles for an oddly satisfying physics "
               "simulation channel. No clickbait lies, no ALL CAPS, at most one emoji. Return only JSON.")


def _views(rec: dict) -> int:
    return (rec.get("stats") or {}).get("views", 0)


def own_stats(cfg: dict, state: dict, limit: int = 72) -> list[dict]:
    """Refresh views/reach/likes/saves/shares of our latest Reels (stored in state)."""
    token = instagram.fresh_token(cfg)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    recs = [v for v in state.get("videos", []) if v.get("instagram_id")][-limit:]
    for rec in recs:
        r = requests.get(f"{instagram.GRAPH}/{rec['instagram_id']}/insights",
                         params={"metric": "views,reach,saved,shares", "access_token": token}, timeout=30)
        m = requests.get(f"{instagram.GRAPH}/{rec['instagram_id']}",
                         params={"fields": "like_count,comments_count", "access_token": token}, timeout=30)
        if r.ok and m.ok:
            rec["stats"] = {d["name"]: d["values"][0]["value"] for d in r.json().get("data", [])}
            rec["stats"].update(likes=m.json().get("like_count", 0), comments=m.json().get("comments_count", 0), at=now)
    return recs


def followers(cfg: dict, state: dict, yt_token: str | None) -> None:
    """Today's follower counts (Instagram, YouTube) in state["followers"] – which weeks win followers."""
    snap = {"date": dt.datetime.now(dt.timezone.utc).date().isoformat()}
    try:
        if instagram.configured(cfg):
            r = requests.get(f"{instagram.GRAPH}/me", timeout=30,
                             params={"fields": "followers_count", "access_token": instagram.fresh_token(cfg)})
            if r.ok and "followers_count" in r.json():
                snap["instagram"] = int(r.json()["followers_count"])
        if yt_token:
            r = requests.get("https://www.googleapis.com/youtube/v3/channels", timeout=30,
                             params={"part": "statistics", "mine": "true"}, headers={"Authorization": f"Bearer {yt_token}"})
            if r.ok and r.json().get("items"):
                snap["youtube"] = int(r.json()["items"][0]["statistics"].get("subscriberCount", 0))
    except requests.RequestException as err:
        print(f"  followers: {err}", flush=True)
    if len(snap) > 1:
        state["followers"] = [h for h in state.get("followers", []) if h["date"] != snap["date"]][-179:] + [snap]


def youtube_trends(token: str, days: int = 7) -> list[dict]:
    """Most viewed satisfying Shorts of the last days (kept in memory only)."""
    h = {"Authorization": f"Bearer {token}"}
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    for q in QUERIES:
        r = requests.get(f"{YT}/search", headers=h, timeout=30, params={
            "part": "id", "q": q, "type": "video", "videoDuration": "short", "order": "viewCount",
            "publishedAfter": since, "maxResults": 25, "relevanceLanguage": "en", "safeSearch": "moderate"})
        if r.ok:
            ids += [i["id"]["videoId"] for i in r.json().get("items", []) if i["id"].get("videoId")]
    ids = list(dict.fromkeys(ids))
    out = []
    for k in range(0, len(ids), 50):
        r = requests.get(f"{YT}/videos", headers=h, timeout=30,
                         params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids[k:k + 50])})
        for v in r.json().get("items", []) if r.ok else []:
            m = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+)S)?", v["contentDetails"].get("duration", ""))
            out.append({"text": (v["snippet"]["title"] + " " + " ".join(v["snippet"].get("tags", []))).casefold(),
                        "title": v["snippet"]["title"].casefold(), "tags": v["snippet"].get("tags", []),
                        "views": int(v["statistics"].get("viewCount", 0)),
                        "seconds": (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 0})
    return sorted(out, key=lambda v: -v["views"])


def _classify(text: str) -> list[str]:
    words = {**{k: c.trend_words for k, c in sims.KINDS.items() if c.trend_words}, **KIND_WORDS}
    return [k for k, ws in words.items() if any(re.search(rf"\b{re.escape(w)}\b", text) for w in ws)]


def _melody_named(melody: str, text: str) -> bool:
    """Does a trending Short's title/tags name this melody ("für elise", "fur elise", "moonlight sonata" …)?"""
    name = sims.MELODIES[melody][0].split(" – ")[0].casefold()
    plain = name.replace("ü", "u").replace("è", "e").replace("é", "e")
    names = {name, plain, re.sub(r"^in the ", "", plain), melody.replace("_", " ")}
    return any(re.search(rf"\b{re.escape(n)}\b", text) for n in names)


def run() -> dict:
    cfg, state = simchannel.load(simchannel.CONFIG, {}), simchannel.load(simchannel.STATE, {"videos": []})
    old = simchannel.load(simchannel.TUNING, {})
    kinds = list(sims.KINDS)
    now = dt.datetime.now(dt.timezone.utc)

    # 1) our own Instagram numbers
    recs = own_stats(cfg, state) if instagram.configured(cfg) else []
    simchannel.save(simchannel.STATE, state)
    aged = [r for r in recs if r.get("stats") and now - dt.datetime.fromisoformat(r["date"]) > dt.timedelta(hours=6)]
    overall = statistics.median([_views(r) for r in aged]) if aged else 0
    perf, own_avg = {}, {}
    for k in kinds:
        vs = [_views(r) for r in aged if r["kind"] == k]
        own_avg[k] = round(sum(vs) / len(vs)) if vs else None
        perf[k] = min(2.0, max(0.5, (statistics.median(vs) / overall) ** 0.8)) if len(vs) >= 2 and overall else 1.0

    # 2) what goes viral on YouTube right now (aggregated only)
    token = simchannel._youtube_token(cfg)
    followers(cfg, state, token)
    simchannel.save(simchannel.STATE, state)
    trend = youtube_trends(token) if token else []
    total = sum(v["views"] for v in trend) or 1
    share = {k: sum(v["views"] for v in trend if k in _classify(v["text"])) / total for k in kinds}
    words: Counter = Counter()
    for v in trend:
        toks = [t for t in re.findall(r"[a-z][a-z']+", v["title"]) if t not in STOP and len(t) > 2]
        for t in set(toks + [" ".join(p) for p in zip(toks, toks[1:])]):
            words[t] += math.log10(v["views"] + 10)
    tags: Counter = Counter()
    for v in trend:
        found = {t.casefold().replace(" ", "") for t in v["tags"]} | set(re.findall(r"#([a-z0-9]+)", v["title"]))
        for t in found:
            if re.fullmatch(r"[a-z0-9]{4,24}", t) and t not in JUNK_TAGS:
                tags[t] += 1
    secs = [v["seconds"] for v in trend[:40] if v["seconds"]]
    median_len = statistics.median(secs) if secs else 45
    ranges = ([(22, 32), (28, 40), (35, 48)] if median_len < 35 else
              [(35, 48), (42, 56)] if median_len > 48 else [(28, 40), (35, 48), (42, 56)])

    weights = {k: round(min(3.0, max(0.4, perf[k] * (1 + 2 * share[k]))), 2) for k in kinds}
    melody_trend = {m: round(sum(v["views"] for v in trend if _melody_named(m, v["text"])) / total, 3)
                    for m in sims.MELODIES}
    keywords = [w for w, _ in words.most_common(25)]
    hashtags = [t for t, n in tags.most_common(12) if n >= 2 and t != "satisfying"][:6] or old.get("hashtags", [])

    # 3) fresh title hooks and questions from the trend keywords (our own wording)
    addons, questions, summary = old.get("title_addons", []), old.get("questions", []), ""
    if generate.available() and keywords:
        try:
            best = sorted(aged, key=_views, reverse=True)[:5]
            res = generate.ask_json(
                "Keywords trending this week in viral satisfying-simulation Shorts (most important first):\n"
                + ", ".join(keywords) + "\n\nHow strongly each of our formats trends (0-1): "
                + ", ".join(f"{k} {share[k]:.2f}" for k in kinds)
                + "\nOur best Reels so far: " + "; ".join(f"{r['title']} ({_views(r)} views)" for r in best)
                + "\n\nOur titles are the question shown in the video, e.g. 'Can the ball escape all 14 rings?' or "
                  "'Which color escapes first?'. Write 10 short add-ons (2-6 words, max 30 characters) that we append "
                  "after a dash and that fit ANY such question, inspired by the trend keywords – e.g. 'Wait for the "
                  "ending', 'Sound on', 'Guess the song'. No hashtags, no specific shapes or colours. "
                  "Also write 4 short questions that invite comments, and for the channel owner a 3-sentence summary "
                  "in German of what is trending and how we adapt (plain language, no placeholders).\n"
                  'Return JSON: {"addons": [...], "questions": [...], "summary_de": "..."}',
                max_tokens=1500, system=HOOK_SYSTEM)
            ok = []
            for t in res.get("addons", []):
                t = str(t).strip().strip(".!–- ")
                specific = re.search(SPECIFIC, t, re.I)
                if 3 < len(t) <= 32 and not re.search(r"[#{}?]", t) and not specific:
                    ok.append(t)
            addons = list(dict.fromkeys(ok))[:10] or addons
            questions = [q for q in (str(q).strip() for q in res.get("questions", []))
                         if 5 < len(q) <= 90 and not re.search(SPECIFIC, q, re.I)][:4] or questions
            summary = str(res.get("summary_de", ""))[:800]
        except Exception as err:
            print(f"  LLM step skipped: {err}", flush=True)

    tuning = {"updated": now.isoformat(timespec="minutes"), "kind_weights": weights, "ranges": ranges,
              "hashtags": hashtags, "title_addons": addons, "questions": questions, "trend_keywords": keywords[:15],
              "trend_share": {k: round(share[k], 3) for k in kinds}, "trend_videos": len(trend),
              "trend_median_seconds": median_len, "summary_de": summary, "melody_trend": melody_trend}
    simchannel.save(simchannel.TUNING, tuning)
    report(tuning, state, own_avg)
    print(f"[trends] {len(trend)} trending Shorts, {len(aged)} own Reels; weights {weights}", flush=True)
    return tuning


def report(t: dict, state: dict, own_avg: dict) -> None:
    vids = [v for v in state.get("videos", []) if v.get("stats")]
    day = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=30)
    fresh = sorted([v for v in vids if dt.datetime.fromisoformat(v["date"]) > day], key=_views, reverse=True)[:3]
    lines = ["# Loop Physics – Trend-Check", "", f"Stand: {t['updated'][:16].replace('T', ' ')} UTC · "
             f"{t['trend_videos']} angesagte Satisfying-Shorts der letzten 7 Tage ausgewertet · "
             f"typische Länge {round(t['trend_median_seconds'])} s", ""]
    if t.get("summary_de"):
        lines += [t["summary_de"], ""]
    cfg = simchannel.load(simchannel.CONFIG, {})
    base, perf = simchannel.performance(state)
    stars = simchannel.standouts(state)
    queue = simchannel.concept_queue(cfg, state)
    lines += ["## Konzepte", "",
              f"Neue Konzepte haben Vorrang. Warteschlange: {', '.join(queue) or 'leer'}. Dazwischen kommen "
              f"gelaufene Konzepte nach Aufrufen gewichtet zurück; Ausreißer nach oben (mind. {simchannel.STANDOUT}× "
              f"Kanal-Median von {base:.0f} Aufrufen) deutlich öfter: {', '.join(stars) or 'noch keiner'}.", "",
              "| Konzept | Posts | Aufrufe vs. Median | bestes Video | Trend-Anteil |", "|---|---:|---:|---:|---:|"]
    for k, (r, n, best) in sorted(perf.items(), key=lambda kv: -kv[1][0]):
        lines.append(f"| {k}{' ⭐' if k in stars else ''} | {n} | ×{r} | {best} | "
                     f"{round(100 * t['trend_share'].get(k, 0))} % |")
    lines += ["", "## Angesagte Schlagwörter", "", ", ".join(t.get("trend_keywords") or ["–"]), "",
              "## Hashtags in den Captions", "", " ".join(f"#{h}" for h in ["satisfying"] + t.get("hashtags", [])[:3]), "",
              "## Titel-Zusätze (werden an die Frage im Video gehängt)", ""] + [f"- … – {h}" for h in t.get("title_addons", [])] + [""]
    if fresh:
        lines += ["## Heute für YouTube empfohlen (beste Reels der letzten 30 Stunden)", ""]
        for v in fresh:
            links = ([f"[Video & Texte]({v['release']})"] if v.get("release") else []) + [f"[Reel]({v.get('instagram_url', '')})"]
            lines.append(f"- **{v['title']}** – {_views(v)} Aufrufe auf Instagram · " + " · ".join(links))
        lines.append("")
    top = sorted(vids, key=_views, reverse=True)[:10]
    lines += ["## Unsere Top 10 Reels", "", "| Titel | Format | Aufrufe | Likes | Saves | Shares |", "|---|---|---:|---:|---:|---:|"]
    for v in top:
        s = v["stats"]
        lines.append(f"| [{v['title']}]({v.get('instagram_url', '')}) | {v['kind']} | {s.get('views', 0)} | "
                     f"{s.get('likes', 0)} | {s.get('saved', 0)} | {s.get('shares', 0)} |")
    (simchannel.ROOT / "docs" / "loop-physics-trends.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
