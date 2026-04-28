"""Download EA Apex Legends news posts (patch notes, designer's notes, events).

The EA site is Next.js SSR and embeds a __NEXT_DATA__ JSON blob that already
contains the article body as markdown in `articleDetailsFallback.body`. We just
fetch, extract, and save. No HTML parsing needed.

Downloads every post on the index; filtering by "is this really a patch note"
is deferred to analysis code. Midseason balance updates frequently live inside
event-themed posts (e.g. aftershock-event, winter-wipeout-event), so a title
filter misses real patch content.

Usage:
  uv run python src/scrape_patch_notes.py --max-pages 20         # full history
  uv run python src/scrape_patch_notes.py                        # most recent page only
  uv run python src/scrape_patch_notes.py --url <url1> <url2>    # additional explicit URLs
  uv run python src/scrape_patch_notes.py --no-index --url <u>   # only explicit URLs
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

NEWS_INDEX = "https://www.ea.com/en/games/apex-legends/apex-legends/news"
ARTICLE_BASE = "https://www.ea.com/en/games/apex-legends/apex-legends/news/"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', re.DOTALL)


def fetch_next_data(url):
    r = requests.get(url, headers=HEADERS, timeout=(5, 30))
    logger.debug(f"GET {url} -> {r.status_code}")
    r.raise_for_status()
    match = NEXT_DATA_RE.search(r.text)
    if not match:
        raise RuntimeError(f"No __NEXT_DATA__ in {url} (site may have changed)")
    return json.loads(match.group(1))


def fetch_index_items(max_pages=1, sleep=0.5):
    """Fetch posts from the news index, paginating via ?page=N&type=latest.

    Stops on the first empty page or when a page returns no new slugs.
    """
    all_items = []
    seen_slugs = set()
    for page in range(1, max_pages + 1):
        url = NEWS_INDEX if page == 1 else f"{NEWS_INDEX}?page={page}&type=latest"
        data = fetch_next_data(url)
        items = data["props"]["pageProps"]["newsDataFallback"]["items"]
        new_items = [it for it in items if it.get("slug") not in seen_slugs]
        logger.info(f"  page {page}: {len(items)} items ({len(new_items)} new)")
        if not new_items:
            break
        for it in new_items:
            seen_slugs.add(it.get("slug"))
            all_items.append(it)
        if page < max_pages:
            time.sleep(sleep)
    logger.info(f"Index returned {len(all_items)} unique posts across {page} page(s)")
    return all_items


def fetch_article(url):
    data = fetch_next_data(url)
    return data["props"]["pageProps"]["articleDetailsFallback"]


def save_article(article, raw_dir, clean_dir):
    slug = article["slug"]
    date = (article.get("publishingDate") or "")[:10]  # YYYY-MM-DD
    title = article.get("title", "")
    tags = [t.get("name") if isinstance(t, dict) else t for t in (article.get("tags") or [])]
    body = article.get("body", "") or ""

    raw_path = os.path.join(raw_dir, f"{slug}.json")
    with open(raw_path, "w") as fh:
        json.dump(article, fh, indent=2, ensure_ascii=False)

    md_name = f"{date}_{slug}.md" if date else f"{slug}.md"
    md_path = os.path.join(clean_dir, md_name)
    frontmatter = (
        f"---\n"
        f"title: {json.dumps(title)}\n"
        f"date: {date}\n"
        f"slug: {slug}\n"
        f"type: {article.get('type', '')}\n"
        f"tags: {json.dumps(tags)}\n"
        f"source: {ARTICLE_BASE + slug}\n"
        f"---\n\n"
        f"# {title}\n\n"
    )
    with open(md_path, "w") as fh:
        fh.write(frontmatter + body)

    return md_path


def main():
    parser = ArgumentParser()
    parser.add_argument("--out-dir", default="data/patch_notes")
    parser.add_argument("--url", nargs="*", default=[],
                        help="Extra article URLs to download in addition to the index (or the only sources with --no-index).")
    parser.add_argument("--no-index", action="store_true", help="Skip scraping the news index; only process --url.")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds between requests (default 1).")
    parser.add_argument("--max-pages", type=int, default=1,
                        help="How many index pages to paginate through (?page=N). Default 1; set higher to fetch older posts.")
    args = parser.parse_args()

    raw_dir = os.path.join(args.out_dir, "raw")
    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    targets = []  # list of (slug, url, title) tuples

    if not args.no_index:
        for item in fetch_index_items(max_pages=args.max_pages, sleep=args.sleep):
            slug = item.get("slug", "")
            title = item.get("title", "")
            targets.append((slug, ARTICLE_BASE + slug, title))

    for url in args.url:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        targets.append((slug, url, "(explicit --url)"))

    seen = set()
    unique_targets = []
    for t in targets:
        if t[0] in seen:
            continue
        seen.add(t[0])
        unique_targets.append(t)

    logger.info(f"Downloading {len(unique_targets)} articles")
    for slug, url, title in unique_targets:
        try:
            article = fetch_article(url)
            path = save_article(article, raw_dir, args.out_dir)
            logger.info(f"  saved {path}  ({title})")
        except Exception as exc:
            logger.error(f"  FAILED {slug}: {exc}")
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
