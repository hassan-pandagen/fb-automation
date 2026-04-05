# FB Page Automation — Complete Setup Guide

---

## Project Status (Last updated: 2026-04-05)

### What's Built & Working
- Full automation pipeline: RSS -> Image -> AI Caption -> Facebook Post
- 7 niches configured: crime, drama, finance, taichi, weird, sports, dance
- Image generation: Bing search (via US proxy) for real news photos + Pexels stock fallback + branded overlay
- Caption AI: Groq (Llama 3) generates full-story original commentary (200-300 words)
- Image processing: random crop, color grading, pixel noise, EXIF strip -- every image is unique
- Logo overlay in footer bar
- Facebook Graph API v25.0 posting (photo + video)
- Token auto-refresh system (60-day tokens, weekly check, auto-renew at 10 days before expiry)
- Upload endpoints for tai chi photos and dance reels
- APScheduler for automated job scheduling
- App in LIVE mode (not development) -- required for real posting

### Pages Configured
| Page | Niche | Page ID | Token Expires | Posts/Day | Status |
|------|-------|---------|---------------|-----------|--------|
| YUAN Zhi. tai chi Fans | taichi | 643142612213141 | 60-day valid | 10 | Drop 10 photos daily to uploads/taichi/ |
| That Plot Twist Tho | crime | 1053392647859519 | 60-day valid | 2 | LIVE -- monetization active |
| Grab Your Popcorn | drama | 61574305924466 | 2026-06-04 | 2 | LIVE -- created on James Peace |
| No Way That's Real | weird | 61575390941996 | 2026-06-04 | 2 | LIVE -- created on James Peace |

### Accounts & Business Managers
- James Peace account: created Grab Your Popcorn, No Way That's Real, That Plot Twist Tho
- Hassan Jamal account: developer account, admin on ALL pages, generates all tokens
- Popcorn Media: business portfolio (new, for future page creation)
- Hassan Jamal: business portfolio (has YUAN Zhi taichi page)

### Facebook Developer App
- App: Page Auto Poster (LIVE MODE)
- App ID: 939252218478662
- App Secret: in .env (FB_APP_SECRET)
- Graph API version: v25.0
- Graph Explorer: https://developers.facebook.com/tools/explorer/

### API Keys
| Key | Provider | Status |
|-----|----------|--------|
| GROQ_API_KEY | Groq (Llama 3) | Working -- primary caption AI |
| GEMINI_API_KEY | Google | Blocked from Pakistan, works on US VPS |
| PEXELS_API_KEY | Pexels | Working -- royalty-free stock photos |
| US_PROXY | proxy-cheap.com | Expires 2026-04-13, not needed after VPS deploy |

### Architecture
```
RSS Feeds -> fetch_news_for_niche() -> ContentItem DB
ContentItem -> generate_caption() [Groq] + create_image_card() [Bing/Pexels/Pillow] -> ScheduledPost DB
ScheduledPost -> fire_due_posts() -> FacebookPoster.post_photo() -> Facebook
```

### Post Schedule (all times EST)
| Page | Time 1 | Time 2 | Notes |
|------|--------|--------|-------|
| That Plot Twist Tho (crime) | 11:00 AM | 7:00 PM | Staggered from other pages |
| Grab Your Popcorn (drama) | 10:00 AM | 8:00 PM | Staggered from other pages |
| No Way That's Real (weird) | 12:00 PM | 6:00 PM | Staggered from other pages |
| YUAN Zhi (taichi) | Every ~2.5 hrs | 10 slots | 1am,3:30,6,8:30,11,1:30pm,4,6:30,9,11:30 |

### Image Strategy Per Niche
| Niche | Mode | How it works |
|-------|------|-------------|
| crime | news_search_real | Scrape article og:image -> Bing search -> Pexels fallback |
| drama | news_search_real | Scrape article for celeb photos -> Bing search -> Pexels fallback |
| weird | news_search | Pexels stock first -> Bing fallback |
| sports | news_search_real | Scrape article og:image -> Bing search -> Pexels fallback |
| finance | news_search | Pexels stock first (copyright-safe for monetization) |
| taichi | local_folder | Picks from uploads/taichi/ FIFO, moves to posted/ after use |
| dance | N/A | Posts videos/photos from uploads/dance_reels/ |

### Scheduler Jobs
| Job | Frequency | What |
|-----|-----------|------|
| fetch_news | Every 2 hours | Pull RSS feeds for all niches |
| schedule_posts | Every 6 hours | Generate images + captions, fill queue |
| fire_posts | Every 60 seconds | Post anything that's due |
| insights | Daily 6 AM UTC | Track reach/engagement |
| dance_reel | Daily 10 PM UTC (6 PM EST) | Post 1 dance reel |
| followers | Weekly Monday | Log follower counts |
| token_refresh | Weekly Sunday 5 AM UTC | Auto-refresh tokens expiring within 10 days |
| cleanup | Daily 3 AM UTC | Delete generated images older than 7 days |

### API Endpoints
| Endpoint | Method | What |
|----------|--------|------|
| /status | GET | Dashboard -- queue sizes, jobs, image counts |
| /health | GET | Health check |
| /trigger/fetch | POST | Manual: fetch news now |
| /trigger/schedule | POST | Manual: fill post queues now |
| /trigger/fire | POST | Manual: fire due posts now |
| /trigger/dance | POST | Manual: post a dance reel now |
| /upload/taichi | POST | Upload tai chi influencer photos |
| /upload/dance | POST | Upload dance reels (MP4) |
| /upload/taichi/list | GET | List available tai chi photos |
| /upload/dance/list | GET | List pending/posted dance reels |

---

## Daily Operations

### Your daily routine (5 minutes)
1. Drop 10 tai chi photos into `uploads/taichi/` on VPS (via SFTP or upload endpoint)
2. Check `/status` endpoint to see queue sizes and next scheduled jobs
3. Optionally check Facebook pages for reach/engagement

### Everything else is automatic:
- Crime, Drama, Weird pages: RSS fetch -> AI caption -> image -> post (fully automated)
- Taichi: you drop photos, bot generates caption + posts + moves to posted/
- Tokens: auto-refresh weekly before expiry
- Images: auto-cleanup after 7 days

### Monitoring
- Week 1: Check daily -- verify posts are going out, captions look good, no errors
- After Week 1: Check once a week via `/status` endpoint
- Logs: `journalctl -u fb-automation -f` on VPS for real-time logs

---

## VPS Deployment Steps

```bash
# SSH to VPS
ssh root@YOUR_VPS_IP

# Install Python
apt update && apt upgrade -y
apt install python3.11 python3.11-venv python3-pip git fonts-dejavu-core -y

# Clone project
cd /root
git clone https://github.com/YOUR_USERNAME/fb_automation.git
cd fb_automation

# Setup
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env (copy from local)
nano .env
# Paste your full .env contents here

# Create upload directories
mkdir -p uploads/taichi uploads/dance_reels/posted generated_images

# Test run (Ctrl+C to stop)
python main.py

# Install as systemd service
cat > /etc/systemd/system/fb-automation.service << 'EOF'
[Unit]
Description=FB Page Automation Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/fb_automation
ExecStart=/root/fb_automation/venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=/root/fb_automation/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fb-automation
systemctl start fb-automation
systemctl status fb-automation

# View logs
journalctl -u fb-automation -f
```

### Updating code on VPS (after git push)
```bash
cd /root/fb_automation
git pull
systemctl restart fb-automation
```

### Upload tai chi photos to VPS
```bash
# From local machine (Windows)
scp -r "E:/fb automation/uploads/taichi/*.jpg" root@YOUR_VPS_IP:/root/fb_automation/uploads/taichi/

# Or use the API endpoint
curl -X POST http://YOUR_VPS_IP:8000/upload/taichi -F "files=@photo1.jpg" -F "files=@photo2.jpg"
```

---

## File Structure
```
fb_automation/
├── main.py                     <- FastAPI + schedulers + upload endpoints
├── cli.py                      <- Terminal dashboard
├── requirements.txt            <- Python packages
├── .env                        <- Private keys (never commit)
├── .env.example                <- Template
├── CLAUDE.md                   <- This file
├── assets/
│   └── logo.png                <- Page logo for image overlay
├── uploads/
│   ├── taichi/                 <- Drop tai chi influencer photos here
│   │   └── posted/             <- Bot moves posted photos here
│   └── dance_reels/            <- Drop dance videos here
│       └── posted/             <- Bot moves posted reels here
├── generated_images/           <- Bot-generated branded images (auto-cleanup 7 days)
├── core/
│   ├── config.py               <- Niches, RSS feeds, post times, caption prompts
│   ├── database.py             <- SQLite: content, posts, performance
│   ├── fetcher.py              <- RSS news fetcher
│   ├── caption_gen.py          <- Groq -> Gemini -> Anthropic caption AI
│   ├── image_gen.py            <- Bing search + Pexels + Pillow overlay
│   └── fb_poster.py            <- Facebook Graph API v25.0 (photo + video + insights)
├── schedulers/
│   ├── post_scheduler.py       <- Queue management + firing posts
│   └── performance_tracker.py  <- Engagement tracking
└── utils/
    ├── token_manager.py        <- Facebook token auto-refresh
    └── recycler.py             <- Re-queues top performing posts
```

---

## Key Design Decisions
- Captions are ORIGINAL COMMENTARY (200-300 words, full story) -- not headline rewrites. Required for Meta monetization in 2026.
- Crime/Drama use real article photos (public domain). Weird uses Pexels stock (copyright-safe).
- Every image is processed (crop, color grade, noise, EXIF strip) to be unique.
- Logo overlay in footer brands every post.
- Taichi photos are posted as-is (influencer content, no overlay), moved to posted/ after use.
- Pages spread across 2 Facebook accounts (Hassan Jamal + James Peace) to reduce risk.
- Post times staggered so pages don't fire simultaneously.
- Facebook app must be in LIVE mode (not development) for posts to be visible publicly.
- Graph API v25.0: use `message` field for photo captions on /photos endpoint.

---

## TODO

### Future Improvements
- GitHub Actions auto-deploy (push -> VPS updates)
- Build web dashboard frontend
- Add more niches (Military/Veterans, Pets, AI/Tech, Sports, Finance)
- Create Sports page (OverTime ReacTions) when ready
- Create Finance page when ready
- Consistent AI influencer face generation for tai chi (Replicate API)
