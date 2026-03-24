#!/usr/bin/env python3
"""
Word-by-word transcription using AssemblyAI.
Input:  inputs/background_audio.mp3
Output: tmp/background_audio_transcript_full.json
        tmp/background_audio_words.txt

Requirements:
    pip install requests

Before running:
    export ASSEMBLYAI_API_KEY="your_api_key_here"   # macOS / Linux
    set ASSEMBLYAI_API_KEY=98dd4c7e12d745bc97722b54671ebeff       # Windows CMD
    $Env:ASSEMBLYAI_API_KEY="your_api_key_here"    # PowerShell

Notes:
- AssemblyAI returns start/end timestamps (ms) for words in the transcript JSON.
- If you prefer the official Python SDK, you can adapt this to use it; this script uses plain requests so it's easy to follow.
"""
import os
import time
import json
import requests

API_KEY = "98dd4c7e12d745bc97722b54671ebeff"
if not API_KEY:
    raise RuntimeError("Set ASSEMBLYAI_API_KEY environment variable before running.")

UPLOAD_ENDPOINT = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_ENDPOINT = "https://api.assemblyai.com/v2/transcript"

AUDIO_FILENAME = "inputs/background_audio.mp3"
OUTPUT_TEXTFILE = "tmp/background_audio_words.txt"
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
    # We request default transcription. AssemblyAI will include word-level timestamps
    # in the completed transcript response.
    payload = {
        "audio_url": audio_url,
        # add any other parameters you'd like — e.g. "speaker_labels": True
        # "speaker_labels": True
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
    Expected structure: transcript_json may contain a "words" list where each word
    has 'text', 'start', 'end', 'confidence', and possibly 'speaker'.
    """
    words = transcript_json.get("words") or transcript_json.get("utterances") or []
    # Some responses put words under the top-level "words". If not present,
    # try to collect words from sentences/utterances.
    if not words:
        # fallback: try to extract word-like tokens from 'sentences' or 'text' (best-effort)
        collected = []
        # try sentences (each sentence may have 'tokens' or 'words')
        for s in transcript_json.get("sentences", []) :
            if isinstance(s, dict) and "tokens" in s:
                for t in s["tokens"]:
                    collected.append(t)
        words = collected

    if not words:
        # final fallback — try to split transcript text into words (no timestamps)
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
            # many word objects use ms for start/end
            text = w.get("text") or w.get("word") or ""
            start_ms = w.get("start")
            end_ms = w.get("end")
            conf = w.get("confidence")  # may be None
            speaker = w.get("speaker") or w.get("speaker_label") or ""
            # convert to seconds when possible
            start_s = round(start_ms/1000.0, 3) if isinstance(start_ms, (int, float)) else ""
            end_s = round(end_ms/1000.0, 3) if isinstance(end_ms, (int, float)) else ""
            out.write(f"{text}\t{start_s}\t{end_s}\t{conf}\t{speaker}\n")
    print(f"Wrote {len(words)} words to {outpath}")

def main():
    if not os.path.exists(AUDIO_FILENAME):
        raise FileNotFoundError(f"Audio file not found: {AUDIO_FILENAME}")

    os.makedirs("tmp", exist_ok=True)
    print("Uploading audio...")
    upload_url = upload_file(AUDIO_FILENAME)
    print("Uploaded. URL:", upload_url)

    print("Creating transcript job...")
    tid = create_transcript(upload_url)
    print("Transcript ID:", tid)

    print("Polling for completion...")
    transcript = poll_transcript(tid, poll_interval=3)

    # Save full JSON (optional)
    with open("tmp/background_audio_transcript_full.json", "w", encoding="utf-8") as fj:
        json.dump(transcript, fj, ensure_ascii=False, indent=2)

    # Extract word-by-word and write to txt
    write_words_to_file(transcript, OUTPUT_TEXTFILE)

    # Print first 20 words as preview
    try:
        words = transcript.get("words") or []
        preview = words[:20]
        print("\nPreview (first 20 words):")
        for w in preview:
            text = w.get("text") or ""
            s = w.get("start")
            e = w.get("end")
            s_s = round(s/1000,3) if isinstance(s,(int,float)) else ""
            e_s = round(e/1000,3) if isinstance(e,(int,float)) else ""
            print(f"{text}\t{ s_s } -> { e_s }")
    except Exception:
        print("No preview available.")

if __name__ == "__main__":
    main()
