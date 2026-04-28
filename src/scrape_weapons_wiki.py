"""Scrape weapon stats from apexlegends.wiki.gg and/or apexlegends.fandom.com.

Both sites are MediaWiki. Their public web pages return 403 to our UA, but the
MediaWiki API (/api.php) answers fine. For each weapon page we grab the raw
wikitext and a parsed version of its {{Infobox-Weapon ...}} template.

Output layout per wiki:
  data/weapons_wiki/{wiki}/wikitext/{slug}.txt   # raw wikitext
  data/weapons_wiki/{wiki}/infobox/{slug}.json   # parsed infobox fields
  data/weapons_wiki/{wiki}/index.json            # list of scraped pages

No reconciliation or schema normalisation here. Downstream processing decides
how to fold these into guns_stats.csv.
"""
import json
import logging
import os
import re
import time
from argparse import ArgumentParser

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

WIKIS = {
    "wikigg": "https://apexlegends.wiki.gg/api.php",
    "fandom": "https://apexlegends.fandom.com/api.php",
}
HEADERS = {"User-Agent": "apexlegends-data-analysis research (github.com/mo-arvan)"}

INFOBOX_START_RE = re.compile(r"\{\{\s*Infobox[-_\s]?Weapon", re.IGNORECASE)
LEVEL0123_RE = re.compile(r"\{\{\s*Level0123\s*\|([^}]+)\}\}", re.IGNORECASE)
FILE_WIKILINK_RE = re.compile(r"\[\[\s*File:[^\]]*?\]\]", re.IGNORECASE)
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def fetch_category_members(base_url, category="Weapons"):
    titles = []
    cmcontinue = None
    while True:
        params = {"action": "query", "list": "categorymembers",
                  "cmtitle": f"Category:{category}", "cmlimit": "500", "format": "json"}
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        r = requests.get(base_url, params=params, headers=HEADERS, timeout=(5, 30))
        r.raise_for_status()
        data = r.json()
        for m in data.get("query", {}).get("categorymembers", []):
            if m["ns"] == 0:
                titles.append(m["title"])
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break
    return titles


def fetch_wikitext(base_url, title):
    params = {"action": "parse", "page": title, "format": "json", "prop": "wikitext"}
    r = requests.get(base_url, params=params, headers=HEADERS, timeout=(5, 30))
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"API error for {title}: {data['error']}")
    return data["parse"]["wikitext"]["*"]


def extract_infobox(wikitext):
    """Find {{Infobox-Weapon ...}} and return the full template text."""
    m = INFOBOX_START_RE.search(wikitext)
    if not m:
        return None
    start = m.start()
    # Walk forward, tracking {{ / }} depth. Treat [[ / ]] similarly so internal
    # wikilinks with | don't confuse later field splitting.
    depth = 0
    i = start
    while i < len(wikitext):
        two = wikitext[i:i + 2]
        if two == "{{":
            depth += 1
            i += 2
            continue
        if two == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return wikitext[start:i]
            continue
        i += 1
    return None  # unterminated


def split_infobox_fields(infobox_text):
    """Parse {{Infobox-Weapon | k=v | k=v ...}} into a dict."""
    if not (infobox_text.startswith("{{") and infobox_text.endswith("}}")):
        return {}
    inner = infobox_text[2:-2]

    # Find first top-level | (marks end of template name, start of first field).
    depth = 0
    first_pipe = -1
    i = 0
    while i < len(inner):
        two = inner[i:i + 2]
        if two in ("{{", "[["):
            depth += 1
            i += 2
            continue
        if two in ("}}", "]]"):
            depth -= 1
            i += 2
            continue
        if inner[i] == "|" and depth == 0:
            first_pipe = i
            break
        i += 1
    if first_pipe < 0:
        return {}

    body = inner[first_pipe + 1:]

    # Split body on top-level |, respecting {{ }} and [[ ]] depth.
    parts = []
    buf = []
    depth = 0
    i = 0
    while i < len(body):
        two = body[i:i + 2]
        if two in ("{{", "[["):
            depth += 1
            buf.append(two)
            i += 2
            continue
        if two in ("}}", "]]"):
            depth -= 1
            buf.append(two)
            i += 2
            continue
        if body[i] == "|" and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(body[i])
        i += 1
    if buf:
        parts.append("".join(buf).strip())

    fields = {}
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        fields[k.strip()] = v.strip()
    return fields


def clean_value(v):
    """Turn wiki markup into a Python-friendly value.

    {{Level0123|a|b|c|d}}      -> ['a','b','c','d']
    [[File:Icon.svg|25px|...]] -> '' (dropped, they leak page-chrome into numbers)
    [[Light Rounds]]           -> 'Light Rounds'
    [[Page|Display Text]]      -> 'Display Text' (take the last | segment)
    Plain scalar               -> stripped string
    """
    if not v:
        return v
    m = LEVEL0123_RE.search(v)
    if m:
        return [p.strip() for p in m.group(1).split("|")]
    # File-image wikilinks never contain the display text we want; drop them entirely.
    v = FILE_WIKILINK_RE.sub("", v)
    # For remaining wikilinks, keep the display text (the part after the last |).
    v = WIKILINK_RE.sub(lambda mm: mm.group(1).rsplit("|", 1)[-1], v)
    v = HTML_TAG_RE.sub("", v)
    return v.strip()


def parse_infobox(wikitext):
    ib = extract_infobox(wikitext)
    if not ib:
        return {}
    raw = split_infobox_fields(ib)
    return {k: clean_value(v) for k, v in raw.items()}


def safe_slug(title):
    return title.replace("/", "__").replace(" ", "_")


def main():
    parser = ArgumentParser()
    parser.add_argument("--wiki", choices=list(WIKIS.keys()) + ["both"], default="both")
    parser.add_argument("--out-dir", default="data/weapons_wiki")
    parser.add_argument("--category", default="Weapons")
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    wikis_to_scrape = list(WIKIS.keys()) if args.wiki == "both" else [args.wiki]

    for wiki in wikis_to_scrape:
        base = WIKIS[wiki]
        out = os.path.join(args.out_dir, wiki)
        wt_dir = os.path.join(out, "wikitext")
        ib_dir = os.path.join(out, "infobox")
        os.makedirs(wt_dir, exist_ok=True)
        os.makedirs(ib_dir, exist_ok=True)

        logger.info(f"[{wiki}] fetching Category:{args.category}")
        titles = fetch_category_members(base, args.category)
        logger.info(f"[{wiki}] {len(titles)} pages")

        index = []
        for i, title in enumerate(titles, 1):
            slug = safe_slug(title)
            try:
                wt = fetch_wikitext(base, title)
            except Exception as exc:
                logger.error(f"  [{i}/{len(titles)}] {title}: FAILED {exc}")
                continue
            with open(os.path.join(wt_dir, f"{slug}.txt"), "w") as fh:
                fh.write(wt)
            infobox = parse_infobox(wt)
            with open(os.path.join(ib_dir, f"{slug}.json"), "w") as fh:
                json.dump({"title": title, "infobox": infobox}, fh, indent=2, ensure_ascii=False)
            logger.info(f"  [{i}/{len(titles)}] {title}  fields={len(infobox)}")
            index.append({"title": title, "slug": slug,
                          "has_infobox": bool(infobox), "field_count": len(infobox)})
            time.sleep(args.sleep)

        with open(os.path.join(out, "index.json"), "w") as fh:
            json.dump(index, fh, indent=2, ensure_ascii=False)
        logger.info(f"[{wiki}] done. {out}/index.json")


if __name__ == "__main__":
    main()
