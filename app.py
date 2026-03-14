import os
import tempfile
import warnings
import logging

# 屏蔽第三方库的各种非致命警告 (UserWarning, FutureWarning, etc.)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
# 针对特定库（如 pyannote, speechbrain）静音，仅显示 ERROR
logging.getLogger("speechbrain").setLevel(logging.ERROR)
logging.getLogger("pyannote").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
# 设置环境变量，从系统层面减少警告输出
os.environ["PYTHONWARNINGS"] = "ignore"

# 强制将 Gradio 和系统临时目录设置在当前项目所在的 D 盘，防止 C 盘空间不足
CUSTOM_TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
os.makedirs(CUSTOM_TEMP_DIR, exist_ok=True)
os.environ["GRADIO_TEMP_DIR"] = CUSTOM_TEMP_DIR
tempfile.tempdir = CUSTOM_TEMP_DIR

import argparse
import gradio as gr
from gradio_i18n import Translate, gettext as _
import yaml
import torch

# 适配 PyTorch 2.6+ 的安全机制 (策略 B：全局信任模型来源)
# 由于 pyannote 内部类极其复杂且多变，逐个添加白名单极易导致“打地鼠”式连续报错。
# 鉴于模型来源于受信任的 HuggingFace 官方，我们通过补丁强制关闭 weights_only 检查。
import functools
import inspect

# 尝试添加基础安全全局变量，防止某些场景下的反序列化失败
try:
    if hasattr(torch.serialization, 'add_safe_globals'):
        torch.serialization.add_safe_globals([torch.torch_version.TorchVersion])
except Exception:
    pass

_original_torch_load = torch.load
_load_params = inspect.signature(_original_torch_load).parameters

@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    # 如果当前 Torch 版本支持 weights_only 参数，强制设为 False 以兼容旧模型结构
    if 'weights_only' in _load_params:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load

from modules.utils.paths import (FASTER_WHISPER_MODELS_DIR, DIARIZATION_MODELS_DIR, OUTPUT_DIR, WHISPER_MODELS_DIR,
                                 INSANELY_FAST_WHISPER_MODELS_DIR, NLLB_MODELS_DIR, DEFAULT_PARAMETERS_CONFIG_PATH,
                                 UVR_MODELS_DIR, I18N_YAML_PATH)
from modules.utils.files_manager import load_yaml, MEDIA_EXTENSION
from modules.whisper.whisper_factory import WhisperFactory
from modules.translation.nllb_inference import NLLBInference
from modules.ui.htmls import *
from modules.utils.cli_manager import str2bool
from modules.utils.youtube_manager import get_ytmetas
from modules.utils.podcast_manager import download_podcast_audio
from modules.translation.deepl_api import DeepLAPI
from modules.whisper.data_classes import *
from modules.llm.llm_processor import LLMProcessor
from modules.utils.logger import get_logger
from clean_temp import clean_temp_dir


logger = get_logger()


def format_refined_text_to_html(text: str) -> str:
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
        
        return f"""
        <div class="transcript-item">
            <div class="speaker-avatar" style="background-color: {color}">{icon}</div>
            <div class="speaker-body">
                <div class="speaker-header">
                    <span class="speaker-name">{name}</span>
                </div>
                <div class="speaker-text">{content}</div>
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
                # 兜底：处理没有标签的纯文本
                html += f'<div class="speaker-text" style="margin-bottom:15px; border-radius:12px; background:#f0f0f0; padding:10px 15px;">{line}</div>'
                
    # 结尾闭合
    last_msg = flush_message(current_speaker, current_content)
    if section_started:
        html += last_msg + '</div>'
    else:
        html += last_msg
        
    html += '</div>'
    return html


class App:
    def __init__(self, args):
        self.args = args
        # Check every 1 hour (3600) for cached files and delete them if older than 1 day (86400)
        self.app = gr.Blocks(css=CSS, theme=self.args.theme, delete_cache=(3600, 86400))
        self.whisper_inf = WhisperFactory.create_whisper_inference(
            whisper_type=self.args.whisper_type,
            whisper_model_dir=self.args.whisper_model_dir,
            faster_whisper_model_dir=self.args.faster_whisper_model_dir,
            insanely_fast_whisper_model_dir=self.args.insanely_fast_whisper_model_dir,
            uvr_model_dir=self.args.uvr_model_dir,
            output_dir=self.args.output_dir,
        )
        self.nllb_inf = NLLBInference(
            model_dir=self.args.nllb_model_dir,
            output_dir=os.path.join(self.args.output_dir, "translations")
        )
        self.deepl_api = DeepLAPI(
            output_dir=os.path.join(self.args.output_dir, "translations")
        )
        self.i18n = load_yaml(I18N_YAML_PATH)
        self.default_params = load_yaml(DEFAULT_PARAMETERS_CONFIG_PATH)
        logger.info(f"Use \"{self.args.whisper_type}\" implementation\n"
                    f"Device \"{self.whisper_inf.device}\" is detected")

    def create_pipeline_inputs(self):
        whisper_params = self.default_params["whisper"]
        vad_params = self.default_params["vad"]
        diarization_params = self.default_params["diarization"]
        uvr_params = self.default_params["bgm_separation"]

        with gr.Row():
            dd_model = gr.Dropdown(choices=self.whisper_inf.available_models, value=whisper_params["model_size"],
                                   label=_("Model"), allow_custom_value=True)
            dd_lang = gr.Dropdown(choices=self.whisper_inf.available_langs + [AUTOMATIC_DETECTION],
                                  value=AUTOMATIC_DETECTION if whisper_params["lang"] == AUTOMATIC_DETECTION.unwrap()
                                  else whisper_params["lang"], label=_("Language"))
            dd_file_format = gr.Dropdown(choices=["SRT", "WebVTT", "txt", "LRC"], value=whisper_params["file_format"], label=_("File Format"))
        with gr.Row():
            cb_translate = gr.Checkbox(value=whisper_params["is_translate"], label=_("Translate to English?"),
                                       interactive=True)
            cb_timestamp = gr.Checkbox(value=whisper_params["add_timestamp"],
                                       label=_("Add a timestamp to the end of the filename"),
                                       interactive=True)

        def get_status_text(is_enabled):
            status_cls = "status-on" if is_enabled else "status-off"
            status_label = _("ON") if is_enabled else _("OFF")
            return f'<span class="status-pill {status_cls}">{status_label}</span>'

        def update_acc_status(is_enabled, label_prefix, base_id):
            status_html = get_status_text(is_enabled)
            # 这里的 label 可以包含 HTML，Gradio Accordion 支持简单 HTML 或我们在 CSS 中处理
            return gr.update(label=f"{label_prefix} {status_html}")

        with gr.Accordion(_("Advanced Parameters"), open=False, elem_id="acc_whisper_advanced"):
            whisper_inputs = WhisperParams.to_gradio_inputs(defaults=whisper_params, only_advanced=True,
                                                            whisper_type=self.args.whisper_type,
                                                            available_compute_types=self.whisper_inf.available_compute_types,
                                                            compute_type=self.whisper_inf.current_compute_type)

        uvr_label = _("Background Music Remover Filter")
        uvr_id = "acc_uvr"
        with gr.Accordion(f"{uvr_label} {get_status_text(uvr_params['is_separate_bgm'])}", 
                          open=False, 
                          elem_id=uvr_id) as acc_uvr:
            uvr_inputs = BGMSeparationParams.to_gradio_input(defaults=uvr_params,
                                                             available_models=self.whisper_inf.music_separator.available_models,
                                                             available_devices=self.whisper_inf.music_separator.available_devices,
                                                             device=self.whisper_inf.music_separator.device)
        uvr_inputs[0].change(fn=lambda x: update_acc_status(x, uvr_label, uvr_id), inputs=uvr_inputs[0], outputs=acc_uvr)

        vad_label = _("Voice Detection Filter")
        vad_id = "acc_vad"
        with gr.Accordion(f"{vad_label} {get_status_text(vad_params['vad_filter'])}", 
                          open=False, 
                          elem_id=vad_id) as acc_vad:
            vad_inputs = VadParams.to_gradio_inputs(defaults=vad_params)
        vad_inputs[0].change(fn=lambda x: update_acc_status(x, vad_label, vad_id), inputs=vad_inputs[0], outputs=acc_vad)

        diarization_label = _("Diarization")
        diar_id = "acc_diarization"
        with gr.Accordion(f"{diarization_label} {get_status_text(diarization_params['is_diarize'])}", 
                          open=False, 
                          elem_id=diar_id) as acc_diarization:
            diarization_inputs = DiarizationParams.to_gradio_inputs(defaults=diarization_params,
                                                                    available_devices=self.whisper_inf.diarizer.available_device,
                                                                    device=self.whisper_inf.diarizer.device)
        diarization_inputs[0].change(fn=lambda x: update_acc_status(x, diarization_label, diar_id), inputs=diarization_inputs[0], outputs=acc_diarization)

        pipeline_inputs = [dd_model, dd_lang, cb_translate] + whisper_inputs + vad_inputs + diarization_inputs + uvr_inputs

        return (
            pipeline_inputs,
            dd_file_format,
            cb_timestamp
        )

    def launch(self):
        translation_params = self.default_params["translation"]
        deepl_params = translation_params["deepl"]
        nllb_params = translation_params["nllb"]
        uvr_params = self.default_params["bgm_separation"]

        with self.app:
            lang = gr.Radio(choices=list(self.i18n.keys()),
                            label=_("Language"), interactive=True,
                            visible=False,  # Set it by development purpose.
                            )
            with Translate(self.i18n):  # Add `lang = lang` here to test dynamic change of the languages.
                with gr.Row():
                    with gr.Column():
                        gr.Markdown(MARKDOWN, elem_id="md_project")
                with gr.Tabs():
                    with gr.TabItem(_("File")):  # tab1
                        with gr.Group(): # 使用 Group 而非 Accordion 使其更紧凑
                            with gr.Row():
                                tb_podcast_link = gr.Textbox(
                                    show_label=False,
                                    placeholder=_("Podcast URL (Xiaoyuzhou etc.)"),
                                    scale=4
                                )
                                btn_download_podcast = gr.Button(_("Download"), scale=1, variant="secondary")
                            tb_podcast_status = gr.Textbox(show_label=False, interactive=False, visible=False)

                        with gr.Accordion(_("Local Files"), open=False):
                            with gr.Column():
                                input_file = gr.Files(type="filepath", label=_("Upload File here"), file_types=MEDIA_EXTENSION)
                                tb_input_folder = gr.Textbox(show_label=True, label=_("Input Folder Path (Optional)"),
                                                             info=_("Optional: Specify the folder path where the input files are located, if you prefer to use local files instead of uploading them. Leave this field empty if you do not wish to use a local path."),
                                                             visible=self.args.colab,
                                                             value="")
                                cb_include_subdirectory = gr.Checkbox(label="Include Subdirectory Files",
                                                                      info="When using Input Folder Path above, whether to include all files in the subdirectory or not.",
                                                                      visible=self.args.colab,
                                                                      value=False)
                                cb_save_same_dir = gr.Checkbox(label="Save outputs at same directory",
                                                               info="When using Input Folder Path above, whether to save output in the same directory as inputs or not, in addition to the original"
                                                                    " output directory.",
                                                               visible=self.args.colab,
                                                               value=True)
                        pipeline_params, dd_file_format, cb_timestamp = self.create_pipeline_inputs()

                        with gr.Row():
                            btn_run = gr.Button(_("GENERATE SUBTITLE FILE"), variant="primary")
                        
                        with gr.Row():
                            tb_indicator = gr.Textbox(label=_("Output"), scale=5, interactive=True)
                            files_subtitles = gr.Files(label=_("Downloadable output file"), scale=3, interactive=False)
                            btn_openfolder = gr.Button('📂', scale=1)

                        # AI 洗稿/总结预览区
                        with gr.Accordion(_("✨ AI 一键整理 (LLM Post-Processing)"), open=True, elem_id="acc_ai_post_processing"):
                            with gr.Row():
                                btn_ai_refine = gr.Button(_("✨ AI One-Click Refine"), variant="secondary")
                            
                            with gr.Row():
                                with gr.Column(scale=1): # 左侧留白
                                    pass
                                with gr.Column(scale=8): # 核心阅读区域
                                    tb_ai_refined_preview = gr.HTML(label=_("AI Refinement Preview"))
                                    file_ai_refined = gr.Files(label=_("AI Refinement Download (Includes Pretty HTML)"), interactive=False)
                                with gr.Column(scale=1): # 右侧留白
                                    pass

                        params = [input_file, tb_input_folder, cb_include_subdirectory, cb_save_same_dir,
                                  dd_file_format, cb_timestamp]
                        params = params + pipeline_params

                        def _run_and_maybe_refine(*all_inputs):
                            """
                            Wrapper to run transcription.
                            Since logic of auto refining is moved to transcribe_file,
                            we just need to parse the results correctly for UI.
                            """
                            try:
                                fixed = all_inputs[:6]
                                pipeline_vals = list(all_inputs[6:])

                                # call original transcription function
                                result_str, files = self.whisper_inf.transcribe_file(*fixed, gr.Progress(), *pipeline_vals)

                                # logic for UI update:
                                # files[0] is always subtitle.
                                # if auto_llm_refine is ON, files will contain [subtitle, txt, html, pdf]
                                refined_html = ""
                                refined_files = []
                                
                                if files and len(files) > 1:
                                    # find the .html file for preview
                                    for f in files:
                                        f_path = str(f.name if hasattr(f, "name") else f)
                                        if f_path.endswith("_AI_Refined_Pretty.html"):
                                            try:
                                                with open(f_path, "r", encoding="utf-8") as hf:
                                                    refined_html = hf.read()
                                            except:
                                                pass
                                    # find and filter refine-related files for the LLM download panel
                                    for f in files:
                                        f_path = str(f.name if hasattr(f, "name") else f)
                                        if "_AI_Refined" in f_path:
                                            refined_files.append(f)

                                return result_str, files, refined_html, refined_files
                            except Exception as e:
                                raise

                        btn_run.click(fn=_run_and_maybe_refine,
                                      inputs=params,
                                      outputs=[tb_indicator, files_subtitles, tb_ai_refined_preview, file_ai_refined])
                        btn_openfolder.click(fn=lambda: self.open_folder("outputs"), inputs=None, outputs=None)

                        def _download_podcast(url):
                            if not url or not url.strip():
                                return gr.update(), gr.update(value=_("Please enter podcast link"), visible=True)
                            try:
                                audio_path, title = download_podcast_audio(url)
                                return gr.update(value=[audio_path]), gr.update(value=_("Download finished: ") + title, visible=True)
                            except Exception as e:
                                return gr.update(), gr.update(value=_("Download failed: ") + str(e), visible=True)

                        btn_download_podcast.click(
                            fn=_download_podcast,
                            inputs=[tb_podcast_link],
                            outputs=[input_file, tb_podcast_status]
                        )
                        
                        def _ai_post_process(files, manual_text, progress=gr.Progress()):
                            txt_file = None
                            original_text = ""

                            # 1. 优先从生成的 .txt 文件中读取
                            if files and len(files) > 0:
                                for f in files:
                                    # f 可能是字符串路径，也可能是 gradio.File 对象
                                    f_path = f.name if hasattr(f, "name") else str(f)
                                    if f_path.endswith(".txt"):
                                        txt_file = f_path
                                        break
                                
                                if txt_file and os.path.exists(txt_file):
                                    with open(txt_file, "r", encoding="utf-8") as rf:
                                        original_text = rf.read()
                            
                            # 2. 如果没有文件，尝试从“输出”文本框读取手动输入的内容
                            if not original_text and manual_text and manual_text.strip():
                                if len(manual_text.strip()) < 10:
                                    return "手动输入内容太短，请粘贴完整的转录文本。", gr.update(), None
                                
                                original_text = manual_text
                                txt_file = os.path.join(CUSTOM_TEMP_DIR, "manual_input.txt")
                                with open(txt_file, "w", encoding="utf-8") as wf:
                                    wf.write(manual_text)

                            if not original_text:
                                return "未找到转录文件或手动输入内容，请先运行生成或在『输出』框粘贴文本。", gr.update(), None
                            
                            llm_config = self.default_params.get("llm_post_process", {})
                            processor = LLMProcessor(
                                api_base=llm_config.get("api_base"),
                                api_key=llm_config.get("api_key"),
                                model=llm_config.get("model"),
                                prompt=llm_config.get("prompt"),
                                reasoning=llm_config.get("reasoning", False)
                            )
                            
                            refined_text = processor.process_text(original_text, progress_callback=progress)
                            if not original_text or original_text.startswith("Error:"):
                                return format_refined_text_to_html(refined_text if refined_text else _("AI post-processing failed, please check API configuration.")), None
                            
                            # Determine the media file to use for naming (prefer original MP3 when available)
                            media_for_naming = txt_file
                            try:
                                # candidate: same base name with .mp3
                                candidate_mp3 = os.path.splitext(txt_file)[0] + '.mp3'
                                if os.path.exists(candidate_mp3):
                                    media_for_naming = candidate_mp3
                                else:
                                    # search same directory for mp3s that contain the cleaned base name
                                    tdir = os.path.dirname(txt_file)
                                    cleaned = os.path.splitext(os.path.basename(txt_file))[0].replace('podcast_tmp_', '')
                                    mp3_matches = []
                                    if os.path.isdir(tdir):
                                        for fname in os.listdir(tdir):
                                            if fname.lower().endswith('.mp3') and cleaned in fname:
                                                mp3_matches.append(os.path.join(tdir, fname))
                                    if mp3_matches:
                                        media_for_naming = mp3_matches[0]
                                    else:
                                        # fallback: check the uploaded files list for an mp3
                                        if files:
                                            for f in files:
                                                f_path = f.name if hasattr(f, 'name') else str(f)
                                                if f_path.lower().endswith('.mp3'):
                                                    media_for_naming = f_path
                                                    break
                            except Exception:
                                # defensive: keep txt_file if anything goes wrong
                                media_for_naming = txt_file

                            # 1. 保存原始 TXT (use media_for_naming for folder naming)
                            txt_path = processor.save_refined_text(media_for_naming, refined_text)

                            # 2. 生成并保存美化版 HTML
                            html_content = format_refined_text_to_html(refined_text)
                            html_path = processor.save_refined_html(media_for_naming, html_content, CSS)

                            # 3. 直接生成并保存 PDF 文件
                            pdf_path = processor.save_refined_pdf(media_for_naming, refined_text)
                            
                            download_files = [txt_path, html_path]
                            if pdf_path:
                                download_files.append(pdf_path)
                            # 尝试自动打开输出目录，方便用户查看生成的文件
                            try:
                                # 优先以 txt_path 为准，否则以 media_for_naming 的目录为准
                                folder_to_open = None
                                if txt_path and os.path.exists(txt_path):
                                    folder_to_open = os.path.dirname(txt_path)
                                elif media_for_naming and os.path.exists(media_for_naming):
                                    folder_to_open = os.path.dirname(media_for_naming)
                                else:
                                    # fallback: outputs/<clean_name>/ pattern
                                    try:
                                        cleaned = os.path.splitext(os.path.basename(media_for_naming))[0].replace('podcast_tmp_', '')
                                        folder_to_open = os.path.join(os.getcwd(), 'outputs', cleaned)
                                    except Exception:
                                        folder_to_open = None

                                if folder_to_open:
                                    # open_folder will create directory if missing
                                    self.open_folder(folder_to_open)
                            except Exception:
                                # don't let UI break if opening fails
                                pass

                            return html_content, download_files

                        btn_ai_refine.click(
                            fn=_ai_post_process,
                            inputs=[files_subtitles, tb_indicator],
                            outputs=[tb_ai_refined_preview, file_ai_refined]
                        )

                    with gr.TabItem(_("Youtube")):  # tab2
                        with gr.Row():
                            tb_youtubelink = gr.Textbox(label=_("Youtube Link"))
                        with gr.Row(equal_height=True):
                            with gr.Column():
                                img_thumbnail = gr.Image(label=_("Youtube Thumbnail"))
                            with gr.Column():
                                tb_title = gr.Label(label=_("Youtube Title"))
                                tb_description = gr.Textbox(label=_("Youtube Description"), max_lines=15)

                        pipeline_params, dd_file_format, cb_timestamp = self.create_pipeline_inputs()

                        with gr.Row():
                            btn_run = gr.Button(_("GENERATE SUBTITLE FILE"), variant="primary")
                        with gr.Row():
                            tb_indicator = gr.Textbox(label=_("Output"), scale=5)
                            files_subtitles = gr.Files(label=_("Downloadable output file"), scale=3)
                            btn_openfolder = gr.Button('📂', scale=1)

                        params = [tb_youtubelink, dd_file_format, cb_timestamp]

                        btn_run.click(fn=self.whisper_inf.transcribe_youtube,
                                      inputs=params + pipeline_params,
                                      outputs=[tb_indicator, files_subtitles])
                        tb_youtubelink.change(get_ytmetas, inputs=[tb_youtubelink],
                                              outputs=[img_thumbnail, tb_title, tb_description])
                        btn_openfolder.click(fn=lambda: self.open_folder("outputs"), inputs=None, outputs=None)

                    with gr.TabItem(_("Mic")):  # tab3
                        with gr.Row():
                            mic_input = gr.Microphone(label=_("Record with Mic"), type="filepath", interactive=True,
                                                      show_download_button=True)

                        pipeline_params, dd_file_format, cb_timestamp = self.create_pipeline_inputs()

                        with gr.Row():
                            btn_run = gr.Button(_("GENERATE SUBTITLE FILE"), variant="primary")
                        with gr.Row():
                            tb_indicator = gr.Textbox(label=_("Output"), scale=5)
                            files_subtitles = gr.Files(label=_("Downloadable output file"), scale=3)
                            btn_openfolder = gr.Button('📂', scale=1)

                        params = [mic_input, dd_file_format, cb_timestamp]

                        btn_run.click(fn=self.whisper_inf.transcribe_mic,
                                      inputs=params + pipeline_params,
                                      outputs=[tb_indicator, files_subtitles])
                        btn_openfolder.click(fn=lambda: self.open_folder("outputs"), inputs=None, outputs=None)

                    with gr.TabItem(_("T2T Translation")):  # tab 4
                        with gr.Row():
                            file_subs = gr.Files(type="filepath", label=_("Upload Subtitle Files to translate here"))

                        with gr.TabItem(_("DeepL API")):  # sub tab1
                            with gr.Row():
                                tb_api_key = gr.Textbox(label=_("Your Auth Key (API KEY)"),
                                                        value=deepl_params["api_key"])
                            with gr.Row():
                                dd_source_lang = gr.Dropdown(label=_("Source Language"),
                                                             value=AUTOMATIC_DETECTION if deepl_params["source_lang"] == AUTOMATIC_DETECTION.unwrap()
                                                             else deepl_params["source_lang"],
                                                             choices=list(self.deepl_api.available_source_langs.keys()))
                                dd_target_lang = gr.Dropdown(label=_("Target Language"),
                                                             value=deepl_params["target_lang"],
                                                             choices=list(self.deepl_api.available_target_langs.keys()))
                            with gr.Row():
                                cb_is_pro = gr.Checkbox(label=_("Pro User?"), value=deepl_params["is_pro"])
                            with gr.Row():
                                cb_timestamp = gr.Checkbox(value=translation_params["add_timestamp"],
                                                           label=_("Add a timestamp to the end of the filename"),
                                                           interactive=True)
                            with gr.Row():
                                btn_run = gr.Button(_("TRANSLATE SUBTITLE FILE"), variant="primary")
                            with gr.Row():
                                tb_indicator = gr.Textbox(label=_("Output"), scale=5)
                                files_subtitles = gr.Files(label=_("Downloadable output file"), scale=3)
                                btn_openfolder = gr.Button('📂', scale=1)

                        btn_run.click(fn=self.deepl_api.translate_deepl,
                                      inputs=[tb_api_key, file_subs, dd_source_lang, dd_target_lang,
                                              cb_is_pro, cb_timestamp],
                                      outputs=[tb_indicator, files_subtitles])

                        btn_openfolder.click(
                            fn=lambda: self.open_folder(os.path.join(self.args.output_dir, "translations")),
                            inputs=None,
                            outputs=None)

                        with gr.TabItem(_("NLLB")):  # sub tab2
                            with gr.Row():
                                dd_model_size = gr.Dropdown(label=_("Model"), value=nllb_params["model_size"],
                                                            choices=self.nllb_inf.available_models)
                                dd_source_lang = gr.Dropdown(label=_("Source Language"),
                                                             value=nllb_params["source_lang"],
                                                             choices=self.nllb_inf.available_source_langs)
                                dd_target_lang = gr.Dropdown(label=_("Target Language"),
                                                             value=nllb_params["target_lang"],
                                                             choices=self.nllb_inf.available_target_langs)
                            with gr.Row():
                                nb_max_length = gr.Number(label="Max Length Per Line", value=nllb_params["max_length"],
                                                          precision=0)
                            with gr.Row():
                                cb_timestamp = gr.Checkbox(value=translation_params["add_timestamp"],
                                                           label=_("Add a timestamp to the end of the filename"),
                                                           interactive=True)
                            with gr.Row():
                                btn_run = gr.Button(_("TRANSLATE SUBTITLE FILE"), variant="primary")
                            with gr.Row():
                                tb_indicator = gr.Textbox(label=_("Output"), scale=5)
                                files_subtitles = gr.Files(label=_("Downloadable output file"), scale=3)
                                btn_openfolder = gr.Button('📂', scale=1)
                            with gr.Column():
                                md_vram_table = gr.HTML(NLLB_VRAM_TABLE, elem_id="md_nllb_vram_table")

                        btn_run.click(fn=self.nllb_inf.translate_file,
                                      inputs=[file_subs, dd_model_size, dd_source_lang, dd_target_lang,
                                              nb_max_length, cb_timestamp],
                                      outputs=[tb_indicator, files_subtitles])

                        btn_openfolder.click(
                            fn=lambda: self.open_folder(os.path.join(self.args.output_dir, "translations")),
                            inputs=None,
                            outputs=None)

                    with gr.TabItem(_("BGM Separation")):
                        files_audio = gr.Files(type="filepath", label=_("Upload Audio Files to separate background music"))
                        dd_uvr_device = gr.Dropdown(label=_("Device"), value=self.whisper_inf.music_separator.device,
                                                    choices=self.whisper_inf.music_separator.available_devices)
                        dd_uvr_model_size = gr.Dropdown(label=_("Model"), value=uvr_params["uvr_model_size"],
                                                        choices=self.whisper_inf.music_separator.available_models)
                        nb_uvr_segment_size = gr.Number(label="Segment Size", value=uvr_params["segment_size"],
                                                        precision=0)
                        cb_uvr_save_file = gr.Checkbox(label=_("Save separated files to output"),
                                                       value=True, visible=False)
                        btn_run = gr.Button(_("SEPARATE BACKGROUND MUSIC"), variant="primary")
                        with gr.Column():
                            with gr.Row():
                                ad_instrumental = gr.Audio(label=_("Instrumental"), scale=8)
                                btn_open_instrumental_folder = gr.Button('📂', scale=1)
                            with gr.Row():
                                ad_vocals = gr.Audio(label=_("Vocals"), scale=8)
                                btn_open_vocals_folder = gr.Button('📂', scale=1)

                        btn_run.click(fn=self.whisper_inf.music_separator.separate_files,
                                      inputs=[files_audio, dd_uvr_model_size, dd_uvr_device, nb_uvr_segment_size,
                                              cb_uvr_save_file],
                                      outputs=[ad_instrumental, ad_vocals])
                        btn_open_instrumental_folder.click(inputs=None,
                                                           outputs=None,
                                                           fn=lambda: self.open_folder(os.path.join(
                                                               self.args.output_dir, "UVR", "instrumental"
                                                           )))
                        btn_open_vocals_folder.click(inputs=None,
                                                     outputs=None,
                                                     fn=lambda: self.open_folder(os.path.join(
                                                         self.args.output_dir, "UVR", "vocals"
                                                     )))

                    with gr.TabItem("LLM Settings"):
                        llm_params = self.default_params.get("llm_post_process", {})
                        with gr.Column():
                            gr.Markdown("### 🤖 LLM 自动化洗稿配置 (OpenAI 兼容)")
                            tb_ai_base = gr.Textbox(label="API Base URL", value=llm_params.get("api_base"), placeholder="https://api.openai.com/v1")
                            tb_ai_key = gr.Textbox(label="API Key", value=llm_params.get("api_key"), type="password")
                            tb_ai_model = gr.Textbox(label="LLM Model", value=llm_params.get("model"), placeholder="gpt-3.5-turbo")
                            cb_ai_reasoning = gr.Checkbox(label="开启深度思考 (Reasoning)", value=llm_params.get("reasoning", False), info="开启后将尝试引导模型进行深度推理（需模型支持）")
                            tb_ai_prompt = gr.Textbox(label="AI Prompt", value=llm_params.get("prompt"), lines=5)
                            btn_save_llm = gr.Button("💾 保存配置", variant="primary")
                            tb_save_status = gr.Textbox(label="状态", interactive=False)

                        def _save_llm_config(base, key, model, prompt, reasoning):
                            self.default_params["llm_post_process"] = {
                                "api_base": base,
                                "api_key": key,
                                "model": model,
                                "prompt": prompt,
                                "reasoning": reasoning
                            }
                            with open(DEFAULT_PARAMETERS_CONFIG_PATH, "w", encoding="utf-8") as wf:
                                yaml.dump(self.default_params, wf, allow_unicode=True)
                            return "✅ 配置已保存到 configs/default_parameters.yaml"

                        btn_save_llm.click(
                            fn=_save_llm_config,
                            inputs=[tb_ai_base, tb_ai_key, tb_ai_model, tb_ai_prompt, cb_ai_reasoning],
                            outputs=[tb_save_status]
                        )
                        
                        # 底部清理按钮
                        with gr.Row():
                            btn_clean_temp = gr.Button("🧹 一键清理音频缓存", variant="secondary", size="sm")
                        
                        btn_clean_temp.click(fn=lambda: gr.Info(clean_temp_dir()), outputs=None)
                

        # Launch the app with optional gradio settings
        args = self.args
        self.app.queue(
            api_open=args.api_open
        ).launch(
            share=args.share,
            server_name=args.server_name,
            server_port=args.server_port,
            auth=(args.username, args.password) if args.username and args.password else None,
            root_path=args.root_path,
            inbrowser=args.inbrowser,
            ssl_verify=args.ssl_verify,
            ssl_keyfile=args.ssl_keyfile,
            ssl_keyfile_password=args.ssl_keyfile_password,
            ssl_certfile=args.ssl_certfile,
            allowed_paths=eval(args.allowed_paths) if args.allowed_paths else None
        )

    @staticmethod
    def open_folder(folder_path: str):
        if os.path.exists(folder_path):
            import platform
            try:
                if platform.system() == "Windows":
                    os.startfile(folder_path)
                elif platform.system() == "Darwin":
                    os.system(f"open \"{folder_path}\"")
                else:
                    os.system(f"xdg-open \"{folder_path}\"")
            except Exception as e:
                logger.error(f"Failed to open folder {folder_path}: {e}")
        else:
            os.makedirs(folder_path, exist_ok=True)
            logger.info(f"The directory path {folder_path} has newly created.")


parser = argparse.ArgumentParser()
parser.add_argument('--whisper_type', type=str, default=WhisperImpl.FASTER_WHISPER.value,
                    choices=[item.value for item in WhisperImpl],
                    help='A type of the whisper implementation (Github repo name)')
parser.add_argument('--share', type=str2bool, default=False, nargs='?', const=True, help='Gradio share value')
parser.add_argument('--server_name', type=str, default=None, help='Gradio server host')
parser.add_argument('--server_port', type=int, default=None, help='Gradio server port')
parser.add_argument('--root_path', type=str, default=None, help='Gradio root path')
parser.add_argument('--username', type=str, default=None, help='Gradio authentication username')
parser.add_argument('--password', type=str, default=None, help='Gradio authentication password')
parser.add_argument('--theme', type=str, default=None, help='Gradio Blocks theme')
parser.add_argument('--colab', type=str2bool, default=False, nargs='?', const=True, help='Is colab user or not')
parser.add_argument('--api_open', type=str2bool, default=False, nargs='?', const=True,
                    help='Enable api or not in Gradio')
parser.add_argument('--allowed_paths', type=str, default=None, help='Gradio allowed paths')
parser.add_argument('--inbrowser', type=str2bool, default=True, nargs='?', const=True,
                    help='Whether to automatically start Gradio app or not')
parser.add_argument('--ssl_verify', type=str2bool, default=True, nargs='?', const=True,
                    help='Whether to verify SSL or not')
parser.add_argument('--ssl_keyfile', type=str, default=None, help='SSL Key file location')
parser.add_argument('--ssl_keyfile_password', type=str, default=None, help='SSL Key file password')
parser.add_argument('--ssl_certfile', type=str, default=None, help='SSL cert file location')
parser.add_argument('--whisper_model_dir', type=str, default=WHISPER_MODELS_DIR,
                    help='Directory path of the whisper model')
parser.add_argument('--faster_whisper_model_dir', type=str, default=FASTER_WHISPER_MODELS_DIR,
                    help='Directory path of the faster-whisper model')
parser.add_argument('--insanely_fast_whisper_model_dir', type=str,
                    default=INSANELY_FAST_WHISPER_MODELS_DIR,
                    help='Directory path of the insanely-fast-whisper model')
parser.add_argument('--diarization_model_dir', type=str, default=DIARIZATION_MODELS_DIR,
                    help='Directory path of the diarization model')
parser.add_argument('--nllb_model_dir', type=str, default=NLLB_MODELS_DIR,
                    help='Directory path of the Facebook NLLB model')
parser.add_argument('--uvr_model_dir', type=str, default=UVR_MODELS_DIR,
                    help='Directory path of the UVR model')
parser.add_argument('--output_dir', type=str, default=OUTPUT_DIR, help='Directory path of the outputs')
_args = parser.parse_args()

if __name__ == "__main__":
    app = App(args=_args)
    app.launch()
