# FB Page Automation System

Python + Railway. Finds US news, generates image cards, writes AI captions,
posts to your Facebook pages at US peak times. Hands-off after setup.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python main.py         # test locally
```

## Deploy to Railway (5 minutes)

```bash
npm install -g @railway/cli
railway login
railway init
railway variables set PAGE_1_ID=xxx PAGE_1_TOKEN=xxx PAGE_1_NICHE=crime
# repeat for PAGE_2, PAGE_3 and all other env vars
railway up
```

Check: https://your-app.railway.app/status

## Getting Facebook Page Tokens

1. Go to developers.facebook.com/tools/explorer
2. Add permissions: pages_manage_posts, pages_read_engagement
3. Generate token, then exchange for 60-day long-lived token:
   GET https://graph.facebook.com/oauth/access_token
     ?grant_type=fb_exchange_token&client_id=APP_ID
     &client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN

## Manual Triggers

POST /trigger/fetch     — pull news now
POST /trigger/schedule  — fill queue now
POST /trigger/fire      — fire due posts now

## Cost: ~$8/month total (Railway $5 + Claude API ~$3)
