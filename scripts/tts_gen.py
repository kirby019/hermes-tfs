import os
import re
import io
import json
from openai import OpenAI
from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv("/home/hermes/.env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VOICE = "onyx"
MODEL = "tts-1-hd"

PAUSE_AFTER_PERIOD     = 1100
PAUSE_AFTER_QUESTION   = 1300
PAUSE_AFTER_COMMA      =  500
PAUSE_AFTER_PARAGRAPH  = 1900
PAUSE_BETWEEN_SECTIONS = 2500

MIN_VIDEO_SECONDS = 480


def chunk_speed(text):
    is_question = text.strip().endswith("?")
    words       = len(text.split())
    if is_question:
        return 0.92
    elif words <= 3:
        return 0.78
    elif words <= 6:
        return 0.82
    elif words <= 10:
        return 0.86
    else:
        return 0.90


def split_into_chunks(text):
    chunks     = []
    paragraphs = re.split(r'\n{2,}', text.strip())

    for i, para in enumerate(paragraphs):
        lines = [l.strip() for l in para.strip().split('\n') if l.strip()]

        for line in lines:
            is_question = line.strip().endswith("?")
            if is_question:
                chunks.append({"text": line.strip(), "pause": PAUSE_AFTER_QUESTION})
            else:
                clauses = re.split(r'(?<=,)\s+', line)
                for clause in clauses:
                    clause = clause.strip()
                    if not clause:
                        continue
                    ends_sentence = bool(re.search(r'[.!]$', clause))
                    pause = PAUSE_AFTER_PERIOD if ends_sentence else PAUSE_AFTER_COMMA
                    chunks.append({"text": clause, "pause": pause})

        if i < len(paragraphs) - 1:
            chunks.append({"text": None, "pause": PAUSE_AFTER_PARAGRAPH})

    return chunks


def tts_chunk(text, speed):
    response    = client.audio.speech.create(
        model=MODEL,
        voice=VOICE,
        input=text,
        speed=speed,
        response_format="mp3",
    )
    audio_bytes = b"".join(response.iter_bytes())
    return AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")


def build_audio_from_text(script_text, show_progress=True):
    chunks = split_into_chunks(script_text)
    final  = AudioSegment.empty()
    total  = len([c for c in chunks if c["text"]])
    done   = 0

    for chunk in chunks:
        if chunk["text"] is None:
            final += AudioSegment.silent(duration=chunk["pause"])
            continue

        speed = chunk_speed(chunk["text"])
        done += 1
        if show_progress:
            print(f"  [{done}/{total}] {chunk['text'][:50]}{'...' if len(chunk['text']) > 50 else ''}")

        segment = tts_chunk(chunk["text"], speed)
        final  += segment
        final  += AudioSegment.silent(duration=chunk["pause"])

    return final


def build_audio_from_sections(sections, show_progress=True):
    SECTION_ORDER = ["HOOK", "STORY", "UNIVERSAL TRUTH", "REFLECTION",
                     "COMPANION", "CLOSING QUESTION", "END CARD"]

    final = AudioSegment.empty()

    for section_name in SECTION_ORDER:
        text = sections.get(section_name, "")
        if not text:
            continue

        if show_progress:
            print(f"\n[{section_name}]")

        section_audio = build_audio_from_text(text, show_progress)
        final        += section_audio
        final        += AudioSegment.silent(duration=PAUSE_BETWEEN_SECTIONS)

    return final


def generate_voiceover(script_path, output_path, show_progress=True):
    with open(script_path) as f:
        script_data = json.load(f)

    sections = script_data.get("sections", {})

    if sections:
        if show_progress:
            print(f"Generating voiceover from {len(sections)} sections...")
        audio = build_audio_from_sections(sections, show_progress)
    else:
        full_script = script_data.get("full_script", "")
        if show_progress:
            print("Generating voiceover from full script...")
        audio = build_audio_from_text(full_script, show_progress)

    duration = len(audio) / 1000
    if duration < MIN_VIDEO_SECONDS:
        print(f"[TTS] WARNING: voiceover is {duration:.0f}s — under 8 minutes. Check script word count.")

    audio.export(output_path, format="mp3", bitrate="192k")

    mins = int(duration // 60)
    secs = int(duration % 60)

    if show_progress:
        print(f"\nVoiceover saved: {output_path}  ({mins}m {secs}s)")

    return output_path, duration


if __name__ == "__main__":
    import sys
    script_path = sys.argv[1] if len(sys.argv) > 1 else "/home/hermes/video_scripts/test.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "/home/hermes/tts/test.mp3"
    generate_voiceover(script_path, output_path)
