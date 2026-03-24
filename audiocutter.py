import json
import re
import argparse
from pathlib import Path
from pydub import AudioSegment
from rapidfuzz import fuzz

# ---------------- CONFIG ----------------
SCENES_DIR = "assets/scenes"
TRANSCRIPT_FILE = "tmp/background_audio_transcript_full.json"
AUDIO_FILE = "inputs/background_audio.mp3"

OUTPUT_AUDIO_DIR = "assets/scenes_audio"
OUTPUT_TIMELINE_JSON = "assets/sections_timeline.json"

PADDING_MS = 200
MATCH_THRESHOLD = 75  # Lowered slightly because we are using the stricter 'ratio' now
# ----------------------------------------


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


# ---------- WORD LIST ----------
def build_word_list(transcript_words):
    return [
        {
            "word": normalize(w["text"]),
            "start": w["start"],
            "end": w["end"]
        }
        for w in transcript_words
    ]


def find_sentence_span(sentence, words, cursor):
    """
    Finds the BEST matching span of words ahead of the cursor.
    This prevents early shifted matches that chop off the end of paragraphs.
    """
    target_words = normalize(sentence).split()
    if not target_words:
        return None, None, cursor

    target_text = " ".join(target_words)
    target_len = len(target_words)

    best_score = 0
    best_span = None

    # Search window: look up to 200 words ahead of our current cursor.
    # This is fast and works well when scenes are processed sequentially.
    search_limit = min(len(words), cursor + 200)

    for i in range(cursor, search_limit):
        
        # Test window sizes: slightly shorter (-4 words) to slightly longer (+8 words)
        # This handles cases where the AI transcript grouped/split words differently
        for extra in range(-4, 9):
            j = i + target_len + extra
            
            if j <= i or j > len(words):
                continue

            window_words = [w["word"] for w in words[i:j]]
            window_text = " ".join(window_words)

            # Combined score: token_set_ratio handles word substitutions,
            # fuzz.ratio enforces correct sequence/boundaries
            score = (fuzz.ratio(target_text, window_text) + fuzz.token_set_ratio(target_text, window_text)) / 2

            span_len = j - i
            len_diff = abs(span_len - target_len)
            best_len_diff = abs((best_span[1] - best_span[0]) - target_len) if best_span else float('inf')
            if score > best_score or (score == best_score and len_diff < best_len_diff):
                best_score = score
                best_span = (i, j)

    # Fallback: if nothing good was found nearby, scan the remaining transcript.
    # This is useful when running only a later paragraph (e.g., para3) where the
    # first requested sentence may be far beyond the initial cursor window.
    if (not best_span or best_score < MATCH_THRESHOLD) and search_limit < len(words):
        for i in range(search_limit, len(words)):
            for extra in range(-4, 9):
                j = i + target_len + extra

                if j <= i or j > len(words):
                    continue

                window_words = [w["word"] for w in words[i:j]]
                window_text = " ".join(window_words)
                score = fuzz.token_set_ratio(target_text, window_text)

                span_len = j - i
                len_diff = abs(span_len - target_len)
                best_len_diff = abs((best_span[1] - best_span[0]) - target_len) if best_span else float('inf')
                if score > best_score or (score == best_score and len_diff < best_len_diff):
                    best_score = score
                    best_span = (i, j)

    # If the highest score found is acceptable, return that exact span
    if best_span and best_score >= MATCH_THRESHOLD:
        i, j = best_span
        start_ms = words[i]["start"]
        end_ms = words[j-1]["end"]
        return start_ms, end_ms, j

    return None, None, cursor


# ---------- LOAD SCENES ----------
def load_scenes(para_numbers=None):
    scenes_data = []
    scenes_path = Path(SCENES_DIR)
    
    if not scenes_path.exists():
        print(f"ERROR: Directory '{SCENES_DIR}' not found.")
        return scenes_data

    if para_numbers:
        scene_files = []
        for n in para_numbers:
            file_path = scenes_path / f"para{n}.json"
            if file_path.exists():
                scene_files.append(file_path)
            else:
                print(f"File not found: {file_path}")
    else:
        # Sort files to maintain chronological order
        scene_files = sorted(scenes_path.glob("*.json"))
    
    for file_path in scene_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "scenes" in data:
                scenes_data.extend(data["scenes"])
                
    return scenes_data


# ---------- SECTION DATA ----------
def compute_section_data(scenes_data, words):
    section_data = {}
    cursor = 0

    for scene in scenes_data:
        sec_id = scene.get("scene_id")
        voiceover = scene.get("voiceover")
        
        if not sec_id or not voiceover:
            continue

        start, end, new_cursor = find_sentence_span(voiceover, words, cursor)

        if start is None:
            print(f"WARNING: Could not find match for {sec_id}. Skipping.")
            continue

        # Update cursor so the next search starts exactly where this one ended
        cursor = new_cursor

        start = max(0, start - PADDING_MS)
        end = end + PADDING_MS

        section_data[sec_id] = {
            "start": start,
            "end": end,
            "text": voiceover
        }

    return section_data


# ---------- CUT AUDIO ----------
def cut_audio(section_data):
    print("Loading audio file...")
    audio = AudioSegment.from_file(AUDIO_FILE)
    Path(OUTPUT_AUDIO_DIR).mkdir(exist_ok=True)

    for sec, data in section_data.items():
        start = max(0, data["start"])
        end = min(len(audio), data["end"])

        clip = audio[start:end]
        out = Path(OUTPUT_AUDIO_DIR) / f"{sec}.mp3"
        clip.export(out, format="mp3")

        print(f"Saved {sec}.mp3  ({start}ms -> {end}ms)")


# ---------- MAIN ----------
def main():
    parser = argparse.ArgumentParser(
        description="Cut scene audio clips using scene voiceovers and transcript timing."
    )
    parser.add_argument(
        "paras",
        nargs="*",
        type=int,
        help="Paragraph numbers to load (example: 1 2 3 => scenes/para1.json, para2.json, para3.json).",
    )
    args = parser.parse_args()

    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    scenes_data = load_scenes(args.paras)
    
    if not scenes_data:
        print(f"ERROR: No scenes found to process. Check your '{SCENES_DIR}' folder.")
        return

    words = build_word_list(transcript["words"])

    section_data = compute_section_data(scenes_data, words)

    if not section_data:
        print("ERROR: No matches found. Check voiceover wording.")
        return

    cut_audio(section_data)

    with open(OUTPUT_TIMELINE_JSON, "w", encoding="utf-8") as f:
        json.dump(section_data, f, indent=2)

    print("\nDone")


if __name__ == "__main__":
    main()

