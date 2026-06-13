import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv("/home/hermes/.env")

client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

SYSTEM_PROMPT = """You are writing the narration script for a YouTube video for The Flawed Seeker — a daily reflection channel.

The Flawed Seeker voice rules:
- Plain language. Every word should be invisible. The reader never pauses on a word, only on a feeling.
- Short sentences. Under 12 words wherever possible.
- Single-sentence paragraphs are encouraged at key moments.
- No em dashes. Ever. Use a period. Start a new sentence.
- No transition phrases: "This brings us to", "With that in mind", "It's worth noting"
- No thesis statements. No summarising what you just said.
- "We" and "us" in the universal truth section — never "you"
- Never ranks whose pain is harder
- Never cites studies or says "research shows"
- Ends on a question, never a tidy conclusion
- No banned words: delve, testament, beacon, tapestry, furthermore, moreover, in conclusion, profound, reminds us, navigate (metaphorical), journey (metaphorical), empower, transformative, unpack, resonate, deeply, truly, simply, heartfelt, poignant, raw, authentic, vulnerable

Structure — write exactly these 7 sections in order:

[HOOK] (~80 words)
Drop straight into the scene. One vivid moment. Short sentences. Make them feel like they were there.

[STORY] (~250 words)
Expand the story. Specific details. What happened, what was said, what was not said. No preamble.

[UNIVERSAL TRUTH] (~180 words)
Pull back. Speak to all of us with "we" and "us". Name the pattern. Do not resolve it.

[REFLECTION] (~220 words)
Turn inward. Not a formula. What this story opens up. What cannot be stopped thinking about.

[COMPANION] (~220 words)
Go deeper or wider. Connect to a broader human pattern. Stay in the same voice.

[CLOSING QUESTION] (~100 words)
Slow down. One question the listener has to carry home. Not a lesson. An open door.

[END CARD] (~40 words)
Simple sign-off. "The Flawed Seeker. New reflection every day. theflawedseeker.com"

Total target: 1090 words minimum (approx 9.5 minutes at 115 words per minute with pauses).
The video MUST be at least 8 minutes long for YouTube monetization. Do not write short.

Return ONLY the script with the section headers in square brackets. No commentary, no intro, no explanation."""


def generate_video_script(article_title, article_body, pillar_name):
    prompt = f"""Write the YouTube narration script for this article.

Article title: {article_title}
Pillar: {pillar_name}

Article:
{article_body}

Expand this into a full narration script following the 7-section structure.
Target minimum 1090 words — the video must be at least 8 minutes long.
Keep the same story and emotional core. Deepen it."""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def parse_script_sections(script_text):
    sections        = {}
    current_section = None
    current_lines   = []

    for line in script_text.split("\n"):
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[1:-1]
            current_lines   = []
        elif line and current_section:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


def save_script(script_text, output_path):
    sections          = parse_script_sections(script_text)
    word_count        = len(script_text.split())
    estimated_minutes = round(word_count / 115, 1)

    output = {
        "full_script":        script_text,
        "sections":           sections,
        "word_count":         word_count,
        "estimated_minutes":  estimated_minutes,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Script saved: {output_path}")
    print(f"Words: {word_count} (~{estimated_minutes} min)")
    return output


if __name__ == "__main__":
    import sys

    sample_title = "She Quit After 12 Years and Felt Nothing"
    sample_body  = """She handed in her notice after twelve years.
She expected relief. She expected freedom.
Instead she sat in her car for forty-five minutes and stared at the steering wheel.
Her manager said okay. That was it.
Twelve years and that was it."""

    script_text = generate_video_script(sample_title, sample_body, "Burnout & Exhaustion")
    save_script(script_text, "/home/hermes/video_scripts/test.json")
    print("\n--- SCRIPT PREVIEW ---")
    print(script_text[:500])
