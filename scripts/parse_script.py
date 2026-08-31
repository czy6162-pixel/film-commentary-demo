import argparse
import json
import re
from pathlib import Path


ENGLISH_SCENE_PATTERN = re.compile(
    r"^(INT\.|EXT\.|INT/EXT\.|EXT/INT\.|I/E\.)\s*(.+)$",
    re.IGNORECASE,
)
CHINESE_SCENE_PATTERNS = (
    re.compile(r"^场景\s*([一二三四五六七八九十百零〇\d]+)?\s*[：:]\s*(.+)$"),
    re.compile(r"^第\s*([一二三四五六七八九十百零〇\d]+)\s*场\s*[：:]?\s*(.+)$"),
)
CHINESE_DIALOGUE_PATTERN = re.compile(
    r"^([\u3400-\u9fffA-Za-z][\u3400-\u9fffA-Za-z0-9·._\- ]{0,19})"
    r"(?:[（(]([^）)]*)[）)])?\s*[：:]\s*(.*)$"
)
TIME_WORDS = {
    "DAY",
    "NIGHT",
    "DAWN",
    "DUSK",
    "MORNING",
    "AFTERNOON",
    "EVENING",
    "CONTINUOUS",
    "LATER",
}
CHINESE_TIME_WORDS = {
    "日",
    "白天",
    "夜",
    "夜晚",
    "清晨",
    "早晨",
    "上午",
    "中午",
    "午后",
    "下午",
    "黄昏",
    "傍晚",
    "凌晨",
    "连续",
    "稍后",
}
CHINESE_SPACE_WORDS = {"室内", "内景", "室外", "外景"}
NON_CHARACTER_CUES = {
    "FADE IN",
    "FADE OUT",
    "CUT TO",
    "DISSOLVE TO",
    "ANOTHER ANGLE",
    "WIDER ANGLE",
    "CLOSE SHOT",
    "MEDIUM SHOT",
    "REVERSE SHOT",
}
PROP_TERMS = {
    "water pistol": ("Water Pistol", "A small toy water pistol."),
    "magazine": ("Magazine", "A printed magazine."),
    "key": ("Key", "A key mentioned in the script."),
    "letter": ("Letter", "A paper letter mentioned in the script."),
    "photograph": ("Photograph", "A photograph mentioned in the script."),
    "photo": ("Photograph", "A photograph mentioned in the script."),
    "gun": ("Gun", "A gun mentioned in the script."),
    "knife": ("Knife", "A knife mentioned in the script."),
    "phone": ("Phone", "A phone mentioned in the script."),
    "suitcase": ("Suitcase", "A suitcase mentioned in the script."),
    "红色钥匙": ("红色钥匙", "剧本中出现的一把红色钥匙。"),
    "钥匙": ("钥匙", "剧本中出现的钥匙。"),
    "落地钟": ("落地钟", "剧本中出现的落地钟。"),
    "木盒": ("木盒", "剧本中出现的木盒。"),
    "童年合照": ("童年合照", "剧本中出现的童年合照。"),
    "合照": ("合照", "剧本中出现的合照。"),
    "照片": ("照片", "剧本中出现的照片。"),
    "手机": ("手机", "剧本中出现的手机。"),
    "电话": ("电话", "剧本中出现的电话。"),
    "信件": ("信件", "剧本中出现的信件。"),
    "手枪": ("手枪", "剧本中出现的手枪。"),
    "刀": ("刀", "剧本中出现的刀具。"),
    "行李箱": ("行李箱", "剧本中出现的行李箱。"),
    "文件": ("文件", "剧本中出现的文件。"),
    "电脑": ("电脑", "剧本中出现的电脑。"),
    "雨伞": ("雨伞", "剧本中出现的雨伞。"),
}


def contains_chinese(text):
    return bool(re.search(r"[\u3400-\u9fff]", text))


def text_contains(text, term):
    if contains_chinese(term):
        return term in text
    return bool(re.search(rf"\b{re.escape(term)}s?\b", text, re.IGNORECASE))


def parse_chinese_heading(line):
    stripped = line.strip()
    for pattern in CHINESE_SCENE_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        body = match.group(2).strip()
        parts = [part for part in re.split(r"[，,\s]+", body) if part]
        time = next((part for part in parts if part in CHINESE_TIME_WORDS), "")
        location_parts = [
            part
            for part in parts
            if part not in CHINESE_TIME_WORDS and part not in CHINESE_SPACE_WORDS
        ]
        location = " ".join(location_parts).strip() or body
        return {"heading": stripped, "location": location, "time": time}
    return None


def is_english_character_cue(line):
    stripped = line.strip().rstrip(":")
    if not stripped or len(stripped) > 40:
        return False
    if stripped.upper() != stripped:
        return False
    if stripped in NON_CHARACTER_CUES:
        return False
    if ENGLISH_SCENE_PATTERN.match(stripped):
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9 .'-]*", stripped))


def split_english_heading(heading):
    normalized = re.sub(r"\s*--\s*", " - ", heading.strip())
    parts = [part.strip() for part in normalized.rsplit(" - ", 1)]
    if len(parts) == 2 and parts[1].upper() in TIME_WORDS:
        return parts[0], parts[1].title()
    return normalized, ""


def read_title(lines, input_name):
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("TITLE:"):
            return stripped.split(":", 1)[1].strip()
        if stripped.startswith("标题：") or stripped.startswith("标题:"):
            return re.split(r"[：:]", stripped, maxsplit=1)[1].strip()
        match = re.fullmatch(r"《(.+)》", stripped)
        if match:
            return match.group(1).strip()
    return Path(input_name).stem.replace("_", " ").title()


def collect_scenes(lines):
    scenes = []
    current = None
    language = "en"
    for line in lines:
        stripped = line.strip()
        english_match = ENGLISH_SCENE_PATTERN.match(stripped)
        chinese_heading = parse_chinese_heading(stripped)
        if english_match or chinese_heading:
            if current:
                scenes.append(current)
            if english_match:
                location, time = split_english_heading(english_match.group(2))
                current = {
                    "heading": stripped,
                    "location": location,
                    "time": time,
                    "language": "en",
                    "lines": [],
                }
            else:
                language = "zh"
                current = {
                    **chinese_heading,
                    "language": "zh",
                    "lines": [],
                }
        elif current is not None:
            current["lines"].append(line.rstrip())
    if current:
        scenes.append(current)
    if scenes:
        language = "zh" if any(scene["language"] == "zh" for scene in scenes) else "en"
    return scenes, language


def parse_english_scene_content(lines):
    blocks = []
    paragraph = []
    index = 0

    def flush_paragraph():
        if paragraph:
            blocks.append({"type": "action", "text": " ".join(paragraph)})
            paragraph.clear()

    while index < len(lines):
        line = lines[index].strip()
        if not line:
            flush_paragraph()
            index += 1
            continue
        if is_english_character_cue(line):
            next_index = index + 1
            while next_index < len(lines) and not lines[next_index].strip():
                next_index += 1
            if next_index < len(lines):
                next_line = lines[next_index].strip()
                if not is_english_character_cue(next_line) and not ENGLISH_SCENE_PATTERN.match(next_line):
                    flush_paragraph()
                    speaker = line.rstrip(":").strip()
                    delivery = ""
                    if next_line.startswith("(") and next_line.endswith(")"):
                        delivery = next_line[1:-1].strip()
                        next_index += 1
                    dialogue_lines = []
                    while next_index < len(lines):
                        dialogue_line = lines[next_index].strip()
                        if not dialogue_line:
                            break
                        if is_english_character_cue(dialogue_line) or ENGLISH_SCENE_PATTERN.match(dialogue_line):
                            break
                        dialogue_lines.append(dialogue_line)
                        next_index += 1
                    if dialogue_lines:
                        blocks.append(
                            {
                                "type": "dialogue",
                                "speaker": speaker,
                                "delivery": delivery,
                                "text": " ".join(dialogue_lines),
                            }
                        )
                        index = next_index
                        continue
        paragraph.append(line)
        index += 1
    flush_paragraph()
    return blocks


def parse_chinese_dialogue(line):
    match = CHINESE_DIALOGUE_PATTERN.match(line.strip())
    if not match:
        return None
    speaker = match.group(1).strip()
    delivery = (match.group(2) or "").strip()
    text = match.group(3).strip()
    leading_delivery = re.match(r"^[（(]([^）)]*)[）)]\s*(.*)$", text)
    if leading_delivery:
        delivery = delivery or leading_delivery.group(1).strip()
        text = leading_delivery.group(2).strip()
    if not text:
        return None
    return {"type": "dialogue", "speaker": speaker, "delivery": delivery, "text": text}


def parse_chinese_scene_content(lines):
    blocks = []
    paragraph = []

    def flush_paragraph():
        if paragraph:
            blocks.append({"type": "action", "text": "".join(paragraph)})
            paragraph.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue
        dialogue = parse_chinese_dialogue(line)
        if dialogue:
            flush_paragraph()
            blocks.append(dialogue)
        else:
            paragraph.append(line)
    flush_paragraph()
    return blocks


def character_name(cue):
    cue = re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", cue).strip()
    return cue if contains_chinese(cue) else cue.title()


def detect_props(scene_texts):
    combined = "\n".join(scene_texts)
    found = []
    seen_names = set()
    for term in sorted(PROP_TERMS, key=len, reverse=True):
        name, description = PROP_TERMS[term]
        if any(term in existing["term"] for existing in found):
            continue
        candidate_text = combined
        if text_contains(candidate_text, term) and name not in seen_names:
            found.append({"term": term, "name": name, "description": description})
            seen_names.add(name)
    return found


def mentioned_cues(text, cue_order):
    return [
        cue
        for cue in cue_order
        if (cue in text if contains_chinese(cue) else bool(re.search(rf"\b{re.escape(cue)}\b", text, re.IGNORECASE)))
    ]


def action_items(text, cue_order, character_ids):
    items = []
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?。！？；;])\s*", text.strip())
        if part.strip()
    ]
    for sentence in sentences:
        clauses = [
            part.strip()
            for part in re.split(r"\s+while\s+|与此同时|同时", sentence, flags=re.IGNORECASE)
            if part.strip()
        ]
        for clause in clauses:
            mentioned = mentioned_cues(clause, cue_order)
            if not mentioned:
                items.append({"character_id": None, "description": clause})
            else:
                for cue in mentioned:
                    items.append({"character_id": character_ids[cue], "description": clause})
    return items


def build_default_chinese_scene(lines):
    content_lines = [
        line
        for line in lines
        if line.strip()
        and not re.fullmatch(r"《.+》", line.strip())
        and not line.strip().startswith(("标题：", "标题:"))
    ]
    return [
        {
            "heading": "场景：未命名场景",
            "location": "未命名场景",
            "time": "",
            "language": "zh",
            "lines": content_lines,
        }
    ]


def parse_script_text(text, project_id, visual_style, input_name="screenplay.txt"):
    lines = text.splitlines()
    raw_scenes, source_language = collect_scenes(lines)
    if not raw_scenes and contains_chinese(text):
        raw_scenes = build_default_chinese_scene(lines)
        source_language = "zh"
    if not raw_scenes:
        raise ValueError("No supported English or Chinese scene headings were found.")

    for scene in raw_scenes:
        scene["blocks"] = (
            parse_chinese_scene_content(scene["lines"])
            if scene["language"] == "zh"
            else parse_english_scene_content(scene["lines"])
        )

    cue_order = []
    for scene in raw_scenes:
        for block in scene["blocks"]:
            if block["type"] == "dialogue" and block["speaker"] not in cue_order:
                cue_order.append(block["speaker"])

    character_ids = {
        cue: f"char_{index:03d}" for index, cue in enumerate(cue_order, start=1)
    }
    scene_ids = [f"scene_{index:03d}" for index in range(1, len(raw_scenes) + 1)]
    prop_candidates = detect_props(["\n".join(scene["lines"]) for scene in raw_scenes])
    prop_ids = {
        candidate["name"]: f"prop_{index:03d}"
        for index, candidate in enumerate(prop_candidates, start=1)
    }

    characters = []
    for cue in cue_order:
        description = ""
        for scene in raw_scenes:
            for block in scene["blocks"]:
                if block["type"] == "action" and cue in mentioned_cues(block["text"], [cue]):
                    description = block["text"]
                    break
            if description:
                break
        characters.append(
            {
                "character_id": character_ids[cue],
                "name": character_name(cue),
                "aliases": [],
                "description": description,
            }
        )

    props = []
    for candidate in prop_candidates:
        matching_scene_ids = []
        description = candidate["description"]
        for scene_id, scene in zip(scene_ids, raw_scenes):
            scene_text = " ".join(scene["lines"])
            if text_contains(scene_text, candidate["term"]):
                matching_scene_ids.append(scene_id)
                for block in scene["blocks"]:
                    if block["type"] == "action" and text_contains(block["text"], candidate["term"]):
                        description = block["text"]
                        break
        props.append(
            {
                "prop_id": prop_ids[candidate["name"]],
                "name": candidate["name"],
                "description": description,
                "scene_ids": matching_scene_ids,
            }
        )

    dialogue_number = 1
    scenes = []
    for sequence, (scene_id, scene) in enumerate(zip(scene_ids, raw_scenes), start=1):
        present_cues = []
        actions = []
        dialogues = []
        action_texts = []
        for block in scene["blocks"]:
            if block["type"] == "dialogue":
                cue = block["speaker"]
                if cue not in present_cues:
                    present_cues.append(cue)
                dialogues.append(
                    {
                        "dialogue_id": f"dialogue_{dialogue_number:03d}",
                        "speaker_id": character_ids[cue],
                        "text": block["text"],
                        "delivery": block["delivery"],
                    }
                )
                dialogue_number += 1
                continue
            action_texts.append(block["text"])
            for cue in mentioned_cues(block["text"], cue_order):
                if cue not in present_cues:
                    present_cues.append(cue)
            actions.extend(action_items(block["text"], cue_order, character_ids))

        scene_text = " ".join(scene["lines"])
        used_prop_ids = [
            prop_ids[candidate["name"]]
            for candidate in prop_candidates
            if text_contains(scene_text, candidate["term"])
        ]
        if action_texts:
            summary = action_texts[0]
        elif dialogues:
            first_name = character_name(cue_order[0]) if cue_order else "角色"
            summary = (
                f"{first_name}在{scene['location']}展开对话。"
                if source_language == "zh"
                else f"{first_name} begins a conversation in {scene['location']}."
            )
        else:
            summary = scene["location"]
        scenes.append(
            {
                "scene_id": scene_id,
                "sequence": sequence,
                "heading": scene["heading"],
                "location": scene["location"] if source_language == "zh" else scene["location"].title(),
                "time": scene["time"],
                "summary": summary,
                "character_ids": [character_ids[cue] for cue in present_cues],
                "prop_ids": list(dict.fromkeys(used_prop_ids)),
                "actions": actions,
                "dialogues": dialogues,
            }
        )

    return {
        "format_version": "1.1",
        "project_id": project_id,
        "title": read_title(lines, input_name),
        "source_language": source_language,
        "visual_style": visual_style,
        "characters": characters,
        "props": props,
        "scenes": scenes,
    }


def parse_script(input_path, project_id, visual_style):
    return parse_script_text(
        input_path.read_text(encoding="utf-8-sig"),
        project_id,
        visual_style,
        input_path.name,
    )


def main():
    parser = argparse.ArgumentParser(description="Parse a short English or Chinese screenplay.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--project-id", default="project_001")
    parser.add_argument("--style-name", default="Classic mystery film")
    args = parser.parse_args()
    visual_style = {
        "style_name": args.style_name,
        "rendering": "Realistic cinematic photography with subtle film grain",
        "color_palette": "Muted cool colors with restrained warm highlights",
        "period": "Contemporary",
        "lighting": "Natural cinematic lighting with soft contrast",
    }
    result = parse_script(args.input, args.project_id, visual_style)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Parsed {result['source_language']} screenplay: "
        f"{len(result['characters'])} characters, {len(result['scenes'])} scenes, "
        f"{sum(len(scene['dialogues']) for scene in result['scenes'])} dialogues, "
        f"and {len(result['props'])} props."
    )


if __name__ == "__main__":
    main()

