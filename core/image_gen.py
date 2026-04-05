"""
Image generator — cascading strategy:
  1. Together AI (Flux Schnell Free) → AI-generated images from prompts
  2. Pexels API → real stock photos + branded overlay
  3. Pillow text card → guaranteed fallback

Each niche can prefer AI-generated or stock photos.
"""

import os
import io
import uuid
import logging
import random
import base64
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

IMAGES_DIR = Path("generated_images")
IMAGES_DIR.mkdir(exist_ok=True)

# ── Niche brand config ─────────────────────────────────────────────────────────
NICHE_STYLES = {
    "crime": {
        "bg": (15, 15, 25),
        "accent": (220, 50, 50),
        "text": (255, 255, 255),
        "label": "LATEST NEWS",
        "watermark": "Follow @ThatPlotTwistTho for daily updates",
        "image_mode": "news_search_real",
        "search_queries": ["crime scene", "police", "courtroom", "handcuffs", "detective"],
    },
    "sports": {
        "bg": (10, 15, 40),
        "accent": (0, 120, 220),
        "text": (255, 255, 255),
        "label": "SPORTS",
        "watermark": "Follow for the latest sports news",
        "image_mode": "news_search_real",
        "search_queries": ["NBA", "NFL", "MLB", "UFC", "sports"],
    },
    "finance": {
        "bg": (10, 30, 55),
        "accent": (30, 180, 130),
        "text": (255, 255, 255),
        "label": "FINANCE NEWS",
        "watermark": "Follow for daily finance updates",
        "image_mode": "news_search",
        "search_queries": ["US economy", "wall street", "federal reserve", "tax", "stock market"],
    },
    "taichi": {
        "bg": (15, 35, 20),
        "accent": (200, 160, 50),
        "text": (255, 255, 255),
        "label": "TAI CHI",
        "watermark": "Follow @YuanZhi for daily tai chi wisdom",
        "image_mode": "local_folder",
        "folder": "uploads/taichi",
    },
    "drama": {
        "bg": (25, 10, 10),
        "accent": (200, 30, 80),
        "text": (255, 255, 255),
        "label": "DRAMA ALERT",
        "watermark": "Follow @GrabYourPopcorn for the tea 🍿",
        "image_mode": "news_search_real",
        "search_queries": ["celebrity drama", "celebrity beef", "viral moment", "pop culture news"],
    },
    "weird": {
        "bg": (30, 20, 50),
        "accent": (220, 150, 30),
        "text": (255, 255, 255),
        "label": "NO WAY",
        "watermark": "Follow @NoWayThatsReal for the wildest stories 🤯",
        "image_mode": "news_search",
        "search_queries": ["weird news", "bizarre", "strange news", "funny news"],
    },
}

WIDTH, HEIGHT = 1200, 630


# ── Font helpers ───────────────────────────────────────────────────────────────

def _find_font(bold: bool = False) -> str:
    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/impact.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_font(bold)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip() if current else word
        bbox = font.getbbox(test)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ── Google Image Search (find actual news photos) ──────────────────────────────

def _get_proxies() -> dict:
    """Returns proxy dict if US_PROXY is set in env."""
    proxy = os.getenv("US_PROXY", "")
    if proxy:
        return {"http": proxy, "https": proxy}
    return {}


# ── Scrape actual article for the real photo ───────────────────────────────────

def _scrape_article_image(article_url: str) -> Optional[Image.Image]:
    """
    Visits the actual news article page and extracts the main image.
    This guarantees we get the CORRECT photo (real mugshot, real scene).
    """
    if not article_url or not article_url.startswith("http"):
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    proxies = _get_proxies()

    try:
        r = requests.get(article_url, headers=headers, proxies=proxies, timeout=15, verify=False)
        r.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")

        img_url = None

        # Priority 1: Open Graph image (og:image) — most reliable, used by all news sites
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            img_url = og["content"]

        # Priority 2: Twitter card image
        if not img_url:
            tw = soup.find("meta", {"name": "twitter:image"})
            if tw and tw.get("content"):
                img_url = tw["content"]

        # Priority 3: First large image in article body
        if not img_url:
            for img_tag in soup.find_all("img"):
                src = img_tag.get("src", "") or img_tag.get("data-src", "")
                if not src or not src.startswith("http"):
                    continue
                # Skip tiny icons, logos, ads
                width = img_tag.get("width", "")
                if width and width.isdigit() and int(width) < 300:
                    continue
                if any(skip in src.lower() for skip in ["logo", "icon", "avatar", "ad-", "pixel", "tracking", "badge"]):
                    continue
                img_url = src
                break

        if not img_url:
            return None

        # Download the image
        img_r = requests.get(img_url, headers=headers, timeout=12)
        img_r.raise_for_status()
        if len(img_r.content) < 5000:
            return None

        img = Image.open(io.BytesIO(img_r.content)).convert("RGB")
        w, h = img.size
        if w >= 300 and h >= 200:
            logger.info(f"Article image scraped: {w}x{h} from {article_url[:60]}")
            return img

        return None
    except Exception as e:
        logger.warning(f"Article scrape failed for {article_url[:50]}: {e}")
        return None


def _search_news_image(query: str) -> Optional[Image.Image]:
    """
    Searches for the actual news image via US proxy.
    Tries Bing → Google → DuckDuckGo.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    proxies = _get_proxies()
    img_urls = []

    # Source 1: Bing (via US proxy)
    try:
        from urllib.parse import quote
        import re
        bing_url = f"https://www.bing.com/images/search?q={quote(query + ' news photo')}&form=HDRSC2&first=1"
        r = requests.get(bing_url, headers=headers, proxies=proxies, timeout=20, verify=False)
        if r.status_code == 200:
            # Bing encodes URLs with &quot; in HTML
            for match in re.findall(r'murl&quot;:&quot;(https?://[^&]+)&', r.text):
                img_urls.append(match)
            # Also try JSON format
            for match in re.findall(r'"murl":"(https?://[^"]+)"', r.text):
                if match not in img_urls:
                    img_urls.append(match)
            logger.info(f"Bing found {len(img_urls)} image URLs")
    except Exception as e:
        logger.warning(f"Bing search error: {e}")

    # Source 2: Google Images (via US proxy)
    if not img_urls:
        try:
            from urllib.parse import quote
            import re
            google_url = f"https://www.google.com/search?q={quote(query + ' news')}&tbm=isch&tbs=isz:l"
            r = requests.get(google_url, headers=headers, proxies=proxies, timeout=15)
            if r.status_code == 200:
                for match in re.findall(r'\["(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', r.text):
                    if "google" not in match and "gstatic" not in match:
                        img_urls.append(match)
                logger.info(f"Google found {len(img_urls)} image URLs")
        except Exception as e:
            logger.warning(f"Google search error: {e}")

    # Source 3: DuckDuckGo API (no proxy needed)
    if not img_urls:
        try:
            from urllib.parse import quote
            ddg_api = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1"
            r = requests.get(ddg_api, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data.get("Image"):
                    img_urls.append(data["Image"])
                for topic in data.get("RelatedTopics", []):
                    if isinstance(topic, dict) and topic.get("Icon", {}).get("URL"):
                        url = topic["Icon"]["URL"]
                        if url.startswith("http"):
                            img_urls.append(url)
        except Exception:
            pass

    # Download best result (direct, no proxy needed for image download)
    for url in img_urls[:8]:
        try:
            img_r = requests.get(url, timeout=10, headers=headers)
            img_r.raise_for_status()
            if len(img_r.content) < 5000:
                continue
            img = Image.open(io.BytesIO(img_r.content)).convert("RGB")
            w, h = img.size
            if w >= 400 and h >= 250:
                logger.info(f"News image downloaded: {w}x{h}")
                return img
        except Exception:
            continue

    logger.warning(f"No news image found for: {query[:50]}")
    return None


# ── Together AI (Flux Schnell Free) ────────────────────────────────────────────

def _generate_with_together(prompt: str) -> Optional[Image.Image]:
    api_key = os.getenv("TOGETHER_API_KEY", "")
    if not api_key:
        return None

    try:
        import together
        client = together.Together(api_key=api_key)
        response = client.images.generate(
            model="black-forest-labs/FLUX.1-schnell-Free",
            prompt=prompt,
            width=1216,
            height=832,
            steps=4,
            n=1,
            response_format="b64_json",
        )
        img_data = base64.b64decode(response.data[0].b64_json)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        logger.info(f"Together AI image generated ({img.size})")
        return img
    except Exception as e:
        logger.warning(f"Together AI failed: {e}")
        return None


# ── Pollinations.ai (free, no key) ─────────────────────────────────────────────

def _generate_with_pollinations(prompt: str) -> Optional[Image.Image]:
    try:
        from urllib.parse import quote
        encoded = quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&model=flux&nologo=true"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        logger.info(f"Pollinations image generated ({img.size})")
        return img
    except Exception as e:
        logger.warning(f"Pollinations failed: {e}")
        return None


# ── Pexels stock photos ────────────────────────────────────────────────────────

def _fetch_from_pexels(query: str) -> Optional[Image.Image]:
    api_key = os.getenv("PEXELS_API_KEY", "")
    if not api_key:
        return None

    try:
        page = random.randint(1, 5)
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": query, "per_page": 15, "page": page, "orientation": "landscape"},
            timeout=10,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return None

        photo = random.choice(photos)
        img_url = photo["src"]["large2x"]
        img_r = requests.get(img_url, timeout=15)
        img_r.raise_for_status()
        img = Image.open(io.BytesIO(img_r.content)).convert("RGB")
        logger.info(f"Pexels image fetched: {photo['photographer']}")
        return img
    except Exception as e:
        logger.warning(f"Pexels failed: {e}")
        return None


# ── Image modifications (make stock photos unique) ─────────────────────────────

def _make_unique(img: Image.Image) -> Image.Image:
    """
    Standard image processing to create an original composition.
    Every output is a unique image — different crop, color grade, resolution.
    """
    import numpy as np

    w, h = img.size

    # 1. Random crop (3-8% from edges — reframes the composition)
    crop_pct = random.uniform(0.03, 0.08)
    left = int(w * crop_pct * random.random())
    top = int(h * crop_pct * random.random())
    right = w - int(w * crop_pct * random.random())
    bottom = h - int(h * crop_pct * random.random())
    img = img.crop((left, top, right, bottom))

    # 2. Color grading (like applying a photo filter)
    img = ImageEnhance.Color(img).enhance(random.uniform(0.85, 1.25))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.9, 1.15))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.9, 1.1))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.8, 1.3))

    # 3. Slight color tone shift (warm/cool grade)
    arr = np.array(img, dtype=np.int16)
    tone = random.choice(["warm", "cool", "neutral"])
    if tone == "warm":
        arr[:, :, 0] = np.clip(arr[:, :, 0] + random.randint(3, 10), 0, 255)  # red up
        arr[:, :, 2] = np.clip(arr[:, :, 2] - random.randint(2, 6), 0, 255)   # blue down
    elif tone == "cool":
        arr[:, :, 2] = np.clip(arr[:, :, 2] + random.randint(3, 10), 0, 255)  # blue up
        arr[:, :, 0] = np.clip(arr[:, :, 0] - random.randint(2, 6), 0, 255)   # red down
    img = Image.fromarray(arr.astype(np.uint8))

    # 4. Slight random pixel noise (makes every image unique at pixel level)
    arr = np.array(img, dtype=np.int16)
    noise = np.random.randint(-3, 4, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))

    # 5. Strip all EXIF/metadata (fresh image, no source traces)
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    img = clean

    return img


# ── Branded overlay (text on image) ────────────────────────────────────────────

def _add_branded_overlay(img: Image.Image, title: str, niche: str) -> Image.Image:
    """Adds dark gradient overlay + headline text + branding to any image."""
    style = NICHE_STYLES.get(niche, NICHE_STYLES["weird"])

    # Resize to standard dimensions
    img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)

    # Dark gradient overlay (darker at bottom for text readability)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(HEIGHT):
        # Gradient: top is 30% dark, bottom is 80% dark
        alpha = int(80 + (180 * (y / HEIGHT)))
        draw_ov.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Fonts
    font_label = _get_font(20, bold=True)
    font_title = _get_font(44, bold=True)
    font_small = _get_font(20, bold=False)

    # Top accent bar
    draw.rectangle([(0, 0), (WIDTH, 5)], fill=style["accent"])

    # Niche label badge
    label_text = style["label"]
    label_bbox = font_label.getbbox(label_text)
    label_w = label_bbox[2] - label_bbox[0] + 28
    label_h = label_bbox[3] - label_bbox[1] + 14
    draw.rounded_rectangle(
        [(45, 25), (45 + label_w, 25 + label_h)],
        radius=5,
        fill=style["accent"],
    )
    draw.text((59, 29), label_text, font=font_label, fill=(255, 255, 255))

    # Headline — positioned in lower half over the dark gradient
    max_text_width = WIDTH - 120
    lines = _wrap_text(title.upper(), font_title, max_text_width)
    line_height = 54
    total_h = len(lines[:4]) * line_height
    y_start = HEIGHT - 80 - total_h  # Position from bottom

    for line in lines[:4]:
        draw.text((62, y_start + 2), line, font=font_title, fill=(0, 0, 0))
        draw.text((60, y_start), line, font=font_title, fill=style["text"])
        y_start += line_height

    # Bottom bar
    draw.rectangle([(0, HEIGHT - 50), (WIDTH, HEIGHT)], fill=style["accent"])
    watermark = style.get("watermark", "Follow for more")

    # Add page logo if available
    logo_path = Path("assets/logo.png")
    logo_offset = 45
    if logo_path.exists():
        try:
            logo = Image.open(str(logo_path)).convert("RGBA")
            logo_h = 36
            logo_w = int(logo.width * (logo_h / logo.height))
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            img.paste(logo, (45, HEIGHT - 44), logo)
            logo_offset = 45 + logo_w + 10
        except Exception:
            pass

    draw.text((logo_offset, HEIGHT - 38), watermark, font=font_small, fill=(255, 255, 255))

    return img


# ── Pillow text-only card (last resort fallback) ───────────────────────────────

def _generate_text_card(title: str, niche: str) -> Image.Image:
    """Creates a branded text card as final fallback."""
    style = NICHE_STYLES.get(niche, NICHE_STYLES["weird"])
    canvas = Image.new("RGB", (WIDTH, HEIGHT), style["bg"])
    draw = ImageDraw.Draw(canvas)

    font_label = _get_font(22, bold=True)
    font_title = _get_font(48, bold=True)
    font_small = _get_font(22, bold=False)

    # Top accent bar
    draw.rectangle([(0, 0), (WIDTH, 6)], fill=style["accent"])

    # Label badge
    label_text = style["label"]
    label_bbox = font_label.getbbox(label_text)
    label_w = label_bbox[2] - label_bbox[0] + 30
    label_h = label_bbox[3] - label_bbox[1] + 16
    draw.rounded_rectangle([(50, 30), (50 + label_w, 30 + label_h)], radius=6, fill=style["accent"])
    draw.text((65, 36), label_text, font=font_label, fill=(255, 255, 255))

    # Headline
    max_text_width = WIDTH - 120
    lines = _wrap_text(title.upper(), font_title, max_text_width)
    line_height = 58
    total_h = len(lines[:5]) * line_height
    y_start = max(90, (HEIGHT - total_h) // 2 - 20)

    for line in lines[:5]:
        draw.text((62, y_start + 2), line, font=font_title, fill=(0, 0, 0))
        draw.text((60, y_start), line, font=font_title, fill=style["text"])
        y_start += line_height

    # Accent line
    draw.rectangle([(60, y_start + 15), (260, y_start + 19)], fill=style["accent"])

    # Bottom bar
    draw.rectangle([(0, HEIGHT - 56), (WIDTH, HEIGHT)], fill=style["accent"])
    watermark = style.get("watermark", "Follow for more")
    draw.text((50, HEIGHT - 42), watermark, font=font_small, fill=(255, 255, 255))

    return canvas


# ── Main entry point ───────────────────────────────────────────────────────────

def create_image_card(title: str, niche: str, image_url: str = "", source_url: str = "") -> dict:
    """
    Generates an image for a post. Strategy:
      1. Scrape the actual article page for the REAL photo (mugshot, scene, athlete)
      2. Try RSS image_url if article scrape fails
      3. Search Bing for the headline (via US proxy)
      4. Fallback to Pexels stock photo
      5. Last resort: text card
    """
    style = NICHE_STYLES.get(niche, NICHE_STYLES["weird"])
    image_mode = style.get("image_mode", "stock")
    img = None

    if image_mode == "local_folder":
        # Pick the oldest image from the upload folder (FIFO — post in order)
        folder = Path(style.get("folder", "uploads/taichi"))
        photos = list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")) + list(folder.glob("*.png")) + list(folder.glob("*.webp"))
        if photos:
            picked = sorted(photos, key=lambda f: f.stat().st_mtime)[0]  # oldest first
            img = Image.open(str(picked)).convert("RGB")
            logger.info(f"[{niche}] Using local photo: {picked.name}")
            # Post the photo as-is (no overlay, it's your influencer)
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
            filename = IMAGES_DIR / f"{niche}_{uuid.uuid4().hex[:8]}.jpg"
            img.save(str(filename), "JPEG", quality=95)
            # Move to posted folder so it's not reused
            posted_dir = folder / "posted"
            posted_dir.mkdir(exist_ok=True)
            import shutil
            shutil.move(str(picked), str(posted_dir / picked.name))
            logger.info(f"[{niche}] Moved {picked.name} to posted/")
            return {"local_path": str(filename), "canva_url": ""}
        else:
            logger.warning(f"[{niche}] No photos in {folder} — falling back to text card")

    elif image_mode == "news_search_real":
        # For crime/sports: find the ACTUAL photo first (mugshots are public domain)
        # Priority 1: Scrape article page
        if source_url:
            img = _scrape_article_image(source_url)
            if img:
                img = _make_unique(img)

        # Priority 2: Bing search for actual news photo
        if not img:
            img = _search_news_image(title)
            if img:
                img = _make_unique(img)

        # Priority 3: Pexels stock fallback
        if not img:
            queries = style.get("search_queries", ["news"])
            img = _fetch_from_pexels(random.choice(queries))
            if img:
                img = _make_unique(img)

    elif image_mode == "news_search":
        # Priority 1: Pexels stock photos (copyright-safe, monetization-safe)
        queries = style.get("search_queries", ["news"])
        query = random.choice(queries)
        # Try headline-based search for more relevant results
        headline_words = [w for w in title.split()[:4] if len(w) > 3]
        pexels_query = " ".join(headline_words) if headline_words else query

        img = _fetch_from_pexels(pexels_query)
        if not img:
            img = _fetch_from_pexels(query)
        if img:
            img = _make_unique(img)

        # Priority 2: Bing search (for topics Pexels doesn't cover)
        if not img:
            img = _search_news_image(title)
            if img:
                img = _make_unique(img)

    elif image_mode == "ai":
        # Build AI prompt
        template = style.get("ai_prompt_template", "")
        if "{setting}" in template:
            settings = style.get("ai_settings", ["a peaceful outdoor setting"])
            setting = random.choice(settings)
            prompt = template.format(setting=setting)
        elif "{headline}" in template:
            prompt = template.format(headline=title[:100])
        else:
            prompt = template

        # Try AI generation
        img = _generate_with_together(prompt)
        if not img:
            img = _generate_with_pollinations(prompt)

    elif image_mode == "stock":
        # Try Pexels with niche-relevant query
        queries = style.get("search_queries", ["news"])
        query = random.choice(queries)
        img = _fetch_from_pexels(query)
        if img:
            img = _make_unique(img)

    # Try news article image as fallback
    if not img and image_url:
        try:
            r = requests.get(image_url, timeout=8)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            pass

    # Add branded overlay if we have a photo
    if img:
        final = _add_branded_overlay(img, title, niche)
    else:
        # Last resort: text card
        final = _generate_text_card(title, niche)

    # Save
    filename = IMAGES_DIR / f"{niche}_{uuid.uuid4().hex[:8]}.jpg"
    final.save(str(filename), "JPEG", quality=95)
    logger.info(f"[{niche}] Image saved: {filename}")

    return {
        "local_path": str(filename),
        "canva_url": "",
    }
