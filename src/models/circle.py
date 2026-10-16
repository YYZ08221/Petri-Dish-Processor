from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DishCircle:
    x: float
    y: float
    radius: float
    manual_adjusted: bool = False
    rotation_degrees: int = 0

    def copy(self) -> "DishCircle":
        return DishCircle(self.x, self.y, self.radius, self.manual_adjusted, self.rotation_degrees)

    def as_tuple(self) -> tuple[float, float, float]:
        return self.x, self.y, self.radius
