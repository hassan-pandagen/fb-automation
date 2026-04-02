"""
Scheduler — decides WHEN each post fires and manages the queue.

US EST posting slots are defined in config.py per niche.
This module converts them to UTC, checks what's due, and fires them.

Runs as a continuous loop on Railway — checks every 60 seconds.
"""

import logging
import uuid
from datetime import datetime, timedelta, time
from typing import List
from zoneinfo import ZoneInfo

from core.config import load_pages, NICHE_CONFIGS, PageConfig, NicheConfig
from core.database import ScheduledPost, ContentItem, db, init_db
from core.fetcher import get_unused_items
from core.caption_gen import generate_caption
from core.image_gen import create_image_card
from core.fb_poster import FacebookPoster

logger = logging.getLogger(__name__)

EST = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def _next_slot_utc(hour: int, minute: int, from_now: datetime) -> datetime:
    """Returns the next occurrence of (hour, minute) EST as a UTC datetime."""
    est_now   = from_now.astimezone(EST)
    candidate = est_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= est_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC).replace(tzinfo=None)


def schedule_week_for_page(page: PageConfig, days_ahead: int = 7) -> int:
    """
    Fills the queue for a page with posts scheduled across the next N days.
    Skips slots that already have a post queued.
    Returns number of new posts scheduled.
    """
    niche_cfg: NicheConfig = NICHE_CONFIGS[page.niche]
    items: List[ContentItem] = get_unused_items(page.niche, limit=60)

    if not items:
        logger.warning(f"[{page.niche}] No unused content items to schedule")
        return 0

    scheduled = 0
    now = datetime.utcnow()

    db.connect(reuse_if_open=True)

    for day_offset in range(days_ahead):
        base = now + timedelta(days=day_offset)

        for (hour, minute) in niche_cfg.post_slots:
            slot_utc = _next_slot_utc(hour, minute, base.replace(tzinfo=UTC))

            # Skip if slot already occupied
            exists = (ScheduledPost
                      .select()
                      .where(
                          ScheduledPost.page_id == page.page_id,
                          ScheduledPost.scheduled_at == slot_utc,
                          ScheduledPost.posted == False,
                      )
                      .exists())
            if exists:
                continue

            if not items:
                logger.warning(f"[{page.niche}] Ran out of content items")
                break

            item = items.pop(0)

            try:
                # Generate caption
                caption = generate_caption(item.title, item.summary, page.niche)

                # Generate image card
                img_result = create_image_card(item.title, page.niche, item.image_url, item.source_url)

                ScheduledPost.create(
                    id              = uuid.uuid4().hex,
                    page_id         = page.page_id,
                    niche           = page.niche,
                    caption         = caption,
                    image_path      = img_result["local_path"],
                    canva_image_url = img_result["canva_url"],
                    scheduled_at    = slot_utc,
                    posted          = False,
                )

                # Mark source item as used
                item.used = True
                item.save()

                scheduled += 1
                logger.info(
                    f"[{page.niche}] Scheduled post for "
                    f"{slot_utc.strftime('%Y-%m-%d %H:%M UTC')} "
                    f"— '{item.title[:50]}'"
                )

            except Exception as e:
                logger.error(f"Failed to schedule item '{item.title[:40]}': {e}")

    db.close()
    return scheduled


def fire_due_posts() -> int:
    """
    Checks the queue and fires any posts whose scheduled_at <= now.
    Returns number of posts successfully fired.
    """
    now = datetime.utcnow()
    fired = 0

    db.connect(reuse_if_open=True)

    due_posts = list(
        ScheduledPost
        .select()
        .where(
            ScheduledPost.posted  == False,
            ScheduledPost.scheduled_at <= now,
            ScheduledPost.error   == "",
        )
        .order_by(ScheduledPost.scheduled_at)
        .limit(20)
    )

    db.close()

    pages = {p.page_id: p for p in load_pages()}

    for post in due_posts:
        page = pages.get(post.page_id)
        if not page:
            logger.error(f"No config found for page_id {post.page_id}")
            continue

        poster = FacebookPoster(page.page_id, page.token)

        try:
            # Prefer Canva URL if available, else local file
            if post.canva_image_url:
                post_id = poster.post_photo_from_url(post.canva_image_url, post.caption)
            elif post.image_path:
                post_id = poster.post_photo(post.image_path, post.caption)
            else:
                post_id = poster.post_text(post.caption)

            db.connect(reuse_if_open=True)
            if post_id:
                post.posted  = True
                post.post_id = post_id
                fired += 1
                logger.info(f"Fired post {post_id} on page {post.page_id}")
            else:
                post.error = "Facebook API returned no post ID"
            post.save()
            db.close()

        except Exception as e:
            logger.error(f"Fire post exception: {e}")
            db.connect(reuse_if_open=True)
            post.error = str(e)[:500]
            post.save()
            db.close()

    return fired


def queue_size(page_id: str) -> int:
    """Returns number of unposted items in the queue for a page."""
    db.connect(reuse_if_open=True)
    count = (ScheduledPost
             .select()
             .where(ScheduledPost.page_id == page_id, ScheduledPost.posted == False)
             .count())
    db.close()
    return count
