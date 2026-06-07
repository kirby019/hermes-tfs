"""
scraper.py — Medium RSS scraper for Hermes
Fetches stories from Medium RSS feeds matching today's pillar.
No API key needed — uses Medium's public RSS feeds.
"""

import requests
import xml.etree.ElementTree as ET
import time
import re
import html

PILLAR_TAGS = {
    1: ["burnout", "work-life-balance", "career", "workplace"],
    2: ["relationships", "heartbreak", "divorce", "love"],
    3: ["family", "parenting", "belonging", "home"],
    4: ["forgiveness", "healing", "letting-go", "grief"],
    5: ["faith", "spirituality", "religion", "doubt"],
    6: ["money", "personal-finance", "frugality", "debt"],
    7: ["loneliness", "friendship", "social-anxiety", "isolation"],
    8: ["midlife", "identity", "self-discovery", "aging"],
    9: ["ambition", "success", "hustle", "simplicity"],
}

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

SKIP_KEYWORDS = [
    "suicide", "suicidal", "kill myself", "end my life", "self harm",
    "self-harm", "cutting myself", "overdose", "abuse minor", "child abuse",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TheFlawedSeeker/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def fetch_medium_rss(tag):
    """Fetch posts from Medium RSS feed for a tag."""
    url = f"https://medium.com/feed/tag/{tag}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"  HTTP {response.status_code} for tag: {tag}")
            return []

        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        posts = []

        for item in items:
            title_el = item.find("title")
            desc_el = item.find("description")
            link_el = item.find("link")

            if title_el is None or desc_el is None or link_el is None:
                continue

            title = html.unescape(title_el.text or "")
            raw_desc = desc_el.text or ""

            # Strip HTML tags from description
            body = re.sub(r"<[^>]+>", " ", raw_desc)
            body = html.unescape(body)
            body = re.sub(r"\s+", " ", body).strip()

            link = link_el.text or ""

            if len(body) < 150:
                continue

            posts.append({
                "title": title,
                "body": body,
                "url": link,
                "tag": tag,
            })

        return posts

    except ET.ParseError as e:
        print(f"  XML parse error for tag {tag}: {e}")
        return []
    except Exception as e:
        print(f"  Error fetching tag {tag}: {e}")
        return []


def is_safe(post):
    """Return False if post contains crisis/harmful content."""
    text = (post.get("title", "") + " " + post.get("body", "")).lower()
    for keyword in SKIP_KEYWORDS:
        if keyword in text:
            return False
    return True


def score_post(post):
    """Score a post by narrative quality and length."""
    score = 0
    body = post.get("body", "")

    # Length score (max 30pts)
    score += min(len(body) / 100, 30)

    # First-person narrative boost
    first_person = ["i ", "i've", "i was", "i am", "my ", "me ", "myself"]
    for fp in first_person:
        if fp in body.lower():
            score += 15
            break

    # Personal story indicators
    story_words = ["years", "months", "decided", "felt", "realized", "thought", "knew"]
    for word in story_words:
        if word in body.lower():
            score += 2

    return score


def scrape(pillar_number):
    """
    Main scrape function.
    Returns the best candidate story for the given pillar.
    """
    pillar_name = PILLAR_NAMES.get(pillar_number, "Unknown")
    tags = PILLAR_TAGS.get(pillar_number, [])

    print(f"\n[SCRAPER] Pillar {pillar_number}: {pillar_name}")
    print(f"[SCRAPER] Searching Medium tags: {', '.join(tags)}")

    candidates = []
    skipped = []

    for tag in tags:
        print(f"  Fetching medium.com/tag/{tag}...")
        posts = fetch_medium_rss(tag)
        time.sleep(1)

        for post in posts:
            if not is_safe(post):
                skipped.append(post["url"])
                print(f"  [SKIP] Safety filter: {post['title'][:60]}")
                continue

            post["score"] = score_post(post)
            candidates.append(post)

    if not candidates:
        print(f"[SCRAPER] No candidates found for pillar {pillar_number}")
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    print(f"\n[SCRAPER] Best story found:")
    print(f"  Title: {best['title'][:80]}")
    print(f"  Tag: {best['tag']}")
    print(f"  URL: {best['url']}")
    print(f"  Score: {best['score']:.1f}")
    print(f"  Body length: {len(best['body'])} chars")
    print(f"  Skipped {len(skipped)} unsafe stories")

    return best


if __name__ == "__main__":
    result = scrape(1)
    if result:
        print("\n--- STORY PREVIEW ---")
        print(f"Title: {result['title']}")
        print(f"Body (first 400 chars): {result['body'][:400]}...")
