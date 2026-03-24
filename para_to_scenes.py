#!/usr/bin/env python3
"""
Generate assets/scenes/para<id>.json from files in assets/scene_prompts.

Usage: python para_to_scenes.py 1
"""
import os
import sys
import json
import glob
import re


def find_assets_dir():
    cwd = os.getcwd()
    # prefer ./assets if present
    candidate = os.path.join(cwd, "assets")
    if os.path.isdir(candidate):
        return candidate
    # otherwise search upward
    for root, dirs, _ in os.walk(cwd):
        if 'assets' in dirs:
            return os.path.join(root, 'assets')
    raise FileNotFoundError('assets directory not found')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    if len(sys.argv) < 2:
        print('Usage: para_to_scenes.py <para_number>')
        sys.exit(2)
    para = str(sys.argv[1])

    assets = find_assets_dir()
    prompts_dir = os.path.join(assets, 'scene_prompts')
    out_dir = os.path.join(assets, 'scenes')
    if not os.path.isdir(prompts_dir):
        print('scene_prompts directory not found at', prompts_dir)
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)

    scenes = []
    for path in glob.glob(os.path.join(prompts_dir, '*.json')):
        try:
            data = load_json(path)
        except Exception as e:
            print('skipping', path, '->', e)
            continue
        pid = data.get('para_id')
        if pid is None:
            continue
        if str(pid) != para:
            continue

        prompt = data.get('prompt', '')
        if ':' in prompt:
            scene_id, voiceover = prompt.split(':', 1)
            scene_id = scene_id.strip()
            voiceover = voiceover.strip()
        else:
            # fallback to filename
            base = os.path.basename(path)
            m = re.search(r'(scene_\d+)', base)
            scene_id = m.group(1) if m else base
            voiceover = prompt.strip()

        scenes.append({
            'scene_id': scene_id,
            'voiceover': voiceover
        })

    def keyfn(item):
        m = re.search(r'(\d+)', item.get('scene_id',''))
        return int(m.group(1)) if m else 0

    scenes.sort(key=keyfn)

    out = {'scenes': scenes}
    out_path = os.path.join(out_dir, f'para{para}.json')
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print('Wrote', out_path)


if __name__ == '__main__':
    main()
