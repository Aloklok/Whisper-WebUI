import os
import re
import subprocess

import requests

from modules.utils.logger import get_logger

logger = get_logger()

# 小宇宙FM 网页 URL 正则匹配
XIAOYUZHOU_EPISODE_PATTERN = re.compile(
    r"https?://(?:www\.)?xiaoyuzhoufm\.com/episode/[\w-]+"
)


def is_xiaoyuzhou_url(url: str) -> bool:
    """检查是否为小宇宙FM的节目链接"""
    return bool(XIAOYUZHOU_EPISODE_PATTERN.match(url.strip()))


def parse_podcast_url(url: str) -> dict:
    """
    解析小宇宙播客页面，从 HTML <meta> 标签中提取音频链接和标题。

    Parameters
    ----------
    url: str
        小宇宙播客节目链接，例如 https://www.xiaoyuzhoufm.com/episode/xxx

    Returns
    ----------
    dict
        包含 'title' 和 'audio_url' 的字典
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    response = requests.get(url.strip(), headers=headers, timeout=30)
    response.raise_for_status()
    html = response.text

    # 从 <meta property="og:audio" content="..."> 提取音频链接
    audio_match = re.search(
        r'<meta\s+property=["\']og:audio["\']\s+content=["\'](.*?)["\']',
        html
    )
    if not audio_match:
        raise ValueError("无法从页面中提取音频链接，请检查链接是否正确")

    # 从 <meta property="og:title" content="..."> 提取标题
    title_match = re.search(
        r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']',
        html
    )
    title = title_match.group(1) if title_match else "podcast_audio"

    return {
        "title": title,
        "audio_url": audio_match.group(1),
    }


def _sanitize_filename(filename: str) -> str:
    """移除文件名中的非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    return re.sub(illegal_chars, '', filename).strip()


def download_podcast_audio(url: str) -> tuple:
    """
    从小宇宙播客链接下载音频文件。

    Parameters
    ----------
    url: str
        小宇宙播客节目链接

    Returns
    ----------
    tuple(str, str)
        (下载后的音频文件路径, 播客标题)
    """
    if not is_xiaoyuzhou_url(url):
        raise ValueError("暂只支持小宇宙FM链接（xiaoyuzhoufm.com/episode/...）")

    logger.info(f"正在解析播客链接: {url}")
    data = parse_podcast_url(url)
    title = data["title"]
    audio_url = data["audio_url"]
    logger.info(f"播客标题: {title}")
    logger.info(f"音频链接: {audio_url}")

    # 下载音频文件
    safe_title = _sanitize_filename(title)
    
    # 原始下载临时文件
    raw_path = os.path.join("modules", f"podcast_tmp_{safe_title}.m4a")
    # 最终输出的 MP3 文件 (MP3 音质足矣，且兼容 libsndfile 读取，体积仅有 WAV 的 1/8)
    fixed_path = os.path.join("modules", f"podcast_{safe_title}.mp3")

    # [优化] 如果文件已存在，直接返回，避免重复下载和转码
    if os.path.exists(fixed_path):
        logger.info(f"检测到播客文件已存在，跳过下载: {fixed_path}")
        return fixed_path, title

    logger.info(f"正在下载播客音频至临时文件 {raw_path} ...")
    resp = requests.get(audio_url, timeout=300, stream=True)
    resp.raise_for_status()
    with open(raw_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    logger.info(f"音频下载完成: {raw_path}")
    
    # 使用 ffmpeg 转换为 mp3 格式
    # VAD / separation 要求 libsndfile 支持的格式 (mp3、wav、ogg 等)，且 mp3 体积很小
    try:
        subprocess.run([
            'ffmpeg', '-y',
            '-i', raw_path,
            '-c:a', 'libmp3lame', '-q:a', '5',  # -q:a 5 对应约 130kbps VBR，体积和音质的完美平衡
            fixed_path
        ], check=True, capture_output=True)
        logger.info(f"音频转换完成: {fixed_path}")

        # 清理原始下载文件
        if os.path.exists(raw_path):
            os.remove(raw_path)

        return fixed_path, title
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg 转换失败: {e}")
        # 转换失败时尝试返回原始文件
        if os.path.exists(fixed_path):
            os.remove(fixed_path)
        return raw_path, title
    except FileNotFoundError:
        logger.warning("未找到 ffmpeg，跳过格式转换，直接使用原始文件")
        return raw_path, title
