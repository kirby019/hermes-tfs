import os
import math
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy import VideoClip, AudioFileClip, CompositeAudioClip
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

W, H   = 1920, 1080
FPS    = 24
FONTS  = [
    # Linux (VPS)
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    # macOS (local dev)
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

BG    = (10, 8, 6)
CREAM = (240, 228, 210)
GOLD  = (184, 151, 90)
DIM   = (160, 148, 132)
WHITE = (255, 255, 255)


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
    p      = ease_in_out(t / duration)
    zoom   = zoom_start + (zoom_end - zoom_start) * p
    nw     = int(W * zoom)
    nh     = int(H * zoom)
    resized = base_img.resize((nw, nh), Image.LANCZOS)
    ox     = int((nw - W) * (0.5 + pan_x * 0.5))
    oy     = (nh - H) // 2
    ox     = max(0, min(ox, nw - W))
    oy     = max(0, min(oy, nh - H))
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


VIGNETTE = None


def get_vignette():
    global VIGNETTE
    if VIGNETTE is None:
        VIGNETTE = vignette_overlay()
    return VIGNETTE


def dark_overlay(img, alpha=120):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, alpha))
    img.alpha_composite(overlay)


def wrap_text(text, font, max_width):
    words   = text.split()
    lines   = []
    current = []
    draw    = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    for word in words:
        test = " ".join(current + [word])
        bb   = draw.textbbox((0, 0), test, font=font)
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
        bb          = draw.textbbox((0, 0), "A", font=font)
        line_height = (bb[3] - bb[1]) + 18

    total_h = len(lines) * line_height
    y       = y_center - total_h // 2

    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x  = (W - (bb[2] - bb[0])) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, int(alpha * 0.7)))
        draw.text((x, y),         line, font=font, fill=(*color[:3], int(alpha)))
        y += line_height


def build_text_scenes(sections):
    SECTION_ORDER = ["HOOK", "STORY", "UNIVERSAL TRUTH", "REFLECTION",
                     "COMPANION", "CLOSING QUESTION", "END CARD"]

    scenes = []
    for section in SECTION_ORDER:
        text = sections.get(section, "")
        if not text:
            continue
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            word_count = len(para.split())
            duration   = max(4.0, (word_count / 115) * 60 + 2.5)
            scenes.append({
                "text":     para,
                "duration": duration,
                "section":  section,
            })
    return scenes


def make_video(script_path, voiceover_path, music_path, image_path, output_path):
    print("Loading script...")
    with open(script_path) as f:
        script_data = json.load(f)

    sections       = script_data.get("sections", {})
    scenes         = build_text_scenes(sections)
    total_duration = sum(s["duration"] for s in scenes)

    starts = []
    t      = 0.0
    for s in scenes:
        starts.append(t)
        t += s["duration"]

    print(f"Script: {len(scenes)} scenes, {total_duration:.0f}s total")

    print("Loading article image...")
    base_img = load_article_image(image_path)

    print("Loading audio...")
    voice_audio = AudioFileClip(voiceover_path)
    music_audio = AudioFileClip(music_path)

    # Loop music to fill video
    if music_audio.duration < total_duration:
        loops = int(total_duration / music_audio.duration) + 2
        from moviepy import concatenate_audioclips
        music_audio = concatenate_audioclips([music_audio] * loops)
    music_audio = music_audio.subclipped(0, total_duration).with_volume_scaled(0.15)

    font_large  = get_font(64)
    font_medium = get_font(52)
    font_small  = get_font(40)
    font_site   = get_font(32)

    def make_frame(t):
        current_scene = 0
        for i in range(len(scenes) - 1):
            if t >= starts[i + 1]:
                current_scene = i + 1
            else:
                break

        scene     = scenes[current_scene]
        scene_t   = t - starts[current_scene]
        scene_dur = scene["duration"]
        p         = scene_t / scene_dur

        zoom_s = 1.0  if current_scene % 2 == 0 else 1.06
        zoom_e = 1.06 if current_scene % 2 == 0 else 1.0
        pan_x  = -0.3 if current_scene % 3 == 0 else (0.3 if current_scene % 3 == 1 else 0.0)

        img = Image.new("RGBA", (W, H))
        bg  = ken_burns(base_img, scene_t, scene_dur, zoom_s, zoom_e, pan_x)
        img.alpha_composite(bg)

        dark_overlay(img, alpha=150)
        img.alpha_composite(get_vignette())

        draw = ImageDraw.Draw(img)

        fade_in_end    = min(1.0 / scene_dur, 0.25)
        fade_out_start = max(1.0 - 0.8 / scene_dur, 0.75)

        if p < fade_in_end:
            text_alpha = ease_out(p / fade_in_end) * 255
        elif p > fade_out_start:
            text_alpha = ease_out(1.0 - (p - fade_out_start) / (1.0 - fade_out_start)) * 255
        else:
            text_alpha = 255

        text_alpha = max(0, min(255, text_alpha))

        text       = scene["text"]
        word_count = len(text.split())
        font       = font_large if word_count <= 12 else (font_medium if word_count <= 25 else font_small)
        max_w      = int(W * 0.72)

        lines = wrap_text(text, font, max_w)
        draw_text_block(draw, lines, H // 2, font, CREAM, text_alpha)

        if scene["section"] == "END CARD":
            tag_alpha = text_alpha
        else:
            tag_alpha = int(text_alpha * 0.4)

        if tag_alpha > 10:
            site_text = "theflawedseeker.com"
            bb = draw.textbbox((0, 0), site_text, font=font_site)
            x  = (W - (bb[2] - bb[0])) // 2
            draw.text((x, H - 70), site_text, font=font_site,
                      fill=(*GOLD, int(tag_alpha)))

        if p < fade_in_end:
            slide = int(30 * (1 - ease_out(p / fade_in_end)))
        else:
            slide = 0

        if slide > 0:
            arr = np.array(img)
            arr = np.roll(arr, -slide, axis=0)
            img = Image.fromarray(arr, "RGBA")

        return np.array(img.convert("RGB"))

    print("Rendering video...")
    clip = VideoClip(make_frame, duration=total_duration)

    final_audio = CompositeAudioClip([voice_audio, music_audio])
    clip        = clip.with_audio(final_audio)

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
        script_path    = sys.argv[1] if len(sys.argv) > 1 else "/home/hermes/video_scripts/test.json",
        voiceover_path = sys.argv[2] if len(sys.argv) > 2 else "/home/hermes/tts/test.mp3",
        music_path     = sys.argv[3] if len(sys.argv) > 3 else "/home/hermes/music/Burnout.mp3",
        image_path     = sys.argv[4] if len(sys.argv) > 4 else "/home/hermes/images/generated/test.png",
        output_path    = sys.argv[5] if len(sys.argv) > 5 else "/home/hermes/videos/test.mp4",
    )
