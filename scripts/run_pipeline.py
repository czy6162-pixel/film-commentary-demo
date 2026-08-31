import argparse
import json
import os
from pathlib import Path

from generate_assets import generate_assets
from generate_storyboard import generate_prompts, generate_storyboard
from llm_client import enhance_with_api
from parse_script import parse_script


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_pipeline(input_path, output_dir, project_id, visual_style, api_config=None):
    script_analysis = parse_script(input_path, project_id, visual_style)
    assets = generate_assets(script_analysis)
    storyboard = generate_storyboard(script_analysis)
    prompts = generate_prompts(storyboard, script_analysis, assets)

    if api_config:
        storyboard, prompts = enhance_with_api(
            storyboard,
            prompts,
            api_config["base_url"],
            api_config["api_key"],
            api_config["model"],
            api_config.get("timeout", 45),
        )

    outputs = {
        "script_analysis.json": script_analysis,
        "assets.json": assets,
        "storyboard.json": storyboard,
        "prompts.json": prompts,
    }
    for filename, data in outputs.items():
        write_json(output_dir / filename, data)

    return outputs


def main():
    parser = argparse.ArgumentParser(
        description="Run the minimum screenplay-to-video-prompt pipeline."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--project-id", default="project_001")
    parser.add_argument("--style-name", default="Classic mystery film")
    parser.add_argument(
        "--rendering",
        default="Realistic cinematic photography with subtle film grain",
    )
    parser.add_argument(
        "--color-palette",
        default="Muted cool colors with restrained warm highlights",
    )
    parser.add_argument("--period", default="1960s European resort")
    parser.add_argument("--lighting", default="Natural daylight with soft contrast")
    parser.add_argument("--api-base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-model", default="")
    parser.add_argument("--api-timeout", type=int, default=45)
    args = parser.parse_args()

    visual_style = {
        "style_name": args.style_name,
        "rendering": args.rendering,
        "color_palette": args.color_palette,
        "period": args.period,
        "lighting": args.lighting,
    }
    api_values = {
        "base_url": args.api_base_url.strip(),
        "api_key": (args.api_key or os.environ.get("FILM_API_KEY", "")).strip(),
        "model": args.api_model.strip(),
        "timeout": args.api_timeout,
    }
    configured = [api_values["base_url"], api_values["api_key"], api_values["model"]]
    if any(configured) and not all(configured):
        parser.error("API mode requires --api-base-url, --api-model and --api-key or FILM_API_KEY.")
    api_config = api_values if all(configured) else None

    outputs = run_pipeline(
        args.input,
        args.output_dir,
        args.project_id,
        visual_style,
        api_config,
    )

    analysis = outputs["script_analysis.json"]
    print(
        f"Pipeline completed: {len(analysis['characters'])} characters, "
        f"{len(analysis['scenes'])} scenes, "
        f"{len(outputs['assets.json']['assets'])} assets, "
        f"{len(outputs['storyboard.json']['shots'])} shots, "
        f"{len(outputs['prompts.json']['prompts'])} prompts."
    )
    print(f"Output directory: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()

