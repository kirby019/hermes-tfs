"""
image_gen.py — Image generator for Hermes
Generates a unique illustration for each article using gpt-image-1.
The article's opening scene drives the image — style varies randomly.
"""

import openai
import os
import re
import base64
import random
from datetime import date
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

CLIENT = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ART_STYLES = [
    "watercolor illustration, soft washes, gentle bleeds, painterly",
    "2D flat vector illustration, clean lines, bold shapes, minimal",
    "ink sketch, loose expressive linework, editorial illustration style",
    "gouache painting, flat opaque colors, graphic and bold",
    "pencil drawing, soft graphite shading, hand-drawn feel",
    "linocut print style, high contrast, textured, graphic",
    "loose brush painting, gestural marks, ink and wash",
]

CONSTANT_STYLE = "no photorealism, no 3D rendering, no real people, no photographs, no text in image, illustrated style only, warm cream and navy color palette, literary journal aesthetic, generous white space"


def extract_opening_scene(article_text):
    """Pull the first paragraph — the most visual part of the article."""
    text = re.sub(r'\*?Inspired by a real story shared anonymously online\.\*?', '', article_text).strip()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if paragraphs:
        scene = paragraphs[0]
        if len(scene) > 200:
            trimmed = scene[:200]
            last_period = max(trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'))
            if last_period > 80:
                scene = trimmed[:last_period + 1]
            else:
                scene = trimmed
        return scene
    return ""


def generate_image(pillar_number, today=None, article_title=None, article_text=None):
    """
    Generate an illustration for today's article.
    Uses the article's opening scene as the image prompt.
    Returns path to saved image, or None if failed.
    """
    if today is None:
        today = date.today().isoformat()

    output_path = f"/home/hermes/images/generated/{today}.png"

    if os.path.exists(output_path):
        print(f"[IMAGE] Image already exists for today: {output_path}")
        return output_path

    art_style = random.choice(ART_STYLES)

    if article_text:
        scene = extract_opening_scene(article_text)
        if scene:
            prompt = f"A symbolic still life inspired by this story: \"{scene}\". Style: {art_style}. {CONSTANT_STYLE}."
        elif article_title:
            prompt = f"A symbolic still life for a story titled: '{article_title}'. Style: {art_style}. {CONSTANT_STYLE}."
        else:
            prompt = f"A symbolic still life. Style: {art_style}. {CONSTANT_STYLE}."
    elif article_title:
        prompt = f"A symbolic still life for a story titled: '{article_title}'. Style: {art_style}. {CONSTANT_STYLE}."
    else:
        prompt = f"A symbolic still life. Style: {art_style}. {CONSTANT_STYLE}."

    print(f"\n[IMAGE] Generating image for: {article_title or 'pillar ' + str(pillar_number)}")
    print(f"[IMAGE] Style: {art_style}")
    print(f"[IMAGE] Prompt: {prompt[:120]}...")

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
    """Return a default pillar image if generation fails."""
    fallback = f"/home/hermes/images/generated/fallback-{pillar_number}.png"
    if os.path.exists(fallback):
        return fallback
    return None


if __name__ == "__main__":
    test_article = """She spent twelve years in the same building. Same desk, same login, same coffee machine that broke every third Tuesday. Then yesterday she submitted the email. Her hands shook. She expected relief. She expected freedom. Instead she sat in her car for forty-five minutes and stared at the steering wheel.

Her manager said okay.

That was it."""
    result = generate_image(1, article_title="She Quit After 12 Years and Felt Nothing", article_text=test_article)
    if result:
        print(f"\n[IMAGE] Success: {result}")
    else:
        print(f"\n[IMAGE] Failed")
