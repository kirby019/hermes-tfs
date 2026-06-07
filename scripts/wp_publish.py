"""
wp_publish.py — WordPress REST API publisher for Hermes
Uploads image and creates post with all metadata.
"""

import requests
import json
import os
import base64
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

WP_URL = os.getenv("WP_URL")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

# Build auth header
credentials = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode("utf-8")
HEADERS = {
    "Authorization": f"Basic {token}",
    "Content-Type": "application/json",
}

CATEGORY_IDS = {
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


def get_category_ids():
    """Fetch category IDs from WordPress."""
    try:
        response = requests.get(
            f"{WP_URL}/wp-json/wp/v2/categories?per_page=100",
            headers=HEADERS,
            timeout=15
        )
        if response.status_code == 200:
            categories = response.json()
            for cat in categories:
                if cat["name"] in CATEGORY_IDS:
                    CATEGORY_IDS[cat["name"]] = cat["id"]
            print(f"[WP] Categories loaded: {CATEGORY_IDS}")
        else:
            print(f"[WP] Failed to fetch categories: HTTP {response.status_code}")
    except Exception as e:
        print(f"[WP] Error fetching categories: {e}")


def upload_image(image_path, filename):
    """Upload image to WordPress media library."""
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        upload_headers = {
            "Authorization": f"Basic {token}",
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "image/png",
        }

        response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media",
            headers=upload_headers,
            data=image_data,
            timeout=30
        )

        if response.status_code == 201:
            media = response.json()
            print(f"[WP] Image uploaded: ID {media['id']}")
            return media["id"]
        else:
            print(f"[WP] Image upload failed: HTTP {response.status_code}")
            print(response.text[:200])
            return None

    except Exception as e:
        print(f"[WP] Image upload error: {e}")
        return None


def get_or_create_tags(tag_names):
    """Get or create tags, return list of tag IDs."""
    tag_ids = []
    for tag_name in tag_names:
        try:
            # Search for existing tag
            response = requests.get(
                f"{WP_URL}/wp-json/wp/v2/tags?search={tag_name}",
                headers=HEADERS,
                timeout=10
            )
            if response.status_code == 200:
                tags = response.json()
                if tags:
                    tag_ids.append(tags[0]["id"])
                    continue

            # Create new tag
            response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/tags",
                headers=HEADERS,
                json={"name": tag_name},
                timeout=10
            )
            if response.status_code == 201:
                tag_ids.append(response.json()["id"])

        except Exception as e:
            print(f"[WP] Tag error for '{tag_name}': {e}")

    return tag_ids


def format_content(article_text):
    """Convert plain text article to WordPress block HTML."""
    paragraphs = article_text.strip().split("\n\n")
    html_parts = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if para == "---":
            html_parts.append("<!-- wp:separator --><hr class=\"wp-block-separator\"/><!-- /wp:separator -->")
        else:
            lines = para.split("\n")
            for line in lines:
                line = line.strip()
                if line:
                    html_parts.append(f"<!-- wp:paragraph --><p>{line}</p><!-- /wp:paragraph -->")

    return "\n".join(html_parts)


def publish_post(article_data, pillar_name, image_path, today):
    """
    Publish article to WordPress.
    Returns post URL or None if failed.
    """
    print(f"\n[WP] Publishing post: {article_data['seo_title']}")

    # Load category IDs
    get_category_ids()
    category_id = CATEGORY_IDS.get(pillar_name)
    if not category_id:
        print(f"[WP] Warning: category not found for {pillar_name}")

    # Upload featured image
    image_id = None
    if image_path and os.path.exists(image_path):
        filename = f"tfs-{today}.png"
        image_id = upload_image(image_path, filename)

    # Get tag IDs
    tag_ids = get_or_create_tags(article_data.get("tags", []))

    # Format content
    content_html = format_content(article_data["article"])

    # Build post payload
    post_data = {
        "title": article_data["seo_title"],
        "content": content_html,
        "slug": article_data["slug"],
        "status": "publish",
        "categories": [category_id] if category_id else [],
        "tags": tag_ids,
        "meta": {
            "rank_math_title": article_data["seo_title"],
            "rank_math_description": article_data["meta_description"],
            "rank_math_focus_keyword": article_data["focus_keyword"],
        },
    }

    if image_id:
        post_data["featured_media"] = image_id

    # Publish post
    for attempt in range(2):
        try:
            response = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts",
                headers=HEADERS,
                json=post_data,
                timeout=30
            )

            if response.status_code == 201:
                post = response.json()
                post_url = post["link"]
                print(f"[WP] Post published: {post_url}")
                return post_url
            else:
                print(f"[WP] Publish failed (attempt {attempt + 1}): HTTP {response.status_code}")
                print(response.text[:300])
                if attempt == 0:
                    import time
                    time.sleep(60)

        except Exception as e:
            print(f"[WP] Publish error (attempt {attempt + 1}): {e}")

    return None


if __name__ == "__main__":
    # Test with dummy data
    test_article = {
        "article": "She spent twelve years in the same building.\n\nThen yesterday she submitted the email.\n\nHer manager said okay.\n\nThat was it.\n\n---\n\nWe think leaving will feel like opening a door.\n\nSometimes twelve years fits into one word: okay.\n\nWhat do you do when you get what you wanted and it doesn't feel like winning?",
        "seo_title": "She Quit After 12 Years and Felt Nothing",
        "meta_description": "She expected relief when she finally left. Instead she sat in her car for forty-five minutes, not knowing what she felt.",
        "focus_keyword": "quitting job feeling empty",
        "slug": "quit-after-twelve-years-felt-nothing",
        "tags": ["burnout", "leaving job", "career burnout"],
    }

    today = "2026-06-07-test"
    result = publish_post(test_article, "Burnout & Exhaustion", None, today)
    if result:
        print(f"\n[WP] Success: {result}")
    else:
        print(f"\n[WP] Failed")
