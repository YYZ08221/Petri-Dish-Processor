import os
import time
from pathlib import Path

import pytest

from src.core.detection import detect_dishes
from src.core.image_io import read_image


REFERENCE_DIR = Path(os.environ.get('CBL_REFERENCE_DIR', str(Path(__file__).parent / 'reference_images')))
REFERENCE_IMAGES = [
    REFERENCE_DIR / f'IMG_20260609_{suffix}.jpg'
    for suffix in ('091759', '091818', '091843', '091925', '091844', '091907', '091908', '091924')
]

DOUBLE_DISH_IMAGE = REFERENCE_DIR / 'IMG_20260609_092904.jpg'
DOUBLE_DISH_LEGACY_IMAGE = REFERENCE_DIR / 'IMG_20260609_092638.jpg'


@pytest.mark.parametrize("path", REFERENCE_IMAGES, ids=lambda p: p.name)
def test_auto_detects_one_reasonable_single_dish_on_reference_images(path):
    if not path.exists():
        pytest.skip(f"reference image missing: {path}")
    image = read_image(path)

    start = time.perf_counter()
    circles = detect_dishes(image, min_radius=120, max_radius=0, sensitivity=55, detection_mode="自动")
    elapsed = time.perf_counter() - start

    assert elapsed < 3.0
    assert len(circles) == 1
    circle = circles[0]
    height, width = image.shape[:2]
    assert width * 0.25 <= circle.x <= width * 0.75
    assert height * 0.35 <= circle.y <= height * 0.85
    assert min(width, height) * 0.18 <= circle.radius <= min(width, height) * 0.38


def test_multi_mode_detects_two_dishes_on_double_dish_reference_image():
    if not DOUBLE_DISH_IMAGE.exists():
        pytest.skip(f"reference image missing: {DOUBLE_DISH_IMAGE}")
    image = read_image(DOUBLE_DISH_IMAGE)

    circles = detect_dishes(image, min_radius=120, max_radius=0, sensitivity=55, detection_mode="多培养皿")

    assert len(circles) == 2
    left, right = sorted(circles, key=lambda circle: circle.x)
    assert left.x < image.shape[1] * 0.5
    assert right.x > image.shape[1] * 0.5
    assert abs(left.radius - right.radius) <= max(left.radius, right.radius) * 0.20


def test_single_mode_keeps_one_dish_on_double_dish_reference_image():
    if not DOUBLE_DISH_IMAGE.exists():
        pytest.skip(f"reference image missing: {DOUBLE_DISH_IMAGE}")
    image = read_image(DOUBLE_DISH_IMAGE)

    circles = detect_dishes(image, min_radius=120, max_radius=0, sensitivity=55, detection_mode="单培养皿")

    assert len(circles) == 1


def test_multi_mode_keeps_two_dishes_on_double_dish_reference_image():
    if not DOUBLE_DISH_IMAGE.exists():
        pytest.skip(f"reference image missing: {DOUBLE_DISH_IMAGE}")
    image = read_image(DOUBLE_DISH_IMAGE)

    circles = detect_dishes(image, min_radius=120, max_radius=0, sensitivity=55, detection_mode="多培养皿")

    assert len(circles) == 2


def test_multi_mode_uses_legacy_multi_candidate_detection_on_double_dish_reference_image():
    if not DOUBLE_DISH_IMAGE.exists():
        pytest.skip(f"reference image missing: {DOUBLE_DISH_IMAGE}")
    image = read_image(DOUBLE_DISH_IMAGE)

    circles = detect_dishes(image, min_radius=120, max_radius=0, sensitivity=55, detection_mode="多培养皿")

    assert len(circles) >= 2


def test_auto_mode_recovers_second_dish_found_by_legacy_detection():
    if not DOUBLE_DISH_LEGACY_IMAGE.exists():
        pytest.skip(f"reference image missing: {DOUBLE_DISH_LEGACY_IMAGE}")
    image = read_image(DOUBLE_DISH_LEGACY_IMAGE)

    auto_circles = detect_dishes(image, min_radius=120, max_radius=0, sensitivity=55, detection_mode="自动")
    multi_circles = detect_dishes(image, min_radius=120, max_radius=0, sensitivity=55, detection_mode="多培养皿")

    assert len(auto_circles) == 2
    assert len(multi_circles) == 2
