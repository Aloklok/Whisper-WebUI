# Outputs 和 AI 整理说明

此文档描述本项目在“AI 一键整理/生成字幕/导出 PDF”相关的输出行为，便于定位生成结果位置。

## 输出目录规则
- 所有 AI 生成的文件（包含：AI 润色后的 TXT、HTML（美化版）、PDF）默认保存在项目根目录下的 `outputs/<name>/` 目录中。
- `<name>` 的来源优先级：
  1. 若存在与转写文件对应的原始 MP3，则使用 MP3 的文件名（去掉 `podcast_tmp_` 前缀后作为目录名）。
  2. 否则使用转写 TXT 的基础文件名（同样会去掉 `podcast_tmp_` 前缀）。
- 例如：原始 MP3 名为 `podcast_tmp_E228谷歌TPU能撼动英伟达吗前TPU工程师首次揭秘.mp3`，则输出目录为：
  `outputs/E228谷歌TPU能撼动英伟达吗前TPU工程师首次揭秘/`。

## 生成的文件名
- TXT: `<clean_name>_AI_Refined.txt`
- HTML: `<clean_name>_AI_Refined_Pretty.html`
- PDF: `<clean_name>_AI_Refined.pdf`

其中 `<clean_name>` 表示去掉 `podcast_tmp_` 后的基础名（同时会进行文件名安全化处理以避免非法字符）。

## 字幕/转写文件（SRT/VTT/txt 等）
- 使用 `生成字幕文件` 功能时，默认也会将字幕输出到 `outputs/<clean_name>/` 目录（除非你勾选了“保存到与输入相同目录”选项）。
- generate_file 在写文件前会自动创建目录，避免因目录不存在而抛出错误。

## PDF 字体行为（中文显示）
- PDF 优先使用 `Barlow` 字体（用于英文与 UI 风格一致）；当遇到中文字符时，若系统中存在 `NotoSansSC-Regular.ttf`，会作为回退字体使用，以确保中文字符能够正确显示，而不会出现黑框。
- 字体文件位于 `resources/fonts/` 下，xhtml2pdf/pisa 对字体的查找依赖文件路径，代码已尝试注册并通过 `@font-face` 指定本地路径以提高兼容性。

## 日志与用户提示
- 启动转写/AI 流程时，控制台会以清晰的分块打印参数信息：
  - `===== 参数设置 =====`（超参逐行列出，例如 MODEL、BEAM SIZE、BATCH SIZE）
  - `===== 功能设置 =====`（功能开关逐行列出，例如 翻译/VAD/分说话人）
  - `===== 参数说明 =====`（为常用超参给出简短建议，例如：针对 GTX 1660 Ti（6GB）推荐 BEAM SIZE=1–2、BATCH SIZE=1、COMPUTE=int8）

## 兼容性与注意事项
- 若输出目录名中包含操作系统不允许的字符（例如 Windows 下的 `<>:"/\|?*`），系统会把这些字符替换为下划线以保证路径有效。
- 如果希望输出使用原始 MP3 的完整元信息（如发布时间、来源站点等）作为目录名或文件名前缀，可提出需求，我可以把额外的元数据写入输出目录结构。

## 常见问题
- 问：我看到了黑框或中文不能显示？
  - 答：请确认 `resources/fonts/NotoSansSC-Regular.ttf` 是否存在；若不存在，PDF 会优先使用 Barlow，中文可能无法显示。可以把 Noto 字体放入 `resources/fonts/` 后重新生成 PDF。

---
文档由本仓库自动更新脚本生成的补充说明。如需合入项目 README，可手动合并或请求我替你把这节附加到 `README.md`。
