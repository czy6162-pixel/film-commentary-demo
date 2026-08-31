import argparse
import json
from pathlib import Path


VIEW_DEFINITIONS = {
    "character": [
        ("front", "Front view", "front full-body view"),
        ("three_quarter", "Three-quarter view", "three-quarter full-body view"),
        ("side", "Side view", "left side full-body view"),
        ("back", "Back view", "back full-body view"),
    ],
    "scene": [
        ("main", "Main view", "main establishing view from the entrance"),
        ("reverse", "Reverse view", "reverse view facing the entrance"),
        ("side", "Side view", "side view showing spatial depth"),
        ("top", "Top layout", "top-down layout view"),
    ],
    "prop": [
        ("front", "Front view", "front product view"),
        ("three_quarter", "Three-quarter view", "three-quarter product view"),
        ("side", "Side view", "left side product view"),
        ("back", "Back view", "back product view"),
    ],
}


def style_text(visual_style):
    return ", ".join(
        str(visual_style.get(field, "")).strip()
        for field in (
            "style_name",
            "rendering",
            "color_palette",
            "period",
            "lighting",
        )
        if str(visual_style.get(field, "")).strip()
    )


def build_views(asset_type, name, consistency_description, visual_style):
    global_style = style_text(visual_style)
    views = []
    for view_id, view_name, view_instruction in VIEW_DEFINITIONS[asset_type]:
        if asset_type == "character":
            framing = "neutral pose, consistent face, body shape, hair and clothing, plain background"
        elif asset_type == "scene":
            framing = "no characters, consistent architecture, furniture, entrances and lighting"
        else:
            framing = "centered object, consistent shape, material, color and wear, plain background"
        views.append(
            {
                "view_id": view_id,
                "view_name": view_name,
                "prompt": (
                    f"{global_style}. {name}: {consistency_description}. "
                    f"{view_instruction}, {framing}."
                ),
            }
        )
    return views


def character_scene_ids(character_id, scenes):
    return [
        scene["scene_id"]
        for scene in scenes
        if character_id in scene.get("character_ids", [])
    ]


def generate_assets(script_analysis):
    visual_style = script_analysis["visual_style"]
    scenes = script_analysis.get("scenes", [])
    assets = []

    for character in script_analysis.get("characters", []):
        description = character.get("description", "").strip() or character["name"]
        assets.append(
            {
                "asset_id": character["character_id"],
                "asset_type": "character",
                "name": character["name"],
                "source_scene_ids": character_scene_ids(
                    character["character_id"], scenes
                ),
                "consistency_description": description,
                "views": build_views(
                    "character", character["name"], description, visual_style
                ),
            }
        )

    for scene in scenes:
        description_parts = [scene.get("location", ""), scene.get("summary", "")]
        description = ". ".join(
            part.strip().rstrip(".") for part in description_parts if part.strip()
        )
        assets.append(
            {
                "asset_id": scene["scene_id"],
                "asset_type": "scene",
                "name": scene.get("location", scene["heading"]),
                "source_scene_ids": [scene["scene_id"]],
                "consistency_description": description,
                "views": build_views(
                    "scene", scene.get("location", scene["heading"]), description, visual_style
                ),
            }
        )

    for prop in script_analysis.get("props", []):
        description = prop.get("description", "").strip() or prop["name"]
        assets.append(
            {
                "asset_id": prop["prop_id"],
                "asset_type": "prop",
                "name": prop["name"],
                "source_scene_ids": prop.get("scene_ids", []),
                "consistency_description": description,
                "views": build_views("prop", prop["name"], description, visual_style),
            }
        )

    return {
        "format_version": script_analysis["format_version"],
        "project_id": script_analysis["project_id"],
        "visual_style": visual_style,
        "assets": assets,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate four-view asset data from script analysis."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    script_analysis = json.loads(args.input.read_text(encoding="utf-8-sig"))
    result = generate_assets(script_analysis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    counts = {
        asset_type: sum(
            1 for asset in result["assets"] if asset["asset_type"] == asset_type
        )
        for asset_type in VIEW_DEFINITIONS
    }
    print(
        f"Generated {len(result['assets'])} assets: "
        f"{counts['character']} characters, {counts['scene']} scenes, "
        f"{counts['prop']} props."
    )


if __name__ == "__main__":
    main()

