"""
Caption generator — supports Groq (free), Google Gemini, and Anthropic Claude.
Priority order:
  1. Groq (Llama 3 — FREE, no region lock, 30 req/min)
  2. Gemini Flash (FREE tier: 1500 req/day — may be region-blocked)
  3. Anthropic Claude Haiku (paid fallback)
"""

import os
import logging
from core.config import NICHE_CONFIGS

logger = logging.getLogger(__name__)

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

Write ONLY the caption text. No preamble, no quotes around it."""

    # Try Groq first (free, no region block)
    if os.getenv("GROQ_API_KEY"):
        try:
            caption = _generate_with_groq(prompt)
            logger.info(f"[{niche}] Caption via Groq ({len(caption)} chars)")
            return caption
        except Exception as e:
            logger.warning(f"Groq failed: {e}")

    # Try Gemini (free but may be region-blocked)
    if os.getenv("GEMINI_API_KEY"):
        try:
            caption = _generate_with_gemini(prompt)
            logger.info(f"[{niche}] Caption via Gemini ({len(caption)} chars)")
            return caption
        except Exception as e:
            logger.warning(f"Gemini failed: {e}")

    # Fallback to Anthropic (paid)
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            caption = _generate_with_anthropic(prompt)
            logger.info(f"[{niche}] Caption via Anthropic ({len(caption)} chars)")
            return caption
        except Exception as e:
            logger.error(f"Anthropic also failed: {e}")
            raise

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
