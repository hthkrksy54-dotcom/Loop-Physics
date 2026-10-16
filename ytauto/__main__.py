"""Command line entry point.

  python -m ytauto run --langs de en           pick next topic, write/load script, render, publish
  python -m ytauto run --langs de --no-upload  same, but keep files locally (out/)
  python -m ytauto render --lang en --topic hedonic-treadmill   render only (preview)
  python -m ytauto check                       test voice, script AI and YouTube connection
  python -m ytauto sync                        match manual YouTube uploads, post Instagram Reels
  python -m ytauto carousel                    post the next Instagram quote carousel
  python -m ytauto story                       daily Instagram story (quote / Sunday recap)
  python -m ytauto highlights                  which recent stories go into which highlight
  python -m ytauto sim --kind escape           render a satisfying physics simulation Short
  python -m ytauto sims                        Loop Physics channel: render + publish the next simulation
  python -m ytauto trends                      Loop Physics: daily trend check and tuning
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

from . import check, generate, instagram, publish, render, simchannel, sims, social, sync, trends, watchdog, youtube

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "channels.json"
TOPICS = ROOT / "content" / "topics.json"
SCRIPTS = ROOT / "content" / "scripts"
STATE = ROOT / "state" / "published.json"
OUT = ROOT / "out"


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_topic(lang: str, state: dict, topics: list[dict]) -> dict:
    done = {e["id"] for e in state.get(lang, [])}
    can_write = generate.available()
    for t in topics:
        if t["id"] in done:
            continue
        if can_write or (SCRIPTS / lang / f"{t['id']}.json").exists():
            return t
    if not can_write:
        raise RuntimeError(
            "No finished script left and no LLM key configured. Add the free GEMINI_API_KEY secret (see SETUP.md)."
        )
    print("Topic backlog empty – asking the LLM for new topics", flush=True)
    new = generate.propose_topics(topics)
    if not new:
        raise RuntimeError("no new topics available")
    topics.extend(new)
    _save(TOPICS, topics)
    return new[0]


def load_or_write_script(topic: dict, lang: str) -> dict:
    path = SCRIPTS / lang / f"{topic['id']}.json"
    if path.exists():
        return _load(path, None)
    print(f"Writing new {lang} script for '{topic['id']}' with LLM", flush=True)
    example = next(iter(sorted((SCRIPTS / lang).glob("*.json"))), None)
    script = generate.generate_script(topic, lang, _load(example, None) if example else None)
    _save(path, script)
    return script


def produce(lang: str, topic_id: str | None, upload: bool, with_short: bool, keep_record: bool = True) -> dict:
    cfg = _load(CONFIG, {})[lang]
    topics = _load(TOPICS, [])
    state = _load(STATE, {})
    topic = next((t for t in topics if t["id"] == topic_id), None) if topic_id else next_topic(lang, state, topics)
    if topic is None:
        raise SystemExit(f"unknown topic {topic_id}")
    script = load_or_write_script(topic, lang)
    print(f"[{lang}] {script['title']}", flush=True)

    outdir = OUT / lang / script["id"]
    long = render.render_long(script, cfg, outdir)
    print(f"  long video: {long['duration'] / 60:.1f} min", flush=True)
    short = render.render_short(script, cfg, outdir) if with_short else None
    long["cover"] = social.reel_cover(outdir / "cover.jpg", script, cfg)  # vertical cover for the Instagram Reel

    record = {
        "id": script["id"],
        "title": script["title"],
        "date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "duration_min": round(long["duration"] / 60, 1),
    }
    if upload:
        connected = youtube.configured(cfg["youtube"]["refresh_token_secret"])
        if connected and cfg["youtube"].get("upload_enabled"):
            record.update(publish.to_youtube(script, cfg, long, short))
        else:
            reason = "upload paused until the API audit is approved" if connected else "YouTube not connected yet"
            print(f"  YouTube: {reason} – files are in the GitHub release", flush=True)
        # Every video is archived as a release; its public Short URL also feeds Instagram.
        release = publish.to_github_release(script, cfg, long, short)
        short_url = release.pop("short_url", None)
        record.update(release)
        if short_url:
            record["short_url"] = short_url
        # The Reel goes out right away – with a link to the video once it is on YouTube, else "link in bio".
        if short and short_url and instagram.configured(cfg):
            try:
                yt_url = f"https://youtu.be/{record['youtube_id']}" if record.get("youtube_id") else None
                record.update(instagram.post_reel(cfg, short_url, instagram.caption(script, cfg, yt_url),
                                                  highlight=social.highlight_for(script), label=script["short"]["title"],
                                                  cover_url=record.get("cover_url")))
            except Exception as err:  # Instagram must never block the YouTube side
                record.setdefault("warnings", []).append(f"instagram: {err}")
                print(f"  warning: instagram reel failed: {err}", flush=True)
        if keep_record:
            state = _load(STATE, {})
            state.setdefault(lang, []).append(record)
            _save(STATE, state)
    return record


def post_carousel(lang: str, cfg: dict, render_only: bool = False) -> bool:
    """Post a quote carousel for the oldest published video that has none yet (live on YouTube first)."""
    state = _load(STATE, {})
    now = dt.datetime.now(dt.timezone.utc)
    last = max((dt.datetime.fromisoformat(r["carousel_date"]) for r in state.get(lang, []) if r.get("carousel_date")), default=None)
    if last and now - last < dt.timedelta(hours=30) and not render_only:
        print(f"[{lang}] a carousel already went out at {last:%Y-%m-%d %H:%M} UTC – skipping", flush=True)
        return False
    records = [r for r in state.get(lang, []) if not r.get("carousel_id")]
    records.sort(key=lambda r: not r.get("youtube_id"))  # stable: oldest video with a YouTube link first
    for rec in records:
        path = SCRIPTS / lang / f"{rec['id']}.json"
        script = _load(path, None)
        if script is None:
            continue
        if not script.get("carousel"):
            if not generate.available():
                continue
            try:
                script.update(generate.social_extras(script))
                _save(path, script)
            except Exception as err:
                print(f"[{lang}] no carousel for '{rec['id']}': {err}", flush=True)
                continue
        outdir = OUT / lang / script["id"] / "carousel"
        slides = social.carousel(script, cfg, outdir)
        print(f"[{lang}] carousel '{rec['id']}': {len(slides)} slides in {outdir}", flush=True)
        if render_only:
            return False
        images = list(slides)
        quote = social.best_quote(script)
        if quote:  # the same day a quote card goes to Stories (feeds the "Quotes" highlight)
            images.append(social.quote_story(outdir / "story_quote.jpg", quote["text"], quote["author"],
                                             render.seed_for(script), "@" + cfg["instagram"].get("account", "")))
        tag = f"carousel-{lang}-{script['id']}"
        rel = publish.github_release(
            tag, f"[{lang.upper()}] Carousel – {script['carousel']['cover']}",
            f"Instagram carousel for “{script['title']}”.",
            [(p, f"{tag}-{p.stem}.jpg", "image/jpeg") for p in images],
        )
        urls = {p: rel.get("assets", {}).get(f"{tag}-{p.stem}.jpg") for p in images}
        if not all(urls[p] for p in slides):
            raise RuntimeError("carousel images could not be published as release assets")
        yt = f"https://youtu.be/{rec['youtube_id']}" if rec.get("youtube_id") else None
        rec.update(instagram.post_carousel(cfg, [urls[p] for p in slides], instagram.carousel_caption(script, cfg, yt)))
        rec["carousel_date"] = now.isoformat(timespec="seconds")
        _save(STATE, state)
        if quote and urls.get(images[-1]):
            try:
                rec["quote_story_id"] = instagram.post_story(cfg, image_url=urls[images[-1]], kind="quote", highlight="Quotes",
                                                             label=f"{quote['author']}: {quote['text'][:60]}")
                _save(STATE, state)
            except Exception as err:
                print(f"  warning: quote story failed: {err}", flush=True)
        return True
    print(f"[{lang}] no video left without a carousel", flush=True)
    return False


def daily_story(lang: str, cfg: dict, force: bool = False) -> bool:
    """Keep a fresh story up every day: Sunday a weekly recap, otherwise a quote – unless a Reel or
    carousel story already went out in the last 20 hours."""
    now = dt.datetime.now(dt.timezone.utc)
    sunday = now.weekday() == 6
    if not (force or sunday):
        fresh = [s for s in instagram.live_stories(cfg)
                 if now - dt.datetime.strptime(s["timestamp"], "%Y-%m-%dT%H:%M:%S%z") < dt.timedelta(hours=20)]
        if fresh:
            print(f"[{lang}] {len(fresh)} fresh stor{'y' if len(fresh) == 1 else 'ies'} already up – nothing to do", flush=True)
            return False
    state = _load(STATE, {})
    records = state.get(lang, [])
    scripts = {r["id"]: _load(SCRIPTS / lang / f"{r['id']}.json", None) for r in records}
    live = [r for r in records if r.get("youtube_id") and scripts.get(r["id"])]
    outdir = OUT / lang / "stories"
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y-%m-%d")
    week = [r for r in live if now - dt.datetime.fromisoformat(r["date"]) < dt.timedelta(days=8)]

    if sunday and week:
        path = social.story_card(
            outdir / f"{stamp}-week.jpg", "This week", cfg["channel_name"],
            [scripts[r["id"]]["title_card"] for r in week] + ["Full video essays on YouTube – link in bio"],
            seed=now.isocalendar()[1],
        )
        kind, highlight, label = "recap", None, f"week {now:%G-W%V}: {len(week)} videos"
    else:
        pool = social.quote_pool([scripts[r["id"]] for r in live] or [s for s in scripts.values() if s])
        if not pool:
            print(f"[{lang}] no quotes available for a story", flush=True)
            return False
        used = {}
        for i, e in enumerate(instagram.story_log(cfg)):
            if e.get("kind") == "quote":
                used[e.get("label", "")] = i
        key = lambda q: f"{q['author']}: {q['text'][:60]}"
        quote = min(pool, key=lambda q: used.get(key(q), -1))  # unused first, then the longest-ago one
        path = social.quote_story(outdir / f"{stamp}-quote.jpg", quote["text"], quote["author"],
                                  render.seed_for(quote["script"]) + now.toordinal(), "@" + cfg["instagram"].get("account", ""))
        kind, highlight, label = "quote", "Quotes", key(quote)

    url = publish.release_asset(f"stories-{lang}", f"[{lang.upper()}] Instagram stories", path,
                                f"story-{lang}-{path.name}", "image/jpeg")
    if not url:
        raise RuntimeError("story image could not be published as a release asset")
    instagram.post_story(cfg, image_url=url, kind=kind, highlight=highlight, label=label)
    return True


def highlight_list(cfg: dict, days: int = 7) -> list[str]:
    """Stories of the last days, grouped by the highlight they belong in (for the owner to file)."""
    now = dt.datetime.now(dt.timezone.utc)
    groups: dict[str, list[str]] = {}
    for e in instagram.story_log(cfg):
        if e.get("highlight") and now - dt.datetime.fromisoformat(e["date"]) < dt.timedelta(days=days):
            day = dt.datetime.fromisoformat(e["date"]).strftime("%a %d.%m.")
            groups.setdefault(e["highlight"], []).append(f"{day} {e['kind']}: {e.get('label', '')}")
    return [f"{h}: " + " | ".join(items) for h, items in groups.items()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ytauto")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--langs", nargs="+", default=["de", "en"])
    run.add_argument("--topic")
    run.add_argument("--no-upload", action="store_true")
    run.add_argument("--no-short", action="store_true")
    run.add_argument("--no-record", action="store_true", help="test run: publish but don't mark the topic as done")
    ren = sub.add_parser("render")
    ren.add_argument("--lang", required=True)
    ren.add_argument("--topic", required=True)
    ren.add_argument("--no-short", action="store_true")
    sub.add_parser("check")
    sub.add_parser("sync", help="match manual YouTube uploads, fix Shorts, post Instagram Reels")
    car = sub.add_parser("carousel", help="post the next Instagram quote carousel")
    car.add_argument("--render-only", action="store_true")
    sto = sub.add_parser("story", help="daily Instagram story (quote, or Sunday weekly recap)")
    sto.add_argument("--force", action="store_true", help="post even if a fresh story is already up")
    sm = sub.add_parser("sim", help="render a satisfying physics simulation (vertical, with generated melody)")
    sm.add_argument("--kind", choices=sorted(sims.KINDS), default="escape")
    sm.add_argument("--seed", type=int, help="fixed seed; default: first seed after --start with a 35-55 s run")
    sm.add_argument("--start", type=int, default=0)
    sm.add_argument("--melody", choices=sorted(sims.MELODIES))
    sm.add_argument("--handle", default="")
    sc = sub.add_parser("sims", help="Loop Physics channel: render and publish the next simulation Short")
    sc.add_argument("--no-upload", action="store_true")
    sc.add_argument("--branding", action="store_true", help="set banner, description and keywords on YouTube")
    sc.add_argument("--youtube", choices=["check", "apply"], help="match manual YouTube uploads and polish them")
    sub.add_parser("trends", help="Loop Physics: daily trend check, writes config/sims_tuning.json")
    sub.add_parser("watchdog", help="print overdue workflows as JSON lines (file, inputs)")
    hl = sub.add_parser("highlights", help="list recent stories by the highlight they belong in")
    hl.add_argument("--days", type=int, default=7)
    args = ap.parse_args(argv)

    if args.cmd == "check":
        return check.run(_load(CONFIG, {}))
    if args.cmd == "sync":
        config, state = _load(CONFIG, {}), _load(STATE, {})
        changed = False
        for lang, cfg in config.items():
            if cfg.get("active", True):
                changed |= sync.run(lang, cfg, state, lambda tid, lang=lang: _load(SCRIPTS / lang / f"{tid}.json", None))
        if changed:
            _save(STATE, state)
        return 0

    if args.cmd == "carousel":
        for lang, cfg in _load(CONFIG, {}).items():
            if cfg.get("active", True) and (args.render_only or instagram.configured(cfg)):
                post_carousel(lang, cfg, render_only=args.render_only)
        return 0

    if args.cmd == "sim":
        seed = args.seed if args.seed is not None else sims.pick_seed(args.kind, args.start)
        result = sims.render(args.kind, seed, OUT / "sims" / f"{args.kind}-{seed}.mp4", args.melody, args.handle)
        print(f"{result['video']}  ({result['duration']:.1f}s, {result['melody_name']})")
        return 0

    if args.cmd == "sims":
        if args.branding:
            simchannel.branding()
        elif args.youtube:
            simchannel.youtube_polish(apply=args.youtube == "apply")
        else:
            simchannel.run(upload=not args.no_upload)
        return 0

    if args.cmd == "watchdog":
        for wf, inputs in watchdog.due():
            print(json.dumps({"workflow": wf, "inputs": inputs}))
        return 0

    if args.cmd == "trends":
        trends.run()
        return 0

    if args.cmd == "highlights":
        for lang, cfg in _load(CONFIG, {}).items():
            if cfg.get("active", True) and cfg.get("instagram", {}).get("enabled"):
                print("\n".join(highlight_list(cfg, args.days)) or f"[{lang}] no new stories")
        return 0

    if args.cmd == "story":
        for lang, cfg in _load(CONFIG, {}).items():
            if cfg.get("active", True) and instagram.configured(cfg):
                daily_story(lang, cfg, force=args.force)
        return 0

    if args.cmd == "render":
        produce(args.lang, args.topic, upload=False, with_short=not args.no_short)
        return 0

    failed = []
    config = _load(CONFIG, {})
    import os
    unattended = os.environ.get("GITHUB_EVENT_NAME") == "schedule" or os.environ.get("IN_SOURCE") == "watchdog"
    today = dt.datetime.now(dt.timezone.utc).date()
    for lang in args.langs:
        if unattended and any(dt.datetime.fromisoformat(r["date"]).date() == today for r in _load(STATE, {}).get(lang, [])):
            print(f"[{lang}] today's video is already out – skipping", flush=True)
            continue
        if not config.get(lang, {}).get("active", True):
            print(f"[{lang}] paused (\"active\": false in config/channels.json) – skipping", flush=True)
            continue
        try:
            produce(lang, args.topic, upload=not args.no_upload, with_short=not args.no_short, keep_record=not args.no_record)
        except Exception:
            traceback.print_exc()
            failed.append(lang)
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
