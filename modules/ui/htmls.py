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

/* --- 新增：功能卡片标题着色 (状态联动版) --- */
/* 高级选项 (始终蓝色) */
#acc_whisper_advanced > div > summary,
#acc_whisper_advanced .label-wrap {
    background-color: #eff6ff !important;
    color: #1e40af !important;
    border-radius: 8px 8px 0 0;
}

/* 开启状态色彩 (On) */
#acc_uvr_on > div > summary, #acc_uvr_on .label-wrap {
    background-color: #eff6ff !important; /* 淡蓝 */
    color: #1e40af !important;
    border-radius: 8px 8px 0 0;
}

#acc_vad_on > div > summary, #acc_vad_on .label-wrap {
    background-color: #f0fdf4 !important; /* 淡绿 */
    color: #166534 !important;
    border-radius: 8px 8px 0 0;
}

#acc_diarization_on > div > summary, #acc_diarization_on .label-wrap {
    background-color: #f5f3ff !important; /* 淡紫 */
    color: #5b21b6 !important;
    border-radius: 8px 8px 0 0;
}

/* 关闭状态色彩 (Off - 统一灰色) */
#acc_uvr_off > div > summary, #acc_uvr_off .label-wrap,
#acc_vad_off > div > summary, #acc_vad_off .label-wrap,
#acc_diarization_off > div > summary, #acc_diarization_off .label-wrap {
    background-color: #f3f4f6 !important; /* 浅灰 */
    color: #6b7280 !important;
    border-radius: 8px 8px 0 0;
}

/* 统一手风琴标题样式增强 */
summary {
    font-weight: 700 !important;
    padding: 10px 15px !important;
    cursor: pointer;
    transition: all 0.2s ease-in-out !important;
}
summary:hover {
    filter: brightness(0.95);
}

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