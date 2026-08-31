import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_assets import generate_assets
from generate_storyboard import generate_prompts, generate_storyboard
from llm_client import apply_enhancement, chat_completions_url, extract_json
from parse_script import parse_script_text
from run_pipeline import run_pipeline


STYLE = {
    "style_name": "悬疑电影写实风格",
    "rendering": "写实电影摄影",
    "color_palette": "低饱和冷色",
    "period": "当代",
    "lighting": "电影照明",
}

ZH_TWO_SCENES = """《红色钥匙》

场景一：旧公寓客厅，夜，室内
林夏推门进入客厅，手里攥着一把红色钥匙。张叔站在落地钟旁。
张叔（低声）：你终于回来了。
林夏：这把钥匙能打开什么？

场景二：走廊，夜，室内
林夏用红色钥匙打开小门，一只木盒出现在门后。
林夏（紧张）：这里面是什么？
"""


def build(text=ZH_TWO_SCENES):
    analysis = parse_script_text(text, "test_project", STYLE)
    assets = generate_assets(analysis)
    storyboard = generate_storyboard(analysis)
    prompts = generate_prompts(storyboard, analysis, assets)
    return analysis, assets, storyboard, prompts


class PipelineTests(unittest.TestCase):
    def test_01_chinese_numbered_scene_headings(self):
        analysis, _, _, _ = build()
        self.assertEqual(analysis["source_language"], "zh")
        self.assertEqual(len(analysis["scenes"]), 2)

    def test_02_chinese_first_scene_heading(self):
        text = "第一场：医院走廊，日，室内\n医生：检查结果出来了。"
        analysis, _, _, _ = build(text)
        self.assertEqual(analysis["scenes"][0]["location"], "医院走廊")

    def test_03_chinese_without_heading_uses_default_scene(self):
        text = "《电话》\n小周拿起手机。\n小周：喂，你好。"
        analysis, _, _, _ = build(text)
        self.assertEqual(analysis["scenes"][0]["location"], "未命名场景")

    def test_04_chinese_delivery_is_extracted(self):
        analysis, _, _, _ = build()
        dialogue = analysis["scenes"][0]["dialogues"][0]
        self.assertEqual(dialogue["delivery"], "低声")

    def test_05_standard_english_screenplay(self):
        text = """TITLE: The Call
INT. OFFICE - NIGHT
MAYA enters with a phone.
MAYA
(nervous)
We need to leave now.
"""
        analysis, _, storyboard, _ = build(text)
        self.assertEqual(analysis["source_language"], "en")
        self.assertEqual(analysis["characters"][0]["name"], "Maya")
        self.assertEqual(storyboard["shots"][1]["dialogue_id"], "dialogue_001")

    def test_06_english_delivery_is_extracted(self):
        text = "INT. ROOM - DAY\nJOHN\n(whispering)\nDo not move."
        analysis, _, _, _ = build(text)
        self.assertEqual(analysis["scenes"][0]["dialogues"][0]["delivery"], "whispering")

    def test_07_longest_prop_name_wins(self):
        analysis, _, _, _ = build()
        names = [prop["name"] for prop in analysis["props"]]
        self.assertIn("红色钥匙", names)
        self.assertNotIn("钥匙", names)

    def test_08_actions_keep_performer_ids(self):
        analysis, _, _, _ = build()
        performer_ids = {a["character_id"] for a in analysis["scenes"][0]["actions"]}
        self.assertIn("char_002", performer_ids)

    def test_09_each_asset_has_four_views(self):
        _, assets, _, _ = build()
        self.assertTrue(assets["assets"])
        self.assertTrue(all(len(asset["views"]) == 4 for asset in assets["assets"]))

    def test_10_global_style_reaches_every_asset_prompt(self):
        _, assets, _, _ = build()
        self.assertTrue(
            all(STYLE["style_name"] in view["prompt"] for asset in assets["assets"] for view in asset["views"])
        )

    def test_11_narration_is_never_empty(self):
        _, _, storyboard, _ = build()
        self.assertTrue(all(shot["narration"].strip() for shot in storyboard["shots"]))

    def test_12_dialogue_camera_plans_vary(self):
        _, _, storyboard, _ = build()
        dialogue_shots = [shot for shot in storyboard["shots"] if shot["dialogue_id"]]
        plans = {(s["shot_size"], s["camera_angle"], s["camera_movement"]) for s in dialogue_shots}
        self.assertGreaterEqual(len(plans), 3)

    def test_13_negative_prompts_change_by_shot(self):
        _, _, _, prompts = build()
        negatives = {prompt["negative_prompt"] for prompt in prompts["prompts"]}
        self.assertGreater(len(negatives), 1)

    def test_14_reference_asset_view_ids_are_valid(self):
        _, assets, _, prompts = build()
        valid = {
            (asset["asset_id"], view["view_id"])
            for asset in assets["assets"]
            for view in asset["views"]
        }
        for prompt in prompts["prompts"]:
            for ref in prompt["reference_assets"]:
                self.assertIn((ref["asset_id"], ref["view_id"]), valid)

    def test_15_full_chinese_pipeline_writes_four_json_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "短剧本.txt"
            output_dir = Path(temp_dir) / "output"
            input_path.write_text(ZH_TWO_SCENES, encoding="utf-8")
            run_pipeline(input_path, output_dir, "e2e", STYLE)
            files = {path.name for path in output_dir.glob("*.json")}
            self.assertEqual(files, {"script_analysis.json", "assets.json", "storyboard.json", "prompts.json"})
            storyboard = json.loads((output_dir / "storyboard.json").read_text(encoding="utf-8"))
            self.assertTrue(all(shot["narration"] for shot in storyboard["shots"]))

    def test_16_unsupported_english_text_is_rejected(self):
        with self.assertRaises(ValueError):
            build("This is prose without a screenplay scene heading.")

    def test_17_api_url_is_normalized(self):
        self.assertEqual(chat_completions_url("https://example.com/v1"), "https://example.com/v1/chat/completions")
        self.assertEqual(chat_completions_url("https://example.com/v1/chat/completions"), "https://example.com/v1/chat/completions")

    def test_18_api_json_code_fence_is_accepted(self):
        data = extract_json("```json\n{\"shots\": [], \"prompts\": []}\n```")
        self.assertEqual(data["shots"], [])

    def test_19_api_enhancement_updates_only_known_ids(self):
        _, _, storyboard, prompts = build()
        first_id = storyboard["shots"][0]["shot_id"]
        response = {
            "shots": [{"shot_id": first_id, "narration": "新的解说词"}, {"shot_id": "missing", "narration": "错误"}],
            "prompts": [{"shot_id": first_id, "negative_prompt": "dynamic negative"}],
        }
        apply_enhancement(storyboard, prompts, response)
        self.assertEqual(storyboard["shots"][0]["narration"], "新的解说词")
        self.assertEqual(prompts["prompts"][0]["negative_prompt"], "dynamic negative")
        self.assertEqual(storyboard["narration_generation"]["mode"], "api_enhanced")


if __name__ == "__main__":
    unittest.main()

