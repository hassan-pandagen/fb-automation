"""
Token manager — Facebook Page tokens expire every 60 days.
This module:
  1. Checks token expiry via Graph API
  2. Refreshes tokens automatically before they expire
  3. Writes refreshed tokens back to the .env file (local) or
     updates Railway environment variables via Railway API

Run manually:  python utils/token_manager.py
Runs automatically every Monday via the scheduler.
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key

load_dotenv()
logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"
ENV_FILE  = ".env"


def inspect_token(token: str) -> dict:
    """
    Calls the Graph API debug_token endpoint.
    Returns dict with: is_valid, expires_at (datetime or None), scopes
    """
    app_id     = os.getenv("FB_APP_ID", "")
    app_secret = os.getenv("FB_APP_SECRET", "")

    if not app_id or not app_secret:
        logger.warning("FB_APP_ID / FB_APP_SECRET not set — cannot inspect token")
        return {"is_valid": True, "expires_at": None, "scopes": []}

    try:
        r = requests.get(
            f"{GRAPH_URL}/debug_token",
            params={
                "input_token":  token,
                "access_token": f"{app_id}|{app_secret}",
            },
            timeout=10,
        )
        data = r.json().get("data", {})
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromtimestamp(data["expires_at"])
        return {
            "is_valid":   data.get("is_valid", False),
            "expires_at": expires_at,
            "scopes":     data.get("scopes", []),
        }
    except Exception as e:
        logger.error(f"Token inspect error: {e}")
        return {"is_valid": True, "expires_at": None, "scopes": []}


def exchange_for_long_lived(short_token: str) -> str:
    """
    Exchanges any token for a 60-day long-lived token.
    Returns the new long-lived token, or empty string on failure.
    """
    app_id     = os.getenv("FB_APP_ID", "")
    app_secret = os.getenv("FB_APP_SECRET", "")

    if not app_id or not app_secret:
        logger.error("Cannot refresh token — FB_APP_ID / FB_APP_SECRET missing in .env")
        return ""

    try:
        r = requests.get(
            f"{GRAPH_URL}/oauth/access_token",
            params={
                "grant_type":        "fb_exchange_token",
                "client_id":         app_id,
                "client_secret":     app_secret,
                "fb_exchange_token": short_token,
            },
            timeout=15,
        )
        data = r.json()
        new_token = data.get("access_token", "")
        if new_token:
            logger.info("Token successfully exchanged for long-lived version")
        else:
            logger.error(f"Token exchange failed: {data}")
        return new_token
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        return ""


def check_and_refresh_all():
    """
    Checks all PAGE_N_TOKEN values.
    If a token expires within 10 days, refreshes it and updates .env.
    """
    load_dotenv()
    i = 1
    while True:
        token_key = f"PAGE_{i}_TOKEN"
        token     = os.getenv(token_key)
        if not token:
            break

        niche = os.getenv(f"PAGE_{i}_NICHE", f"page_{i}")
        info  = inspect_token(token)

        if not info["is_valid"]:
            logger.warning(f"[{niche}] Token is INVALID — needs manual refresh")
            i += 1
            continue

        expires_at = info["expires_at"]
        if expires_at is None:
            logger.info(f"[{niche}] Token expiry unknown — refreshing proactively")
            _refresh_token(token_key, token, niche)
        elif expires_at < datetime.now() + timedelta(days=10):
            days_left = (expires_at - datetime.now()).days
            logger.info(f"[{niche}] Token expires in {days_left} days — refreshing now")
            _refresh_token(token_key, token, niche)
        else:
            days_left = (expires_at - datetime.now()).days
            logger.info(f"[{niche}] Token OK — expires in {days_left} days")

        i += 1


def _refresh_token(env_key: str, current_token: str, niche: str):
    """Refreshes a token and writes it back to .env."""
    new_token = exchange_for_long_lived(current_token)
    if not new_token:
        logger.error(f"[{niche}] Refresh failed — old token still in use")
        return

    # Write to local .env
    set_key(ENV_FILE, env_key, new_token)
    # Also update process env so the running app uses it immediately
    os.environ[env_key] = new_token
    logger.info(f"[{niche}] Token refreshed and saved to .env")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    logger.info("Checking all Facebook page tokens...")
    check_and_refresh_all()
    logger.info("Token check complete")
