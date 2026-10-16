import numpy as np

from src.core.cropping import apply_full_image_rotation, crop_square_rotated, rotate_circle_quarter_turn, rotate_image_keep_size
from src.models.circle import DishCircle


def test_rotate_image_keep_size_preserves_shape_and_fills_corners():
    image = np.full((9, 9, 3), 255, dtype=np.uint8)

    rotated = rotate_image_keep_size(image, 45)

    assert rotated.shape == image.shape
    assert rotated[0, 0].tolist() == [0, 0, 0]
    assert rotated[4, 4].tolist() == [255, 255, 255]


def test_circle_copy_preserves_rotation_angle():
    circle = DishCircle(10, 20, 30, manual_adjusted=True, rotation_degrees=13)

    copied = circle.copy()

    assert copied.rotation_degrees == 13
    assert copied.manual_adjusted is True


def test_crop_square_rotated_rotates_before_final_crop_to_avoid_corner_black_edges():
    image = np.full((60, 60, 3), 255, dtype=np.uint8)
    circle = DishCircle(30, 30, 10, rotation_degrees=45)

    cropped, side = crop_square_rotated(image, circle, crop_factor=1.0)

    assert side == 20
    assert cropped.shape == (20, 20, 3)
    assert cropped[0, 0].tolist() == [255, 255, 255]
    assert cropped[-1, -1].tolist() == [255, 255, 255]


def test_apply_full_image_rotation_rotates_clockwise_without_padding():
    image = np.zeros((2, 3, 3), dtype=np.uint8)
    image[0, 0] = [255, 0, 0]

    rotated = apply_full_image_rotation(image, 90)

    assert rotated.shape == (3, 2, 3)
    assert rotated[0, 1].tolist() == [255, 0, 0]


def test_rotate_circle_quarter_turn_updates_center_coordinates():
    circle = DishCircle(1, 0, 3, rotation_degrees=12)

    rotated = rotate_circle_quarter_turn(circle, width=3, height=2, angle_degrees=90)

    assert rotated.x == 1
    assert rotated.y == 1
    assert rotated.radius == 3
    assert rotated.rotation_degrees == 12
