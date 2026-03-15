from typing import List

def format_refined_text_to_html(text: str) -> str:
    """
    将 LLM 处理后的文本转换为精美的 HTML 格式，包含说话人头像、颜色标识及话题标签。
    """
    if not text or text.startswith("Error"):
        return f"<div style='color: red; padding: 20px;'>{text}</div>"
    
    # 颜色与图标库
    colors = ["#f87171", "#fbbf24", "#34d399", "#60a5fa", "#a78bfa", "#f472b6"]
    icons = ["👤", "🐧", "🌟", "🍀", "💎", "🔥"]
    
    html = '<div class="transcript-container">'
    
    lines = text.split('\n')
    current_speaker = None
    current_content = []
    
    def flush_message(speaker, content_list):
        if not speaker or not content_list:
            return ""
        
        try:
            # 提取数字，例如 SPEAKER_01 -> 1
            idx_str = ''.join(filter(str.isdigit, speaker))
            idx = int(idx_str) if idx_str else 0
        except:
            idx = 0
            
        color = colors[idx % len(colors)]
        icon = icons[idx % len(icons)]
        name = f"发言人 {idx}"
        content = "\n".join(content_list).strip()
        
        if not content: return ""
        
        # 针对 HTML 预览的基础清理，防止 XSS
        safe_content = content.replace('<', '&lt;').replace('>', '&gt;')
        
        return f"""
        <div class="transcript-item">
            <div class="speaker-avatar" style="background-color: {color}">{icon}</div>
            <div class="speaker-body">
                <div class="speaker-header">
                    <span class="speaker-name">{name}</span>
                </div>
                <div class="speaker-text">{safe_content}</div>
            </div>
        </div>
        """

    section_started = False
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 处理话题/核心议题标签
        if (line.startswith('【') and '】' in line) or line.startswith('###'):
            # 先把当前正在记录的消息刷新掉
            msg_html = flush_message(current_speaker, current_content)
            
            # 如果已经在一个话题块里，先闭合它
            if section_started:
                html += msg_html + '</div>'
            else:
                html += msg_html
                
            current_speaker = None
            current_content = []
            
            # 开启新的话题块容器，这样 sticky header 就能“推走”旧的
            topic = line.strip('【】# ')
            html += '<div class="topic-section">'
            html += f'<div class="topic-tag">{topic}</div>'
            section_started = True
            continue
            
        # 处理说话人标签 SPEAKER_XX|
        if '|' in line and line.startswith('SPEAKER_'):
            parts = line.split('|', 1)
            speaker_tag = parts[0]
            content = parts[1] if len(parts) > 1 else ""
            
            if speaker_tag == current_speaker:
                current_content.append(content)
            else:
                html += flush_message(current_speaker, current_content)
                current_speaker = speaker_tag
                current_content = [content]
        else:
            if current_speaker:
                current_content.append(line)
            else:
                # 没有任何标签的孤立行，直接作为普通文本
                html += f'<div class="speaker-text" style="margin-left: 64px; margin-bottom: 20px;">{line}</div>'

    # 结束后的清理
    html += flush_message(current_speaker, current_content)
    if section_started:
        html += '</div>'
    
    html += '</div>'
    return html
