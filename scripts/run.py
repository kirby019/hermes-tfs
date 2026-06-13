"""
run.py — Hermes daily pipeline
Runs once per day via cron. Scrapes a story, writes the article,
generates the image, publishes to WordPress, renders the YouTube video,
and uploads it — all in one shot.
"""

import json
import os
import sys
import traceback
from datetime import date

BASE_DIR    = "/home/hermes"
SCRIPTS_DIR = os.path.join(BASE_DIR, "repo/scripts")
STATE_FILE  = os.path.join(BASE_DIR, "state.json")
LOG_DIR     = os.path.join(BASE_DIR, "logs")

sys.path.insert(0, SCRIPTS_DIR)

from scraper         import scrape, PILLAR_NAMES
from writer          import generate_article
from image_gen       import generate_image, get_fallback_image
from wp_publish      import publish_post
from video_script    import generate_video_script, save_script
from tts_gen         import generate_voiceover
from music_gen       import get_music_for_video
from video_assembler import make_video
from youtube_upload  import upload_video

DEFAULT_STATE = {
    "last_run": None,
    "next_pillar": 1,
    "posts_published": 0,
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return DEFAULT_STATE.copy()


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def advance_pillar(state):
    current = state.get("next_pillar", 1)
    state["next_pillar"] = (current % 9) + 1
    return state


def write_log(today, log):
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"{today}.json")
    with open(path, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"[LOG] {path}")


def abort(state, log, today, post_url, reason):
    print(f"\n[ABORT] {reason}")
    log["errors"].append(reason)
    state = advance_pillar(state)
    state["last_run"] = today
    state["posts_published"] = state.get("posts_published", 0) + (1 if post_url else 0)
    save_state(state)
    write_log(today, log)
    sys.exit(1)


def main():
    today = date.today().isoformat()
    print(f"\n{'='*60}\nHERMES — {today}\n{'='*60}\n")

    state       = load_state()
    pillar_num  = state.get("next_pillar", 1)
    pillar_name = PILLAR_NAMES.get(pillar_num, "Burnout & Exhaustion")
    post_url    = ""

    log = {"date": today, "pillar": pillar_name, "steps": {}, "errors": []}
    print(f"[PIPELINE] Pillar {pillar_num}: {pillar_name}\n")

    # 1 — Scrape
    print("[1/9] Scraping story...")
    try:
        candidates = scrape(pillar_num)
        if not candidates:
            abort(state, log, today, post_url, "No suitable stories found.")
        if isinstance(candidates, dict):
            candidates = [candidates]
        log["steps"]["scrape"] = "ok"
        print(f"[SCRAPE] {len(candidates)} candidates ready")
    except Exception as e:
        log["steps"]["scrape"] = "error"
        abort(state, log, today, post_url, f"scrape: {e}")

    # 2 — Generate article (try each candidate until one passes)
    print("\n[2/9] Generating article...")
    article_data = None
    story = None
    for i, candidate in enumerate(candidates):
        print(f"[WRITER] Trying candidate {i+1}/{len(candidates)}: {candidate['title'][:60]}")
        try:
            result = generate_article(candidate, pillar_name)
            if result:
                article_data = result
                story = candidate
                break
        except Exception as e:
            print(f"[WRITER] Candidate {i+1} error: {e}")

    if not article_data:
        abort(state, log, today, post_url, "All candidates failed article generation.")
    log["steps"]["article"] = "ok"
    log["story_url"] = story.get("url", "")
    log["article_title"] = article_data.get("seo_title", "")
    print(f"[WRITER] {article_data['seo_title']}")

    # 3 — Generate image
    print("\n[3/9] Generating image...")
    try:
        image_path = generate_image(pillar_num, today)
        if not image_path:
            image_path = get_fallback_image(pillar_num)
            log["steps"]["image"] = "fallback"
        else:
            log["steps"]["image"] = "ok"
        log["image_path"] = image_path or ""
        print(f"[IMAGE] {image_path}")
    except Exception as e:
        image_path = get_fallback_image(pillar_num)
        log["errors"].append(f"image_gen: {e}")
        log["steps"]["image"] = "fallback"
        log["image_path"] = image_path or ""
        print(f"[IMAGE] Fallback after error: {e}")

    # 4 — Publish to WordPress
    print("\n[4/9] Publishing to WordPress...")
    try:
        post_url = publish_post(article_data, pillar_name, image_path, today) or ""
        if post_url:
            log["steps"]["wordpress"] = "ok"
            log["post_url"] = post_url
            print(f"[WP] {post_url}")
        else:
            log["steps"]["wordpress"] = "failed"
            log["errors"].append("WordPress publish failed — video pipeline continuing.")
            print("[WP] Publish failed. Continuing with video pipeline.")
    except Exception as e:
        log["steps"]["wordpress"] = "error"
        log["errors"].append(f"wordpress: {e}")
        print(f"[WP] ERROR (continuing): {e}")

    # 5 — Generate video script
    print("\n[5/9] Generating video script...")
    script_dir  = os.path.join(BASE_DIR, "video_scripts")
    script_path = os.path.join(script_dir, f"{today}.json")
    os.makedirs(script_dir, exist_ok=True)
    try:
        script_text = generate_video_script(
            article_data["seo_title"],
            article_data["article"],
            pillar_name,
        )
        save_script(script_text, script_path)
        log["steps"]["video_script"] = "ok"
        print(f"[SCRIPT] {script_path}")
    except Exception as e:
        log["steps"]["video_script"] = "error"
        abort(state, log, today, post_url, f"video_script: {e}")

    # 6 — TTS voiceover
    print("\n[6/9] Generating voiceover...")
    tts_dir  = os.path.join(BASE_DIR, "tts")
    tts_path = os.path.join(tts_dir, f"{today}.mp3")
    os.makedirs(tts_dir, exist_ok=True)
    try:
        _, voice_duration = generate_voiceover(script_path, tts_path)
        log["steps"]["tts"] = "ok"
        log["voice_duration_s"] = round(voice_duration)
        print(f"[TTS] {tts_path}  ({voice_duration:.0f}s)")
    except Exception as e:
        log["steps"]["tts"] = "error"
        abort(state, log, today, post_url, f"tts: {e}")

    # 7 — Background music
    print("\n[7/9] Getting background music...")
    music_path = os.path.join(tts_dir, f"{today}_music.mp3")
    try:
        music_out = get_music_for_video(pillar_name, voice_duration, music_path)
        log["steps"]["music"] = "ok"
        print(f"[MUSIC] {music_out}")
    except Exception as e:
        log["steps"]["music"] = "error"
        abort(state, log, today, post_url, f"music: {e}")

    # 8 — Render video
    print("\n[8/9] Rendering video...")
    video_dir  = os.path.join(BASE_DIR, "videos")
    video_path = os.path.join(video_dir, f"{today}.mp4")
    os.makedirs(video_dir, exist_ok=True)
    try:
        make_video(
            script_path    = script_path,
            voiceover_path = tts_path,
            music_path     = music_out,
            image_path     = image_path,
            output_path    = video_path,
        )
        log["steps"]["video"] = "ok"
        log["video_path"] = video_path
        print(f"[VIDEO] {video_path}")
    except Exception as e:
        traceback.print_exc()
        log["steps"]["video"] = "error"
        abort(state, log, today, post_url, f"video: {e}")

    # 9 — Upload to YouTube
    print("\n[9/9] Uploading to YouTube...")
    try:
        video_id, youtube_url = upload_video(
            video_path    = video_path,
            article_title = article_data["seo_title"],
            article_url   = post_url,
            pillar_name   = pillar_name,
            thumbnail_path= image_path,
        )
        log["steps"]["youtube"] = "ok"
        log["youtube_url"] = youtube_url
        print(f"[YOUTUBE] {youtube_url}")
    except Exception as e:
        log["steps"]["youtube"] = "error"
        log["errors"].append(f"youtube: {e}")
        print(f"[YOUTUBE] ERROR (non-fatal): {e}")

    # Advance pillar and save state
    state = advance_pillar(state)
    state["last_run"] = today
    state["posts_published"] = state.get("posts_published", 0) + (1 if post_url else 0)
    save_state(state)
    write_log(today, log)

    print(f"\n{'='*60}\nDONE — {today}")
    if log["errors"]:
        print(f"Non-fatal errors ({len(log['errors'])}):")
        for e in log["errors"]:
            print(f"  • {e}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
