"""
run.py — Hermes orchestrator
Runs the full daily pipeline: scrape → write → image → pin → publish → pinterest
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, "/home/hermes/scripts")

from scraper import scrape
from writer import generate_article
from image_gen import generate_image
from pin_gen import generate_pin
from wp_publish import publish_post, fetch_all_titles
from pinterest import post_pin

STATE_FILE = "/home/hermes/state.json"
LOG_DIR = "/home/hermes/logs"
MAX_STORY_ATTEMPTS = 3

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


def save_log(today, log_data):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = f"{LOG_DIR}/{today}.json"
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)
    print(f"[RUN] Log saved: {log_path}")


def main():
    today = date.today().isoformat()
    state = load_state()

    print("=" * 50)
    print(f"[RUN] Hermes starting — {today}")
    print("=" * 50)

    pillar_number = state.get("next_pillar", 1)
    pillar_name = PILLAR_NAMES.get(pillar_number, "Burnout & Exhaustion")
    print(f"[RUN] Today's pillar: {pillar_name} (#{pillar_number})")

    log = {
        "date": today,
        "pillar": pillar_name,
        "pillar_number": pillar_number,
        "steps": {},
        "story_attempts": 0,
    }

    # Step 2a: Fetch all existing post titles from WordPress for memory
    print(f"\n[RUN] Step 2a: Loading post memory from WordPress...")
    all_existing_posts = fetch_all_titles()
    log["steps"]["memory"] = f"{len(all_existing_posts)} posts loaded"

    # Steps 1 + 2b: Scrape and write — retry with fresh story if writer fails
    article_data = None
    tried_urls = []

    for attempt in range(1, MAX_STORY_ATTEMPTS + 1):
        print(f"\n[RUN] Step 1: Scraping story (attempt {attempt}/{MAX_STORY_ATTEMPTS})...")
        story = scrape(pillar_number)

        if not story:
            print("[RUN] No story found — aborting")
            log["steps"]["scrape"] = "failed"
            save_log(today, log)
            return

        # Skip stories we already tried
        if story["url"] in tried_urls:
            print(f"[RUN] Same story returned — skipping")
            continue

        tried_urls.append(story["url"])
        log["steps"][f"scrape_attempt_{attempt}"] = story["url"]
        log["story_attempts"] = attempt
        print(f"[RUN] Story found: {story['title'][:60]}")

        print(f"\n[RUN] Step 2b: Generating article (attempt {attempt}/{MAX_STORY_ATTEMPTS})...")
        article_data = generate_article(story, pillar_name, recent_posts=all_existing_posts)

        if article_data:
            print(f"[RUN] Article ready: {article_data['seo_title']}")
            log["steps"]["write"] = article_data["seo_title"]
            break
        else:
            print(f"[RUN] Article generation failed — trying a different story...")
            log["steps"][f"write_attempt_{attempt}"] = "failed"

    if not article_data:
        print("[RUN] All story attempts failed — aborting")
        log["steps"]["write"] = "failed after 3 attempts"
        save_log(today, log)
        return

    # Step 3: Generate image
    print(f"\n[RUN] Step 3: Generating image...")
    custom_prompt = article_data.get("image_prompt", "")
    image_path = generate_image(pillar_number, today, custom_prompt=custom_prompt if custom_prompt else None)
    log["steps"]["image"] = image_path or "failed"

    # Step 4: Generate Pinterest pin
    print(f"\n[RUN] Step 4: Generating Pinterest pin...")
    pin_path = None
    if image_path:
        pin_path = generate_pin(article_data["seo_title"], image_path, today)
        log["steps"]["pin"] = pin_path or "failed"

    # Step 5: Publish to WordPress
    print(f"\n[RUN] Step 5: Publishing to WordPress...")
    post_url = publish_post(article_data, pillar_name, image_path, today)
    if not post_url:
        print("[RUN] WordPress publish failed — aborting")
        log["steps"]["publish"] = "failed"
        save_log(today, log)
        return
    log["steps"]["publish"] = post_url
    print(f"[RUN] Post live: {post_url}")

    # Step 6: Post to Pinterest
    print(f"\n[RUN] Step 6: Posting to Pinterest...")
    pinterest_result = post_pin(
        article_title=article_data["seo_title"],
        meta_description=article_data["meta_description"],
        post_url=post_url,
        pin_image_path=pin_path,
        pillar_name=pillar_name,
    )
    if pinterest_result:
        log["steps"]["pinterest"] = pinterest_result
    else:
        log["steps"]["pinterest"] = "failed — retry when Standard access approved"
        print("[RUN] Pinterest failed — logged for retry")

    # Update state
    next_pillar = (pillar_number % 9) + 1
    state["last_run"] = today
    state["next_pillar"] = next_pillar
    state["posts_published"] = state.get("posts_published", 0) + 1
    save_state(state)

    save_log(today, log)

    print("\n" + "=" * 50)
    print(f"[RUN] Hermes complete!")
    print(f"[RUN] Article: {article_data['seo_title']}")
    print(f"[RUN] Post: {post_url}")
    print(f"[RUN] Story attempts: {log['story_attempts']}")
    print(f"[RUN] Posts published total: {state['posts_published']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
