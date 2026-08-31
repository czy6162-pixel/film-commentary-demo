import argparse
import json
import re
from pathlib import Path


CAMERA_PLANS = (
    ("Close-up", "Front view", "Static"),
    ("Medium close-up", "Three-quarter view", "Subtle push in"),
    ("Over-the-shoulder", "Eye level", "Slow lateral move"),
    ("Medium shot", "Slight low angle", "Slow pull back"),
    ("Close-up", "Profile view", "Gentle handheld drift"),
)


def contains_chinese(text):
    return bool(re.search(r"[\u3400-\u9fff]", text or ""))


def text_contains(text, term):
    if contains_chinese(term):
        return term in text
    return bool(re.search(rf"\b{re.escape(term)}s?\b", text, re.IGNORECASE))


def style_text(visual_style):
    return ", ".join(
        str(visual_style.get(field, "")).strip()
        for field in ("style_name", "rendering", "color_palette", "period", "lighting")
        if str(visual_style.get(field, "")).strip()
    )


def character_names(script_analysis):
    return {
        character["character_id"]: character["name"]
        for character in script_analysis.get("characters", [])
    }


def dialogue_map(script_analysis):
    return {
        dialogue["dialogue_id"]: dialogue
        for scene in script_analysis.get("scenes", [])
        for dialogue in scene.get("dialogues", [])
    }


def prop_map(script_analysis):
    return {prop["prop_id"]: prop for prop in script_analysis.get("props", [])}


def unique_actions(scene, character_id=None):
    actions = scene.get("actions", [])
    if character_id:
        matching = [action for action in actions if action.get("character_id") == character_id]
        if matching:
            actions = matching
    seen = set()
    result = []
    for action in actions:
        description = action.get("description", "").strip()
        if description and description not in seen:
            result.append(action)
            seen.add(description)
    return result


def select_action(scene, dialogue_index=0, character_id=None):
    actions = unique_actions(scene, character_id)
    if not actions:
        actions = unique_actions(scene)
    if actions:
        return actions[dialogue_index % len(actions)]
    return {"character_id": character_id, "description": scene.get("summary", "")}


def referenced_props(scene, text, props):
    return [
        prop_id
        for prop_id in scene.get("prop_ids", [])
        if prop_id in props and text_contains(text, props[prop_id]["name"])
    ]


def present_characters(text, scene, names):
    found = []
    for character_id in scene.get("character_ids", []):
        name = names.get(character_id, "")
        if name and text_contains(text, name):
            found.append(character_id)
    return found


def narration_for_establishing(scene, language):
    location = scene.get("location", "").strip()
    summary = scene.get("summary", "").strip()
    if language == "zh":
        if summary and summary != location:
            return f"镜头来到{location}。{summary}"
        return f"故事发生在{location}。"
    if summary and summary.lower() != location.lower():
        return f"The scene opens in {location}. {summary}"
    return f"The story moves to {location}."


def narration_for_dialogue(name, dialogue, index, language):
    delivery = dialogue.get("delivery", "").strip()
    line = dialogue.get("text", "").strip()
    if language == "zh":
        templates = (
            f"{name}{'以' + delivery + '的语气' if delivery else ''}说道：“{line}”",
            f"面对眼前的情形，{name}{'显得' + delivery if delivery else '开口'}：“{line}”",
            f"{name}的回应打破了沉默：“{line}”",
            f"此时，{name}{'带着' + delivery if delivery else ''}说：“{line}”",
        )
    else:
        tone = f" {delivery}" if delivery else ""
        templates = (
            f"{name} says{tone}, \"{line}\"",
            f"Breaking the silence, {name} replies, \"{line}\"",
            f"{name}'s response follows: \"{line}\"",
            f"At that moment, {name} says, \"{line}\"",
        )
    return templates[index % len(templates)]


def adjusted_camera_movement(base_movement, delivery):
    lowered = delivery.lower()
    if any(word in lowered for word in ("愤怒", "急", "喊", "angry", "urgent", "shout")):
        return "Quick push in"
    if any(word in lowered for word in ("紧张", "害怕", "nervous", "afraid")):
        return "Subtle handheld drift"
    if any(word in lowered for word in ("轻声", "低声", "平静", "whisper", "quiet", "calm")):
        return "Slow push in"
    return base_movement


def dialogue_duration(text, language):
    length = len(re.sub(r"\s+", "", text)) if language == "zh" else len(text.split())
    divisor = 4.2 if language == "zh" else 2.5
    return max(3, min(8, round(length / divisor)))


def make_establishing_shot(scene, shot_number, names, language):
    action = select_action(scene)
    visual = scene.get("summary", "") or scene.get("location", "")
    return {
        "shot_id": f"shot_{shot_number:03d}",
        "sequence": shot_number,
        "scene_id": scene["scene_id"],
        "duration_seconds": 4,
        "shot_size": "Wide shot",
        "camera_angle": "Eye level",
        "camera_movement": "Slow push in",
        "character_ids": present_characters(visual, scene, names),
        "prop_ids": [],
        "visual": visual,
        "actions": [action],
        "dialogue_id": None,
        "narration": narration_for_establishing(scene, language),
        "transition": "Cut",
    }


def make_dialogue_shot(scene, dialogue, dialogue_index, shot_number, names, props, language):
    character_id = dialogue["speaker_id"]
    name = names[character_id]
    action = select_action(scene, dialogue_index, character_id)
    shot_size, camera_angle, base_movement = CAMERA_PLANS[dialogue_index % len(CAMERA_PLANS)]
    camera_movement = adjusted_camera_movement(base_movement, dialogue.get("delivery", ""))
    action_text = action.get("description", "").strip()
    visual = (
        f"{name}在{scene['location']}说话。{action_text}"
        if language == "zh"
        else f"{name} speaks in {scene['location']}. {action_text}"
    )
    characters = present_characters(visual, scene, names)
    if character_id not in characters:
        characters.insert(0, character_id)
    return {
        "shot_id": f"shot_{shot_number:03d}",
        "sequence": shot_number,
        "scene_id": scene["scene_id"],
        "duration_seconds": dialogue_duration(dialogue["text"], language),
        "shot_size": shot_size,
        "camera_angle": camera_angle,
        "camera_movement": camera_movement,
        "character_ids": characters,
        "prop_ids": referenced_props(scene, visual, props),
        "visual": visual,
        "actions": [action],
        "dialogue_id": dialogue["dialogue_id"],
        "narration": narration_for_dialogue(name, dialogue, dialogue_index, language),
        "transition": "Cut",
    }


def generate_storyboard(script_analysis):
    names = character_names(script_analysis)
    props = prop_map(script_analysis)
    language = script_analysis.get("source_language", "en")
    shots = []
    shot_number = 1
    dialogue_index = 0
    for scene in script_analysis.get("scenes", []):
        shots.append(make_establishing_shot(scene, shot_number, names, language))
        shot_number += 1
        for dialogue in scene.get("dialogues", []):
            shots.append(make_dialogue_shot(scene, dialogue, dialogue_index, shot_number, names, props, language))
            dialogue_index += 1
            shot_number += 1
    if shots:
        shots[-1]["transition"] = "Fade out"
    return {
        "format_version": script_analysis["format_version"],
        "project_id": script_analysis["project_id"],
        "visual_style": script_analysis["visual_style"],
        "narration_generation": {"mode": "deterministic_rules", "language": language},
        "shots": shots,
    }


def asset_view(asset, view_id):
    available = {view["view_id"] for view in asset["views"]}
    return view_id if view_id in available else asset["views"][0]["view_id"]


def reference_assets_for_shot(shot, assets_by_id):
    references = []
    scene_asset = assets_by_id[shot["scene_id"]]
    scene_view = "main" if shot["shot_size"] == "Wide shot" else "side"
    references.append({"asset_id": shot["scene_id"], "view_id": asset_view(scene_asset, scene_view)})
    angle = shot["camera_angle"]
    character_view = "front" if angle == "Front view" else "side" if angle == "Profile view" else "three_quarter"
    for character_id in shot.get("character_ids", []):
        asset = assets_by_id[character_id]
        references.append({"asset_id": character_id, "view_id": asset_view(asset, character_view)})
    prop_view = "front" if angle == "Front view" else "three_quarter"
    for prop_id in shot.get("prop_ids", []):
        asset = assets_by_id[prop_id]
        references.append({"asset_id": prop_id, "view_id": asset_view(asset, prop_view)})
    return references


def dynamic_negative_prompt(shot, scene, dialogue):
    terms = ["deformed anatomy", "extra fingers", "flicker", "text", "watermark"]
    if len(shot.get("character_ids", [])) > 1:
        terms += ["duplicated people", "swapped faces", "incorrect eyelines"]
    else:
        terms += ["duplicate subject", "inconsistent face"]
    if "Close-up" in shot["shot_size"]:
        terms += ["blurred eyes", "distorted mouth", "cropped chin"]
    elif shot["shot_size"] == "Wide shot":
        terms += ["inconsistent architecture", "warped perspective"]
    if shot["camera_movement"] != "Static":
        terms += ["camera jitter", "motion smear"]
    if shot.get("prop_ids"):
        terms += ["changing props", "floating objects"]
    if dialogue:
        terms += ["incorrect lip sync", "unreadable subtitles"]
    if str(scene.get("time", "")).lower() in {"night", "夜", "夜晚", "凌晨"}:
        terms += ["crushed shadows", "overexposed highlights"]
    return ", ".join(dict.fromkeys(terms))


def generate_prompts(storyboard, script_analysis, assets_data):
    global_style = style_text(storyboard["visual_style"])
    dialogues = dialogue_map(script_analysis)
    scenes = {scene["scene_id"]: scene for scene in script_analysis.get("scenes", [])}
    assets_by_id = {asset["asset_id"]: asset for asset in assets_data.get("assets", [])}
    prompts = []
    for shot in storyboard.get("shots", []):
        dialogue = dialogues.get(shot.get("dialogue_id"))
        delivery = dialogue.get("delivery", "") if dialogue else ""
        dialogue_instruction = ""
        if dialogue:
            dialogue_instruction = f" The character delivers the line {delivery or 'naturally'}: {dialogue['text']}"
        action_text = " ".join(action.get("description", "") for action in shot.get("actions", [])).strip().rstrip(".")
        prompts.append({
            "shot_id": shot["shot_id"],
            "reference_assets": reference_assets_for_shot(shot, assets_by_id),
            "image_prompt": f"{global_style}. {shot['visual']} {shot['shot_size']}, {shot['camera_angle']}, cinematic composition, 16:9.",
            "video_prompt": (
                f"{global_style}. {shot['duration_seconds']}-second shot. {shot['shot_size']}, "
                f"{shot['camera_angle']}. {shot['camera_movement']}. {shot['visual']} {action_text}."
                f"{dialogue_instruction} Keep character appearance, clothing, props and scene layout consistent."
            ),
            "negative_prompt": dynamic_negative_prompt(shot, scenes.get(shot["scene_id"], {}), dialogue),
        })
    return {
        "format_version": storyboard["format_version"],
        "project_id": storyboard["project_id"],
        "visual_style": storyboard["visual_style"],
        "generation_mode": "deterministic_rules",
        "prompts": prompts,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate storyboard and video prompts.")
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--storyboard-output", required=True, type=Path)
    parser.add_argument("--prompts-output", required=True, type=Path)
    args = parser.parse_args()
    analysis = json.loads(args.analysis.read_text(encoding="utf-8-sig"))
    assets = json.loads(args.assets.read_text(encoding="utf-8-sig"))
    storyboard = generate_storyboard(analysis)
    prompts = generate_prompts(storyboard, analysis, assets)
    args.storyboard_output.parent.mkdir(parents=True, exist_ok=True)
    args.prompts_output.parent.mkdir(parents=True, exist_ok=True)
    args.storyboard_output.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.prompts_output.write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(storyboard['shots'])} shots and {len(prompts['prompts'])} prompt records.")


if __name__ == "__main__":
    main()

