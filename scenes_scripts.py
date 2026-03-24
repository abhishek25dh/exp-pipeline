#!/usr/bin/env python3
"""
Word-by-word transcription using AssemblyAI for multiple files.
Place this script in a folder with your .mp3 files and run.

Requirements:
    pip install requests
"""
import os
import time
import json
import requests
import glob

API_KEY = "98dd4c7e12d745bc97722b54671ebeff"
if not API_KEY:
    raise RuntimeError("Set ASSEMBLYAI_API_KEY environment variable before running.")

UPLOAD_ENDPOINT = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_ENDPOINT = "https://api.assemblyai.com/v2/transcript"
HEADERS = {"authorization": API_KEY}

def upload_file(filepath):
    """Upload file to AssemblyAI. Returns upload_url."""
    CHUNK_SIZE = 5242880  # 5MB
    with open(filepath, "rb") as f:
        response = requests.post(
            UPLOAD_ENDPOINT,
            headers=HEADERS,
            data=f
        )
    response.raise_for_status()
    return response.json()["upload_url"]

def create_transcript(audio_url):
    """Create transcript job. Returns transcript id."""
    payload = {
        "audio_url": audio_url,
    }
    r = requests.post(TRANSCRIPT_ENDPOINT, json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()["id"]

def poll_transcript(transcript_id, poll_interval=3):
    """Poll the transcript endpoint until completed or failed. Returns full JSON."""
    url = f"{TRANSCRIPT_ENDPOINT}/{transcript_id}"
    while True:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        if status == "completed":
            return data
        if status == "error":
            raise RuntimeError("Transcription failed: " + json.dumps(data, indent=2))
        print(f"Status: {status}. Waiting {poll_interval}s...")
        time.sleep(poll_interval)

def write_words_to_file(transcript_json, outpath):
    """
    Extracts word-level info and writes to file.
    """
    words = transcript_json.get("words") or transcript_json.get("utterances") or []
    
    if not words:
        collected = []
        for s in transcript_json.get("sentences", []):
            if isinstance(s, dict) and "tokens" in s:
                for t in s["tokens"]:
                    collected.append(t)
        words = collected

    if not words:
        text = transcript_json.get("text", "").strip()
        with open(outpath, "w", encoding="utf-8") as out:
            out.write("# NOTE: No word-level timestamps returned. This file contains tokenized text without timestamps.\n")
            for w in text.split():
                out.write(f"{w}\n")
        print("No structured word timestamps found. Wrote plain tokenized words (no timestamps).")
        return

    # Write structured words
    with open(outpath, "w", encoding="utf-8") as out:
        out.write("# word\tstart_s\tend_s\tconfidence\tspeaker\n")
        for w in words:
            text = w.get("text") or w.get("word") or ""
            start_ms = w.get("start")
            end_ms = w.get("end")
            conf = w.get("confidence")  
            speaker = w.get("speaker") or w.get("speaker_label") or ""
            
            start_s = round(start_ms/1000.0, 3) if isinstance(start_ms, (int, float)) else ""
            end_s = round(end_ms/1000.0, 3) if isinstance(end_ms, (int, float)) else ""
            out.write(f"{text}\t{start_s}\t{end_s}\t{conf}\t{speaker}\n")
    print(f"Wrote {len(words)} words to {outpath}")

SCENES_AUDIO_DIR = "assets/scenes_audio"

def main():
    import sys
    if len(sys.argv) > 1:
        # Single scene mode: process only scene_N.mp3
        scene_num = sys.argv[1]
        target = os.path.join(SCENES_AUDIO_DIR, f"scene_{scene_num}.mp3")
        if not os.path.exists(target):
            print(f"File not found: {target}")
            sys.exit(1)
        mp3_files = [target]
    else:
        # All scenes mode
        mp3_files = glob.glob(os.path.join(SCENES_AUDIO_DIR, "*.mp3"))

    if not mp3_files:
        print(f"No .mp3 files found in {SCENES_AUDIO_DIR}.")
        return

    print(f"Found {len(mp3_files)} .mp3 file(s). Starting transcription process...\n")

    for audio_filename in mp3_files:
        # Create dynamic output filenames based on the input audio file
        base_name = os.path.splitext(os.path.basename(audio_filename))[0]
        output_textfile = os.path.join(SCENES_AUDIO_DIR, f"{base_name}_words.txt")
        output_jsonfile = os.path.join(SCENES_AUDIO_DIR, f"{base_name}_transcript_full.json")
        
        print("=" * 50)
        print(f"Processing: {audio_filename}")
        print("=" * 50)

        try:
            print("Uploading audio...")
            upload_url = upload_file(audio_filename)
            print("Uploaded. URL:", upload_url)

            print("Creating transcript job...")
            tid = create_transcript(upload_url)
            print("Transcript ID:", tid)

            print("Polling for completion...")
            transcript = poll_transcript(tid, poll_interval=3)

            # Save full JSON
            with open(output_jsonfile, "w", encoding="utf-8") as fj:
                json.dump(transcript, fj, ensure_ascii=False, indent=2)

            # Extract word-by-word and write to txt
            write_words_to_file(transcript, output_textfile)

            # Print first 5 words as preview (shortened so it doesn't flood the console for multiple files)
            try:
                words = transcript.get("words") or []
                preview = words[:5]
                print(f"\nPreview (first 5 words of {audio_filename}):")
                for w in preview:
                    text = w.get("text") or ""
                    s = w.get("start")
                    e = w.get("end")
                    s_s = round(s/1000, 3) if isinstance(s, (int, float)) else ""
                    e_s = round(e/1000, 3) if isinstance(e, (int, float)) else ""
                    print(f"{text}\t{ s_s } -> { e_s }")
            except Exception:
                print("No preview available.")
                
        except Exception as e:
            print(f"An error occurred while processing {audio_filename}: {e}")
            
        print("\n") # Add spacing between files

    print("All files processed successfully!")

if __name__ == "__main__":
    main()