# Whisper-WebUI (中文定制版)

本项目是基于 [Whisper](https://github.com/openai/whisper) 的 Gradio 浏览器界面，专为中文播客转录和中端显卡优化。

![screen](https://github.com/user-attachments/assets/caea3afd-a73c-40af-a347-8d57914b1d0f)

## 功能特性
- **多种 Whisper 引擎切换**：
   - [openai/whisper](https://github.com/openai/whisper)
   - [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) (默认使用)
   - [Vaibhavs10/insanely-fast-whisper](https://github.com/Vaibhavs10/insanely-fast-whisper) (在此 Fork 版中支持 **投机采样** 加速)
- **多源音频输入**：
   - 本地文件上传
   - YouTube 链接
   - **小宇宙播客 (xiaoyuzhoufm.com) 直接解析下载** (新增)
   - 麦克风录音
- **辅助功能**：
   - **一键清理缓存**：保持磁盘整洁。
   - 说话人分离 (Speaker Diarization)：基于 pyannote 模型。
   - 语音活动检测 (VAD)：裁剪静音，提高识别效率。
   - 背景音乐去除 (UVR)：在转录前分离背景音。

## 安装与运行

### 本地运行
1. 克隆仓库。
2. 运行 `install.bat` 安装依赖（建议 Python 3.10-3.12）。
3. 运行 `start-webui.bat` 开启常规模式，或运行 `start-insanely-fast.bat` 开启 **投机采样极速模式**。

## 显存使用情况 (VRAM Usages)

本项目默认集成 `faster-whisper` 以降低显存占用。

### 推荐模型排序与说明

为了方便选择，我已将下拉框重新排序并添加了“标签胶囊”：
1. **🚀 large-v3-turbo**：2024年9月发布。**目前最推荐**，兼顾极速与极高准度。
2. **⚡ turbo**：OpenAI 官方极谏版，速度最快。
3. **🥇 large-v3**：2023年11月旗舰。追求极致准度（速度稍慢）的首选。
4. **⚖️ medium/small**：显存不足 8GB 时的阶梯选择。

> [!TIP]
> 针对中文播客，建议优先尝试 `large-v3-turbo`，效果往往令人惊喜。

| 实现方式 | 精度 | Beam size | 时间 | 最大 GPU 显存 | 最大 CPU 内存 |
|-------------------|-----------|-----------|-------|-----------------|-----------------|
| openai/whisper    | fp16      | 5         | 4m30s | 11325MB         | 9439MB          |
| faster-whisper    | fp16      | 5         | 54s   | 4755MB          | 3244MB          |

想要使用投机采样，请使用：
```shell
python app.py --whisper_type insanely_fast_whisper
```
或直接运行 `start-insanely-fast.bat`。

## 开发者说明
有关更多 CLI 参数配置，请参考 [Wiki](https://github.com/jhj0517/Whisper-WebUI/wiki/Command-Line-Arguments)。
本项目特别针对 GTX 1660 Ti (6GB) 进行了优化，详情请见 [FORK_CHANGES.md](file:///d:/Whisper-WebUI/FORK_CHANGES.md)。
