"""
Caption generator — supports Groq (free), Google Gemini, and Anthropic Claude.
Priority order:
  1. Groq (Llama 3 — FREE, no region lock, 30 req/min)
  2. Gemini Flash (FREE tier: 1500 req/day — may be region-blocked)
  3. Anthropic Claude Haiku (paid fallback)
"""

import os
import re
import logging
from core.config import NICHE_CONFIGS

logger = logging.getLogger(__name__)

# Words that trigger Facebook's auto-moderation and can get posts removed or pages restricted.
# The AI is instructed not to use them, but this filter catches any that slip through.
BANNED_WORDS = [
    # Sexual content — FB zero tolerance
    "prostitute", "prostitution", "hooker", "escort service", "sex worker",
    "sexual assault", "rape", "raped", "rapist", "molest", "molestation",
    "pedophile", "pedophilia", "child abuse", "grooming",
    "porn", "pornography", "nude", "naked", "explicit",
    "sex trafficking", "sex trade", "sexual exploitation",
    # Extreme violence — FB restricts graphic descriptions
    "beheaded", "beheading", "decapitated", "dismembered", "mutilated",
    "tortured", "gore", "gory", "disemboweled", "castrated",
    "burned alive", "skinned alive",
    # Hate speech triggers
    "n-word", "faggot", "retard", "retarded", "tranny",
    # Self-harm
    "suicide method", "how to kill yourself", "kill myself",
    "self-harm", "cutting myself",
    # Drugs — specific terms FB flags
    "buy drugs", "sell drugs", "drug dealer", "meth lab",
    "cocaine for sale", "weed for sale",
    # Weapons sales language
    "buy guns", "guns for sale", "sell firearms",
    # Terrorism
    "terrorist attack", "bomb threat", "ISIS", "jihad",
    "mass shooting", "school shooting",
]

# Safe replacements for common flagged terms that might appear in news
WORD_REPLACEMENTS = {
    "prostitute": "s*x worker",
    "prostitution": "the s*x trade",
    "rape": "s*xual assault",
    "raped": "s*xually assaulted",
    "rapist": "s*x offender",
    "molest": "abuse",
    "molestation": "abuse",
    "pedophile": "predator",
    "pedophilia": "child exploitation",
    "beheaded": "unalived",
    "beheading": "unaliving",
    "suicide": "unalived themselves",
    "killed himself": "was found unalived",
    "killed herself": "was found unalived",
    "mass shooting": "mass violence incident",
    "school shooting": "school violence incident",
    "sex trafficking": "human trafficking",
    "drug dealer": "substance distributor",
}


def _sanitize_caption(caption: str) -> str:
    """Replaces banned/flagged words with Facebook-safe alternatives."""
    sanitized = caption
    # Apply replacements (case-insensitive)
    for bad_word, replacement in WORD_REPLACEMENTS.items():
        pattern = re.compile(re.escape(bad_word), re.IGNORECASE)
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized

# ── Groq (free, primary) ────────────────────────────────────────────────────

def _generate_with_groq(prompt: str) -> str:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()


# ── Gemini (free tier, secondary) ───────────────────────────────────────────

def _generate_with_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text.strip()


# ── Anthropic Claude (paid fallback) ────────────────────────────────────────

def _generate_with_anthropic(prompt: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_caption(title: str, summary: str, niche: str) -> str:
    """
    Generates a Facebook caption for a news item.
    Tries Groq first (free), then Gemini, then Anthropic.
    """
    niche_cfg = NICHE_CONFIGS.get(niche)
    if not niche_cfg:
        raise ValueError(f"Unknown niche: {niche}")

    prompt = f"""{niche_cfg.caption_style}

News headline: {title}
Summary: {summary[:300] if summary else 'No summary available.'}

FORMATTING RULES:
- Write ONLY the caption text. No preamble, no quotes around it.
- Use short paragraphs (2-3 sentences max per paragraph).
- Add a blank line between each paragraph for readability.
- Put the hook on its own line at the top.
- Put hashtags on their own line at the bottom.
- Make it easy to read on a phone screen.

FACEBOOK CONTENT SAFETY (CRITICAL — violations get the page banned):
- NEVER use these words: prostitute, rape, rapist, suicide, pedophile, nude, porn, beheaded, dismembered, terrorist, mass shooting, school shooting, sex trafficking, drug dealer
- Instead use safe alternatives: "unalived" for killed/suicide, "predator" for pedophile, "s*x worker" for prostitute, "s*xual assault" for rape, "human trafficking" for sex trafficking, "substance distributor" for drug dealer
- Censor explicit words with asterisks: s*x, k*ll, d*ath if needed
- Do NOT describe graphic violence, sexual acts, or self-harm methods in detail
- Keep it news commentary, not graphic retelling"""

    caption = None

    # Try Groq first (free, no region block)
    if not caption and os.getenv("GROQ_API_KEY"):
        try:
            caption = _generate_with_groq(prompt)
            logger.info(f"[{niche}] Caption via Groq ({len(caption)} chars)")
        except Exception as e:
            logger.warning(f"Groq failed: {e}")

    # Try Gemini (free but may be region-blocked)
    if not caption and os.getenv("GEMINI_API_KEY"):
        try:
            caption = _generate_with_gemini(prompt)
            logger.info(f"[{niche}] Caption via Gemini ({len(caption)} chars)")
        except Exception as e:
            logger.warning(f"Gemini failed: {e}")

    # Fallback to Anthropic (paid)
    if not caption and os.getenv("ANTHROPIC_API_KEY"):
        try:
            caption = _generate_with_anthropic(prompt)
            logger.info(f"[{niche}] Caption via Anthropic ({len(caption)} chars)")
        except Exception as e:
            logger.error(f"Anthropic also failed: {e}")
            raise

    if caption:
        # Run through Facebook safety filter before posting
        caption = _sanitize_caption(caption)
        return caption

    raise RuntimeError("No AI provider configured. Set GROQ_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY in .env")


def batch_generate_captions(niche: str, items: list, limit: int = 30) -> list[dict]:
    """Generates captions for a batch of ContentItems."""
    results = []
    for item in items[:limit]:
        try:
            caption = generate_caption(item.title, item.summary, niche)
            results.append({"item": item, "caption": caption})
        except Exception as e:
            logger.error(f"Caption failed for '{item.title[:40]}': {e}")
    return results
