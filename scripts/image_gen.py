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

PILLAR_OBJECTS = {
    1: "a single wilting botanical stem in a simple vase, leaves beginning to curl downward",
    2: "two chairs facing slightly away from each other, one tipped forward as if recently vacated",
    3: "a dining table with one chair pulled slightly apart from the others, a single candle",
    4: "an open window with light coming through, a folded piece of paper resting on the sill",
    5: "a single lit candle against a dark background, soft halo of warm light, minimal",
    6: "a delicate balance scale tipped slightly to one side, botanical elements on each tray",
    7: "two teacups on a surface, one full and steaming, one empty and cold, soft morning light",
    8: "a vintage compass with its needle pointing slightly off-center, botanical frame, soft navy tones",
    9: "a winding path leading up a gentle hill that disappears into soft mist, minimal botanical border",
}

BASE_PROMPT = "Flat vector illustration, warm cream background, navy and muted gold accents, {object}, botanical minimalist style, no people, no faces, no text, soft edges, literary journal aesthetic, generous white space"


def generate_image(pillar_number, today=None):
    if today is None:
        today = date.today().isoformat()

    output_path = f"/home/hermes/images/generated/{today}.png"

    if os.path.exists(output_path):
        print(f"[IMAGE] Image already exists for today: {output_path}")
        return output_path

    pillar_object = PILLAR_OBJECTS.get(pillar_number, PILLAR_OBJECTS[1])
    prompt = BASE_PROMPT.format(object=pillar_object)

    print(f"\n[IMAGE] Generating image for pillar {pillar_number}")
    print(f"[IMAGE] Prompt: {prompt[:80]}...")

    try:
        response = CLIENT.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            quality="medium",
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
    result = generate_image(1)
    if result:
        print(f"\n[IMAGE] Success: {result}")
    else:
        print(f"\n[IMAGE] Failed")
