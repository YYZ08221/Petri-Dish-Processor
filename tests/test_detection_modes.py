from src.core.detection import _filter_by_detection_mode
from src.models.circle import DishCircle


def test_single_mode_keeps_only_largest_centered_candidate():
    circles = [
        DishCircle(425, 535, 221),
        DishCircle(641, 595, 193),
        DishCircle(106, 705, 128),
    ]

    filtered = _filter_by_detection_mode(circles, "单培养皿", (951, 879))

    assert len(filtered) == 1
    assert filtered[0].x == 425
    assert filtered[0].y == 535
    assert filtered[0].radius == 221


def test_auto_mode_collapses_clear_single_dish_false_candidates():
    circles = [
        DishCircle(425, 535, 221),
        DishCircle(641, 595, 193),
        DishCircle(776, 423, 146),
        DishCircle(106, 705, 128),
    ]

    filtered = _filter_by_detection_mode(circles, "自动", (951, 879))

    assert len(filtered) == 1
    assert filtered[0].radius == 221


def test_multi_mode_keeps_multiple_separate_candidates():
    circles = [
        DishCircle(160, 250, 100),
        DishCircle(380, 250, 100),
    ]

    filtered = _filter_by_detection_mode(circles, "多培养皿", (520, 540))

    assert len(filtered) == 2
