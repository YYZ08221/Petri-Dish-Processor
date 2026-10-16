from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.models.circle import DishCircle


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


@dataclass
class ImageItem:
    path: Path
    status: str = "未处理"
    circles: list[DishCircle] = field(default_factory=list)
    original_circles: list[DishCircle] = field(default_factory=list)
    manual_adjusted: bool = False
    image_rotation_degrees: int = 0
    error: str = ""

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def count(self) -> int:
        return len(self.circles)

    def set_detected_circles(self, circles: list[DishCircle]) -> None:
        ordered = sort_circles(circles)
        self.circles = [c.copy() for c in ordered]
        self.original_circles = [c.copy() for c in ordered]
        self.manual_adjusted = False
        self.status = "需确认" if self.circles else "需确认"

    def reset(self) -> None:
        self.circles = [c.copy() for c in self.original_circles]
        self.manual_adjusted = False
        self.status = "需确认"


def sort_circles(circles: list[DishCircle]) -> list[DishCircle]:
    if not circles:
        return []
    avg_radius = sum(c.radius for c in circles) / len(circles)
    row_height = max(avg_radius * 1.5, 1.0)
    return sorted(circles, key=lambda c: (round(c.y / row_height), c.x))
