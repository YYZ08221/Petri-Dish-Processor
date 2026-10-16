from __future__ import annotations

import cv2
import numpy as np

from src.models.circle import DishCircle


def crop_square_with_padding(
    image: np.ndarray,
    circle: DishCircle,
    crop_factor: float = 1.10,
    pad_color: tuple[int, int, int] = (0, 0, 0),
) -> tuple[np.ndarray, int]:
    side = max(1, int(round(circle.radius * 2 * crop_factor)))
    half = side / 2.0
    left = int(round(circle.x - half))
    top = int(round(circle.y - half))
    right = left + side
    bottom = top + side

    h, w = image.shape[:2]
    src_left = max(left, 0)
    src_top = max(top, 0)
    src_right = min(right, w)
    src_bottom = min(bottom, h)

    output = np.full((side, side, image.shape[2]), pad_color, dtype=image.dtype)
    dst_left = src_left - left
    dst_top = src_top - top
    dst_right = dst_left + max(0, src_right - src_left)
    dst_bottom = dst_top + max(0, src_bottom - src_top)

    if src_right > src_left and src_bottom > src_top:
        output[dst_top:dst_bottom, dst_left:dst_right] = image[src_top:src_bottom, src_left:src_right]
    return output, side


def crop_square_rotated(
    image: np.ndarray,
    circle: DishCircle,
    crop_factor: float = 1.10,
    pad_color: tuple[int, int, int] = (0, 0, 0),
) -> tuple[np.ndarray, int]:
    side = max(1, int(round(circle.radius * 2 * crop_factor)))
    angle = int(circle.rotation_degrees) % 360
    if angle == 0:
        return crop_square_with_padding(image, circle, crop_factor, pad_color)

    expanded_side = int(np.ceil(side * np.sqrt(2)))
    if expanded_side % 2 != side % 2:
        expanded_side += 1
    expanded_radius = expanded_side / (2 * crop_factor)
    expanded = DishCircle(circle.x, circle.y, expanded_radius)
    oversized, _expanded_side = crop_square_with_padding(image, expanded, crop_factor, pad_color)
    rotated = rotate_image_keep_size(oversized, circle.rotation_degrees, pad_color)

    start = max(0, (rotated.shape[0] - side) // 2)
    end = start + side
    return rotated[start:end, start:end].copy(), side


def crop_dish_image(
    image: np.ndarray,
    circle: DishCircle,
    crop_factor: float = 1.10,
    crop_shape: str = "方形",
    pad_color: tuple[int, int, int] = (0, 0, 0),
) -> tuple[np.ndarray, int]:
    cropped, side = crop_square_rotated(image, circle, crop_factor, pad_color)
    if crop_shape != "圆形":
        return cropped, side

    center = (side - 1) / 2.0
    radius = side / 2.0
    y, x = np.ogrid[:side, :side]
    mask = (x - center) ** 2 + (y - center) ** 2 <= radius**2
    output = np.full_like(cropped, pad_color)
    output[mask] = cropped[mask]
    return output, side


def apply_full_image_rotation(image: np.ndarray, angle_degrees: int) -> np.ndarray:
    angle = int(angle_degrees) % 360
    if angle == 0:
        return image.copy()
    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError("全图旋转只支持 0、90、180、270 度")


def rotate_circle_quarter_turn(circle: DishCircle, width: int, height: int, angle_degrees: int) -> DishCircle:
    angle = int(angle_degrees) % 360
    if angle == 0:
        return circle.copy()
    if angle == 90:
        x, y = height - 1 - circle.y, circle.x
    elif angle == 180:
        x, y = width - 1 - circle.x, height - 1 - circle.y
    elif angle == 270:
        x, y = circle.y, width - 1 - circle.x
    else:
        raise ValueError("全图旋转只支持 0、90、180、270 度")
    return DishCircle(x, y, circle.radius, circle.manual_adjusted, circle.rotation_degrees)


def rotate_image_keep_size(
    image: np.ndarray,
    angle_degrees: int,
    fill_color: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    angle = int(angle_degrees) % 360
    if angle == 0:
        return image.copy()

    h, w = image.shape[:2]
    center = ((w - 1) / 2.0, (h - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=fill_color,
    )


def draw_detection_preview(image: np.ndarray, circles: list[DishCircle]) -> np.ndarray:
    preview = image.copy()
    for index, circle in enumerate(circles, start=1):
        center = (int(round(circle.x)), int(round(circle.y)))
        radius = int(round(circle.radius))
        cv2.circle(preview, center, radius, (0, 255, 0), 3)
        cv2.putText(
            preview,
            str(index),
            (center[0] + 8, center[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return preview
