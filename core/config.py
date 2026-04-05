"""
Loads all page configs and niche settings from environment variables.
Add more pages by adding PAGE_4_*, PAGE_5_* etc to your .env
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class PageConfig:
    page_id: str
    token: str
    niche: str


@dataclass
class NicheConfig:
    name: str
    rss_feeds: List[str]
    canva_template_id: str
    # US EST post times (hour, minute)
    post_slots: List[tuple]
    # Prompts for AI caption generation
    caption_style: str
    keywords: List[str]


def load_pages() -> List[PageConfig]:
    pages = []
    i = 1
    while True:
        pid   = os.getenv(f"PAGE_{i}_ID")
        token = os.getenv(f"PAGE_{i}_TOKEN")
        niche = os.getenv(f"PAGE_{i}_NICHE")
        if not pid or not token or not niche:
            break
        pages.append(PageConfig(page_id=pid, token=token, niche=niche))
        i += 1
    return pages


NICHE_CONFIGS: dict[str, NicheConfig] = {
    "crime": NicheConfig(
        name="crime",
        rss_feeds=[
            "https://nypost.com/tag/crime/feed/",
            "https://www.dailymail.co.uk/news/us-crime/index.rss",
            "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
            "https://www.reddit.com/r/TrueCrime/.rss",
            "https://news.google.com/rss/search?q=US+crime+murder+arrest+sentencing&hl=en-US&gl=US&ceid=US:en",
        ],
        canva_template_id=os.getenv("CANVA_TEMPLATE_CRIME", ""),
        # Start with 2/day for new pages, increase after 2 weeks to 5-7/day
        post_slots=[
            (11, 0), (19, 0)
        ],
        caption_style=(
            "You are a true crime commentator on Facebook. Write an ORIGINAL caption that tells "
            "the FULL STORY — not just a teaser. Include all key details: who, what, where, when, "
            "and the outcome. Then add YOUR personal opinion and analysis. "
            "200-300 words. Start with a shocking hook. Tell the complete story in the middle. "
            "End with your hot take and a debate question that makes people comment. "
            "Write like you're telling your friends about this crazy story you just read. "
            "American English, conversational. Add 3-5 hashtags at the end."
        ),
        keywords=["murder", "arrest", "crime", "police", "court", "sentenced", "suspect",
                   "shooting", "robbery", "killed", "charged", "guilty", "prison", "FBI",
                   "hero", "saved", "rescued", "bystander", "good samaritan", "justice",
                   "self defense", "brave", "caught", "stopped"]
    ),

    "finance": NicheConfig(
        name="finance",
        rss_feeds=[
            "https://www.cnbc.com/id/10000108/device/rss/rss.html",
            "https://www.marketwatch.com/rss/topstories",
            "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
            "https://news.google.com/rss/search?q=social+security+OR+stimulus+OR+tax+changes+OR+IRS&hl=en-US&gl=US&ceid=US:en",
            "https://www.reddit.com/r/Economics/.rss",
        ],
        canva_template_id=os.getenv("CANVA_TEMPLATE_FINANCE", ""),
        post_slots=[
            (7, 30), (9, 0), (12, 0), (15, 0), (18, 0), (20, 30)
        ],
        caption_style=(
            "You are a personal finance commentator on Facebook. Write an ORIGINAL caption that "
            "explains the FULL STORY — not just a teaser. Break down what happened, why it matters, "
            "and exactly how it affects everyday Americans' wallets. "
            "200-300 words. Start with a hook that makes people stop scrolling. "
            "Explain the full details in plain language. Add YOUR analysis — is this good or bad? "
            "What should people actually do about it? "
            "End with 'Share this so your family knows' or a question. "
            "American English, no jargon. Add 3-5 hashtags at the end."
        ),
        keywords=["money", "tax", "IRS", "social security", "stimulus", "inflation",
                   "recession", "federal reserve", "interest rate", "government",
                   "economy", "budget", "debt", "Wall Street", "stock market",
                   "Medicare", "Medicaid", "housing", "rent", "mortgage"]
    ),

    "taichi": NicheConfig(
        name="taichi",
        rss_feeds=[
            "https://www.reddit.com/r/taichi/.rss",
            "https://www.reddit.com/r/martialarts/.rss",
            "https://www.reddit.com/r/kungfu/.rss",
            "https://www.reddit.com/r/ChineseLanguage/.rss",
        ],
        canva_template_id=os.getenv("CANVA_TEMPLATE_TAICHI", ""),
        post_slots=[
            (1, 0), (3, 30), (6, 0), (8, 30), (11, 0),
            (13, 30), (16, 0), (18, 30), (21, 0), (23, 30)
        ],
        caption_style=(
            "Write a Facebook caption for a tai chi, martial arts, or Chinese culture post. "
            "Under 130 words. Start with a wisdom hook or inspiring martial arts insight. "
            "Keep the tone respectful, knowledgeable, and motivating. "
            "End with a question that invites community discussion (e.g. 'What does your practice look like today?'). "
            "Add 3-5 relevant hashtags at the end (e.g. #TaiChi #MartialArts #InnerPeace). "
            "Use plain conversational English."
        ),
        keywords=["tai chi", "taichi", "kung fu", "martial arts", "qigong", "wushu",
                   "meditation", "chi", "balance", "training", "form", "stance", "practice"]
    ),

    "drama": NicheConfig(
        name="drama",
        rss_feeds=[
            "https://www.tmz.com/rss.xml",
            "https://pagesix.com/feed/",
            "https://www.dailymail.co.uk/tvshowbiz/index.rss",
            "https://www.reddit.com/r/entertainment/.rss",
            "https://www.reddit.com/r/popculturechat/.rss",
            "https://www.reddit.com/r/Fauxmoi/.rss",
            "https://news.google.com/rss/search?q=celebrity+drama+OR+beef+OR+feud+OR+viral+moment&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=Trump+OR+Kanye+OR+Drake+OR+celebrity+controversy&hl=en-US&gl=US&ceid=US:en",
        ],
        canva_template_id="",
        post_slots=[
            (10, 0), (20, 0)
        ],
        caption_style=(
            "You are a pop culture and drama commentator on Facebook. Write an ORIGINAL caption that "
            "tells the FULL STORY with all the juicy details — who said what, who clapped back, "
            "the whole timeline of the beef or drama. "
            "200-300 words. Start with a hook that makes people stop scrolling. "
            "Tell the complete story like you're catching your friend up on the drama they missed. "
            "Pick a side or give your hot take. React like a real person — 'NAH BECAUSE...' energy. "
            "End with a spicy question that makes people comment and tag friends. "
            "American English, Gen Z/millennial tone. Add 3-5 hashtags at the end."
        ),
        keywords=["drama", "beef", "feud", "clap back", "viral", "controversy",
                   "celebrity", "Trump", "Kanye", "Drake", "Kardashian", "exposed",
                   "cancelled", "responded", "fired back", "called out", "receipts",
                   "tea", "shade", "diss", "fight", "breakup", "cheating", "scandal"]
    ),

    "weird": NicheConfig(
        name="weird",
        rss_feeds=[
            "https://www.reddit.com/r/nottheonion/.rss",
            "https://www.reddit.com/r/FloridaMan/.rss",
            "https://nypost.com/tag/weird-news/feed/",
            "https://www.upi.com/Odd_News/feed/",
            "https://www.dailymail.co.uk/news/weird-news/index.rss",
            "https://news.google.com/rss/search?q=%22florida+man%22+OR+bizarre+OR+weird+arrest&hl=en-US&gl=US&ceid=US:en",
        ],
        canva_template_id=os.getenv("CANVA_TEMPLATE_WEIRD", ""),
        post_slots=[
            (12, 0), (18, 0)
        ],
        caption_style=(
            "You are a comedy writer reacting to bizarre news on Facebook. Write an ORIGINAL caption "
            "that tells the FULL STORY with your hilarious commentary woven in. "
            "200-250 words. Start with the most absurd detail. Tell the complete story — all the "
            "crazy details that make it unbelievable. Add your own jokes and sarcastic observations throughout. "
            "React like you're telling your group chat about the wildest thing you just read. "
            "End with a funny hot take or question. "
            "Add 3-5 hashtags at the end (e.g. #WeirdNews #FloridaMan #OnlyInAmerica)."
        ),
        keywords=["weird", "bizarre", "odd", "strange", "Florida", "man", "unexpected",
                   "unbelievable", "crazy", "wild", "arrested", "caught"]
    ),

    "sports": NicheConfig(
        name="sports",
        rss_feeds=[
            "https://www.espn.com/espn/rss/news",
            "https://www.espn.com/espn/rss/nba/news",
            "https://www.espn.com/espn/rss/nfl/news",
            "https://www.espn.com/espn/rss/mlb/news",
            "https://nypost.com/sports/feed/",
            "https://www.reddit.com/r/nba/.rss",
            "https://www.reddit.com/r/nfl/.rss",
            "https://www.reddit.com/r/MMA/.rss",
            "https://news.google.com/rss/search?q=NBA+OR+NFL+OR+MLB+OR+UFC&hl=en-US&gl=US&ceid=US:en",
        ],
        canva_template_id=os.getenv("CANVA_TEMPLATE_SPORTS", ""),
        post_slots=[
            (7, 0), (9, 30), (12, 0), (15, 0), (18, 0), (20, 0), (22, 30)
        ],
        caption_style=(
            "You are a passionate sports commentator on Facebook. Write an ORIGINAL caption that "
            "covers the FULL STORY with your hot take woven in. "
            "200-300 words. Start with a bold statement. Give all the key stats, scores, and details. "
            "Add YOUR analysis — compare to other players, reference history, make bold predictions. "
            "Write like you're at a sports bar arguing with your buddies. High energy. "
            "End with a spicy debate question that makes fans comment. "
            "American English. Add 3-5 hashtags at the end."
        ),
        keywords=["NBA", "NFL", "MLB", "UFC", "NBA playoffs", "Super Bowl",
                   "LeBron", "Curry", "Mahomes", "touchdown", "home run",
                   "trade", "draft", "championship", "MVP", "injury",
                   "baseball", "basketball", "football", "hockey", "MMA",
                   "World Series", "March Madness", "ESPN"]
    ),

    "dance": NicheConfig(
        name="dance",
        rss_feeds=[],  # No RSS — uses uploaded reels
        canva_template_id="",
        post_slots=[(18, 0)],  # 6 PM EST — 1 reel per day
        caption_style="",  # No caption needed for reels
        keywords=[],
    ),
}
