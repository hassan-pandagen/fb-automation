"""
Fetches fresh US news from RSS feeds for each niche.
Runs every 2 hours. Deduplicates against the database.
"""

import hashlib
import logging
import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Optional
from bs4 import BeautifulSoup

from core.config import NicheConfig
from core.database import ContentItem, db

logger = logging.getLogger(__name__)


def _item_id(title: str) -> str:
    return hashlib.md5(title.strip().lower().encode()).hexdigest()


def _extract_image(entry) -> str:
    """Try to pull a usable image from an RSS entry."""
    # 1. media:content tag
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            if m.get("type", "").startswith("image"):
                return m.get("url", "")

    # 2. enclosures
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if "image" in enc.get("type", ""):
                return enc.get("href", "")

    # 3. Parse first <img> from summary HTML
    summary = getattr(entry, "summary", "") or ""
    soup = BeautifulSoup(summary, "lxml")
    img = soup.find("img")
    if img and img.get("src"):
        return img["src"]

    return ""


def _is_us_relevant(title: str, summary: str, keywords: List[str]) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in keywords)


def fetch_news_for_niche(niche_cfg: NicheConfig, max_per_feed: int = 10) -> int:
    """
    Fetches RSS items for a niche, saves new ones to DB.
    Returns count of new items saved.
    """
    new_count = 0
    cutoff = datetime.utcnow() - timedelta(hours=48)

    db.connect(reuse_if_open=True)

    for feed_url in niche_cfg.rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
            entries = feed.entries[:max_per_feed]

            for entry in entries:
                title   = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "").strip()
                link    = getattr(entry, "link", "").strip()

                if not title or len(title) < 15:
                    continue

                item_id = _item_id(title)

                # Skip duplicates
                if ContentItem.select().where(ContentItem.id == item_id).exists():
                    continue

                # Basic US relevance check
                if not _is_us_relevant(title, summary, niche_cfg.keywords):
                    # Still save it — caption AI will handle filtering
                    pass

                image_url = _extract_image(entry)

                ContentItem.create(
                    id            = item_id,
                    niche         = niche_cfg.name,
                    title         = title,
                    summary       = summary[:500],
                    source_url    = link,
                    image_url     = image_url,
                    discovered_at = datetime.utcnow(),
                    used          = False,
                )
                new_count += 1
                logger.info(f"[{niche_cfg.name}] New item: {title[:60]}")

        except Exception as e:
            logger.error(f"Feed error {feed_url}: {e}")

    db.close()
    return new_count


def get_unused_items(niche: str, limit: int = 20) -> List[ContentItem]:
    """Returns unused content items for a niche, newest first."""
    db.connect(reuse_if_open=True)
    items = list(
        ContentItem
        .select()
        .where(ContentItem.niche == niche, ContentItem.used == False)
        .order_by(ContentItem.discovered_at.desc())
        .limit(limit)
    )
    db.close()
    return items
