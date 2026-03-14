CSS = """
@font-face {
    font-family: 'Barlow';
    src: url('file/resources/fonts/Barlow-Regular.ttf') format('truetype');
}
body, .gradio-container, * {
  font-family: 'Barlow', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}

.bmc-button {
    padding: 2px 5px;
    border-radius: 5px;
    background-color: #FF813F;
    color: white;
    box-shadow: 0px 1px 2px rgba(0, 0, 0, 0.3);
    text-decoration: none;
    display: inline-block;
    font-size: 20px;
    margin: 2px;
    cursor: pointer;
    -webkit-transition: background-color 0.3s ease;
    -ms-transition: background-color 0.3s ease;
    transition: background-color 0.3s ease;
}
.bmc-button:hover,
.bmc-button:active,
.bmc-button:focus {
    background-color: #FF5633;
}
.markdown {
    margin-bottom: 0;
    padding-bottom: 0;
}
.tabs {
    margin-top: 0;
    padding-top: 0;
}

#md_project a {
  color: black;
  text-decoration: none;
}
#md_project a:hover {
  text-decoration: underline;
}

/* --- Minimal Premium UI 核心系统 --- */
:root {
    --primary-color: #2563eb;
    --success-color: #10b981;
    --gray-color: #94a3b8;
    --border-color: #e2e8f0;
    --bg-soft: #f8fafc;
}

/* 统一手风琴标题样式：移除大面积背景，增加呼吸感 */
summary {
    font-weight: 600 !important;
    padding: 12px 16px !important;
    color: #334155 !important;
    background: white !important;
    border-bottom: 1px solid transparent;
    transition: all 0.2s ease;
    display: flex !important;
    align-items: center;
    gap: 8px;
}

summary:hover {
    background: var(--bg-soft) !important;
}

/* 状态灯 (Status Pillars) - 替代繁琐文字 */
.status-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-left: auto; /* 置右 */
}

.status-on {
    background-color: #dcfce7 !important;
    color: #166534 !important;
}

.status-off {
    background-color: #f1f5f9 !important;
    color: #64748b !important;
}

/* 容器美化：轻边框、柔投影 */
.gradio-container {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

.gr-box, .gr-panel {
    border: 1px solid var(--border-color) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1) !important;
}

/* 移除输入框内部标签 (Gradio 默认 Textbox 标题) */
.gr-textbox label {
    display: none !important;
}

/* AI 整理区核心标识：微妙的左侧色条 */
#acc_ai_post_processing {
    border-left: 4px solid #f97316 !important;
}

#acc_whisper_advanced { border-left: 4px solid #3b82f6 !important; }
#acc_uvr { border-left: 4px solid #8b5cf6 !important; }
#acc_vad { border-left: 4px solid #10b981 !important; }
#acc_diarization { border-left: 4px solid #f43f5e !important; }

.transcript-container {
    padding: 30px;
    background: #fdfdfd;
    border-radius: 12px;
    max-height: 800px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    border: 1px solid #f0f0f0;
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
}
.topic-section {
    display: flex;
    flex-direction: column;
    gap: 32px;
    margin-bottom: 40px;
}
.transcript-item {
    display: flex;
    gap: 20px;
    align-items: flex-start;
}
.speaker-avatar {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    color: white;
    flex-shrink: 0;
    font-size: 1.3rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.speaker-body {
    flex-grow: 1;
    padding-top: 2px;
}
.speaker-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}
.speaker-name {
    font-weight: 600;
    color: #4b5563;
    font-size: 1rem;
}
.speaker-text {
    color: #1f2937;
    line-height: 1.8;
    font-size: 1.05rem;
    white-space: pre-wrap;
    text-align: justify;
}
.topic-tag {
    align-self: center;
    background: rgba(239, 246, 255, 0.98);
    color: #2563eb;
    padding: 12px 40px;
    border-radius: 9999px;
    font-weight: 800;
    font-size: 1.05rem;
    margin: 15px 0;
    border: 2px solid #3b82f6;
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.2);
    position: sticky;
    top: 5px; /* 距离容器顶部一点距离，看起来更悬浮 */
    z-index: 100;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    width: fit-content;
    max-width: 90% ;
    text-align: center;
}
"""

MARKDOWN = """
### [Whisper-WebUI](https://github.com/jhj0517/Whsiper-WebUI)
"""


NLLB_VRAM_TABLE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    table {
      border-collapse: collapse;
      width: 100%;
    }
    th, td {
      border: 1px solid #dddddd;
      text-align: left;
      padding: 8px;
    }
    th {
      background-color: #f2f2f2;
    }
  </style>
</head>
<body>

<details>
  <summary>VRAM usage for each model</summary>
  <table>
    <thead>
      <tr>
        <th>Model name</th>
        <th>Required VRAM</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>nllb-200-3.3B</td>
        <td>~16GB</td>
      </tr>
      <tr>
        <td>nllb-200-1.3B</td>
        <td>~8GB</td>
      </tr>
      <tr>
        <td>nllb-200-distilled-600M</td>
        <td>~4GB</td>
      </tr>
    </tbody>
  </table>
  <p><strong>Note:</strong> Be mindful of your VRAM! The table above provides an approximate VRAM usage for each model.</p>
</details>

</body>
</html>
"""