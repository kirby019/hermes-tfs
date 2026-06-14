import os
import re
import json
import numpy as np
import openai
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from moviepy import VideoClip, AudioFileClip, CompositeAudioClip
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

W, H              = 1920, 1080
FPS               = 24
END_CARD_DURATION = 5.0

FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

BG    = (10, 8, 6)
CREAM = (240, 228, 210)
GOLD  = (184, 151, 90)


def get_font(size):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except:
            pass
    return ImageFont.load_default()


def ease_out(t):
    return 1 - (1 - min(max(t, 0), 1)) ** 3


def ease_in_out(t):
    t = min(max(t, 0), 1)
    return t * t * (3 - 2 * t)


def load_article_image(image_path):
    img = Image.open(image_path).convert("RGBA")
    scale = H / img.height
    new_w = int(img.width * scale)
    img = img.resize((new_w, H), Image.LANCZOS)
    if new_w > W:
        x = (new_w - W) // 2
        img = img.crop((x, 0, x + W, H))
    else:
        canvas = Image.new("RGBA", (W, H), (*BG, 255))
        x = (W - new_w) // 2
        canvas.paste(img, (x, 0))
        img = canvas
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(0.80)
    arr = np.array(rgb).astype(np.float32)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.05, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.88, 0, 255)
    return Image.fromarray(arr.astype(np.uint8)).convert("RGBA")


def ken_burns(base_img, t, duration, zoom_start=1.0, zoom_end=1.06, pan_x=0.0):
    p = ease_in_out(t / max(duration, 0.001))
    zoom = zoom_start + (zoom_end - zoom_start) * p
    nw = int(W * zoom)
    nh = int(H * zoom)
    resized = base_img.resize((nw, nh), Image.LANCZOS)
    ox = int((nw - W) * (0.5 + pan_x * 0.5))
    oy = (nh - H) // 2
    ox = max(0, min(ox, nw - W))
    oy = max(0, min(oy, nh - H))
    return resized.crop((ox, oy, ox + W, oy + H))


def vignette_overlay():
    cx, cy = W / 2, H / 2
    xs = np.linspace(0, W, W)
    ys = np.linspace(0, H, H)
    xx, yy = np.meshgrid(xs, ys)
    d = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / (cy * 1.2)) ** 2)
    alpha = np.clip(d * 0.9, 0, 1) ** 1.8
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    arr[:, :, 3] = (alpha * 200).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def bottom_gradient_overlay(height=220):
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    for i in range(height):
        alpha = int(150 * (i / height) ** 1.5)
        arr[H - height + i, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


VIGNETTE    = None
BOTTOM_GRAD = None


def get_vignette():
    global VIGNETTE
    if VIGNETTE is None:
        VIGNETTE = vignette_overlay()
    return VIGNETTE


def get_bottom_gradient():
    global BOTTOM_GRAD
    if BOTTOM_GRAD is None:
        BOTTOM_GRAD = bottom_gradient_overlay()
    return BOTTOM_GRAD


def dark_overlay(img, alpha=110):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, alpha))
    img.alpha_composite(overlay)


def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current = []
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for word in words:
        test = " ".join(current + [word])
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def draw_text_block(draw, lines, y_center, font, color, alpha, line_height=None):
    if line_height is None:
        bb = draw.textbbox((0, 0), "A", font=font)
        line_height = (bb[3] - bb[1]) + 18
    total_h = len(lines) * line_height
    y = y_center - total_h // 2
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x = (W - (bb[2] - bb[0])) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, int(alpha * 0.7)))
        draw.text((x, y), line, font=font, fill=(*color[:3], int(alpha)))
        y += line_height


def get_whisper_captions(voiceover_path):
    """Use Whisper to get word-level timestamps, grouped into short phrases."""
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        with open(voiceover_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )

        if not result.words:
            print("[WHISPER] No word timestamps returned")
            return None

        words = result.words
        phrases = []
        current_words = []
        current_start = None

        for w in words:
            word_text = w.word.strip()
            if not word_text:
                continue

            if current_start is None:
                current_start = w.start

            current_words.append(word_text)
            is_sentence_end = word_text.rstrip('"\'').endswith(('.', '!', '?'))

            if is_sentence_end or len(current_words) >= 7:
                phrases.append({
                    "text": " ".join(current_words),
                    "start": current_start,
                    "end": w.end,
                })
                current_words = []
                current_start = None

        if current_words and current_start is not None:
            phrases.append({
                "text": " ".join(current_words),
                "start": current_start,
                "end": words[-1].end,
            })

        timed = []
        for i, phrase in enumerate(phrases):
            natural_dur = phrase["end"] - phrase["start"]
            if i + 1 < len(phrases):
                gap_dur = phrases[i + 1]["start"] - phrase["start"]
                duration = min(max(natural_dur + 0.3, 1.5), max(natural_dur, gap_dur))
            else:
                duration = max(natural_dur + 0.3, 1.5)

            timed.append({
                "text": phrase["text"],
                "start": phrase["start"],
                "duration": duration,
                "end_card": False,
            })

        print(f"[WHISPER] {len(timed)} captions synced to audio")
        return timed

    except Exception as e:
        print(f"[WHISPER] Error: {e} — falling back to even distribution")
        return None


def extract_captions_fallback(sections):
    """Fallback: extract short phrases from script sections, evenly distributed."""
    SECTION_ORDER = ["HOOK", "STORY", "UNIVERSAL TRUTH", "REFLECTION",
                     "COMPANION", "CLOSING QUESTION"]

    captions = []
    for section in SECTION_ORDER:
        text = sections.get(section, "")
        if not text:
            continue

        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 4:
                continue

            words = sentence.split()
            if len(words) <= 10:
                captions.append(sentence)
            else:
                comma_idx = sentence.find(',')
                if 0 < comma_idx < 55:
                    first_clause = sentence[:comma_idx].strip()
                    if len(first_clause.split()) <= 10:
                        captions.append(first_clause)
                        continue
                captions.append(" ".join(words[:7]))

    return captions if captions else ["The Flawed Seeker"]


def make_video(script_path, voiceover_path, music_path, image_path, output_path):
    print("Loading script...")
    with open(script_path) as f:
        script_data = json.load(f)

    sections = script_data.get("sections", {})

    print("Loading audio...")
    voice_audio    = AudioFileClip(voiceover_path)
    voice_duration = voice_audio.duration

    print("Getting caption timestamps...")
    timed = get_whisper_captions(voiceover_path)

    if timed is None:
        captions = extract_captions_fallback(sections)
        per_cap  = max(3.0, min(voice_duration / len(captions), 12.0))
        timed    = []
        t        = 0.0
        for cap in captions:
            timed.append({"text": cap, "start": t, "duration": per_cap, "end_card": False})
            t += per_cap
        print(f"[CAPTIONS] Fallback: {len(captions)} captions, {per_cap:.1f}s each")

    total_dur = voice_duration + END_CARD_DURATION

    timed.append({
        "text": "theflawedseeker.com",
        "start": voice_duration,
        "duration": END_CARD_DURATION,
        "end_card": True,
    })

    print(f"Captions: {len(timed) - 1}, total {total_dur:.0f}s")

    print("Loading article image...")
    if image_path and os.path.exists(image_path):
        base_img = load_article_image(image_path)
    else:
        print("[VIDEO] No image — using solid background")
        base_img = Image.new("RGBA", (W, H), (*BG, 255))

    music_audio = AudioFileClip(music_path)
    if music_audio.duration < total_dur:
        loops = int(total_dur / music_audio.duration) + 2
        from moviepy import concatenate_audioclips
        music_audio = concatenate_audioclips([music_audio] * loops)
    music_audio = music_audio.subclipped(0, total_dur).with_volume_scaled(0.15)

    font_caption = get_font(72)
    font_site    = get_font(52)
    font_tagline = get_font(34)

    def make_frame(t):
        current = 0
        for i in range(len(timed) - 1):
            if t >= timed[i + 1]["start"]:
                current = i + 1
            else:
                break

        cap     = timed[current]
        cap_t   = t - cap["start"]
        cap_dur = cap["duration"]
        p       = cap_t / max(cap_dur, 0.001)

        zoom_s = 1.0 if current % 2 == 0 else 1.06
        zoom_e = 1.06 if current % 2 == 0 else 1.0
        pan_x  = [-0.3, 0.3, 0.0][current % 3]

        img = Image.new("RGBA", (W, H))
        bg  = ken_burns(base_img, cap_t, cap_dur, zoom_s, zoom_e, pan_x)
        img.alpha_composite(bg)

        dark_overlay(img, alpha=110)
        img.alpha_composite(get_vignette())
        img.alpha_composite(get_bottom_gradient())

        draw = ImageDraw.Draw(img)

        fade = 0.4 / max(cap_dur, 0.001)
        if p < fade:
            text_alpha = int(ease_out(p / fade) * 255)
        elif p > (1.0 - fade):
            text_alpha = int(ease_out((1.0 - p) / fade) * 255)
        else:
            text_alpha = 255
        text_alpha = max(0, min(255, text_alpha))

        if cap["end_card"]:
            bb = draw.textbbox((0, 0), "theflawedseeker.com", font=font_site)
            x  = (W - (bb[2] - bb[0])) // 2
            y  = H // 2 - (bb[3] - bb[1]) // 2
            draw.text((x + 2, y + 2), "theflawedseeker.com", font=font_site, fill=(0, 0, 0, int(text_alpha * 0.7)))
            draw.text((x, y), "theflawedseeker.com", font=font_site, fill=(*GOLD, text_alpha))

            tagline = "A new reflection every day."
            bb2 = draw.textbbox((0, 0), tagline, font=font_tagline)
            x2  = (W - (bb2[2] - bb2[0])) // 2
            draw.text((x2, y + 74), tagline, font=font_tagline, fill=(*CREAM, int(text_alpha * 0.8)))
        else:
            lines = wrap_text(cap["text"], font_caption, int(W * 0.78))
            draw_text_block(draw, lines, int(H * 0.80), font_caption, CREAM, text_alpha)

            site_alpha = int(text_alpha * 0.35)
            if site_alpha > 10:
                bb = draw.textbbox((0, 0), "theflawedseeker.com", font=font_tagline)
                x  = (W - (bb[2] - bb[0])) // 2
                draw.text((x, H - 40), "theflawedseeker.com", font=font_tagline, fill=(*GOLD, site_alpha))

        return np.array(img.convert("RGB"))

    print("Rendering video...")
    clip = VideoClip(make_frame, duration=total_dur)

    final_audio = CompositeAudioClip([voice_audio, music_audio])
    clip = clip.with_audio(final_audio)

    clip.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        ffmpeg_params=["-crf", "20", "-pix_fmt", "yuv420p"],
        logger=None,
    )

    print(f"\nVideo saved: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    make_video(
        script_path    = sys.argv[1] if len(sys.argv) > 1 else "/home/hermes/scripts/test_script.json",
        voiceover_path = sys.argv[2] if len(sys.argv) > 2 else "/home/hermes/tts/test_voiceover.mp3",
        music_path     = sys.argv[3] if len(sys.argv) > 3 else "/home/hermes/music/Money.mp3",
        image_path     = sys.argv[4] if len(sys.argv) > 4 else "/home/hermes/images/test.png",
        output_path    = sys.argv[5] if len(sys.argv) > 5 else "/home/hermes/videos/test_video.mp4",
    )
