import os
import json
import re
import argparse

def clean_word(word):
    """
    Removes punctuation and special characters, and converts to lowercase.
    This ensures matching works even if the script has 'way.' and the transcript has 'way,'
    """
    return re.sub(r'[^a-z0-9]', '', word.lower())

def get_element_index(element_id):
    """
    Extracts the numerical suffix from an element_id for accurate sorting.
    E.g., 'text_2' -> 2, 'icon_12' -> 12
    """
    match = re.search(r'\d+', element_id)
    return int(match.group()) if match else 999

def parse_scene_numbers(raw_args):
    scene_numbers = set()
    for arg in raw_args:
        for part in arg.split(","):
            part = part.strip()
            if not part:
                continue
            if part.lower() == "a":
                return None
            if part.isdigit():
                scene_numbers.add(int(part))
            else:
                raise ValueError(f"Invalid scene number: '{part}'")
    return scene_numbers


def process_scenes(scene_numbers=None):
    # Define directory paths
    director_dir = 'assets/directorscript'
    audio_dir = 'assets/scenes_audio'
    timings_dir = 'assets/timings'

    # Create the timings directory if it doesn't exist
    if not os.path.exists(timings_dir):
        os.makedirs(timings_dir)

    if not os.path.exists(director_dir):
        print(f"ERROR: {director_dir} not found. Run layout_creator.py first.")
        return

    # Find all director JSON files
    for filename in os.listdir(director_dir):
        if not filename.endswith('_director.json'):
            continue
        
        # Extract the scene_id (e.g., "scene_1")
        scene_id = filename.replace('_director.json', '')
        scene_match = re.search(r'(\d+)$', scene_id)
        scene_num = int(scene_match.group(1)) if scene_match else None

        if scene_numbers and scene_num not in scene_numbers:
            continue
        
        director_path = os.path.join(director_dir, filename)
        transcript_path = os.path.join(audio_dir, f"{scene_id}_transcript_full.json")
        
        # Check if the matching transcript exists
        if not os.path.exists(transcript_path):
            print(f"WARNING: Transcript not found for {scene_id}, skipping.")
            continue
            
        # Load the JSON files
        with open(director_path, 'r', encoding='utf-8') as f:
            director_data = json.load(f)
            
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
            
        # Determine the total audio duration for the 'end' time
        end_time = float(transcript_data.get('audio_duration', 0))
        if end_time == 0.0 and transcript_data.get('words'):
            # Fallback to the end time of the very last word in milliseconds
            end_time = transcript_data['words'][-1]['end'] / 1000.0
            
        # Prepare transcript words for matching
        t_words = transcript_data.get('words', [])
        cleaned_t_words = [clean_word(w['text']) for w in t_words]
        
        # Group director elements by their cleaned phrase
        elements = director_data.get('elements', [])
        phrase_groups = {}
        
        for el in elements:
            phrase = el.get('phrase', '')
            # Normalize hyphens to spaces before cleaning so "follow-up" matches
            # transcript words ["follow", "up"] rather than failing as "followup".
            phrase_normalized = phrase.replace('-', ' ')
            clean_p = tuple([clean_word(w) for w in phrase_normalized.split() if clean_word(w)])
            
            if clean_p not in phrase_groups:
                phrase_groups[clean_p] = []
            phrase_groups[clean_p].append(el)
            
        # Sort each group of elements by their element_id suffix
        # (Handles your requirement: smaller ID gets the first occurrence)
        for clean_p in phrase_groups:
            phrase_groups[clean_p].sort(key=lambda x: get_element_index(x['element_id']))
            
        timings_output = []
        
        # Map timestamps to elements
        for clean_p, els in phrase_groups.items():
            matches = []
            
            if not clean_p:
                # Empty phrase — handled in a second pass below (sub-line pattern).
                continue
            else:
                phrase_len = len(clean_p)
                # Slide through the transcript to find exact phrase sequences
                for i in range(len(cleaned_t_words) - phrase_len + 1):
                    if tuple(cleaned_t_words[i:i+phrase_len]) == clean_p:
                        # Append the start time (converted from ms to seconds)
                        matches.append(t_words[i]['start'] / 1000.0)
            
            if not matches:
                original_phrase = els[0].get('phrase', '')
                print(f"  WARNING [{scene_id}]: phrase not found in transcript: {original_phrase!r} — defaulting to end of audio ({end_time:.2f}s)")

            # Assign the found times chronologically to the sorted elements
            for idx, el in enumerate(els):
                # If we found enough matches, grab the specific one.
                # If the script has more elements than transcript matches, fallback to the last match.
                # If phrase was never found, fallback to end_time so the element appears last.
                if idx < len(matches):
                    start_time = matches[idx]
                else:
                    start_time = matches[-1] if matches else end_time
                
                # Build the output dictionary preserving the requested key order
                timing_entry = {
                    "element_id": el["element_id"]
                }
                if "filename" in el:
                    timing_entry["filename"] = el["filename"]
                
                timing_entry["phrase"] = el["phrase"]
                timing_entry["start"] = start_time
                timing_entry["end"] = end_time
                
                timings_output.append(timing_entry)
        
        # Second pass: assign empty-phrase elements the timing of their preceding element.
        # This handles wrapped text sub-lines (e.g. label_step_1_2, center_title_2)
        # which share the visual moment of their parent line 1.
        _timed_ids = {e["element_id"]: e["start"] for e in timings_output}
        _last_start = 0.0
        for el in elements:
            eid = el["element_id"]
            phrase = el.get("phrase", "")
            clean_p = tuple([clean_word(w) for w in phrase.replace("-", " ").split() if clean_word(w)])
            if clean_p:
                if eid in _timed_ids:
                    _last_start = _timed_ids[eid]
            else:
                timing_entry = {"element_id": eid}
                if "filename" in el:
                    timing_entry["filename"] = el["filename"]
                timing_entry["phrase"] = ""
                timing_entry["start"] = _last_start
                timing_entry["end"] = end_time
                timings_output.append(timing_entry)

        # Sort the final list by start time first, then element_id to keep the JSON tidy
        timings_output.sort(key=lambda x: (x['start'], get_element_index(x['element_id'])))
        
        # Save output JSON
        output_path = os.path.join(timings_dir, f"{scene_id}_timings.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(timings_output, f, indent=2)
            
        print(f"Generated {output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Generate timings JSON from director scripts and scene transcripts."
    )
    parser.add_argument(
        "scenes",
        nargs="*",
        help="Scene numbers to process (examples: 1 2 3 or 1,2,3). Use 'a' for all scenes.",
    )
    args = parser.parse_args()

    selected_scenes = parse_scene_numbers(args.scenes) if args.scenes else None

    print("Starting timing generation...")
    process_scenes(selected_scenes)
    print("Done!")
