from __future__ import annotations

import cv2
import numpy as np

from src.models.circle import DishCircle
from src.models.image_item import sort_circles


def detect_dishes(
    image: np.ndarray,
    min_radius: int = 40,
    max_radius: int = 0,
    sensitivity: int = 55,
    detection_mode: str = "自动",
) -> list[DishCircle]:
    """Detect petri-dish-like circles conservatively using Hough circles plus filtering."""
    if image.size == 0:
        return []

    mode = _normalize_detection_mode(detection_mode)
    if mode == "single":
        segmented = _detect_dishes_by_segmentation(image, min_radius, max_radius, mode)
        if segmented:
            return segmented
        return _detect_dishes_by_hough(image, min_radius, max_radius, sensitivity, detection_mode)

    if mode == "auto":
        segmented = _detect_dishes_by_segmentation(image, min_radius, max_radius, mode)
        hough = _detect_dishes_by_hough(image, min_radius, max_radius, sensitivity, "multi", max_working_side=900)
        if segmented:
            return _promote_similar_second_dishes(segmented, hough)
        return _filter_by_detection_mode(hough, detection_mode, image.shape[:2])

    return _detect_dishes_by_hough(image, min_radius, max_radius, sensitivity, detection_mode)


def _detect_dishes_by_hough(
    image: np.ndarray,
    min_radius: int,
    max_radius: int,
    sensitivity: int,
    detection_mode: str,
    max_working_side: int = 1600,
) -> list[DishCircle]:
    h0, w0 = image.shape[:2]
    scale = 1.0
    if max(h0, w0) > max_working_side:
        scale = max_working_side / max(h0, w0)
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        min_radius = max(5, int(round(min_radius * scale)))
        max_radius = int(round(max_radius * scale)) if max_radius > 0 else 0

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    h, w = gray.shape[:2]
    auto_min_radius = max(20, min(h, w) // 9)
    if max_radius <= 0:
        max_radius = max(50, min(h, w) // 3)
    min_radius = max(5, int(min_radius), auto_min_radius)
    max_radius = max(min_radius + 1, int(max_radius))

    # Higher sensitivity lowers param2, but keep it conservative to avoid colonies/noise.
    param2 = int(np.interp(np.clip(sensitivity, 1, 100), [1, 100], [92, 46]))
    min_dist = max(min_radius * 1.8, min(h, w) * 0.16, 30)
    raw = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_dist,
        param1=140,
        param2=param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    scored: list[tuple[float, DishCircle]] = []
    if raw is not None:
        for x, y, r in np.round(raw[0, :]).astype(int):
            score = _score_circle_candidate(gray, x, y, r)
            if score >= 0.12:
                scored.append((score, DishCircle(float(x), float(y), float(r))))

    circles = [circle for _score, circle in sorted(scored, key=lambda item: item[0], reverse=True)]

    if not circles:
        circles = _detect_by_contours(gray, min_radius, max_radius)

    deduped = _dedupe_circles(circles, max_count=24)
    detected = sort_circles(_filter_by_detection_mode(deduped, detection_mode, gray.shape))
    if scale != 1.0:
        detected = [DishCircle(c.x / scale, c.y / scale, c.radius / scale, c.manual_adjusted) for c in detected]
    return sort_circles(detected)


def _filter_by_detection_mode(
    circles: list[DishCircle],
    detection_mode: str,
    image_shape: tuple[int, int],
) -> list[DishCircle]:
    if not circles:
        return []

    mode = _normalize_detection_mode(detection_mode)
    if mode == "multi":
        return circles

    ranked = sorted(circles, key=lambda c: _single_dish_score(c, image_shape), reverse=True)
    best = ranked[0]
    if mode == "single":
        return [best]

    if _looks_like_single_dish_scene(ranked, image_shape):
        return [best]
    return circles


def _promote_similar_second_dishes(segmented: list[DishCircle], hough: list[DishCircle]) -> list[DishCircle]:
    if not segmented:
        return sort_circles(hough)
    if len(segmented) > 1:
        return sort_circles(segmented)

    primary = segmented[0]
    similar: list[DishCircle] = []
    for candidate in hough:
        if _is_duplicate_circle(primary, candidate):
            continue
        radius_ratio = candidate.radius / max(primary.radius, 1.0)
        if not 0.82 <= radius_ratio <= 1.22:
            continue
        center_distance = float(np.hypot(candidate.x - primary.x, candidate.y - primary.y))
        if center_distance < max(primary.radius, candidate.radius) * 1.35:
            continue
        similar.append(candidate)

    if not similar:
        return sort_circles(segmented)

    # A true second dish should appear as a small set of strong legacy candidates.
    # Large Hough result sets on single-dish images are usually background false positives.
    if len(hough) > 4 and len(similar) != 1:
        return sort_circles(segmented)

    return sort_circles([primary] + similar[:3])


def _is_duplicate_circle(first: DishCircle, second: DishCircle) -> bool:
    distance = float(np.hypot(first.x - second.x, first.y - second.y))
    radius_delta = abs(first.radius - second.radius)
    return distance < min(first.radius, second.radius) * 0.35 and radius_delta < max(first.radius, second.radius) * 0.25


def _normalize_detection_mode(detection_mode: str) -> str:
    aliases = {
        "自动": "auto",
        "auto": "auto",
        "单培养皿": "single",
        "single": "single",
        "多培养皿": "multi",
        "multi": "multi",
    }
    return aliases.get(detection_mode, "auto")


def _detect_dishes_by_segmentation(
    image: np.ndarray,
    min_radius: int,
    max_radius: int,
    mode: str,
) -> list[DishCircle]:
    h0, w0 = image.shape[:2]
    if h0 <= 0 or w0 <= 0:
        return []

    scale = min(1.0, 900 / max(h0, w0))
    working = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1.0 else image
    gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)
    otsu_threshold, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = max(55, int(otsu_threshold * 0.85))
    mask = np.where(blurred >= threshold, 255, 0).astype(np.uint8)

    h, w = mask.shape[:2]
    close_size = max(15, int(min(h, w) * 0.035))
    if close_size % 2 == 0:
        close_size += 1
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)

    components, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask)
    candidates: list[tuple[float, DishCircle]] = []
    min_area = h * w * 0.03
    scaled_min_radius = min_radius * scale
    scaled_max_radius = max_radius * scale if max_radius > 0 else min(h, w) * 0.45

    for label in range(1, components):
        x, y, width, height, area = stats[label]
        if area < min_area:
            continue
        if y < h * 0.05 and height < h * 0.18:
            continue

        ys, xs = np.where(labels == label)
        if xs.size == 0:
            continue
        points = np.column_stack((xs, ys)).astype(np.float32)
        (cx, cy), radius = cv2.minEnclosingCircle(points)
        if radius < scaled_min_radius or radius > scaled_max_radius:
            continue

        circularity = area / max(np.pi * radius * radius, 1.0)
        if circularity < 0.55:
            continue
        center_ok = (w * 0.15 <= cx <= w * 0.85) and (h * 0.25 <= cy <= h * 0.92)
        if not center_ok:
            continue

        edge_margin = min(cx, cy, w - cx, h - cy) / max(radius, 1.0)
        if edge_margin < 0.15:
            continue

        score = float(area) * (0.5 + 0.5 * min(circularity, 1.0)) * (0.8 + 0.2 * (cy / h))
        candidates.append((score, DishCircle(cx / scale, cy / scale, radius / scale)))

    if not candidates:
        return []

    ordered = [circle for _score, circle in sorted(candidates, key=lambda item: item[0], reverse=True)]
    deduped = _dedupe_circles(ordered, max_count=24)
    if mode == "single":
        ranked = sorted(deduped, key=lambda c: _single_dish_score(c, image.shape[:2]), reverse=True)
        return ranked[:1]
    return sort_circles(deduped)


def _single_dish_score(circle: DishCircle, image_shape: tuple[int, int]) -> float:
    h, w = image_shape[:2]
    diagonal = float(np.hypot(w, h))
    center_dist = float(np.hypot(circle.x - w / 2.0, circle.y - h / 2.0))
    centrality = max(0.0, 1.0 - center_dist / max(diagonal / 2.0, 1.0))
    visible = _visible_circle_area_ratio(image_shape, int(round(circle.x)), int(round(circle.y)), int(round(circle.radius)))
    return circle.radius * (0.65 + 0.25 * centrality + 0.10 * visible)


def _looks_like_single_dish_scene(circles: list[DishCircle], image_shape: tuple[int, int]) -> bool:
    if len(circles) <= 1:
        return False
    h, w = image_shape[:2]
    best = circles[0]
    second = circles[1]
    radius_ratio = best.radius / max(second.radius, 1.0)
    large_enough = best.radius >= min(h, w) * 0.22
    clearly_larger = radius_ratio >= 1.10
    visible = _visible_circle_area_ratio(image_shape, int(round(best.x)), int(round(best.y)), int(round(best.radius)))
    mostly_inside = visible >= 0.75
    return large_enough and clearly_larger and mostly_inside


def _score_circle_candidate(gray: np.ndarray, x: int, y: int, r: int) -> float:
    h, w = gray.shape[:2]
    if r <= 0 or x + r < 0 or y + r < 0 or x - r >= w or y - r >= h:
        return 0.0

    visible_area = _visible_circle_area_ratio(gray.shape, x, y, r)
    if visible_area < 0.45:
        return 0.0

    mask = np.zeros_like(gray, dtype=np.uint8)
    cv2.circle(mask, (x, y), int(r), 255, max(2, int(r * 0.025)))
    edge = cv2.Canny(gray, 50, 140)
    ring_pixels = np.count_nonzero(mask)
    if ring_pixels == 0:
        return 0.0
    edge_on_ring = np.count_nonzero(cv2.bitwise_and(edge, edge, mask=mask))
    edge_ratio = edge_on_ring / ring_pixels

    inner_mask = np.zeros_like(gray, dtype=np.uint8)
    outer_mask = np.zeros_like(gray, dtype=np.uint8)
    cv2.circle(inner_mask, (x, y), max(1, int(r * 0.82)), 255, -1)
    cv2.circle(outer_mask, (x, y), max(1, int(r * 1.08)), 255, -1)
    cv2.circle(outer_mask, (x, y), max(1, int(r * 0.92)), 0, -1)
    inner_values = gray[inner_mask > 0]
    outer_values = gray[outer_mask > 0]
    if inner_values.size == 0 or outer_values.size == 0:
        contrast = 0.0
    else:
        contrast = abs(float(np.mean(inner_values)) - float(np.mean(outer_values))) / 255.0

    if edge_ratio < 0.08 and contrast < 0.06:
        return 0.0
    return edge_ratio * 0.75 + contrast * 0.25


def _visible_circle_area_ratio(shape: tuple[int, int], x: int, y: int, r: int) -> float:
    h, w = shape[:2]
    left = max(0, x - r)
    top = max(0, y - r)
    right = min(w, x + r)
    bottom = min(h, y + r)
    visible_box_area = max(0, right - left) * max(0, bottom - top)
    full_box_area = max(1, (2 * r) * (2 * r))
    return visible_box_area / full_box_area


def _detect_by_contours(gray: np.ndarray, min_radius: int, max_radius: int) -> list[DishCircle]:
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edges = cv2.Canny(blurred, 35, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    circles: list[DishCircle] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area <= 0:
            continue
        (x, y), r = cv2.minEnclosingCircle(contour)
        if r < min_radius or r > max_radius:
            continue
        circularity = area / (np.pi * r * r)
        if 0.35 <= circularity <= 1.25:
            circles.append(DishCircle(float(x), float(y), float(r)))
    return circles


def _dedupe_circles(circles: list[DishCircle], max_count: int = 24) -> list[DishCircle]:
    ordered = sorted(circles, key=lambda c: c.radius, reverse=True)
    kept: list[DishCircle] = []
    for circle in ordered:
        duplicate = False
        for existing in kept:
            dist = float(np.hypot(circle.x - existing.x, circle.y - existing.y))
            overlap_limit = max(min(circle.radius, existing.radius) * 0.75, abs(circle.radius - existing.radius) * 0.35)
            if dist < overlap_limit:
                duplicate = True
                break
        if not duplicate:
            kept.append(circle)
        if len(kept) >= max_count:
            break
    return kept
