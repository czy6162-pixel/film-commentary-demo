# 影视解说自动化 Skill（技能）

输入中文或标准格式英文短剧本，自动生成剧本解析、资产四视图、解说词、分镜和绘画及视频提示词四份 JSON（结构化数据格式）文件。

## 在线演示

- 演示网址：<https://czy6162-pixel.github.io/film-commentary-demo/>
- 代码仓库：<https://github.com/czy6162-pixel/film-commentary-demo>

不填写 API（应用程序接口）时，网页使用可复现的本地规则；完整填写服务地址、模型名称和访问密钥后，会真实调用兼容接口优化解说词和提示词。

## 命令行运行

环境要求：Python（编程语言）3.10 或更高版本，仅使用标准库。

```powershell
python scripts/run_pipeline.py `
  --input "examples/输入剧本.txt" `
  --output-dir "output" `
  --project-id "red_key_demo" `
  --style-name "悬疑电影写实风格"
```

生成 `script_analysis.json`、`assets.json`、`storyboard.json` 和 `prompts.json`。

## 中文示例复现

```powershell
python scripts/regenerate_examples.py
```

`examples/` 内随包结果全部由上述代码自动生成，不是人工填写，也未调用外部模型。详细说明见 [中文示例生成说明.md](中文示例生成说明.md)。

## 自动化测试

```powershell
python -m unittest discover -s tests -v
```

当前包含 19 项测试，覆盖多种中文和英文格式、四视图、解说词、镜头变化、动态负面词、资产引用和完整流水线。

## 交付内容

- `SKILL.md`：技能说明书和编排层。
- `开发者文档.md`：架构、部署、接口和扩展说明。
- `数据格式说明.md`：四份输出的字段契约。
- `scripts/`：解析、资产、分镜、接口和流水线代码。
- `tests/`：自动化测试。
- `examples/`：可复现的中文输入和输出。
- `第三阶段_端到端演示/`：网页与端到端运行结果。

项目生成结构化前期数据，不直接生成图片或视频。

