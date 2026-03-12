CSS = """
@font-face {
    font-family: 'Barlow';
    src: url('file/resources/fonts/Barlow-Regular.ttf') format('truetype');
}
@font-face {
    font-family: 'Noto Sans SC';
    src: url('file/resources/fonts/NotoSansSC-Regular.ttf') format('truetype');
}

body, .gradio-container, * {
    font-family: 'Barlow', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
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

/* Transcript Styles */
.transcript-container {
    padding: 30px;
    background: #fdfdfd;
    border-radius: 12px;
    max-height: 800px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    /* 移除 gap，交给内部的 topic-section 控制 */
    border: 1px solid #f0f0f0;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
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