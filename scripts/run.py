"""
run.py — Main pipeline orchestrator for Hermes
Runs daily: scrape → write → image → pin → publish → log
"""

import json
import os
import sys
from datetime import date
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

from scraper import scrape
from writer import generate_article
from image_gen import generate_image, get_fallback_image
from pin_gen import generate_pin
from wp_publish import publish_post
from pinterest import post_pin

STATE_FILE = "/home/hermes/state.json"
LOG_DIR = "/home/hermes/logs"

PILLAR_NAMES = {
    1: "Burnout & Exhaustion",
    2: "Relationships & Regret",
    3: "Family & Belonging",
    4: "Forgiveness",
    5: "Faith & Doubt",
    6: "Money & Enough",
    7: "Friendship & Loneliness",
    8: "Mid-life Drift",
    9: "Ambition & Peace",
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "last_run": None,
        "next_pillar": 1,
        "posts_published": 0,
        "pillar_rotation": [1, 2, 3, 4, 5, 6, 7, 8, 9],
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def next_pillar(state):
    current = state["next_pillar"]
    rotation = state["pillar_rotation"]
    current_index = rotation.index(current)
    next_index = (current_index + 1) % len(rotation)
    state["next_pillar"] = rotation[next_index]
    return current


def write_log(today, log_data):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = f"{LOG_DIR}/{today}.json"
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)
    print(f"\n[RUN] Log saved: {log_path}")


def run():
    today = date.today().isoformat()
    print(f"\n{'='*50}")
    print(f"[RUN] Hermes starting — {today}")
    print(f"{'='*50}")

    log = {
        "date": today,
        "status": "started",
        "pillar": None,
        "story_url": None,
        "article_title": None,
        "post_url": None,
        "image_path": None,
        "pin_path": None,
        "pinterest_url": None,
        "errors": [],
    }

    # Load state
    state = load_state()
    pillar_number = next_pillar(state)
    pillar_name = PILLAR_NAMES[pillar_number]
    log["pillar"] = pillar_name

    print(f"[RUN] Today's pillar: {pillar_name} (#{pillar_number})")

    # STEP 1 — SCRAPE
    print(f"\n[RUN] Step 1: Scraping story...")
    story = scrape(pillar_number)
    if not story:
        log["status"] = "failed"
        log["errors"].append("No story found")
        write_log(today, log)
        print("[RUN] No story found — exiting")
        return False

    log["story_url"] = story.get("url", "")
    print(f"[RUN] Story found: {story['title'][:60]}")

    # STEP 2 — GENERATE ARTICLE
    print(f"\n[RUN] Step 2: Generating article...")
    article_data = generate_article(story, pillar_name)
    if not article_data:
        log["status"] = "failed"
        log["errors"].append("Article generation failed")
        write_log(today, log)
        print("[RUN] Article generation failed — exiting")
        return False

    log["article_title"] = article_data["seo_title"]
    print(f"[RUN] Article ready: {article_data['seo_title']}")

    # STEP 3 — GENERATE IMAGE
    print(f"\n[RUN] Step 3: Generating image...")
    image_path = generate_image(pillar_number, today)
    if not image_path:
        image_path = get_fallback_image(pillar_number)
        if image_path:
            print(f"[RUN] Using fallback image")
            log["errors"].append("DALL-E failed — used fallback image")
        else:
            print(f"[RUN] No image available — continuing without image")
            log["errors"].append("No image available")

    log["image_path"] = image_path

    # STEP 4 — GENERATE PIN
    print(f"\n[RUN] Step 4: Generating Pinterest pin...")
    pin_path = None
    if image_path:
        pin_path = generate_pin(article_data["seo_title"], image_path, today)
    log["pin_path"] = pin_path

    # STEP 5 — PUBLISH TO WORDPRESS
    print(f"\n[RUN] Step 5: Publishing to WordPress...")
    post_url = publish_post(article_data, pillar_name, image_path, today)
    if not post_url:
        log["status"] = "failed"
        log["errors"].append("WordPress publish failed")
        write_log(today, log)
        print("[RUN] WordPress publish failed — exiting")
        return False

    log["post_url"] = post_url
    print(f"[RUN] Post live: {post_url}")

    # STEP 6 — POST TO PINTEREST
    print(f"\n[RUN] Step 6: Posting to Pinterest...")
    if pin_path and os.path.exists(pin_path):
        pinterest_url = post_pin(
            article_data["seo_title"],
            article_data["meta_description"],
            post_url,
            pin_path,
            pillar_name,
        )
        if pinterest_url:
            log["pinterest_url"] = pinterest_url
        else:
            log["errors"].append("Pinterest post failed — will retry next run")
            print("[RUN] Pinterest failed — logged for retry")
    else:
        print("[RUN] No pin image — skipping Pinterest")
        log["errors"].append("No pin image — Pinterest skipped")

    # STEP 7 — UPDATE STATE AND LOG
    state["last_run"] = today
    state["posts_published"] = state.get("posts_published", 0) + 1
    save_state(state)

    log["status"] = "success"
    write_log(today, log)

    print(f"\n{'='*50}")
    print(f"[RUN] Hermes complete!")
    print(f"[RUN] Article: {article_data['seo_title']}")
    print(f"[RUN] Post: {post_url}")
    print(f"[RUN] Posts published total: {state['posts_published']}")
    print(f"{'='*50}")

    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
