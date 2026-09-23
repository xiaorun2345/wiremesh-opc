"""文件处理工具函数"""
import os
import tempfile
from pathlib import Path
from loguru import logger


def safe_temp_file(suffix: str = "", prefix: str = "openspec_") -> str:
    """创建临时文件，返回路径。调用方负责删除。"""
    f = tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix, delete=False)
    f.close()
    return f.name


def cleanup_temp_file(path: str):
    """安全删除临时文件，失败时只记录警告不抛出异常"""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception as e:
        logger.warning(f"删除临时文件失败: {path} — {e}")


def cleanup_temp_files(*paths: str):
    """批量删除临时文件"""
    for path in paths:
        cleanup_temp_file(path)


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写，不含点）"""
    return Path(filename).suffix.lstrip(".").lower()


def is_safe_filename(filename: str) -> bool:
    """检查文件名是否安全（防路径穿越）"""
    name = Path(filename).name
    return name == filename and ".." not in filename and "/" not in filename
