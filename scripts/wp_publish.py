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
    # Remove any variation of the footer — added once cleanly at the end
    article_text = re.sub(r'\*?Inspired by a real story shared anonymously online\.\*?', '', article_text).strip()

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

    # Add footer once at the end
    html_parts.append("<!-- wp:separator --><hr class=\"wp-block-separator\"/><!-- /wp:separator -->")
    html_parts.append("<!-- wp:paragraph --><p><em>Inspired by a real story shared anonymously online.</em></p><!-- /wp:paragraph -->")

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


if __name__ == "__main__":
    test_article = {
        "article": "She spent twelve years in the same building. Same desk, same login, same coffee machine that broke every third Tuesday. Then yesterday she submitted the email. Her hands shook. She expected relief. She expected freedom. Instead she sat in her car for forty-five minutes and stared at the steering wheel.\n\nHer manager said okay.\n\nThat was it.\n\n---\n\nWe think leaving will feel like opening a door. We rehearse the moment. We imagine the weight lifting. But sometimes freedom arrives and we don't recognize it. Sometimes we sit in parking lots because our bodies haven't caught up to the decision our minds already made. Sometimes twelve years fits into one word: okay.\n\nThe shaking hands knew something the resignation letter didn't.\n\n---\n\nShe thought she would know what she felt. Not that she left, but that she expected clarity on the other side. Like crossing a finish line would change the fact that she doesn't know how to stand still without something to push against.\n\nWhat do you do when you get what you wanted and it doesn't feel like winning?\n\n*Inspired by a real story shared anonymously online.*",
        "seo_title": "She Quit After 12 Years and Felt Nothing",
        "meta_description": "She expected relief when she finally left. Instead she sat in her car for forty-five minutes, not knowing what she felt. Twelve years, and her manager just said okay.",
        "focus_keyword": "quitting job feeling empty",
        "slug": "quit-after-twelve-years-felt-nothing-4",
        "tags": ["burnout", "leaving job", "career burnout"],
    }

    today = "2026-06-07-test4"
    result = publish_post(test_article, "Burnout & Exhaustion", None, today)
    if result:
        print(f"\n[WP] Success: {result}")
    else:
        print(f"\n[WP] Failed")
