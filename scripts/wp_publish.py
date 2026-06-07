"""
wp_publish.py — WordPress REST API publisher for Hermes
Uploads image and creates post with all metadata.
"""

import requests
import os
import base64
import time
import re
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

WP_URL = os.getenv("WP_URL")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

credentials = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode("utf-8")
HEADERS = {
    "Authorization": f"Basic {token}",
    "Content-Type": "application/json",
}

CATEGORY_IDS = {
    "Burnout & Exhaustion": 17,
    "Relationships & Regret": 9,
    "Family & Belonging": 10,
    "Forgiveness": 11,
    "Faith & Doubt": 12,
    "Money & Enough": 13,
    "Friendship & Loneliness": 14,
    "Mid-life Drift": 15,
    "Ambition & Peace": 19,
}

CATEGORY_NAMES = {v: k for k, v in CATEGORY_IDS.items()}


def fetch_all_titles():
    """
    Fetch all published post titles from WordPress.
    Returns list of {title, pillar, url} dicts.
    """
    all_posts = []
    page = 1

    print(f"[WP] Fetching all published post titles for memory...")

    while True:
        try:
            response = requests.get(
                f"{WP_URL}/wp-json/wp/v2/posts",
                headers=HEADERS,
                params={
                    "status": "publish",
                    "per_page": 100,
                    "page": page,
                    "_fields": "title,link,categories",
                },
                timeout=15
            )

            if response.status_code == 400:
                break  # No more pages
            if response.status_code != 200:
                print(f"[WP] Failed to fetch titles: HTTP {response.status_code}")
                break

            posts = response.json()
            if not posts:
                break

            for post in posts:
                title = post.get("title", {}).get("rendered", "")
                link = post.get("link", "")
                cats = post.get("categories", [])

                # Map category ID back to pillar name
                pillar = None
                for cat_id in cats:
                    if cat_id in CATEGORY_NAMES:
                        pillar = CATEGORY_NAMES[cat_id]
                        break

                all_posts.append({
                    "title": title,
                    "pillar": pillar,
                    "url": link,
                })

            # Check if there are more pages
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break
            page += 1

        except Exception as e:
            print(f"[WP] Error fetching titles page {page}: {e}")
            break

    print(f"[WP] Loaded {len(all_posts)} existing posts into memory")
    return all_posts


def upload_image(image_path, filename):
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
            return None

    except Exception as e:
        print(f"[WP] Image upload error: {e}")
        return None


def get_or_create_tags(tag_names):
    tag_ids = []
    for tag_name in tag_names:
        try:
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
    # Remove footer — theme adds it automatically
    article_text = re.sub(r'\*?Inspired by a real story shared anonymously online\.\*?', '', article_text).strip()
    # Strip markdown headings
    article_text = re.sub(r'^#{1,6}\s+.*$', '', article_text, flags=re.MULTILINE).strip()
    # Remove leading empty lines
    lines = article_text.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    article_text = '\n'.join(lines).strip()

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
                if not line:
                    continue
                line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                line = re.sub(r'\*(.*?)\*', r'<em>\1</em>', line)
                html_parts.append(f"<!-- wp:paragraph --><p>{line}</p><!-- /wp:paragraph -->")

    return "\n".join(html_parts)


def publish_post(article_data, pillar_name, image_path, today):
    print(f"\n[WP] Publishing post: {article_data['seo_title']}")

    category_id = CATEGORY_IDS.get(pillar_name)
    if not category_id:
        print(f"[WP] Warning: category not found for {pillar_name}")

    image_id = None
    if image_path and os.path.exists(image_path):
        filename = f"tfs-{today}.png"
        image_id = upload_image(image_path, filename)

    tag_ids = get_or_create_tags(article_data.get("tags", []))
    content_html = format_content(article_data["article"])

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
                    time.sleep(60)

        except Exception as e:
            print(f"[WP] Publish error (attempt {attempt + 1}): {e}")

    return None
