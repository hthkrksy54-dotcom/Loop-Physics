"""Command line entry point.

  python -m ytauto run --langs de en           pick next topic, write/load script, render, publish
  python -m ytauto run --langs de --no-upload  same, but keep files locally (out/)
  python -m ytauto render --lang en --topic hedonic-treadmill   render only (preview)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

from . import generate, publish, render, youtube

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
    for t in topics:
        if t["id"] not in done:
            return t
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


def produce(lang: str, topic_id: str | None, upload: bool, with_short: bool) -> dict:
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

    record = {
        "id": script["id"],
        "title": script["title"],
        "date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "duration_min": round(long["duration"] / 60, 1),
    }
    if upload:
        if youtube.configured(cfg["youtube"]["refresh_token_secret"]):
            record.update(publish.to_youtube(script, cfg, long, short))
        else:
            print("  YouTube not connected yet – publishing as GitHub release instead", flush=True)
            record.update(publish.to_github_release(script, cfg, long, short))
        state = _load(STATE, {})
        state.setdefault(lang, []).append(record)
        _save(STATE, state)
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ytauto")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--langs", nargs="+", default=["de", "en"])
    run.add_argument("--topic")
    run.add_argument("--no-upload", action="store_true")
    run.add_argument("--no-short", action="store_true")
    ren = sub.add_parser("render")
    ren.add_argument("--lang", required=True)
    ren.add_argument("--topic", required=True)
    ren.add_argument("--no-short", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "render":
        produce(args.lang, args.topic, upload=False, with_short=not args.no_short)
        return 0

    failed = []
    for lang in args.langs:
        try:
            produce(lang, args.topic, upload=not args.no_upload, with_short=not args.no_short)
        except Exception:
            traceback.print_exc()
            failed.append(lang)
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
