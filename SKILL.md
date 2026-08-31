---
name: film-commentary-automation
description: Parse short Chinese or standard English screenplays and generate reproducible character, scene, prop, four-view asset, narration, storyboard, image-prompt, and video-prompt JSON data. Use when converting a screenplay into film pre-production data, optionally enhanced through an OpenAI-compatible API; it does not render images or videos.
---

# Film Commentary Automation（影视解说自动化）

把中文或标准格式英文短剧本转换成四份相互关联的 JSON（结构化数据格式）文件。默认采用确定性规则，可离线运行并复现；用户完整配置 API（应用程序接口）后，可真实调用兼容服务优化解说词和提示词。

## 输入要求

- 使用 UTF-8（统一字符编码）文本文件。
- 中文对白使用“角色：对白”或“角色（表演提示）：对白”；场景标题可使用“场景一：地点，时间，室内”或“第一场：地点”。无场景标题时按一个默认场景解析。
- 英文场景标题以 `INT.`、`EXT.`、`INT/EXT.`、`EXT/INT.` 或 `I/E.` 开头；角色提示行使用大写字母。
- 需要一个输出目录、项目编号和全局视觉风格。

## 运行工作流

```powershell
python scripts/run_pipeline.py `
  --input "examples/输入剧本.txt" `
  --output-dir "output" `
  --project-id "red_key_demo" `
  --style-name "悬疑电影写实风格" `
  --rendering "写实电影摄影，轻微胶片颗粒" `
  --color-palette "低饱和冷色，红色作为视觉强调" `
  --period "当代旧公寓" `
  --lighting "夜间低调照明，柔和阴影"
```

必须依次执行：剧本解析、四视图资产数据生成、分镜与解说词生成、绘画及视频提示词生成。

## 可选模型优化

默认模式不需要 API（应用程序接口）。如需调用 OpenAI-compatible API（兼容 OpenAI 格式的应用程序接口），同时提供服务地址、模型和密钥：

```powershell
$env:FILM_API_KEY="用户自己的密钥"
python scripts/run_pipeline.py --input "examples/输入剧本.txt" --output-dir "output_api" `
  --api-base-url "https://服务地址/v1" --api-model "模型名称"
```

密钥不得写入输出文件或项目源码。接口返回结果只能覆盖已存在的 `shot_id`（镜头编号）。

## 输出约束

- `script_analysis.json`：标题、语言、全局视觉风格、角色、道具、场景、动作和对白。
- `assets.json`：每个角色、场景和道具恰好四个文字视图。
- `storyboard.json`：有序分镜、非空解说词、镜头变化和对白关联。
- `prompts.json`：逐镜头绘画、视频、动态负面提示词及 `{asset_id, view_id}` 精确引用。

四个文件的 `project_id`（项目编号）和 `visual_style`（全局视觉风格）必须一致，所有引用必须存在。字段契约见 [数据格式说明.md](数据格式说明.md)。

## 验证

```powershell
python -m unittest discover -s tests -v
python scripts/regenerate_examples.py
```

本技能只生成影视前期结构化文字数据，不直接渲染图片或视频。

