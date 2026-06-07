"""
pinterest.py — Pinterest API poster for Hermes
Posts pin to the correct pillar board.
"""

import requests
import os
import base64
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

PINTEREST_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {PINTEREST_TOKEN}",
    "Content-Type": "application/json",
}

# Pinterest board IDs — fill in after fetching from API
BOARD_IDS = {
    "Burnout & Exhaustion": None,
    "Relationships & Regret": None,
    "Family & Belonging": None,
    "Forgiveness": None,
    "Faith & Doubt": None,
    "Money & Enough": None,
    "Friendship & Loneliness": None,
    "Mid-life Drift": None,
    "Ambition & Peace": None,
}


def get_board_ids():
    """Fetch board IDs from Pinterest account."""
    try:
        response = requests.get(
            "https://api.pinterest.com/v5/boards?page_size=25",
            headers=HEADERS,
            timeout=15
        )
        if response.status_code == 200:
            boards = response.json().get("items", [])
            for board in boards:
                name = board["name"]
                if name in BOARD_IDS:
                    BOARD_IDS[name] = board["id"]
            print(f"[PINTEREST] Boards loaded: {BOARD_IDS}")
            return True
        else:
            print(f"[PINTEREST] Failed to fetch boards: HTTP {response.status_code}")
            print(response.text[:200])
            return False
    except Exception as e:
        print(f"[PINTEREST] Error fetching boards: {e}")
        return False


def upload_pin_image(image_path):
    """Upload pin image to Pinterest media."""
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        upload_headers = {
            "Authorization": f"Bearer {PINTEREST_TOKEN}",
        }

        files = {
            "file": ("pin.png", image_data, "image/png"),
        }

        response = requests.post(
            "https://api.pinterest.com/v5/media",
            headers=upload_headers,
            files=files,
            timeout=30
        )

        if response.status_code == 201:
            media_id = response.json().get("media_id")
            print(f"[PINTEREST] Image uploaded: {media_id}")
            return media_id
        else:
            print(f"[PINTEREST] Image upload failed: HTTP {response.status_code}")
            print(response.text[:200])
            return None

    except Exception as e:
        print(f"[PINTEREST] Image upload error: {e}")
        return None


def post_pin(article_title, meta_description, post_url, pin_image_path, pillar_name):
    """
    Post a pin to Pinterest.
    Returns pin URL or None if failed.
    """
    print(f"\n[PINTEREST] Posting pin: {article_title[:60]}")

    # Get board IDs
    get_board_ids()
    board_id = BOARD_IDS.get(pillar_name)

    if not board_id:
        print(f"[PINTEREST] No board found for pillar: {pillar_name}")
        return None

    # Upload pin image
    media_id = upload_pin_image(pin_image_path)
    if not media_id:
        return None

    # Create pin
    pin_data = {
        "board_id": board_id,
        "title": article_title,
        "description": f"{meta_description}\n\nRead more: {post_url}",
        "link": post_url,
        "media_source": {
            "source_type": "image_base64",
            "content_type": "image/png",
            "data": get_image_base64(pin_image_path),
        },
    }

    try:
        response = requests.post(
            "https://api.pinterest.com/v5/pins",
            headers=HEADERS,
            json=pin_data,
            timeout=30
        )

        if response.status_code == 201:
            pin = response.json()
            pin_url = f"https://pinterest.com/pin/{pin['id']}"
            print(f"[PINTEREST] Pin posted: {pin_url}")
            return pin_url
        else:
            print(f"[PINTEREST] Pin failed: HTTP {response.status_code}")
            print(response.text[:300])
            return None

    except Exception as e:
        print(f"[PINTEREST] Pin error: {e}")
        return None


def get_image_base64(image_path):
    """Return base64 encoded image."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


if __name__ == "__main__":
    # Test: fetch board IDs
    print("[PINTEREST] Fetching boards...")
    get_board_ids()
