"""GitHub drops or delays many scheduled runs. The Loop Physics timer (a run started by workflow_dispatch, which
GitHub executes reliably) calls this every ~2 hours and starts whatever is overdue."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(path: str, default):
    p = ROOT / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _today(iso: str | None, now: dt.datetime) -> bool:
    return bool(iso) and dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).date() == now.date()


def due(now: dt.datetime | None = None) -> list[tuple[str, dict]]:
    """(workflow file, dispatch inputs) for every job that should have run by now but hasn't."""
    now = now or dt.datetime.now(dt.timezone.utc)
    hm = now.hour * 60 + now.minute
    out: list[tuple[str, dict]] = [("sync.yml", {})]  # cheap and idempotent: always

    tuning = _load("config/sims_tuning.json", {})
    if not tuning.get("updated") or now - dt.datetime.fromisoformat(tuning["updated"]) > dt.timedelta(hours=24):
        out.append(("trends.yml", {}))

    config = _load("config/channels.json", {})
    published = _load("state/published.json", {})
    for lang, cfg in config.items():
        if not cfg.get("active", True):
            continue
        recs = published.get(lang, [])
        if hm >= 14 * 60 + 47 and not any(_today(r.get("date"), now) for r in recs):  # one video every day
            out.append(("produce.yml", {"langs": lang, "source": "watchdog"}))
        ig = cfg.get("instagram") or {}
        if ig.get("enabled"):
            if now.weekday() in (1, 3, 5) and hm >= 16 * 60 + 12 and \
                    not any(_today(r.get("carousel_date"), now) for r in recs):
                out.append(("carousel.yml", {}))
            stories = _load(ig.get("story_log", ""), []) if ig.get("story_log") else []
            if hm >= 18 * 60 + 41 and not any(_today(s.get("date"), now) for s in stories):
                out.append(("stories.yml", {}))
    return out
