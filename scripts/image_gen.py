"""
image_gen.py — Image generator for Hermes
Generates a unique illustration for each article using gpt-image-1.
"""

import openai
import os
import base64
from datetime import date
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

CLIENT = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PILLAR_STYLE = {
    1: "wilting botanical elements, objects mid-fall or fading, warm ochre and brown tones",
    2: "empty chairs or spaces, objects left behind, quiet domestic interiors, cool blues",
    3: "family objects, dining or gathering spaces, a single empty seat, soft warm light",
    4: "open windows, folded letters, light breaking through a gap, soft morning tones",
    5: "a single candle or small flame, dark backgrounds, soft halos of light, navy tones",
    6: "a balance scale, measured objects, careful arrangements, muted earth tones",
    7: "two objects close but separate, one full and one empty, morning light, quiet rooms",
    8: "a compass or watch, half-open doors, paths diverging, soft mist and navy blues",
    9: "a winding path, a hilltop in mist, objects mid-journey, soft gold and sage tones",
}

BASE_STYLE = "flat vector illustration, warm cream background, navy and muted gold accents, botanical minimalist style, no people, no faces, no text, soft edges, literary journal aesthetic, generous white space"


def generate_image(pillar_number, today=None, article_title=None):
    if today is None:
        today = date.today().isoformat()

    output_path = f"/home/hermes/images/generated/{today}.png"

    if os.path.exists(output_path):
        print(f"[IMAGE] Image already exists for today: {output_path}")
        return output_path

    style = PILLAR_STYLE.get(pillar_number, PILLAR_STYLE[1])

    if article_title:
        prompt = f"A symbolic still life for a story titled: '{article_title}'. Visual mood: {style}. {BASE_STYLE}."
    else:
        prompt = f"A symbolic still life. Visual mood: {style}. {BASE_STYLE}."

    print(f"\n[IMAGE] Generating image for: {article_title or 'pillar ' + str(pillar_number)}")
    print(f"[IMAGE] Prompt: {prompt[:100]}...")

    try:
        response = CLIENT.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        image_data = base64.b64decode(response.data[0].b64_json)
        with open(output_path, "wb") as f:
            f.write(image_data)
        print(f"[IMAGE] Saved to {output_path}")
        return output_path

    except Exception as e:
        print(f"[IMAGE] Error: {e}")
        return None


def get_fallback_image(pillar_number):
    fallback = f"/home/hermes/images/generated/fallback-{pillar_number}.png"
    if os.path.exists(fallback):
        return fallback
    return None


if __name__ == "__main__":
    result = generate_image(1, article_title="He Quit After Twelve Years and Felt Nothing")
    if result:
        print(f"\n[IMAGE] Success: {result}")
    else:
        print(f"\n[IMAGE] Failed")
