from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.core.cropping import apply_full_image_rotation, crop_dish_image
from src.core.image_io import read_image, save_image
from src.models.image_item import ImageItem, sort_circles
from src.utils.naming import custom_output_name, output_name, timestamp, unique_output_dir, unique_path


class ExportService:
    def __init__(self, crop_factor: float = 1.10, export_format: str = "原格式", crop_shape: str = "方形") -> None:
        self.crop_factor = crop_factor
        self.export_format = export_format
        self.crop_shape = crop_shape

    def resolve_output_dir(self, input_folder: Path | None, selected_output: Path | None) -> Path:
        if selected_output:
            selected_output.mkdir(parents=True, exist_ok=True)
            return unique_output_dir(selected_output)
        if input_folder is None:
            base = Path.cwd() / "exports"
        else:
            base = input_folder
        return unique_output_dir(base)

    def export_items(self, items: list[ImageItem], output_dir: Path, base_name_override: str | None = None) -> Path:
        records: list[dict[str, object]] = []
        process_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in items:
            if item.status == "跳过" or not item.circles:
                continue
            image = apply_full_image_rotation(read_image(item.path), item.image_rotation_degrees)
            circles = sort_circles(item.circles)
            total = len(circles)
            for dish_index, circle in enumerate(circles, start=1):
                cropped, side = crop_dish_image(image, circle, self.crop_factor, self.crop_shape)
                forced_ext = None if self.export_format == "原格式" else self.export_format
                if base_name_override is None:
                    name = output_name(item.path, dish_index, forced_ext)
                else:
                    name = custom_output_name(base_name_override, dish_index, total, forced_ext, item.path.suffix)
                target = unique_path(output_dir / name)
                save_image(target, cropped)
                records.append(
                    {
                        "原图文件名": item.filename,
                        "输出文件名": target.name,
                        "培养皿序号": dish_index,
                        "圆心坐标x": round(circle.x, 2),
                        "圆心坐标y": round(circle.y, 2),
                        "半径": round(circle.radius, 2),
                        "裁剪边长": side,
                        "裁剪系数": self.crop_factor,
                        "裁剪形状": self.crop_shape,
                        "全图旋转角度": item.image_rotation_degrees,
                        "旋转角度": circle.rotation_degrees,
                        "是否人工调整": "是" if (item.manual_adjusted or circle.manual_adjusted) else "否",
                        "处理时间": process_time,
                        "输出路径": str(target),
                    }
                )
            item.status = "已处理"

        log_path = unique_path(output_dir / f"processing_log_{timestamp()}.csv")
        pd.DataFrame.from_records(records).to_csv(log_path, index=False, encoding="utf-8-sig")
        return log_path
