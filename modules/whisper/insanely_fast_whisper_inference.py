import os
import time
import numpy as np
from typing import BinaryIO, Union, Tuple, List, Callable
import torch
from transformers import pipeline
from transformers.utils import is_flash_attn_2_available
import gradio as gr
from huggingface_hub import hf_hub_download, snapshot_download
import whisper
from rich.progress import Progress, TimeElapsedColumn, BarColumn, TextColumn
from argparse import Namespace
import tempfile
import scipy.io.wavfile as wavfile

from modules.utils.paths import (INSANELY_FAST_WHISPER_MODELS_DIR, DIARIZATION_MODELS_DIR, UVR_MODELS_DIR, OUTPUT_DIR)
from modules.whisper.data_classes import *
from modules.whisper.base_transcription_pipeline import BaseTranscriptionPipeline
from modules.utils.logger import get_logger

logger = get_logger()


class InsanelyFastWhisperInference(BaseTranscriptionPipeline):
    def __init__(self,
                 model_dir: str = INSANELY_FAST_WHISPER_MODELS_DIR,
                 diarization_model_dir: str = DIARIZATION_MODELS_DIR,
                 uvr_model_dir: str = UVR_MODELS_DIR,
                 output_dir: str = OUTPUT_DIR,
                 ):
        super().__init__(
            model_dir=model_dir,
            output_dir=output_dir,
            diarization_model_dir=diarization_model_dir,
            uvr_model_dir=uvr_model_dir
        )
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)

        self.available_models = get_labeled_choices(self.get_model_paths())

    def transcribe(self,
                   audio: Union[str, np.ndarray, torch.Tensor],
                   progress: gr.Progress = gr.Progress(),
                   progress_callback: Optional[Callable] = None,
                   *whisper_params,
                   ) -> Tuple[List[Segment], float]:
        """
        transcribe method for faster-whisper.

        Parameters
        ----------
        audio: Union[str, BinaryIO, np.ndarray]
            Audio path or file binary or Audio numpy array
        progress: gr.Progress
            Indicator to show progress directly in gradio.
        progress_callback: Optional[Callable]
            callback function to show progress. Can be used to update progress in the backend.
        *whisper_params: tuple
            Parameters related with whisper. This will be dealt with "WhisperParameters" data class

        Returns
        ----------
        segments_result: List[Segment]
            list of Segment that includes start, end timestamps and transcribed text
        elapsed_time: float
            elapsed time for transcription
        """
        start_time = time.time()
        params = WhisperParams.from_list(list(whisper_params))

        if params.model_size != self.current_model_size or self.model is None or self.current_compute_type != params.compute_type:
            self.update_model(params.model_size, params.compute_type, progress)

        progress(0, desc="Transcribing...Progress is not shown in insanely-fast-whisper.")
        with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(style="yellow1", pulse_style="white"),
                TimeElapsedColumn(),
        ) as progress:
            progress.add_task("[yellow]Transcribing...", total=None)

            kwargs = {
                "no_speech_threshold": params.no_speech_threshold,
                "temperature": params.temperature,
                "compression_ratio_threshold": params.compression_ratio_threshold,
                "logprob_threshold": params.log_prob_threshold,
            }

            if self.current_model_size.endswith(".en"):
                pass
            else:
                kwargs["language"] = params.lang
                kwargs["task"] = "translate" if params.is_translate else "transcribe"

            # 注入投机采样模型
            if hasattr(self, "assistant_model") and self.assistant_model:
                kwargs["assistant_model"] = self.assistant_model

            if self._original_pipeline_transcribe:
                # 标准 Transformers Pipeline 路径
                segments_data = self.model(
                    inputs=audio,
                    return_timestamps=True,
                    chunk_length_s=params.chunk_length,
                    batch_size=params.batch_size,
                    generate_kwargs=kwargs
                )
                
                segments_result = []
                for item in segments_data["chunks"]:
                    start, end = item["timestamp"][0], item["timestamp"][1]
                    if end is None:
                        end = start
                    segments_result.append(Segment(
                        text=item["text"],
                        start=start,
                        end=end
                    ))
            else:
                # Qwen-ASR 原生高性能路径
                qwen_lang = params.lang if params.lang not in [None, "Automatic Detection"] else None
                
                # Qwen-ASR 由于内部实现，目前必须通过文件路径输入才能稳定支持时间轴对齐
                # 如果传入的是 numpy 数组 (通常是因为经过了 VAD 或 BGM 分离预处理)，则需要转存临时文件
                if isinstance(audio, (str, bytes, os.PathLike)):
                    tmp_wav_path = audio
                    is_temp_file = False
                    logger.info(f"Qwen 接口直接使用原始音频路径: {tmp_wav_path}")
                else:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                        tmp_wav_path = tmp_wav.name
                    is_temp_file = True
                    # 将 numpy 数组写入临时 WAV (16kHz, float32)
                    wavfile.write(tmp_wav_path, 16000, audio.astype(np.float32))
                    logger.info(f"已将处理后的音频导出至临时文件以适配 Qwen 接口: {tmp_wav_path}")
                
                try:
                    qwen_results = self.model.transcribe(
                        audio=tmp_wav_path,
                        language=qwen_lang,
                        return_time_stamps=True
                    )
                    
                    segments_result = []
                    for r in qwen_results:
                        if hasattr(r, "time_stamps") and r.time_stamps:
                            for ts in r.time_stamps:
                                segments_result.append(Segment(
                                    text=ts.text, 
                                    start=ts.start_time, 
                                    end=ts.end_time
                                ))
                        else:
                            segments_result.append(Segment(text=r.text, start=0, end=0))
                except Exception as e:
                    logger.error(f"Qwen 原生转录失败，请检查 qwen-asr 库状态: {e}")
                    raise e
                finally:
                    # 确保仅清理我们创建的临时文件
                    if is_temp_file and os.path.exists(tmp_wav_path):
                        try:
                            os.remove(tmp_wav_path)
                            logger.info(f"已清理 Qwen 临时音频文件: {tmp_wav_path}")
                        except:
                            pass

        # 为 Qwen 模型做特定的输出转换（如果使用了 qwen-asr 库）
        if getattr(self, "is_qwen", False):
            # Qwen3ASRModel.transcribe 返回的是包含结果对象的列表
            # 这里需要根据实际 qwen-asr 返回结构同步调整，目前预留适配接口
            pass

        elapsed_time = time.time() - start_time
        return segments_result, elapsed_time

    def update_model(self,
                     model_size: str,
                     compute_type: str,
                     progress: gr.Progress = gr.Progress(),
                     ):
        """
        Update current model setting

        Parameters
        ----------
        model_size: str
            Size of whisper model
        compute_type: str
            Compute type for transcription.
            see more info : https://opennmt.net/CTranslate2/quantization.html
        progress: gr.Progress
            Indicator to show progress directly in gradio.
        """
        progress(0, desc="Initializing Model..")
        model_size = normalize_model_name(model_size)
        # 规范化路径，避免 Windows 上的混合斜杠问题
        model_path = os.path.abspath(os.path.normpath(os.path.join(self.model_dir, model_size)))

        # 强化校验：对于 Qwen 模型，必须检查标志性文件
        is_qwen = "qwen" in model_size.lower()
        needs_download = not os.path.isdir(model_path) or not os.listdir(model_path)
        if is_qwen and os.path.isdir(model_path):
            # 如果是 Qwen 目录已存在，但缺少 merges.txt 或 tokenizer.json，也视为需要补全下载
            vital_files = ["config.json", "tokenizer.json", "merges.txt"]
            if not all(os.path.exists(os.path.join(model_path, f)) for f in vital_files):
                needs_download = True

        if needs_download:
            self.download_model(
                model_size=model_size,
                download_root=model_path,
                progress=progress
            )

        self.current_compute_type = self._get_torch_dtype(compute_type)
        self.current_model_size = model_size
        self.is_qwen = "qwen" in model_size.lower()

        # Qwen 不支持以 int8 加载，强制切换为 float16
        if self.is_qwen and self.current_compute_type == torch.int8:
            logger.info("Qwen 模型不支持 int8 精度，已自动调整为 float16 以确保运行。")
            self.current_compute_type = torch.float16

        if self.is_qwen:
            try:
                from qwen_asr import Qwen3ASRModel
                logger.info("检测到 Qwen 模型，正在尝试使用 qwen-asr 高性能后端...")
                # Qwen 必须配备 Forced Aligner 才能输出用于说话人分离的时间戳
                aligner_model_id = "Qwen/Qwen3-ForcedAligner-0.6B"
                aligner_path = os.path.abspath(os.path.normpath(os.path.join(self.model_dir, aligner_model_id)))
                
                if not os.path.exists(aligner_path) or not os.listdir(aligner_path):
                    logger.info(f"正在补全 Qwen 必备的对齐模型: {aligner_model_id}")
                    self.download_model(model_size=aligner_model_id, download_root=aligner_path, progress=progress)

                self.model = Qwen3ASRModel.from_pretrained(
                    model_path,
                    forced_aligner=aligner_path, # 注入对齐模型路径
                    torch_dtype=self.current_compute_type,
                    device_map="auto" if self.device == "cuda" else None,
                    trust_remote_code=True
                )
                # 修改 transcribe 方法使其兼容 Qwen 模型调用
                self._original_pipeline_transcribe = False
            except (ImportError, Exception) as e:
                logger.warning(f"无法使用 qwen-asr 加载 ({e})，正在回退到标准 Transformers 链路...")
                self.is_qwen = False

        if not self.is_qwen:
            try:
                # 优先尝试标准流程 (适合 Whisper/Distil-Whisper)
                self.model = pipeline(
                    "automatic-speech-recognition",
                    model=model_path,
                    torch_dtype=self.current_compute_type,
                    device=self.device if self.device != "cuda" else None,
                    device_map="auto" if self.device == "cuda" else None,
                    trust_remote_code=True,
                    model_kwargs={"attn_implementation": "flash_attention_2"} if is_flash_attn_2_available() else {"attn_implementation": "sdpa"},
                )
                self._original_pipeline_transcribe = True
            except (ValueError, Exception) as e:
                # 如果标准加载失败 (常见于 Qwen 的 Unrecognized configuration class)，尝试手动加载
                if isinstance(e, ValueError) and "Unrecognized configuration class" in str(e):
                    logger.info(f"标准 pipeline 无法识别 ASR 任务类，正在切换至手动对象加载模式: {model_path}")
                    try:
                        from transformers import AutoModel, AutoProcessor
                        processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
                        model = AutoModel.from_pretrained(
                            model_path,
                            torch_dtype=self.current_compute_type,
                            device_map="auto" if self.device == "cuda" else None,
                            trust_remote_code=True
                        )
                        self.model = pipeline(
                            "automatic-speech-recognition",
                            model=model,
                            tokenizer=processor.tokenizer,
                            feature_extractor=processor.feature_extractor,
                            torch_dtype=self.current_compute_type,
                            device_map=None,
                            trust_remote_code=True,
                            model_kwargs={"attn_implementation": "flash_attention_2"} if is_flash_attn_2_available() else {"attn_implementation": "sdpa"},
                        )
                        self._original_pipeline_transcribe = True
                        logger.info("手动对象加载成功！")
                    except Exception as inner_e:
                        logger.error(f"手动对象加载也失败了: {inner_e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        raise inner_e
                else:
                    logger.error(f"Transformers pipeline 加载极其严重失败: {e}")
                    # 如果还是搞不定，最后尝试强制手动加载处理器
                    try:
                        from transformers import AutoProcessor, AutoModel
                        logger.info("进行最后的强制手动对象加载尝试...")
                        # 显式指定 merges 和 vocab 路径（如果 snapshot 补全了的话）
                        processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
                        model = AutoModel.from_pretrained(model_path, torch_dtype=self.current_compute_type, device_map="auto" if self.device == "cuda" else None, trust_remote_code=True)
                        self.model = pipeline("automatic-speech-recognition", model=model, tokenizer=processor.tokenizer, feature_extractor=processor.feature_extractor, torch_dtype=self.current_compute_type, device_map=None, trust_remote_code=True)
                        self._original_pipeline_transcribe = True
                        logger.info("终极加载方案成功！")
                    except Exception as final_e:
                        logger.error(f"彻底无法加载模型: {final_e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        raise final_e

        # 加载投机采样辅助模型 (Assistant Model)
        self.assistant_model = None
        if "large" in model_size.lower():
            try:
                logger.info("正在加载投机采样辅助模型 (tiny)...")
                # 优先检查本地是否存在 tiny，没有则加载默认的 openai/whisper-tiny
                assistant_model_id = "openai/whisper-tiny"
                self.assistant_model = assistant_model_id
            except Exception as e:
                logger.warning(f"无法加载投机采样辅助模型: {e}")

    def _get_torch_dtype(self, compute_type: str):
        if compute_type == "float16":
            return torch.float16
        elif compute_type == "float32":
            return torch.float32
        elif compute_type == "int8":
            return torch.int8
        elif compute_type == "bfloat16":
            return torch.bfloat16
        return torch.float16

    def get_model_paths(self):
        """
        Get available models from models path including fine-tuned model.

        Returns
        ----------
        Name set of models
        """
        openai_models = whisper.available_models()
        distil_models = ["distil-large-v2", "distil-large-v3", "distil-medium.en", "distil-small.en"]
        qwen_models = ["Qwen/Qwen3-ASR-1.7B", "Qwen/Qwen3-ASR-0.6B"]
        default_models = openai_models + distil_models + qwen_models

        existing_models = os.listdir(self.model_dir)
        wrong_dirs = [".locks", "insanely_fast_whisper_models_will_be_saved_here"]

        available_models = default_models + existing_models
        available_models = [model for model in available_models if model not in wrong_dirs]
        available_models = sorted(set(available_models), key=available_models.index)

        return available_models

    @staticmethod
    def download_model(
        model_size: str,
        download_root: str,
        progress: gr.Progress
    ):
        progress(0, 'Initializing model..')
        logger.info(f'Downloading {model_size} to "{download_root}"....')

        os.makedirs(download_root, exist_ok=True)
        download_list = [
            "model.safetensors",
            "config.json",
            "generation_config.json",
            "preprocessor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "added_tokens.json",
            "special_tokens_map.json",
            "vocab.json",
        ]

        if "/" in model_size:
            repo_id = model_size
        elif model_size.startswith("distil"):
            repo_id = f"distil-whisper/{model_size}"
        else:
            repo_id = f"openai/whisper-{model_size}"
        
        # 使用 snapshot_download 下载全仓文件，这对于 Qwen 这种带 .py 脚本的模型至关重要
        try:
            snapshot_download(
                repo_id=repo_id,
                local_dir=download_root,
                local_dir_use_symlinks=False, # 避免 Windows 符号链接权限问题
                ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
            )
            logger.info(f"模型 {model_size} 下载/补全完成。")
        except Exception as e:
            logger.error(f"下载模型失败: {e}")
            raise e
