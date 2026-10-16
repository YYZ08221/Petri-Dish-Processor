from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = timestamp()
    candidate = path.with_name(f"{path.stem}_{stamp}{path.suffix}")
    index = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{stamp}_{index}{path.suffix}")
        index += 1
    return candidate


def unique_output_dir(base_folder: Path, prefix: str = "processed") -> Path:
    initial = base_folder / f"{prefix}_{timestamp()}"
    if not initial.exists():
        initial.mkdir(parents=True, exist_ok=False)
        return initial
    index = 2
    while True:
        candidate = base_folder / f"{initial.name}_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        index += 1


def output_name(original_path: Path, index: int, forced_ext: str | None = None) -> str:
    ext = forced_ext if forced_ext else original_path.suffix
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"{original_path.stem}-{index}{ext.lower()}"


def sanitize_output_base_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip())
    cleaned = cleaned.rstrip(" .")
    return cleaned


def custom_output_name(base_name: str, index: int, total: int, forced_ext: str | None = None, original_ext: str = "") -> str:
    ext = forced_ext if forced_ext else original_ext
    if not ext.startswith("."):
        ext = f".{ext}"
    stem = sanitize_output_base_name(base_name)
    if not stem:
        raise ValueError("请输入有效的文件名")
    suffix = f"-{index}" if total > 1 else ""
    return f"{stem}{suffix}{ext.lower()}"
