import numpy as np

from src.core.cropping import crop_square_with_padding
from src.models.circle import DishCircle


def test_crop_square_with_black_padding_when_circle_near_edge():
    image = np.full((20, 20, 3), 255, dtype=np.uint8)
    cropped, side = crop_square_with_padding(image, DishCircle(2, 2, 10), 1.1)
    assert cropped.shape == (side, side, 3)
    assert side == 22
    assert cropped[0, 0].tolist() == [0, 0, 0]
