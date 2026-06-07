
"""
scraper.py — Medium RSS scraper for Hermes
Uses Medium tag RSS feeds — works from VPS IPs unlike Reddit.
"""

import requests
import time
import xml.etree.ElementTree as ET
import re

PILLAR_TAGS = {
    1: ["burnout", "work-life-balance", "overwork", "exhaustion"],
    2: ["relationships", "breakup", "regret", "heartbreak"],
    3: ["family", "belonging", "estrangement", "parenting"],
    4: ["forgiveness", "letting-go", "healing", "grief"],
    5: ["faith", "spirituality", "doubt", "religion"],
    6: ["money", "personal-finance", "enough", "financial-stress"],
    7: ["loneliness", "friendship", "isolation", "connection"],
    8: ["midlife", "identity", "self-discovery", "life-transitions"],
    9: ["ambition", "simplicity", "hustle-culture", "work-life-balance"],
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
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def clean_html(text):
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def fetch_medium_rss(tag):
    url = f"https://medium.com/feed/tag/{tag}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  Medium tag/{tag} — HTTP {response.status_code}")
        if response.status_code == 200:
            return response.text
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def parse_medium_rss(xml_text, tag):
    posts = []
    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return posts
        items = channel.findall("item")
        for item in items:
            title_el = item.find("title")
            desc_el = item.find("description")
            link_el = item.find("link")

            title = title_el.text if title_el is not None else ""
            body = clean_html(desc_el.text if desc_el is not None else "")
            url = link_el.text if link_el is not None else ""

            if len(body) < 150:
                continue

            posts.append({
                "title": title,
                "body": body[:3000],
                "url": url,
                "source": f"medium/tag/{tag}",
            })
    except Exception as e:
        print(f"  Parse error: {e}")
    return posts


def is_safe(post):
    text = (post.get("title", "") + " " + post.get("body", "")).lower()
    for keyword in SKIP_KEYWORDS:
        if keyword in text:
            return False
    return True


def score_post(post):
    score = 0
    text = post.get("body", "")
    score += min(len(text) / 100, 30)
    first_person = ["i ", "i've", "i was", "i am", "my ", "me ", "myself"]
    for fp in first_person:
        if fp in text.lower():
            score += 10
            break
    return score


def scrape(pillar_number):
    pillar_name = PILLAR_NAMES.get(pillar_number, "Unknown")
    tags = PILLAR_TAGS.get(pillar_number, [])

    print(f"\n[SCRAPER] Pillar {pillar_number}: {pillar_name}")

    candidates = []
    skipped = []

    for tag in tags:
        print(f"  Fetching Medium tag/{tag}...")
        xml = fetch_medium_rss(tag)
        time.sleep(1)

        if not xml:
            continue

        posts = parse_medium_rss(xml, tag)

        for post in posts:
            if not is_safe(post):
                skipped.append(post["url"])
                continue
            post["score"] = score_post(post)
            candidates.append(post)

    if not candidates:
        print(f"[SCRAPER] No candidates found for pillar {pillar_number}")
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    print(f"\n[SCRAPER] Best story:")
    print(f"  Title: {best['title'][:80]}")
    print(f"  Source: {best['source']}")
    print(f"  Score: {best['score']:.1f}")
    print(f"  Skipped: {len(skipped)} unsafe")

    return best


if __name__ == "__main__":
    result = scrape(1)
    if result:
        print("\n--- STORY PREVIEW ---")
        print(f"Title: {result['title']}")
        print(f"Body (first 300 chars): {result['body'][:300]}...")
