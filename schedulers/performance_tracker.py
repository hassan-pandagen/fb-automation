"""
Runs daily — fetches engagement stats for posts made 24h ago.
Saves to DB so you can see which content performs best.
Also logs follower counts weekly.
"""

import logging
from datetime import datetime, timedelta

from core.database import ScheduledPost, PostPerformance, db
from core.config import load_pages
from core.fb_poster import FacebookPoster

logger = logging.getLogger(__name__)


def collect_post_insights():
    """
    Finds posts made 20–28 hours ago, fetches their insights,
    saves to PostPerformance table.
    """
    now       = datetime.utcnow()
    window_lo = now - timedelta(hours=28)
    window_hi = now - timedelta(hours=20)

    db.connect(reuse_if_open=True)
    recent = list(
        ScheduledPost
        .select()
        .where(
            ScheduledPost.posted       == True,
            ScheduledPost.scheduled_at >= window_lo,
            ScheduledPost.scheduled_at <= window_hi,
            ScheduledPost.post_id      != "",
        )
    )
    db.close()

    if not recent:
        logger.info("No posts in insight window")
        return

    pages = {p.page_id: p for p in load_pages()}

    for post in recent:
        page = pages.get(post.page_id)
        if not page:
            continue

        poster   = FacebookPoster(page.page_id, page.token)
        insights = poster.get_post_insights(post.post_id)

        reach       = insights.get("post_impressions_unique", 0)
        impressions = insights.get("post_impressions", 0)
        reactions   = sum(insights.get("post_reactions_by_type_total", {}).values()) \
                      if isinstance(insights.get("post_reactions_by_type_total"), dict) else 0

        db.connect(reuse_if_open=True)
        PostPerformance.get_or_create(
            post_id = post.post_id,
            defaults={
                "page_id":     post.page_id,
                "niche":       post.niche,
                "reach":       reach,
                "impressions": impressions,
                "reactions":   reactions,
                "checked_at":  now,
            }
        )
        db.close()

        logger.info(
            f"[{post.niche}] Post {post.post_id} — "
            f"reach={reach}, impressions={impressions}, reactions={reactions}"
        )


def log_follower_counts():
    """Logs current follower counts for all pages (run weekly)."""
    for page in load_pages():
        poster = FacebookPoster(page.page_id, page.token)
        count  = poster.get_page_fan_count()
        logger.info(f"[{page.niche}] Followers: {count:,}")


def top_performing_posts(niche: str, limit: int = 5) -> list:
    """Returns the top posts for a niche by reach — useful for recycling."""
    db.connect(reuse_if_open=True)
    top = list(
        PostPerformance
        .select()
        .where(PostPerformance.niche == niche)
        .order_by(PostPerformance.reach.desc())
        .limit(limit)
    )
    db.close()
    return top
