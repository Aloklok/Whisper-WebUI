import os
import shutil
import glob
from modules.utils.logger import get_logger

logger = get_logger()

def clean_temp_dir():
    """清理临时文件夹和播客缓存"""
    # 1. 清理 temp 目录
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
    if os.path.exists(temp_dir):
        logger.info(f"正在清理临时目录: {temp_dir}")
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f"无法删除 {file_path}: {e}")
    
    # 2. 清理 modules 目录下的播客缓存文件 (*.mp3, *.m4a)
    modules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
    podcast_files = glob.glob(os.path.join(modules_dir, "podcast_*.*"))
    for f in podcast_files:
        try:
            os.remove(f)
            logger.info(f"已删除播客缓存: {f}")
        except Exception as e:
            logger.error(f"无法删除播客文件 {f}: {e}")

    return "清理完成！已释放临时空间并清空播客缓存。"

if __name__ == "__main__":
    result = clean_temp_dir()
    print(result)
