"""
Content recycler — automatically re-queues your top performing posts
every 30 days with a freshly generated caption.

Logic:
  - Finds posts with reach > threshold (default 1000)
  - Checks they haven't been recycled in the last 30 days
  - Generates a new caption for the same image
  - Adds them back to the ScheduledPost queue

Runs every Sunday via the scheduler (added in main.py).
"""

import uuid
import logging
from datetime import datetime, timedelta

from core.database import ScheduledPost, PostPerformance, db
from core.config import load_pages, NICHE_CONFIGS
from core.caption_gen import generate_caption
from schedulers.post_scheduler import _next_slot_utc

logger = logging.getLogger(__name__)

RECYCLE_REACH_THRESHOLD = 800   # Only recycle posts that got 800+ reach
RECYCLE_COOLDOWN_DAYS   = 30    # Don't recycle same post more than once/month


def recycle_top_posts() -> int:
    """
    Finds top performing posts and re-queues them with new captions.
    Returns count of posts recycled.
    """
    recycled = 0
    cutoff   = datetime.utcnow() - timedelta(days=RECYCLE_COOLDOWN_DAYS)

    db.connect(reuse_if_open=True)

    top_posts = list(
        PostPerformance
        .select()
        .where(PostPerformance.reach >= RECYCLE_REACH_THRESHOLD)
        .order_by(PostPerformance.reach.desc())
        .limit(30)
    )

    db.close()

    if not top_posts:
        logger.info("No posts above recycling threshold yet")
        return 0

    pages = {p.page_id: p for p in load_pages()}

    for perf in top_posts:
        page = pages.get(perf.page_id)
        if not page:
            continue

        # Find the original scheduled post to get its image
        db.connect(reuse_if_open=True)
        original = ScheduledPost.get_or_none(ScheduledPost.post_id == perf.post_id)

        # Check it hasn't been recycled recently
        recent_recycle = (ScheduledPost
                          .select()
                          .where(
                              ScheduledPost.page_id   == perf.page_id,
                              ScheduledPost.image_path == (original.image_path if original else ""),
                              ScheduledPost.created_at >= cutoff,
                              ScheduledPost.post_id   != perf.post_id,
                          )
                          .exists())
        db.close()

        if recent_recycle or not original:
            continue

        try:
            # Generate a fresh caption for the same story
            # Use a "recycled" style prompt variation
            niche_cfg = NICHE_CONFIGS.get(perf.niche)
            if not niche_cfg:
                continue

            new_caption = generate_caption(
                title   = _extract_title_from_caption(original.caption),
                summary = "",
                niche   = perf.niche,
            )

            # Schedule it for next available slot
            now = datetime.utcnow()
            slot_hour, slot_minute = niche_cfg.post_slots[recycled % len(niche_cfg.post_slots)]
            slot_utc = _next_slot_utc(slot_hour, slot_minute, now)

            db.connect(reuse_if_open=True)
            ScheduledPost.create(
                id              = uuid.uuid4().hex,
                page_id         = perf.page_id,
                niche           = perf.niche,
                caption         = new_caption,
                image_path      = original.image_path,
                canva_image_url = original.canva_image_url,
                scheduled_at    = slot_utc,
                posted          = False,
            )
            db.close()

            recycled += 1
            logger.info(
                f"[{perf.niche}] Recycled post (reach={perf.reach}) "
                f"→ new slot {slot_utc.strftime('%Y-%m-%d %H:%M UTC')}"
            )

        except Exception as e:
            logger.error(f"Recycle error for post {perf.post_id}: {e}")

    return recycled


def _extract_title_from_caption(caption: str) -> str:
    """
    Best-effort extraction of the story title from an existing caption.
    Used so the recycled caption can be regenerated from context.
    """
    lines = caption.strip().split("\n")
    # First line is usually the hook — use first 100 chars as title proxy
    return lines[0][:100] if lines else caption[:100]
