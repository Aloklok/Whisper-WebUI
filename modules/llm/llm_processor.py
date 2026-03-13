import os
import logging
import traceback
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from modules.utils.logger import get_logger

logger = get_logger()

class LLMProcessor:
    def __init__(self, api_base: str, api_key: str, model: str, prompt: str, reasoning: bool = False):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.prompt = prompt
        self.reasoning = reasoning
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_base)

    def split_text(self, text: str, chunk_size: int = 3500) -> List[str]:
        """
        基于 SPEAKER 标签进行智能切分。尽量不在说话人中间断开。
        """
        if not text:
            return []
            
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            # 基础切分点
            end = min(start + chunk_size, len(text))
            
            # 在切分点附近寻找 SPEAKER_ 标签进行智能对齐
            if end < len(text):
                # 向前寻找最近的 SPEAKER_ (搜索范围限定在 chunk_size 的后 20%)
                search_range = min(1000, chunk_size // 2) 
                search_start = max(start, end - search_range)
                last_speaker_pos = text.rfind('SPEAKER_', search_start, end)
                
                if last_speaker_pos != -1 and last_speaker_pos > start:
                    # 找到了说话人标签，从这里切断
                    end = last_speaker_pos
                else:
                    # 没找到标签，退而求其次找换行符
                    last_newline = text.rfind('\n', start, end)
                    if last_newline != -1 and last_newline > start + (chunk_size // 2):
                        end = last_newline + 1
            
            # 强制安全检查：确保 end 始终大于 start，防止死循环
            if end <= start:
                end = start + chunk_size
                
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                
            if end >= len(text):
                break
            start = end
        return chunks

    def _process_chunk(self, chunk: str, index: int, total: int, context: str = "") -> str:
        """
        处理单个分段。
        """
        try:
            logger.info(f"AI 正在处理第 {index+1}/{total} 段...")
            
            # 1. 清理基础提示词，移除可能导致模型误解的引导语
            clean_prompt = self.prompt.replace("待整理文本：", "").strip()

            # 2. 构造更加“隐形”的衔接信息
            context_hint = ""
            if context:
                context_hint = f"（前文衔接参考：...{context}。请注意语义连贯，但严禁在输出中重复此背景内容。）\n\n"
            
            # 3. 构造 User 内容：使用明确的界定符隔离指令与正文
            full_user_content = (
                f"{clean_prompt}\n\n"
                f"{context_hint}"
                f"--- 以下为本次需处理的转录正文 ---\n"
                f"{chunk}\n"
                f"--- 正文结束 ---"
            )

            # 根据推理开关调整参数
            api_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一位专业的播客文字编辑。你只需直接输出整理润色后的文本。注意：必须保留原始文本中的 SPEAKER_XX 标签，不要删除它们。严禁输出任何任务说明、确认信息或界定符。直接从润色后的第一句话开始。"},
                    {"role": "user", "content": full_user_content}
                ],
                "temperature": 0.7 if not self.reasoning else 0.6, # 推理模式通常建议略低温度
                "max_tokens": 4096
            }

            response = self.client.chat.completions.create(**api_kwargs)
            
            if not response.choices or len(response.choices) == 0:
                logger.error(f"第 {index+1} 段响应异常: {response}")
                return chunk

            choice = response.choices[0]
            content = ""
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                content = choice.message.content
            elif isinstance(choice, dict) and 'message' in choice:
                content = choice['message'].get('content', "")

            if not content:
                logger.warning(f"第 {index+1} 段润色结果为空内容，保留原文。")
                return chunk
            
            # 4. 极其重要：清理掉可能被模型带出来的所有辅助标签
            clean_content = content.strip()
            # 移除常见的指令回显前缀
            prefixes_to_remove = ["待整理文本：", "--- 以下为本次需处理的转录正文 ---", "--- 正文结束 ---", "【润色后的文本】"]
            for prefix in prefixes_to_remove:
                if clean_content.startswith(prefix):
                    clean_content = clean_content.replace(prefix, "", 1).strip()
            
            return clean_content

        except Exception as e:
            logger.error(f"处理第 {index+1} 段时发生错误: {e}")
            return chunk # 错误时回退到原文

    def process_text(self, text: str, progress_callback=None) -> Optional[str]:
        """
        并行处理文本，利用多线程极大提升速度。
        """
        if not self.api_key:
            logger.error("LLM API Key 未设置，请在设置中配置。")
            return "Error: API Key is missing."

        if not text or not text.strip():
            logger.warning("待处理文本为空。")
            return "文本内容为空，无需处理。"

        # 1. 智能切分
        chunks = self.split_text(text, chunk_size=3500)
        if not chunks:
            return "文本内容为空，无需处理。"
        
        num_chunks = len(chunks)
        logger.info(f"开始并行处理 AI 润色，共 {num_chunks} 段...")
        
        # 准备每一段的衔接背景 (前一段原文的最后 300 字)
        contexts = [""]
        for i in range(num_chunks - 1):
            prev_chunk = chunks[i]
            contexts.append(prev_chunk[-300:] if len(prev_chunk) > 300 else prev_chunk)

        # 2. 并发执行
        results = [None] * num_chunks
        completed_count = 0
        
        # 使用线程池并发调用 API
        # 建议线程数不要过高，防止触发 API 速率限制 (SiliconFlow 建议 3-5 并发)
        max_workers = min(num_chunks, 5) 
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有分段任务
                future_to_index = {
                    executor.submit(self._process_chunk, chunks[i], i, num_chunks, contexts[i]): i 
                    for i in range(num_chunks)
                }
                
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        results[idx] = future.result()
                        completed_count += 1
                        
                        # 更新进度条
                        if progress_callback is not None:
                            status = f"并行整理中：已完成 {completed_count}/{num_chunks} 段..."
                            try:
                                progress_callback(completed_count / num_chunks, desc=status)
                            except:
                                pass
                    except Exception as e:
                        logger.error(f"线程执行异常 (段 {idx+1}): {e}")
                        results[idx] = chunks[idx] # 异常回退

            # 3. 合并最终结果
            final_text = "\n\n".join(results)
            
            if progress_callback is not None:
                try:
                    progress_callback(1.0, desc="AI 整理完成！")
                except:
                    pass
                    
            return final_text

        except Exception as e:
            logger.error(f"LLM 并行核心流程崩溃: {e}")
            logger.error(traceback.format_exc())
            return f"Error during AI processing: {str(e)}"

    @staticmethod
    def save_refined_text(original_path: str, refined_text: str) -> str:
        """
        将润色后的文本保存为新文件。
        """
        # 保存到 outputs/<original_name_without_prefix>/
        base_name = os.path.splitext(os.path.basename(original_path))[0]
        clean_name = base_name.replace('podcast_tmp_', '')
        out_dir = os.path.join(os.getcwd(), 'outputs', clean_name)
        os.makedirs(out_dir, exist_ok=True)
        new_path = os.path.join(out_dir, f"{clean_name}_AI_Refined.txt")
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(refined_text)
        return new_path

    @staticmethod
    def save_refined_html(original_path: str, html_body: str, css_styles: str) -> str:
        """
        将润色后的美化 HTML 保存为文件。
        """
        # 保存到 outputs/<original_name_without_prefix>/
        base_name = os.path.splitext(os.path.basename(original_path))[0]
        clean_name = base_name.replace('podcast_tmp_', '')
        out_dir = os.path.join(os.getcwd(), 'outputs', clean_name)
        os.makedirs(out_dir, exist_ok=True)
        new_path = os.path.join(out_dir, f"{clean_name}_AI_Refined_Pretty.html")
        
        full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AI 润色整理结果</title>
    <style>
        body {{ 
            background-color: #f3f4f6; 
            padding: 40px 20px; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        {css_styles}
    </style>
</head>
<body>
    <div class="container">
        <h1 style="text-align: center; color: #111827; margin-bottom: 30px;">AI 润色整理结果</h1>
        {html_body}
    </div>
</body>
</html>
"""
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        return new_path

    @staticmethod
    def save_refined_pdf(original_path: str, refined_text: str) -> Optional[str]:
        """
        将润色后的内容保存为 PDF。
        """
        try:
            from xhtml2pdf import pisa
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.fonts import addMapping
            import os
            
            logger.info("开始生成 PDF 文件...")

            # 保存到 outputs/<original_name_without_prefix>/
            base_name = os.path.splitext(os.path.basename(original_path))[0]
            clean_name = base_name.replace('podcast_tmp_', '')
            out_dir = os.path.join(os.getcwd(), 'outputs', clean_name)
            os.makedirs(out_dir, exist_ok=True)
            new_path = os.path.join(out_dir, f"{clean_name}_AI_Refined.pdf")

            # 字体路径
            resources_dir = os.path.join(os.getcwd(), "resources", "fonts")
            barlow_font_path = os.path.join(resources_dir, "Barlow-Regular.ttf")
            noto_font_path = os.path.join(resources_dir, "NotoSansSC-Regular.ttf")
            
            # 1. 尝试注册字体：Barlow（英文）与 NotoSansSC（中文回退）
            font_barlow = "Barlow"
            font_noto = "NotoSansSC"

            # 注册 Barlow
            if os.path.exists(barlow_font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_barlow, barlow_font_path))
                    addMapping(font_barlow, 0, 0, font_barlow)  # normal
                    addMapping(font_barlow, 1, 0, font_barlow)  # bold
                    logger.info(f"成功注册字体: {font_barlow}")
                except Exception as fe:
                    logger.error(f"Barlow 注册失败: {fe}")
                    font_barlow = "Helvetica"
            else:
                logger.error(f"未找到 Barlow 字体文件: {barlow_font_path}，将使用系统默认字体")
                font_barlow = "Helvetica"

            # 注册 Noto (中文字体) 如果存在
            noto_available = False
            if os.path.exists(noto_font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_noto, noto_font_path))
                    addMapping(font_noto, 0, 0, font_noto)
                    addMapping(font_noto, 1, 0, font_noto)
                    noto_available = True
                    logger.info(f"成功注册中文回退字体: {font_noto}")
                except Exception as ne:
                    logger.error(f"Noto 注册失败: {ne}")
                    noto_available = False
            else:
                logger.warning(f"未找到 Noto 中文字体文件: {noto_font_path}，中文可能无法正确显示")

            # 准备 PDF 专用的 HTML (xhtml2pdf 特殊语法)
            colors = ["#f87171", "#fbbf24", "#34d399", "#60a5fa", "#a78bfa", "#f472b6"]
            
            # 使用 <style> 中的 @font-face 明确指定字体路径，并在 body 中使用合适字体
            # xhtml2pdf 在某些系统下需要通过 @font-face 指定本地字体文件路径以确保嵌入
            # 使用 file:// 绝对路径确保 pisa 能找到字体文件
            barlow_abs = barlow_font_path.replace('\\', '/')
            noto_abs = noto_font_path.replace('\\', '/')


            # 优先使用 Barlow；将 Noto 放在回退列表以确保中文能显示
            preferred_font = font_barlow

            html_content = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    @font-face {{
                        font-family: 'Barlow';
                        src: url('file:///{barlow_abs}');
                    }}
                    @font-face {{
                        font-family: 'NotoSansSC';
                        src: url('file:///{noto_abs}');
                    }}
                    @page {{
                        size: a4;
                        margin: 2cm;
                    }}
                    body {{ 
                        /* 优先 Barlow，回退到 NotoSansSC（中文）或系统字体 */
                        font-family: 'Barlow', 'NotoSansSC', sans-serif;
                        font-size: 11pt;
                        line-height: 1.6;
                        color: #1f2937;
                    }}
                    .title {{
                        text-align: center;
                        font-size: 22pt;
                        font-weight: bold;
                        color: #111827;
                        margin-bottom: 40px;
                    }}
                    .topic-tag {{
                        text-align: center;
                        background-color: #eff6ff;
                        color: #2563eb;
                        padding: 10px;
                        border-radius: 15px;
                        font-weight: bold;
                        margin: 20px 0;
                        border: 1px solid #dbeafe;
                    }}
                    .message-box {{
                        margin-bottom: 20px;
                        border-left: 4px solid #e5e7eb;
                        padding-left: 15px;
                    }}
                    .speaker-header {{
                        font-family: 'Barlow';
                        font-weight: bold;
                        color: #4b5563;
                        font-size: 10pt;
                        margin-bottom: 4px;
                    }}
                    .text {{
                        font-family: 'Barlow';
                        font-size: 11pt;
                        color: #111827;
                    }}
                </style>
            </head>
            <body>
                <div class="title">AI 润色整理结果</div>
            """

            lines = refined_text.split('\n')
            current_speaker = None
            current_content = []

            def flush_to_html(speaker, content_list):
                if not speaker or not content_list: return ""
                idx_str = ''.join(filter(str.isdigit, speaker))
                idx = int(idx_str) if idx_str else 0
                color = colors[idx % len(colors)]
                name = f"发言人 {idx}"
                text = "<br/>".join(content_list)
                
                return f"""
                <div class="message-box" style="border-left-color: {color};">
                    <div class="speaker-header">{name}</div>
                    <div class="text">{text}</div>
                </div>
                """

            for line in lines:
                line = line.strip()
                if not line: continue
                
                if (line.startswith('【') and '】' in line) or line.startswith('###'):
                    html_content += flush_to_html(current_speaker, current_content)
                    current_speaker, current_content = None, []
                    topic = line.strip('【】# ')
                    html_content += f'<div class="topic-tag">{topic}</div>'
                elif '|' in line and line.startswith('SPEAKER_'):
                    parts = line.split('|', 1)
                    tag = parts[0]
                    content = parts[1] if len(parts) > 1 else ""
                    if tag == current_speaker:
                        current_content.append(content)
                    else:
                        html_content += flush_to_html(current_speaker, current_content)
                        current_speaker, current_content = tag, [content]
                else:
                    if current_speaker: current_content.append(line)
                    else: html_content += f'<div class="text" style="margin-bottom:10px;">{line}</div>'

            html_content += flush_to_html(current_speaker, current_content)
            html_content += "</body></html>"

            # 执行转换
            with open(new_path, "wb") as f:
                pisa_status = pisa.CreatePDF(html_content, dest=f, encoding='utf-8')
            
            if pisa_status.err:
                logger.error(f"PDF 转换过程中出错: {pisa_status.err}")
                return None
                
            logger.info(f"PDF 生成成功: {new_path}")
            return new_path

        except Exception as e:
            logger.error(f"PDF 生成过程抛出异常: {e}")
            logger.error(traceback.format_exc())
            return None
