"""
Main entry point — FastAPI + APScheduler.
Two things in one process:
  1. FastAPI web server  → health check + upload endpoints
  2. APScheduler         → all automation jobs on their timetables
Start with:  python main.py
"""

import os
import shutil
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from core.database import init_db
from core.config import load_pages, NICHE_CONFIGS
from core.fetcher import fetch_news_for_niche
from schedulers.post_scheduler import schedule_week_for_page, fire_due_posts, queue_size
from schedulers.performance_tracker import collect_post_insights, log_follower_counts

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TAICHI_UPLOAD_DIR = Path("uploads/taichi")
DANCE_REELS_DIR = Path("uploads/dance_reels")
TAICHI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DANCE_REELS_DIR.mkdir(parents=True, exist_ok=True)


def job_fetch_news():
    logger.info("JOB: Fetching news for all niches")
    for niche_name, niche_cfg in NICHE_CONFIGS.items():
        if niche_name in ("taichi", "dance"):
            continue  # These don't use RSS
        try:
            count = fetch_news_for_niche(niche_cfg)
            logger.info(f"  [{niche_name}] {count} new items fetched")
        except Exception as e:
            logger.error(f"  [{niche_name}] Fetch error: {e}")


def job_schedule_posts():
    logger.info("JOB: Filling post queue for all pages")
    for page in load_pages():
        if page.niche == "dance":
            continue  # Dance uses separate reel poster
        try:
            q = queue_size(page.page_id)
            if q < 15:
                new = schedule_week_for_page(page, days_ahead=3)
                logger.info(f"  [{page.niche}] Added {new} posts to queue")
        except Exception as e:
            logger.error(f"  [{page.niche}] Queue fill error: {e}")


def job_fire_posts():
    try:
        fired = fire_due_posts()
        if fired:
            logger.info(f"JOB: Fired {fired} post(s)")
    except Exception as e:
        logger.error(f"JOB fire_posts error: {e}")


def job_collect_insights():
    logger.info("JOB: Collecting post insights")
    try:
        collect_post_insights()
    except Exception as e:
        logger.error(f"JOB insights error: {e}")


def job_follower_count():
    logger.info("JOB: Logging follower counts")
    try:
        log_follower_counts()
    except Exception as e:
        logger.error(f"JOB followers error: {e}")


def job_post_dance_reel():
    """Posts one dance reel per day from the uploads/dance_reels folder."""
    from core.fb_poster import FacebookPoster

    pages = [p for p in load_pages() if p.niche == "dance"]
    if not pages:
        return

    reels = sorted(DANCE_REELS_DIR.glob("*.mp4"))
    if not reels:
        logger.info("No dance reels to post")
        return

    reel_path = reels[0]  # Post the oldest one first

    for page in pages:
        poster = FacebookPoster(page.page_id, page.token)
        try:
            post_id = poster.post_video(str(reel_path), "")
            if post_id:
                logger.info(f"[dance] Posted reel {reel_path.name} → {post_id}")
                # Move to posted folder
                posted_dir = DANCE_REELS_DIR / "posted"
                posted_dir.mkdir(exist_ok=True)
                shutil.move(str(reel_path), str(posted_dir / reel_path.name))
            else:
                logger.error(f"[dance] Failed to post reel {reel_path.name}")
        except Exception as e:
            logger.error(f"[dance] Reel post error: {e}")


def job_refresh_tokens():
    """Auto-refresh Facebook tokens before they expire (runs weekly, refreshes at 50+ days old)."""
    from utils.token_manager import check_and_refresh_all
    try:
        check_and_refresh_all()
    except Exception as e:
        logger.error(f"JOB token refresh error: {e}")


def job_cleanup_images():
    """Deletes generated images older than 7 days to save disk space."""
    import time
    images_dir = Path("generated_images")
    cutoff = time.time() - (7 * 86400)
    deleted = 0
    for f in images_dir.glob("*.*"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    if deleted:
        logger.info(f"JOB: Cleaned up {deleted} old images")


scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler():
    scheduler.add_job(job_fetch_news,       IntervalTrigger(hours=2),      id="fetch_news",  replace_existing=True)
    scheduler.add_job(job_schedule_posts,   IntervalTrigger(hours=6),      id="sched_posts", replace_existing=True)
    scheduler.add_job(job_fire_posts,       IntervalTrigger(seconds=60),   id="fire_posts",  replace_existing=True)
    scheduler.add_job(job_collect_insights, CronTrigger(hour=6, minute=0), id="insights",    replace_existing=True)
    scheduler.add_job(job_follower_count,   CronTrigger(day_of_week="mon",
                                                        hour=7, minute=0), id="followers",   replace_existing=True)
    # Dance reel — 1 per day at 6 PM EST (22:00 UTC)
    scheduler.add_job(job_post_dance_reel,  CronTrigger(hour=22, minute=0), id="dance_reel", replace_existing=True)
    # Token refresh — every Sunday, auto-refresh tokens expiring within 10 days
    scheduler.add_job(job_refresh_tokens,   CronTrigger(day_of_week="sun",
                                                        hour=5, minute=0), id="token_refresh", replace_existing=True)
    # Cleanup old images — daily at 3 AM UTC
    scheduler.add_job(job_cleanup_images,   CronTrigger(hour=3, minute=0),  id="cleanup",   replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started")
    job_fetch_news()
    job_schedule_posts()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FB Automation System")
    init_db()
    start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="FB Automation", lifespan=lifespan)


# ── Health / Status ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running", "service": "FB Page Automation"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/status")
def status():
    pages = load_pages()
    page_status = [{"niche": p.niche, "page_id": p.page_id, "queued": queue_size(p.page_id)} for p in pages]
    jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]

    taichi_images = len(list(TAICHI_UPLOAD_DIR.glob("*.jpg")) + list(TAICHI_UPLOAD_DIR.glob("*.png")))
    dance_reels = len(list(DANCE_REELS_DIR.glob("*.mp4")))

    return {
        "pages": page_status,
        "jobs": jobs,
        "taichi_images_available": taichi_images,
        "dance_reels_available": dance_reels,
    }


# ── Trigger endpoints ───────────────────────────────────────────────────────

@app.post("/trigger/fetch")
def trigger_fetch():
    job_fetch_news()
    return {"triggered": "fetch_news"}


@app.post("/trigger/schedule")
def trigger_schedule():
    job_schedule_posts()
    return {"triggered": "schedule_posts"}


@app.post("/trigger/fire")
def trigger_fire():
    fired = fire_due_posts()
    return {"fired": fired}


@app.post("/trigger/dance")
def trigger_dance():
    job_post_dance_reel()
    return {"triggered": "dance_reel"}


# ── Tai Chi image upload ────────────────────────────────────────────────────

@app.post("/upload/taichi")
async def upload_taichi_images(files: list[UploadFile] = File(...)):
    """
    Upload tai chi images. They'll be used for future posts.
    Drop 10-50 images at once, bot picks randomly for each post.
    """
    saved = []
    for f in files:
        if not f.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        dest = TAICHI_UPLOAD_DIR / f.filename
        with open(dest, "wb") as out:
            content = await f.read()
            out.write(content)
        saved.append(f.filename)

    return {
        "uploaded": len(saved),
        "files": saved,
        "total_available": len(list(TAICHI_UPLOAD_DIR.glob("*.*"))),
    }


@app.get("/upload/taichi/list")
def list_taichi_images():
    images = [f.name for f in TAICHI_UPLOAD_DIR.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    return {"count": len(images), "images": images}


# ── Dance reel upload ───────────────────────────────────────────────────────

@app.post("/upload/dance")
async def upload_dance_reels(files: list[UploadFile] = File(...)):
    """
    Upload dance reels (MP4). Bot posts 1 per day at 6 PM EST.
    """
    saved = []
    for f in files:
        if not f.filename.lower().endswith((".mp4", ".mov")):
            continue
        dest = DANCE_REELS_DIR / f.filename
        with open(dest, "wb") as out:
            content = await f.read()
            out.write(content)
        saved.append(f.filename)

    return {
        "uploaded": len(saved),
        "files": saved,
        "total_available": len(list(DANCE_REELS_DIR.glob("*.mp4"))),
    }


@app.get("/upload/dance/list")
def list_dance_reels():
    reels = [f.name for f in DANCE_REELS_DIR.iterdir() if f.suffix.lower() in (".mp4", ".mov")]
    posted = [f.name for f in (DANCE_REELS_DIR / "posted").iterdir()] if (DANCE_REELS_DIR / "posted").exists() else []
    return {"pending": len(reels), "posted": len(posted), "reels": reels}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
