import os
import requests
from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv("/home/hermes/.env")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
MUSIC_DIR = "/home/hermes/music"
os.makedirs(MUSIC_DIR, exist_ok=True)

PILLAR_MUSIC = {
    "Burnout":       "Slow minimal piano, tired and heavy, quiet ambient drone, melancholic undertone, loopable",
    "Relationships": "Soft acoustic guitar, melancholic, slow and longing, warm but sad, loopable",
    "Family":        "Gentle piano with soft strings, nostalgic, bittersweet, slow and intimate, loopable",
    "Forgiveness":   "Quiet ambient piano, slow, peaceful but heavy, a sense of letting go, loopable",
    "Faith":         "Sparse piano notes, reverberant, searching, quiet and uncertain, loopable",
    "Money":         "Minimal piano, understated, slightly restless, slow ambient undertone, loopable",
    "Friendship":    "Soft piano, isolated feeling, slow, warm but distant, loopable",
    "Midlife":       "Slow ambient piano, reflective, slightly adrift, warm undertone, loopable",
    "Ambition":      "Gentle piano, caught between tension and calm, slow and contemplative, loopable",
}

STYLE_SUFFIX = "Background music only, no dominant melody, suitable for narrated reflection video, 30 seconds"

CATEGORY_TO_PILLAR = {
    "Burnout & Exhaustion":    "Burnout",
    "Relationships & Regret":  "Relationships",
    "Family & Belonging":      "Family",
    "Forgiveness":             "Forgiveness",
    "Faith & Doubt":           "Faith",
    "Money & Enough":          "Money",
    "Friendship & Loneliness": "Friendship",
    "Mid-life Drift":          "Midlife",
    "Ambition & Peace":        "Ambition",
}


def generate_track(pillar_key):
    prompt      = f"{PILLAR_MUSIC[pillar_key]}. {STYLE_SUFFIX}"
    output_path = os.path.join(MUSIC_DIR, f"{pillar_key}.mp3")

    print(f"  Generating: {pillar_key}...")

    response = requests.post(
        "https://api.elevenlabs.io/v1/sound-generation",
        headers={
            "xi-api-key":   ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text":             prompt,
            "duration_seconds": 30,
            "prompt_influence": 0.4,
        },
    )

    if response.status_code != 200:
        raise Exception(f"ElevenLabs failed for {pillar_key}: {response.text}")

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"  Saved: {output_path}")
    return output_path


def get_music_for_video(category_name, video_duration_seconds, output_path):
    pillar_key = CATEGORY_TO_PILLAR.get(category_name)
    if not pillar_key:
        raise ValueError(f"Unknown category: {category_name}")

    track_path = os.path.join(MUSIC_DIR, f"{pillar_key}.mp3")
    if not os.path.exists(track_path):
        print(f"First time for {pillar_key} — generating music track...")
        generate_track(pillar_key)

    base         = AudioSegment.from_file(track_path)
    loops_needed = int((video_duration_seconds * 1000) / len(base)) + 2
    looped       = (base * loops_needed)[:int(video_duration_seconds * 1000)]
    looped       = looped.fade_in(3000).fade_out(5000)
    looped       = looped - 14

    looped.export(output_path, format="mp3", bitrate="192k")
    return output_path


if __name__ == "__main__":
    import sys

    if "--generate-all" in sys.argv:
        print("Generating all 9 pillar music tracks...\n")
        for key in PILLAR_MUSIC:
            generate_track(key)
        print(f"\nDone. All 9 tracks saved to {MUSIC_DIR}")

    elif "--generate" in sys.argv:
        idx        = sys.argv.index("--generate")
        pillar_key = sys.argv[idx + 1]
        generate_track(pillar_key)

    else:
        print("Usage:")
        print("  python3 music_gen.py --generate-all")
        print("  python3 music_gen.py --generate Burnout")
        print()
        print("Available pillars:")
        for k in PILLAR_MUSIC:
            print(f"  {k}")
