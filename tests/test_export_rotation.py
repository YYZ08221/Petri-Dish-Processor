from pathlib import Path

import pandas as pd

from src.core.image_io import read_image, save_image
from src.models.circle import DishCircle
from src.models.image_item import ImageItem
from src.services.export_service import ExportService


def test_export_rotates_before_final_crop_and_logs_angle(tmp_path):
    source = tmp_path / "source.png"
    image = _striped_image(40)
    save_image(source, image)
    item = ImageItem(
        path=source,
        circles=[DishCircle(20, 20, 8, rotation_degrees=45)],
    )

    log_path = ExportService(crop_factor=1.0, export_format="png").export_items([item], tmp_path / "out")

    exported = read_image(tmp_path / "out" / "source-1.png")
    assert exported.shape == (16, 16, 3)
    assert exported[0, 0].tolist() != [0, 0, 0]

    records = pd.read_csv(log_path, encoding="utf-8-sig")
    assert records.loc[0, "旋转角度"] == 45


def test_export_applies_full_image_rotation_and_circle_crop_shape(tmp_path):
    source = tmp_path / "source.png"
    image = _striped_image(40)
    save_image(source, image)
    item = ImageItem(
        path=source,
        circles=[DishCircle(20, 20, 8)],
        image_rotation_degrees=90,
    )

    log_path = ExportService(crop_factor=1.0, export_format="png", crop_shape="圆形").export_items([item], tmp_path / "out")

    exported = read_image(tmp_path / "out" / "source-1.png")
    assert exported.shape == (16, 16, 3)
    assert exported[0, 0].tolist() == [0, 0, 0]
    assert exported[8, 8].tolist() != [0, 0, 0]

    records = pd.read_csv(log_path, encoding="utf-8-sig")
    assert records.loc[0, "全图旋转角度"] == 90
    assert records.loc[0, "裁剪形状"] == "圆形"


def test_export_current_can_use_custom_name_for_single_crop(tmp_path):
    source = tmp_path / "source.png"
    save_image(source, _striped_image(40))
    item = ImageItem(path=source, circles=[DishCircle(20, 20, 8)])

    ExportService(crop_factor=1.0, export_format="png").export_items(
        [item],
        tmp_path / "out",
        base_name_override="PBS-65",
    )

    assert (tmp_path / "out" / "PBS-65.png").exists()


def test_export_current_suffixes_custom_name_for_multiple_crops(tmp_path):
    source = tmp_path / "source.png"
    save_image(source, _striped_image(80))
    item = ImageItem(
        path=source,
        circles=[
            DishCircle(20, 20, 8),
            DishCircle(60, 60, 8),
        ],
    )

    ExportService(crop_factor=1.0, export_format="png").export_items(
        [item],
        tmp_path / "out",
        base_name_override="PBS-65",
    )

    assert (tmp_path / "out" / "PBS-65-1.png").exists()
    assert (tmp_path / "out" / "PBS-65-2.png").exists()
    assert not (tmp_path / "out" / "source-1.png").exists()


def _striped_image(size: int):
    import numpy as np

    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, : size // 2] = [255, 255, 255]
    image[:, size // 2 :] = [80, 80, 80]
    return image
