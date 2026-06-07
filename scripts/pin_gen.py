"""
pin_gen.py — Pinterest pin graphic generator for Hermes
Creates a 1000x1500px pin with article title + branding overlay.
Uses Pillow for image composition.
"""

from PIL import Image, ImageDraw, ImageFont
import os
from datetime import date


FONT_PATH = "/home/hermes/fonts/PlayfairDisplay-Bold.ttf"
PIN_WIDTH = 1000
PIN_HEIGHT = 1500
CREAM = (245, 240, 232)
NAVY = (44, 58, 82)


def wrap_text(text, font, draw, max_width):
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] > max_width:
            if len(current_line) > 1:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(test_line)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def generate_pin(article_title, image_path, today=None):
    """
    Generate a Pinterest pin graphic.
    Returns path to saved pin, or None if failed.
    """
    if today is None:
        today = date.today().isoformat()

    output_path = f"/home/hermes/images/pins/{today}.png"

    print(f"\n[PIN] Generating Pinterest pin")
    print(f"[PIN] Title: {article_title[:60]}")

    try:
        # Create base canvas
        canvas = Image.new("RGB", (PIN_WIDTH, PIN_HEIGHT), CREAM)

        # Load and overlay article illustration at 25% opacity
        if image_path and os.path.exists(image_path):
            illustration = Image.open(image_path).convert("RGBA")
            illustration = illustration.resize((PIN_WIDTH, PIN_WIDTH))

            # Place illustration in upper portion
            bg = Image.new("RGBA", (PIN_WIDTH, PIN_HEIGHT), (*CREAM, 255))
            illustration_faded = Image.new("RGBA", illustration.size, (0, 0, 0, 0))
            illustration_faded = Image.blend(
                Image.new("RGBA", illustration.size, (*CREAM, 255)),
                illustration,
                alpha=0.30
            )
            bg.paste(illustration_faded, (0, 100), illustration_faded)
            canvas = bg.convert("RGB")

        draw = ImageDraw.Draw(canvas)

        # Load fonts
        try:
            title_font = ImageFont.truetype(FONT_PATH, 72)
            brand_font = ImageFont.truetype(FONT_PATH, 28)
            url_font = ImageFont.truetype(FONT_PATH, 22)
        except Exception:
            title_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()
            url_font = ImageFont.load_default()

        # Draw title — centered, wrapped
        padding = 80
        max_text_width = PIN_WIDTH - (padding * 2)
        lines = wrap_text(article_title, title_font, draw, max_text_width)

        # Calculate total text block height
        line_height = 85
        total_text_height = len(lines) * line_height
        text_start_y = (PIN_HEIGHT - total_text_height) // 2 - 50

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            x = (PIN_WIDTH - text_width) // 2
            y = text_start_y + (i * line_height)
            draw.text((x, y), line, font=title_font, fill=NAVY)

        # Draw horizontal rule above branding
        rule_y = PIN_HEIGHT - 140
        draw.line([(padding, rule_y), (PIN_WIDTH - padding, rule_y)], fill=NAVY, width=1)

        # Draw branding
        brand_text = "THE FLAWED SEEKER"
        bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
        brand_width = bbox[2] - bbox[0]
        brand_x = (PIN_WIDTH - brand_width) // 2
        draw.text((brand_x, PIN_HEIGHT - 120), brand_text, font=brand_font, fill=NAVY)

        # Draw URL
        url_text = "theflawedseeker.com"
        bbox = draw.textbbox((0, 0), url_text, font=url_font)
        url_width = bbox[2] - bbox[0]
        url_x = (PIN_WIDTH - url_width) // 2
        draw.text((url_x, PIN_HEIGHT - 75), url_text, font=url_font, fill=NAVY)

        canvas.save(output_path, "PNG")
        print(f"[PIN] Saved to {output_path}")
        return output_path

    except Exception as e:
        print(f"[PIN] Error: {e}")
        return None


if __name__ == "__main__":
    # Test with today's generated image
    today = date.today().isoformat()
    test_image = f"/home/hermes/images/generated/{today}.png"

    result = generate_pin(
        "She Quit After 12 Years and Felt Nothing",
        test_image
    )

    if result:
        print(f"\n[PIN] Success: {result}")
    else:
        print(f"\n[PIN] Failed")
