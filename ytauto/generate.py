"""Script generation with free LLM tiers.

Providers (tried in order, whichever is configured):
  * GitHub Models  – free inside GitHub Actions via GITHUB_TOKEN (permission `models: read`)
  * Google Gemini  – free tier, needs GEMINI_API_KEY

Generation runs in small steps (outline, narration in two halves, fact review) so each
response stays inside free-tier output limits.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

LANG_NAMES = {"de": "German", "en": "English"}
WORD_TARGET = {"de": (1050, 1450), "en": (1150, 1550)}

SYSTEM = """You write scripts for a calm, thoughtful YouTube channel about philosophy and psychology.
Style: warm, clear, unhurried; short spoken sentences; second person ("you") where natural; concrete
everyday examples; no hype, no clickbait, no filler phrases like "in this video", no calls to like or
subscribe. Write natively in the target language (not a translation).
Accuracy rules (critical):
- Only mention studies, dates, people and books you are certain exist. Prefer well-established findings.
- When research is contested or failed to replicate, say so plainly.
- Only quote a text if you are certain the wording is an established translation or a faithful
  rendering of a real passage, and give the exact source (work and chapter). Otherwise paraphrase.
- Never invent statistics. Avoid precise numbers unless certain.
- Psychology topics are educational: no diagnosis, no treatment advice, no promises of cures.
- Write numbers as words except years (e.g. 1971).
Output strictly valid JSON, no markdown fences."""


class LLMError(RuntimeError):
    pass


class NotConfigured(LLMError):
    pass


def _github_models(messages: list[dict], max_tokens: int) -> str:
    token = os.environ.get("GITHUB_MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise NotConfigured("no GitHub token")
    model = os.environ.get("GITHUB_MODELS_MODEL") or "openai/gpt-4.1"
    url = "https://models.github.ai/inference/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    # Follow redirects manually so the request stays a POST with its body.
    for _ in range(4):
        resp = requests.post(url, headers=headers, json=body, timeout=180, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
            url = requests.compat.urljoin(url, resp.headers["Location"])
            continue
        break
    if resp.status_code != 200:
        raise LLMError(f"GitHub Models {resp.status_code}: {resp.text[:300]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as err:
        raise LLMError(
            f"GitHub Models unexpected response ({err}; url={resp.url}; type={resp.headers.get('content-type')}): {resp.text[:300]!r}"
        )
    if not content:
        raise LLMError(f"GitHub Models returned empty content: {resp.text[:300]!r}")
    return content


def _gemini(messages: list[dict], max_tokens: int) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise NotConfigured("no GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max(max_tokens, 8192),
                "responseMimeType": "application/json",
            },
        },
        timeout=240,
    )
    if resp.status_code != 200:
        raise LLMError(f"Gemini {resp.status_code}: {resp.text[:300]}")
    try:
        parts = resp.json()["candidates"][0]["content"]["parts"]
    except (ValueError, KeyError, IndexError, TypeError) as err:
        raise LLMError(f"Gemini unexpected response ({err}): {resp.text[:300]!r}")
    return "".join(p.get("text", "") for p in parts)


PROVIDERS = {"github": _github_models, "gemini": _gemini}


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def ask_json(prompt: str, max_tokens: int = 3500) -> dict:
    order = os.environ.get("LLM_PROVIDERS", "github,gemini").split(",")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    errors = []
    for name in order:
        fn = PROVIDERS.get(name.strip())
        if not fn:
            continue
        for attempt in range(3):
            try:
                return _parse_json(fn(messages, max_tokens))
            except NotConfigured as err:
                errors.append(str(err))
                break
            except (LLMError, requests.RequestException) as err:
                errors.append(f"{name}: {err}")
                print(f"  LLM attempt failed: {name}: {err}", flush=True)
                time.sleep(10 * (attempt + 1))
            except (json.JSONDecodeError, KeyError, IndexError) as err:
                errors.append(f"{name}: response was not valid JSON ({err})")
                print(f"  LLM returned invalid JSON: {name}: {err}", flush=True)
    raise LLMError("All LLM providers failed: " + " | ".join(errors[-6:]))


def _words(script: dict) -> int:
    n = 0
    for s in script["sections"]:
        n += len(s.get("text", "").split())
        q = s.get("quote") or {}
        n += len(q.get("lead", "").split()) + len(q.get("text", "").split())
    return n


def generate_script(topic: dict, lang: str, example: dict | None = None) -> dict:
    language = LANG_NAMES[lang]
    lo, hi = WORD_TARGET[lang]
    example_hint = ""
    if example:
        trimmed = {k: example[k] for k in ("title", "title_card", "thumbnail_text", "label") if k in example}
        trimmed["first_section"] = example["sections"][0]["text"][:700]
        example_hint = "Example of the house style (do not reuse its content):\n" + json.dumps(trimmed, ensure_ascii=False)

    outline = ask_json(
        f"""Plan a {language} video essay (about 9-10 minutes spoken) on this topic.
Topic id: {topic['id']}
Category: {topic['category']}
Brief: {topic['brief']}
{example_hint}

Return JSON:
{{
 "label": "one or two words naming the field, e.g. Stoicism / Psychology (in {language})",
 "title": "YouTube title, max 90 characters, curiosity without clickbait, may use ' – ' subtitle",
 "title_card": "short form of the title, max 45 characters",
 "thumbnail_text": "3-6 word statement or question for the thumbnail",
 "description": "2-4 sentence YouTube description in {language}",
 "tags": ["10-14 search tags in {language}"],
 "hashtags": "three hashtags",
 "sections": [
   {{"heading": null, "points": ["hook: a relatable everyday scene", "the question the video answers"]}},
   {{"heading": "chapter title (2-5 words)", "points": ["key points with concrete facts"],
     "quote": {{"lead": "one sentence introducing the quote", "text": "quote", "author": "Author, Work chapter"}} or null}}
 ],
 "short": {{"title": "Shorts title, max 70 characters", "text": "a self-contained 100-120 word version for a vertical short"}},
 "sources": ["full references for every study, book and quote used"]
}}
Use 6-7 sections in total (hook + 5-6 chapters). At most 3 quotes. The last chapter offers one practical
reflection or exercise and a quiet closing thought.""",
        max_tokens=3000,
    )

    sections = outline["sections"]
    written: list[str] = []
    half = (len(sections) + 1) // 2
    for part in (sections[:half], sections[half:]):
        start_index = len(written)
        result = ask_json(
            f"""Write the spoken narration in {language} for these sections of the video "{outline['title']}".
Full outline for context: {json.dumps(sections, ensure_ascii=False)}
Already written (continue seamlessly, do not repeat): {json.dumps(written, ensure_ascii=False)[-2500:]}

Write sections {start_index} to {start_index + len(part) - 1} only:
{json.dumps(part, ensure_ascii=False)}

Rules: about {(lo + hi) // 2 // len(sections)} words per section; paragraphs separated by a blank line (\\n\\n);
if a section has a quote, do NOT repeat the quote or its lead in the text (they are shown separately before
the text); the text should follow on from the quote naturally.
Return JSON: {{"texts": ["narration for each requested section, in order"]}}""",
            max_tokens=3800,
        )
        texts = result["texts"]
        if len(texts) != len(part):
            raise LLMError("narration count mismatch")
        written.extend(texts)

    script = {
        "id": topic["id"],
        "lang": lang,
        "category": topic["category"],
        "label": outline["label"],
        "title": outline["title"][:100],
        "title_card": outline.get("title_card", outline["title"])[:60],
        "thumbnail_text": outline["thumbnail_text"],
        "description": outline["description"],
        "tags": outline.get("tags", [])[:15],
        "hashtags": outline.get("hashtags", ""),
        "sections": [],
        "short": outline.get("short"),
        "sources": outline.get("sources", []),
        "generated": True,
    }
    for sec, text in zip(sections, written):
        entry = {"heading": sec.get("heading"), "text": text.strip()}
        if sec.get("quote") and sec["quote"].get("text"):
            entry["quote"] = sec["quote"]
        script["sections"].append(entry)
    script["sections"][0]["heading"] = None

    review(script, language)
    validate(script)
    return script


def review(script: dict, language: str) -> None:
    """Second pass: a fact-checker removes doubtful claims and quotes (edits applied in place)."""
    result = ask_json(
        f"""You are a careful fact-checker for a {language} philosophy/psychology video script.
Check every factual claim, date, attribution, study and quote. Be strict: if you are not confident a quote's
wording or attribution is accurate, mark it for removal. If a claim is wrong or overstated, fix it.
Also fix awkward or unnatural {language} phrasing.
Script JSON: {json.dumps({k: script[k] for k in ('title', 'sections', 'short', 'sources')}, ensure_ascii=False)}

Return JSON:
{{"edits": [{{"field": "sections[i].text | short.text | title", "find": "exact substring", "replace": "new text"}}],
  "remove_quotes": [section indices whose quote should be removed],
  "remove_sources": ["exact source strings that are doubtful"],
  "notes": "short summary"}}
Return empty lists if everything is fine.""",
        max_tokens=3000,
    )
    for edit in result.get("edits", []):
        field, find, repl = edit.get("field", ""), edit.get("find", ""), edit.get("replace", "")
        if not find:
            continue
        m = re.match(r"sections\[(\d+)\]\.text", field)
        if m and int(m.group(1)) < len(script["sections"]):
            sec = script["sections"][int(m.group(1))]
            sec["text"] = sec["text"].replace(find, repl)
        elif field == "short.text" and script.get("short"):
            script["short"]["text"] = script["short"]["text"].replace(find, repl)
        elif field == "title":
            script["title"] = script["title"].replace(find, repl)
    for i in result.get("remove_quotes", []):
        if isinstance(i, int) and i < len(script["sections"]):
            script["sections"][i].pop("quote", None)
    bad = set(result.get("remove_sources", []))
    script["sources"] = [s for s in script["sources"] if s not in bad]
    script["review_notes"] = result.get("notes", "")


def validate(script: dict) -> None:
    lo, hi = WORD_TARGET[script["lang"]]
    n = _words(script)
    if n < lo * 0.75:
        raise LLMError(f"script too short ({n} words)")
    if len(script["sections"]) < 4:
        raise LLMError("too few sections")
    for s in script["sections"][1:]:
        if not s.get("heading"):
            raise LLMError("missing chapter heading")
    if re.search(r"[<>]", script["title"] + script["description"]):
        script["title"] = re.sub(r"[<>]", "", script["title"])
        script["description"] = re.sub(r"[<>]", "", script["description"])


def propose_topics(existing: list[dict], count: int = 12) -> list[dict]:
    ids = [t["id"] for t in existing]
    result = ask_json(
        f"""Propose {count} new topics for a calm philosophy and psychology channel, alternating categories.
Avoid these existing topics: {json.dumps(ids)}
Prefer timeless, well-documented ideas with concrete anchors (named thinkers, works, classic studies).
Return JSON: {{"topics": [{{"id": "kebab-case-id", "category": "philosophy|psychology",
"brief": "one sentence naming the key works, studies and facts to cover"}}]}}""",
        max_tokens=2000,
    )
    out = []
    for t in result.get("topics", []):
        tid = re.sub(r"[^a-z0-9-]", "", str(t.get("id", "")).lower())
        if tid and tid not in ids and t.get("brief"):
            out.append({"id": tid, "category": t.get("category", "philosophy"), "brief": t["brief"]})
            ids.append(tid)
    return out
