import re
path = 'd:/AI Tools/Explainer content/Testing/layout_10_generator.py'

with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

pattern = re.compile(
    r'[ \t]*# Large title sits high above the macro image.*?"description": ""\n[ \t]+}\)',
    re.DOTALL
)

replacement = """    # Large title sits high above the macro image
    max_macro_w = (MACRO_CX - MARGIN) * 2
    macro_words = m_txt_phrase.split()
    lines = [m_txt_phrase]
    macro_scale = 1.7
    
    if m_txt_phrase:
        fit_scale = max_macro_w / max(1, len(m_txt_phrase) * 32)
        if fit_scale < 1.7:
            if fit_scale >= 1.0:
                macro_scale = round(fit_scale, 3)
            else:
                macro_scale = 1.4
                lines = _wrap_words_by_width(macro_words, macro_scale, max_macro_w)
                if len(lines) > 2:
                    macro_scale = 1.1
                    lines = _wrap_words_by_width(macro_words, macro_scale, max_macro_w)

    line_gap = int(55 * macro_scale)
    start_y = 200 - (len(lines) - 1) * line_gap // 2

    if len(lines) == 1:
        script["elements"].append({
            "element_id": "txt_macro",
            "type": m_type,
            "phrase": lines[0],
            "text_content": lines[0].upper(),
            "x": MACRO_CX,
            "y": start_y,
            "scale": macro_scale,
            "angle": 0,
            "animation": "pop",
            "property": "",
            "reason": "Macro Title",
            "filename": "",
            "description": ""
        })
    else:
        for j, line in enumerate(lines):
            script["elements"].append({
                "element_id": f"txt_macro_{j}",
                "type": m_type,
                "phrase": line,
                "text_content": line.upper(),
                "x": MACRO_CX,
                "y": int(start_y + j * line_gap),
                "scale": macro_scale,
                "angle": 0,
                "animation": "pop",
                "property": "",
                "reason": "Macro Title line",
                "filename": "",
                "description": ""
            })"""

new_text = pattern.sub(replacement, text)

if new_text != text:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Patch applied successfully.")
else:
    print("Patch failed: pattern not found.")
