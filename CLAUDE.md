# FB Page Automation — Complete Setup Guide
Run everything from VS Code terminal. Copy-paste every command in order.

---

## Project Status (Last updated: 2026-04-02)

### What's Built & Working
- Full automation pipeline: RSS → Image → AI Caption → Facebook Post
- 6 niches configured: crime, finance, taichi, weird, sports, dance
- Image generation: Bing search (via US proxy) for real news photos + Pexels stock fallback + branded overlay
- Caption AI: Groq (Llama 3) generates full-story original commentary (200-300 words)
- Image processing: random crop, color grading, pixel noise, EXIF strip — every image is unique
- Logo overlay in footer bar
- Facebook Graph API posting (photo + video)
- Token refresh system (60-day tokens)
- Upload endpoints for tai chi photos and dance reels
- APScheduler for automated job scheduling

### Pages Configured
| Page | Niche | Page ID | Token | Status |
|------|-------|---------|-------|--------|
| YUAN Zhi. tai chi Fans | taichi | 643142612213141 | 60-day valid | Needs influencer photos in uploads/taichi/ |
| That Plot Twist Tho | crime | 1053392647859519 | 60-day valid | LIVE — first post done |
| Finance page | finance | NOT CREATED | — | Create on Day 4 |
| Weird News page | weird | NOT CREATED | — | Create on Day 4 |
| Sports page | sports | NOT CREATED | — | Create on Day 7 |
| Dance page | dance | NOT CREATED | — | Create on Day 7 |

### Page Creation Schedule (safe spacing)
- Day 1 (Apr 2): Crime ✅ (That Plot Twist Tho — on James Peace account)
- Day 4 (Apr 5): Finance + Weird (one on Hassan, one on James Peace)
- Day 7 (Apr 8): Sports + Dance (one on each account)
- Hassan Jamal = admin on ALL pages, generates all tokens via Graph Explorer

### Facebook Developer App
- App: Page Auto Poster
- App ID: 939252218478662
- App Secret: in .env (FB_APP_SECRET)
- Hassan Jamal account = developer account
- Graph Explorer: https://developers.facebook.com/tools/explorer/

### API Keys
| Key | Provider | Status |
|-----|----------|--------|
| GROQ_API_KEY | Groq (Llama 3) | Working — primary caption AI |
| GEMINI_API_KEY | Google | Blocked from Pakistan, will work on US VPS |
| PEXELS_API_KEY | Pexels | Working — royalty-free stock photos |
| US_PROXY | proxy-cheap.com | Working — expires 2026-04-13, not needed after VPS deploy |

### Architecture
```
RSS Feeds → fetch_news_for_niche() → ContentItem DB
ContentItem → generate_caption() [Groq] + create_image_card() [Bing/Pexels/Pillow] → ScheduledPost DB
ScheduledPost → fire_due_posts() → FacebookPoster.post_photo() → Facebook
```

### Image Strategy Per Niche
| Niche | Mode | How it works |
|-------|------|-------------|
| crime | news_search_real | Scrape article og:image → Bing search → Pexels fallback |
| sports | news_search_real | Scrape article og:image → Bing search → Pexels fallback |
| finance | news_search | Pexels stock first (copyright-safe for monetization) |
| weird | news_search | Pexels stock first → Bing fallback |
| taichi | local_folder | Picks from uploads/taichi/ (user's AI influencer photos) |
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

### API Endpoints
| Endpoint | Method | What |
|----------|--------|------|
| /status | GET | Dashboard — queue sizes, jobs, image counts |
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

## TODO — Next Session

### Immediate
1. Deploy to VPS (Ubuntu) — upload project, set up venv, systemd service
2. Test auto-posting runs on VPS
3. Gemini will work on VPS (US IP) — test it as caption fallback

### Day 4 (Apr 5)
4. Create Finance page + Weird News page
5. Get tokens, add to .env
6. Generate banners/logos for each

### Day 7 (Apr 8)
7. Create Sports page + Dance page
8. Get tokens, add to .env
9. Copy dance reels from E:/Instagram Bulk downloader/instagram_downloads/pionerka_dina/pionerka_dina/ to VPS
10. Upload tai chi influencer photos

### Future Improvements
- GitHub Actions auto-deploy (push → VPS updates)
- Token refresh cron job
- Build web dashboard frontend
- Add more niches (Military/Veterans, Pets, AI/Tech)
- Consistent AI influencer face generation for tai chi (Replicate API when on VPS)

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

# Test
python main.py

# Install as service
nano /etc/systemd/system/fb-automation.service
# (paste the service config from below)

systemctl daemon-reload
systemctl enable fb-automation
systemctl start fb-automation
systemctl status fb-automation
```

### systemd service file
```ini
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
```

---

## File Structure
```
fb_automation/
├── main.py                     ← FastAPI + schedulers + upload endpoints
├── cli.py                      ← Terminal dashboard
├── requirements.txt            ← Python packages
├── .env                        ← Private keys (never commit)
├── .env.example                ← Template
├── CLAUDE.md                   ← This file
├── assets/
│   └── logo.png                ← Page logo for image overlay
├── uploads/
│   ├── taichi/                 ← Drop tai chi influencer photos here
│   └── dance_reels/            ← Drop dance videos here
│       └── posted/             ← Bot moves posted reels here
├── generated_images/           ← Bot-generated branded images
├── core/
│   ├── config.py               ← Niches, RSS feeds, post times, caption prompts
│   ├── database.py             ← SQLite: content, posts, performance
│   ├── fetcher.py              ← RSS news fetcher
│   ├── caption_gen.py          ← Groq → Gemini → Anthropic caption AI
│   ├── image_gen.py            ← Bing search + Pexels + Pillow overlay
│   └── fb_poster.py            ← Facebook Graph API (photo + video + insights)
├── schedulers/
│   ├── post_scheduler.py       ← Queue management + firing posts
│   └── performance_tracker.py  ← Engagement tracking
└── utils/
    ├── token_manager.py        ← Facebook token refresh
    └── recycler.py             ← Re-queues top performing posts
```

---

## Key Design Decisions
- Captions are ORIGINAL COMMENTARY (200-300 words, full story) — not headline rewrites. This is required for Meta monetization in 2026.
- Crime/Sports use real article photos (mugshots = public domain). Finance/Weird use Pexels stock (copyright-safe).
- Every image is processed (crop, color grade, noise, EXIF strip) to be unique.
- Logo overlay in footer brands every post.
- Dance page is expendable (reposted content risk) — used as traffic funnel for other pages.
- Pages created on 2 different Facebook accounts (Hassan Jamal + James Peace) to spread risk.
- 1 page every 3 days = safe creation rate to avoid Meta flags.
