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

    # 根据 URL 或响应头推断扩展名，优先 MP3，其次 MP4（不要使用 m4a 作为默认扩展）
    def _ext_from_url(u: str):
        for ext in ('.mp3', '.wav', '.ogg', '.mp4', '.m4a', '.aac'):
            if u.lower().split('?')[0].endswith(ext):
                return ext
        return None

    guessed_ext = _ext_from_url(audio_url) or ''

    # 临时下载文件（不要使用 .m4a 扩展）
    if guessed_ext == '.mp3':
        raw_ext = '.mp3'
    elif guessed_ext in ('.mp4', '.m4a'):
        # use .mp4 for container types
        raw_ext = '.mp4'
    elif guessed_ext:
        raw_ext = guessed_ext
    else:
        # 默认优先使用 mp3
        raw_ext = '.mp3'

    raw_path = os.path.join("modules", f"podcast_tmp_{safe_title}{raw_ext}")
    # 最终输出的 MP3 文件
    fixed_path = os.path.join("modules", f"podcast_{safe_title}.mp3")

    # [优化] 如果文件已存在，直接返回，避免重复下载和转码
    if os.path.exists(fixed_path):
        logger.info(f"检测到播客文件已存在，跳过下载: {fixed_path}")
        return fixed_path, title

    # 如果临时下载文件已经存在，则复用该临时文件（避免重复下载）
    if os.path.exists(raw_path):
        logger.info(f"检测到临时文件已存在，复用临时文件: {raw_path}")
        return raw_path, title

    logger.info(f"正在下载播客音频至临时文件 {raw_path} ...")
    resp = requests.get(audio_url, timeout=300, stream=True)
    resp.raise_for_status()

    # 使用 Content-Type 优化扩展判断
    content_type = resp.headers.get('content-type', '').lower()
    if not guessed_ext:
        if 'audio/mpeg' in content_type or 'audio/x-mpeg' in content_type:
            raw_path = os.path.join("modules", f"podcast_tmp_{safe_title}.mp3")
            raw_ext = '.mp3'
            fixed_path = os.path.join("modules", f"podcast_{safe_title}.mp3")
        elif 'mp4' in content_type or 'm4a' in content_type or 'audio/mp4' in content_type:
            raw_path = os.path.join("modules", f"podcast_tmp_{safe_title}.mp4")
            raw_ext = '.mp4'

    with open(raw_path, "wb") as f:
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)

    logger.info(f"音频下载完成: {raw_path} (size={downloaded} bytes)")

    # 简单完整性校验：文件太小很可能是错误页面或不完整
    try:
        file_size = os.path.getsize(raw_path)
    except OSError:
        file_size = downloaded

    if file_size < 1024:
        # 小于 1KB 视为下载失败或非法内容
        logger.error(f"下载文件过小（{file_size} bytes），可能是错误响应或不完整文件: {raw_path}")
        raise ValueError("下载的音频文件过小或不完整，请检查链接或网络")
    
    # 使用 ffmpeg 转换为 mp3 格式
    # VAD / separation 要求 libsndfile 支持的格式 (mp3、wav、ogg 等)，且 mp3 体积很小
    # 如果下载的就是 MP3，直接返回；否则尝试用 ffmpeg 转码为 MP3
    if raw_ext == '.mp3':
        return raw_path, title

    try:
        subprocess.run([
            'ffmpeg', '-y',
            '-i', raw_path,
            '-c:a', 'libmp3lame', '-q:a', '5',
            fixed_path
        ], check=True, capture_output=True)
        logger.info(f"音频转换完成: {fixed_path}")

        # 清理原始下载文件
        try:
            if os.path.exists(raw_path):
                os.remove(raw_path)
        except Exception:
            logger.debug(f"无法删除临时文件: {raw_path}")

        return fixed_path, title
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg 转换失败: {e}")
        logger.info(f"ffmpeg 转换失败，返回原始文件: {raw_path}")
        # 转换失败时返回原始下载文件（可能是 mp4），但不要尝试再次重命名为 m4a
        if os.path.exists(fixed_path):
            try:
                os.remove(fixed_path)
            except Exception:
                pass
        return raw_path, title
    except FileNotFoundError:
        logger.warning("未找到 ffmpeg，跳过格式转换，直接使用原始文件")
        return raw_path, title
