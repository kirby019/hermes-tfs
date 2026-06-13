import os
import json
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CATEGORY_TAGS = {
    "Burnout & Exhaustion":    ["burnout", "exhaustion", "work life balance", "overworked", "mental health"],
    "Relationships & Regret":  ["relationships", "regret", "love", "breakup", "emotional healing"],
    "Family & Belonging":      ["family", "belonging", "home", "parents", "childhood"],
    "Forgiveness":             ["forgiveness", "letting go", "healing", "moving on", "self forgiveness"],
    "Faith & Doubt":           ["faith", "doubt", "spirituality", "belief", "purpose"],
    "Money & Enough":          ["money", "enough", "wealth", "financial freedom", "ambition"],
    "Friendship & Loneliness": ["friendship", "loneliness", "connection", "isolation", "belonging"],
    "Mid-life Drift":          ["midlife", "purpose", "identity", "who am i", "lost"],
    "Ambition & Peace":        ["ambition", "peace", "success", "hustle culture", "slow living"],
}

BASE_TAGS = [
    "theflawedseeker", "reflection", "daily reflection",
    "personal growth", "mental health", "emotional wellness",
    "short story", "human stories", "life lessons",
]


def get_youtube_client():
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
        client_id=os.getenv("YOUTUBE_CLIENT_ID"),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def build_description(article_title, article_url, pillar_name):
    return f"""{article_title}

A daily reflection from The Flawed Seeker.

Real stories. Universal truths. No easy answers. Just the right questions.

Read the full reflection: {article_url}

New reflection every day.
theflawedseeker.com

#TheFlawedSeeker #Reflection #{''.join(w.capitalize() for w in pillar_name.split()[:2])} #MentalHealth #PersonalGrowth"""


def upload_video(video_path, article_title, article_url, pillar_name,
                 thumbnail_path=None, publish_at=None):
    print(f"Uploading: {os.path.basename(video_path)}")

    youtube = get_youtube_client()

    tags = BASE_TAGS + CATEGORY_TAGS.get(pillar_name, [])

    description = build_description(article_title, article_url, pillar_name)

    body = {
        "snippet": {
            "title": article_title,
            "description": description,
            "tags": tags,
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public" if not publish_at else "private",
            "selfDeclaredMadeForKids": False,
            "publishAt": publish_at,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"  Uploading... {pct}%")
        except Exception as e:
            retry += 1
            if retry > 3:
                raise
            print(f"  Retrying ({retry}/3)...")
            time.sleep(5)

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Uploaded: {video_url}")

    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/png"),
            ).execute()
            print("Thumbnail set.")
        except Exception as e:
            print(f"Thumbnail failed (non-critical): {e}")

    return video_id, video_url


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: python3 youtube_upload.py <video.mp4> <article_title> <article_url> <pillar> [thumbnail.png]")
        sys.exit(1)

    video_path    = sys.argv[1]
    article_title = sys.argv[2]
    article_url   = sys.argv[3]
    pillar_name   = sys.argv[4]
    thumbnail     = sys.argv[5] if len(sys.argv) > 5 else None

    video_id, url = upload_video(video_path, article_title, article_url, pillar_name, thumbnail)
    print(f"\nDone. Video ID: {video_id}")
    print(f"URL: {url}")
