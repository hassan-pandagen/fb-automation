"""
Command-line dashboard — run this locally to monitor your Railway deployment
or to control the system without opening a browser.

Usage:
    python cli.py status          # Show queue sizes + recent posts
    python cli.py posts           # List last 20 scheduled posts
    python cli.py top [niche]     # Show top performing posts
    python cli.py trigger fetch   # Trigger news fetch on Railway
    python cli.py trigger fire    # Fire due posts on Railway
    python cli.py tokens          # Check token expiry for all pages
    python cli.py followers       # Print current follower counts
"""

import sys
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

RAILWAY_URL = os.getenv("RAILWAY_URL", "http://localhost:8000")


def _get(path: str) -> dict:
    try:
        r = requests.get(f"{RAILWAY_URL}{path}", timeout=10)
        return r.json()
    except Exception as e:
        print(f"Connection error: {e}")
        print(f"Make sure RAILWAY_URL is set in .env or the app is running locally")
        sys.exit(1)


def _post(path: str) -> dict:
    try:
        r = requests.post(f"{RAILWAY_URL}{path}", timeout=15)
        return r.json()
    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)


def cmd_status():
    data = _get("/status")
    print("\n── Page Queue Status ─────────────────────────────")
    for p in data.get("pages", []):
        bar = "█" * min(p["queued"], 20)
        print(f"  {p['niche']:<12} {bar:<20} {p['queued']} posts queued")

    print("\n── Scheduled Jobs ────────────────────────────────")
    for j in data.get("jobs", []):
        print(f"  {j['id']:<20} next: {j['next_run']}")
    print()


def cmd_posts():
    """Show upcoming scheduled posts (reads local DB)."""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from core.database import ScheduledPost, db, init_db
        init_db()
        db.connect(reuse_if_open=True)
        posts = list(
            ScheduledPost
            .select()
            .where(ScheduledPost.posted == False)
            .order_by(ScheduledPost.scheduled_at)
            .limit(20)
        )
        db.close()
        print(f"\n── Next {len(posts)} Scheduled Posts ─────────────────────")
        for p in posts:
            est_time = p.scheduled_at.strftime("%a %b %d %H:%M UTC")
            caption_preview = p.caption[:55].replace("\n", " ")
            print(f"  [{p.niche:<8}] {est_time}  {caption_preview}…")
        print()
    except Exception as e:
        print(f"Error reading local DB: {e}")
        print("Run this command where the DB file exists (Railway shell or locally)")


def cmd_top(niche: str = ""):
    """Show top performing posts from local DB."""
    try:
        from core.database import PostPerformance, db, init_db
        init_db()
        db.connect(reuse_if_open=True)
        q = PostPerformance.select().order_by(PostPerformance.reach.desc()).limit(10)
        if niche:
            q = q.where(PostPerformance.niche == niche)
        posts = list(q)
        db.close()
        print(f"\n── Top Posts {('(' + niche + ')') if niche else '(all niches)'} ──────────────")
        for p in posts:
            print(f"  {p.niche:<10} reach={p.reach:<8} reactions={p.reactions:<6} post_id={p.post_id}")
        print()
    except Exception as e:
        print(f"Error: {e}")


def cmd_trigger(action: str):
    endpoints = {"fetch": "/trigger/fetch", "schedule": "/trigger/schedule", "fire": "/trigger/fire"}
    if action not in endpoints:
        print(f"Unknown trigger: {action}. Choose: fetch, schedule, fire")
        sys.exit(1)
    result = _post(endpoints[action])
    print(f"\n  Triggered '{action}': {result}\n")


def cmd_tokens():
    """Check token expiry for all pages."""
    from utils.token_manager import inspect_token
    i = 1
    print("\n── Token Status ──────────────────────────────────")
    while True:
        token = os.getenv(f"PAGE_{i}_TOKEN")
        niche = os.getenv(f"PAGE_{i}_NICHE", f"page_{i}")
        if not token:
            break
        info = inspect_token(token)
        exp  = info["expires_at"]
        status = "OK" if info["is_valid"] else "INVALID"
        expiry = exp.strftime("%Y-%m-%d") if exp else "unknown"
        print(f"  Page {i} [{niche:<10}] status={status}  expires={expiry}")
        i += 1
    print()


def cmd_followers():
    """Print current follower counts."""
    from core.config import load_pages
    from core.fb_poster import FacebookPoster
    print("\n── Follower Counts ───────────────────────────────")
    for page in load_pages():
        poster = FacebookPoster(page.page_id, page.token)
        count  = poster.get_page_fan_count()
        bar    = "█" * min(count // 500, 30)
        print(f"  {page.niche:<12} {count:>7,} followers  {bar}")
    print()


def main():
    args = sys.argv[1:]
    if not args or args[0] == "status":
        cmd_status()
    elif args[0] == "posts":
        cmd_posts()
    elif args[0] == "top":
        cmd_top(args[1] if len(args) > 1 else "")
    elif args[0] == "trigger" and len(args) > 1:
        cmd_trigger(args[1])
    elif args[0] == "tokens":
        cmd_tokens()
    elif args[0] == "followers":
        cmd_followers()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
