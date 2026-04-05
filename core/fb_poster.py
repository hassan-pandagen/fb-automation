"""
Posts content to Facebook pages using the Graph API directly.
No third-party library needed — just requests.

Supports:
  - Photo posts (image + caption)
  - Text-only posts
  - Fetching post insights (reach, reactions)
"""

import os
import logging
import requests
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v25.0"


class FacebookPoster:
    def __init__(self, page_id: str, access_token: str):
        self.page_id = page_id
        self.token   = access_token

    def _url(self, endpoint: str) -> str:
        return f"{GRAPH_URL}/{endpoint}"

    # ── Posting ──────────────────────────────────────────────────────────────

    def post_photo(self, image_path: str, caption: str) -> Optional[str]:
        """
        Posts a photo as a FEED POST on the page timeline.

        Key API details (Graph API v25.0):
        - 'caption' is the correct field ('message' is DEPRECATED on /photos)
        - 'no_story' must be false (default) so the photo creates a feed story
        - 'published' = true posts immediately
        - Response includes 'post_id' when a feed story is created
        """
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image not found: {image_path}")
            return None

        try:
            with open(path, "rb") as img_file:
                response = requests.post(
                    self._url(f"{self.page_id}/photos"),
                    data={
                        "message":       caption,
                        "access_token":  self.token,
                        "published":     "true",
                    },
                    files={"source": (path.name, img_file, "image/jpeg")},
                    timeout=30,
                )

            data = response.json()

            if "post_id" in data:
                post_id = data["post_id"]
                logger.info(f"Feed post created on page {self.page_id}: post_id={post_id}")
                return post_id
            elif "id" in data:
                photo_id = data["id"]
                logger.warning(
                    f"Photo uploaded to page {self.page_id} but NO post_id returned "
                    f"(photo may be album-only, not in feed). photo_id={photo_id}"
                )
                return photo_id
            else:
                logger.error(f"Facebook post failed: {data}")
                return None

        except Exception as e:
            logger.error(f"Post photo exception: {e}")
            return None

    def post_text(self, message: str) -> Optional[str]:
        """Posts a text-only update. Returns post ID."""
        try:
            response = requests.post(
                self._url(f"{self.page_id}/feed"),
                data={
                    "message":      message,
                    "access_token": self.token,
                },
                timeout=15,
            )
            data = response.json()
            if "id" in data:
                logger.info(f"Text post to {self.page_id}: {data['id']}")
                return data["id"]
            logger.error(f"Text post failed: {data}")
            return None
        except Exception as e:
            logger.error(f"Text post exception: {e}")
            return None

    def post_photo_from_url(self, image_url: str, caption: str) -> Optional[str]:
        """Posts a photo by URL as a feed post (useful for Canva export URLs)."""
        try:
            response = requests.post(
                self._url(f"{self.page_id}/photos"),
                data={
                    "url":          image_url,
                    "caption":      caption,
                    "access_token": self.token,
                    "published":    "true",
                    "no_story":     "false",
                },
                timeout=20,
            )
            data = response.json()
            if "post_id" in data:
                logger.info(f"URL photo feed post: {data['post_id']}")
                return data["post_id"]
            elif "id" in data:
                logger.warning(f"URL photo posted but may be album-only (no post_id): {data['id']}")
                return data["id"]
            logger.error(f"URL photo post failed: {data}")
            return None
        except Exception as e:
            logger.error(f"URL photo post exception: {e}")
            return None

    def post_video(self, video_path: str, description: str = "") -> Optional[str]:
        """Posts a video/reel to the page. Returns post ID."""
        path = Path(video_path)
        if not path.exists():
            logger.error(f"Video not found: {video_path}")
            return None

        try:
            with open(path, "rb") as vid_file:
                response = requests.post(
                    self._url(f"{self.page_id}/videos"),
                    data={
                        "description":   description,
                        "access_token":  self.token,
                        "published":     "true",
                    },
                    files={"source": (path.name, vid_file, "video/mp4")},
                    timeout=120,
                )

            data = response.json()
            if "id" in data:
                post_id = data["id"]
                logger.info(f"Posted video to page {self.page_id}: post_id={post_id}")
                return post_id
            else:
                logger.error(f"Video post failed: {data}")
                return None

        except Exception as e:
            logger.error(f"Post video exception: {e}")
            return None

    # ── Insights ──────────────────────────────────────────────────────────────

    def get_post_insights(self, post_id: str) -> dict:
        """
        Fetches reach, impressions, reactions for a post.
        Call this ~24h after posting for accurate numbers.
        """
        metrics = "post_impressions,post_impressions_unique,post_reactions_by_type_total"
        try:
            r = requests.get(
                self._url(f"{post_id}/insights"),
                params={
                    "metric":       metrics,
                    "access_token": self.token,
                },
                timeout=10,
            )
            data = r.json().get("data", [])
            result = {}
            for item in data:
                result[item["name"]] = item["values"][-1]["value"] if item.get("values") else 0
            return result
        except Exception as e:
            logger.error(f"Insights fetch failed: {e}")
            return {}

    def get_page_fan_count(self) -> int:
        """Returns current follower count of the page."""
        try:
            r = requests.get(
                self._url(self.page_id),
                params={"fields": "fan_count", "access_token": self.token},
                timeout=10,
            )
            return r.json().get("fan_count", 0)
        except Exception:
            return 0

    def verify_token(self) -> bool:
        """Quick check that the page token is valid."""
        try:
            r = requests.get(
                self._url("me"),
                params={"access_token": self.token, "fields": "id,name"},
                timeout=8,
            )
            return "id" in r.json()
        except Exception:
            return False
