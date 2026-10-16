from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QWidget

from src.models.circle import DishCircle


@dataclass
class _Hit:
    index: int
    mode: str


class ImageCanvas(QWidget):
    circles_changed = Signal()
    selection_changed = Signal(int)
    circle_added = Signal()
    edit_started = Signal()
    edit_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.image: np.ndarray | None = None
        self.pixmap: QPixmap | None = None
        self.circles: list[DishCircle] = []
        self.selected_index = -1
        self.scale = 1.0
        self.offset = QPointF(20, 20)
        self._last_mouse = QPoint()
        self._drag_mode: str | None = None
        self._drag_index = -1
        self.add_mode = False
        self.default_radius = 80.0

    def set_image(self, image: np.ndarray | None, circles: list[DishCircle] | None = None) -> None:
        self.image = image
        self.circles = circles if circles is not None else []
        self.selected_index = -1
        self._drag_mode = None
        self._drag_index = -1
        self.add_mode = False
        if image is None:
            self.pixmap = None
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            qimage = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
            self.pixmap = QPixmap.fromImage(qimage)
            self.fit_to_view()
        self.update()
        self.selection_changed.emit(self.selected_index)

    def fit_to_view(self) -> None:
        if self.image is None:
            return
        h, w = self.image.shape[:2]
        if w <= 0 or h <= 0:
            return
        margin = 40
        self.scale = min(max((self.width() - margin) / w, 0.05), max((self.height() - margin) / h, 0.05))
        self.offset = QPointF((self.width() - w * self.scale) / 2, (self.height() - h * self.scale) / 2)

    def selected_circle_number(self) -> int:
        return self.selected_index + 1 if 0 <= self.selected_index < len(self.circles) else 0

    def select_circle(self, index: int) -> None:
        self.selected_index = index if 0 <= index < len(self.circles) else -1
        self.selection_changed.emit(self.selected_index)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(32, 34, 36))
        if self.pixmap is None:
            painter.setPen(QColor(190, 190, 190))
            painter.drawText(self.rect(), Qt.AlignCenter, "请选择包含培养皿图片的文件夹")
            return

        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        target = self._image_rect()
        painter.drawPixmap(target, self.pixmap)

        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        painter.setFont(font)
        for i, circle in enumerate(self.circles):
            selected = i == self.selected_index
            color = QColor(255, 193, 7) if selected else QColor(0, 220, 120)
            pen = QPen(color, 3 if selected else 2)
            painter.setPen(pen)
            center = self.image_to_screen(QPointF(circle.x, circle.y))
            radius = circle.radius * self.scale
            painter.drawEllipse(center, radius, radius)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(center + QPointF(8, -8), str(i + 1))
            if selected:
                painter.setBrush(QColor(255, 193, 7))
                handle = self.image_to_screen(QPointF(circle.x + circle.radius, circle.y))
                painter.drawEllipse(handle, 5, 5)
                painter.setBrush(Qt.NoBrush)

    def resizeEvent(self, _event) -> None:
        if self.pixmap is not None and self.scale == 1.0:
            self.fit_to_view()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.pixmap is None:
            return
        before = self.screen_to_image(event.position())
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale = max(0.03, min(20.0, self.scale * factor))
        after_screen = self.image_to_screen(before)
        self.offset += event.position() - after_screen
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse = event.position().toPoint()
        if self.pixmap is None:
            return
        if event.button() == Qt.LeftButton:
            image_pos = self.screen_to_image(event.position())
            if self.add_mode:
                self.circles.append(DishCircle(image_pos.x(), image_pos.y(), self.default_radius, True))
                self.selected_index = len(self.circles) - 1
                self.add_mode = False
                self.circle_added.emit()
                self.circles_changed.emit()
                self.selection_changed.emit(self.selected_index)
                self.update()
                return

            hit = self._hit_test(image_pos)
            if hit:
                self.selected_index = hit.index
                self._drag_index = hit.index
                self._drag_mode = hit.mode
                self.edit_started.emit()
                self.selection_changed.emit(self.selected_index)
            else:
                self.selected_index = -1
                self._drag_mode = "pan"
                self.selection_changed.emit(self.selected_index)
            self.update()
        elif event.button() in {Qt.MiddleButton, Qt.RightButton}:
            self._drag_mode = "pan"

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.pixmap is None or self._drag_mode is None:
            return
        current = event.position().toPoint()
        if self._drag_mode == "pan":
            self.offset += current - self._last_mouse
        elif 0 <= self._drag_index < len(self.circles):
            circle = self.circles[self._drag_index]
            image_pos = self.screen_to_image(event.position())
            if self._drag_mode == "move":
                circle.x = image_pos.x()
                circle.y = image_pos.y()
                circle.manual_adjusted = True
            elif self._drag_mode == "radius":
                circle.radius = max(5.0, float(np.hypot(image_pos.x() - circle.x, image_pos.y() - circle.y)))
                circle.manual_adjusted = True
            self.circles_changed.emit()
        self._last_mouse = current
        self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        if self._drag_mode in {"move", "radius"}:
            self.edit_finished.emit()
        self._drag_mode = None
        self._drag_index = -1

    def _hit_test(self, image_pos: QPointF) -> _Hit | None:
        for index in range(len(self.circles) - 1, -1, -1):
            circle = self.circles[index]
            dist = float(np.hypot(image_pos.x() - circle.x, image_pos.y() - circle.y))
            tolerance = max(8 / self.scale, 4)
            if abs(dist - circle.radius) <= tolerance * 1.5:
                return _Hit(index, "radius")
            if dist <= circle.radius:
                return _Hit(index, "move")
        return None

    def _image_rect(self):
        assert self.pixmap is not None
        return self.pixmap.rect().translated(self.offset.toPoint()).adjusted(
            0,
            0,
            int(self.pixmap.width() * self.scale) - self.pixmap.width(),
            int(self.pixmap.height() * self.scale) - self.pixmap.height(),
        )

    def image_to_screen(self, point: QPointF) -> QPointF:
        return QPointF(point.x() * self.scale + self.offset.x(), point.y() * self.scale + self.offset.y())

    def screen_to_image(self, point: QPointF) -> QPointF:
        return QPointF((point.x() - self.offset.x()) / self.scale, (point.y() - self.offset.y()) / self.scale)
