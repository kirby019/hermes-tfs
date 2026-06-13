"""
wp_publish.py — WordPress REST API publisher for Hermes
Uploads image and creates post with all metadata.
"""

import requests
import json
import os
import base64
import time
import re
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

WP_URL          = os.getenv("WP_URL")
WP_USERNAME     = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

credentials = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
token       = base64.b64encode(credentials.encode()).decode("utf-8")
HEADERS     = {
    "Authorization": f"Basic {token}",
    "Content-Type":  "application/json",
}

CATEGORY_IDS = {
    "Burnout & Exhaustion":    17,
    "Relationships & Regret":  9,
    "Family & Belonging":      10,
    "Forgiveness":             11,
    "Faith & Doubt":           12,
    "Money & Enough":          13,
    "Friendship & Loneliness": 14,
    "Mid-life Drift":          15,
    "Ambition & Peace":        19,
}


def upload_image(image_path, filename):
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        upload_headers = {
            "Authorization":       f"Basic {token}",
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type":        "image/png",
        }

        response = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media",
            headers=upload_headers,
            data=image_data,
            timeout=30,
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
    tag_ids = []
    for tag_name in tag_names:
        try:
            response = requests.get(
                f"{WP_URL}/wp-json/wp/v2/tags?search={tag_name}",
                headers=HEADERS,
                timeout=10,
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
                timeout=10,
            )
            if response.status_code == 201:
                tag_ids.append(response.json()["id"])

        except Exception as e:
            print(f"[WP] Tag error for '{tag_name}': {e}")

    return tag_ids


def format_content(article_text, subtitle=""):
    article_text = re.sub(
        r'\*?Inspired by a real story shared anonymously online\.\*?',
        '', article_text
    ).strip()

    html_parts = []

    if subtitle:
        html_parts.append(
            f"<!-- wp:paragraph {{\"className\":\"article-subtitle\"}} -->"
            f"<p class=\"article-subtitle\"><em>{subtitle}</em></p>"
            f"<!-- /wp:paragraph -->"
        )

    paragraphs = article_text.strip().split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if para == "---":
            html_parts.append(
                "<!-- wp:separator -->"
                "<hr class=\"wp-block-separator\"/>"
                "<!-- /wp:separator -->"
            )
        else:
            lines = para.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line = re.sub(r'\*(.*?)\*', r'<em>\1</em>', line)
                line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                html_parts.append(
                    f"<!-- wp:paragraph --><p>{line}</p><!-- /wp:paragraph -->"
                )

    html_parts.append(
        "<!-- wp:separator --><hr class=\"wp-block-separator\"/><!-- /wp:separator -->"
    )
    html_parts.append(
        "<!-- wp:paragraph --><p><em>Inspired by a real story shared anonymously online.</em></p><!-- /wp:paragraph -->"
    )

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

    tag_ids      = get_or_create_tags(article_data.get("tags", []))
    subtitle     = article_data.get("subtitle", "")
    content_html = format_content(article_data["article"], subtitle)

    post_data = {
        "title":      article_data["seo_title"],
        "content":    content_html,
        "slug":       article_data["slug"],
        "status":     "publish",
        "categories": [category_id] if category_id else [],
        "tags":       tag_ids,
        "meta": {
            "rank_math_title":         article_data["seo_title"],
            "rank_math_description":   article_data["meta_description"],
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
                timeout=30,
            )

            if response.status_code == 201:
                post     = response.json()
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
        "article":          "She spent twelve years in the same building.\n\n---\n\nWhat do you do when okay is the only answer you get?",
        "seo_title":        "She Quit After 12 Years and Felt Nothing",
        "subtitle":         "Why Leaving a Job You Hate Does Not Always Feel Like Freedom",
        "meta_description": "She handed in her notice after twelve years. She expected relief. If you have ever gotten what you wanted and felt nothing, this one is for you.",
        "focus_keyword":    "quitting job feeling empty",
        "slug":             "quit-after-twelve-years-felt-nothing",
        "tags":             ["burnout", "leaving job", "career burnout"],
    }

    result = publish_post(test_article, "Burnout & Exhaustion", None, "2026-06-13-test")
    if result:
        print(f"\n[WP] Success: {result}")
    else:
        print(f"\n[WP] Failed")
