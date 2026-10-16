from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from src.models.image_item import SUPPORTED_EXTENSIONS


def list_images(folder: Path) -> list[Path]:
    paths: list[Path] = []
    for path in folder.iterdir():
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            paths.append(path)
    return sorted(paths, key=lambda p: p.name.lower())


def read_image(path: Path) -> np.ndarray:
    """Read an image as BGR uint8 array while supporting Unicode Windows paths."""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is not None:
        return image

    with Image.open(path) as pil_image:
        pil_image = pil_image.convert("RGB")
        rgb = np.array(pil_image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def bgr_to_qimage_data(image: np.ndarray) -> tuple[bytes, int, int, int]:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    bytes_per_line = channels * width
    return rgb.tobytes(), width, height, bytes_per_line


def save_image(path: Path, image: np.ndarray, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    params: list[int] = []
    if ext in {".jpg", ".jpeg"}:
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    ok, encoded = cv2.imencode(ext, image, params)
    if ok:
        encoded.tofile(str(path))
        return

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    Image.fromarray(rgb).save(path)
