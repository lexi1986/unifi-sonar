"""Taal van de app: Nederlands of Engels.

Teksten staan naast elkaar in de code: ``L("Zwak signaal", "Weak signal")`` geeft de tekst in de actieve taal.
De actieve taal is die van de instelling (Instellingen → Taal), behalve binnen ``use("en")``.

Wat bewaard wordt (meldingen, de tijdlijn) staat in beide talen in de database, zodat wisselen van taal ook de
historie meeneemt: meldingen krijgen hun Engelse teksten in ``issue["en"]``, gebeurtenissen een tekst als
``{"nl": ..., "en": ...}``.
"""
from __future__ import annotations

import contextvars
import json
from contextlib import contextmanager

LANGS = ("nl", "en")
TEXT_FIELDS = ("title", "detail", "advice")
_server = ["nl"]
_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("lang", default=None)


def normalize(lang: str | None) -> str | None:
    lang = (lang or "").strip().lower()[:2]
    return lang if lang in LANGS else None


def set_server(lang: str | None) -> None:
    _server[0] = normalize(lang) or "nl"


def current() -> str:
    return _ctx.get() or _server[0]


def L(nl: str, en: str) -> str:   # noqa: N802 – kort en goed zichtbaar tussen de teksten
    return en if current() == "en" else nl


@contextmanager
def use(lang: str):
    tok = _ctx.set(lang)
    try:
        yield
    finally:
        _ctx.reset(tok)


def both(fn):
    """Roep fn() aan in beide talen: {"nl": ..., "en": ...}."""
    out = {}
    for lang in LANGS:
        with use(lang):
            out[lang] = fn()
    return out


def bi(nl: str, en: str) -> dict:
    return {"nl": nl, "en": en}


def pick(v, lang: str | None = None):
    """Tekst uit een tweetalige waarde (dict of als JSON bewaard); gewone tekst blijft zoals hij is."""
    if isinstance(v, str) and v.startswith('{"nl"'):
        try:
            v = json.loads(v)
        except ValueError:
            return v
    if isinstance(v, dict) and "nl" in v:
        return v.get(lang or current()) or v["nl"]
    return v


def dump(v) -> str:
    """Voor opslag: tweetalige teksten als JSON, gewone tekst ongewijzigd."""
    return json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v


def merge_issues(nl: list[dict], en: list[dict]) -> list[dict]:
    """Nederlandse meldingen (de basis) met de Engelse teksten erbij, gekoppeld op sleutel."""
    by_key = {i["key"]: i for i in en}
    for i in nl:
        e = by_key.get(i["key"])
        if e:
            i["en"] = {f: e[f] for f in TEXT_FIELDS}
    return nl


def issue(i: dict, lang: str | None = None) -> dict:
    """Een melding in de gevraagde taal (zonder de vertaling zelf mee te sturen)."""
    lang = lang or current()
    out = {k: v for k, v in i.items() if k != "en"}
    if lang == "en" and i.get("en"):
        out.update(i["en"])
    return out


def issues(items: list[dict], lang: str | None = None) -> list[dict]:
    return [issue(i, lang) for i in items]
