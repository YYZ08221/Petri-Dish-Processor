from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.cropping import apply_full_image_rotation, crop_dish_image, rotate_circle_quarter_turn
from src.core.detection import detect_dishes
from src.core.image_io import bgr_to_qimage_data, list_images, read_image
from src.gui.image_canvas import ImageCanvas
from src.models.circle import DishCircle
from src.models.image_item import ImageItem, sort_circles
from src.services.export_service import ExportService


class DetectionWorker(QObject):
    item_done = Signal(int, list, str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, paths: list[Path], min_radius: int, max_radius: int, sensitivity: int, detection_mode: str) -> None:
        super().__init__()
        self.paths = paths
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.sensitivity = sensitivity
        self.detection_mode = detection_mode
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        total = len(self.paths)
        for index, path in enumerate(self.paths):
            if self._cancelled:
                break
            error = ""
            circles: list[DishCircle] = []
            try:
                image = read_image(path)
                circles = detect_dishes(image, self.min_radius, self.max_radius, self.sensitivity, self.detection_mode)
            except Exception as exc:
                error = str(exc)
            self.item_done.emit(index, circles, error)
            self.progress.emit(index + 1, total)
        self.finished.emit()

    def cancel(self) -> None:
        self._cancelled = True


class CurrentDetectionWorker(QObject):
    done = Signal(list, str)
    finished = Signal()

    def __init__(self, image, min_radius: int, max_radius: int, sensitivity: int, detection_mode: str) -> None:
        super().__init__()
        self.image = image
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.sensitivity = sensitivity
        self.detection_mode = detection_mode
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        error = ""
        circles: list[DishCircle] = []
        if not self._cancelled:
            try:
                circles = detect_dishes(self.image, self.min_radius, self.max_radius, self.sensitivity, self.detection_mode)
            except Exception as exc:
                error = str(exc)
        if not self._cancelled:
            self.done.emit(circles, error)
        self.finished.emit()

    def cancel(self) -> None:
        self._cancelled = True


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("培养皿图片批量处理系统")
        self.input_folder: Path | None = None
        self.output_folder: Path | None = None
        self.items: list[ImageItem] = []
        self.current_index = -1
        self.current_image = None
        self.undo_stack: list[list[DishCircle]] = []
        self.detect_thread: QThread | None = None
        self.detect_worker: DetectionWorker | None = None
        self.current_redetect_thread: QThread | None = None
        self.current_redetect_worker: CurrentDetectionWorker | None = None

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文件名", "状态", "数量"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_selection)

        self.canvas = ImageCanvas()
        self.canvas.circles_changed.connect(self._on_circles_changed)
        self.canvas.selection_changed.connect(self._update_status)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.circle_added.connect(self._mark_manual)
        self.canvas.edit_started.connect(self._push_undo)
        self.canvas.edit_finished.connect(self._finish_circle_edit)

        root = QSplitter(Qt.Horizontal)
        root.addWidget(self._build_left_panel())
        root.addWidget(self.canvas)
        root.addWidget(self._build_right_panel())
        root.setSizes([300, 820, 280])
        self.setCentralWidget(root)

        self.status = QLabel("就绪")
        self.statusBar().addWidget(self.status, 1)

    def closeEvent(self, event) -> None:
        self._stop_detection()
        self._stop_current_redetect()
        super().closeEvent(event)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("文件列表"))
        layout.addWidget(self.table)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.input_label = QLabel("未选择")
        self.output_label = QLabel("未指定，将自动创建")
        choose_input = QPushButton("选择输入文件夹")
        choose_output = QPushButton("选择输出文件夹")
        choose_input.clicked.connect(self.choose_input_folder)
        choose_output.clicked.connect(self.choose_output_folder)

        self.crop_factor = QDoubleSpinBox()
        self.crop_factor.setRange(1.0, 2.0)
        self.crop_factor.setSingleStep(0.05)
        self.crop_factor.setValue(1.10)
        self.crop_factor.valueChanged.connect(self._update_rotation_preview)

        self.min_radius = QSpinBox()
        self.min_radius.setRange(5, 5000)
        self.min_radius.setValue(120)

        self.max_radius = QSpinBox()
        self.max_radius.setRange(0, 10000)
        self.max_radius.setValue(0)
        self.max_radius.setToolTip("0 表示按图片尺寸自动估计")

        self.sensitivity = QSpinBox()
        self.sensitivity.setRange(1, 100)
        self.sensitivity.setValue(55)

        self.detection_mode = QComboBox()
        self.detection_mode.addItems(["自动", "单培养皿", "多培养皿"])
        self.detection_mode.setToolTip("单培养皿模式只保留最可信的一个圆，多培养皿模式保留多个候选圆")

        self.export_format = QComboBox()
        self.export_format.addItems(["原格式", "png", "tif", "jpg"])
        self.crop_shape = QComboBox()
        self.crop_shape.addItems(["方形", "圆形"])
        self.crop_shape.currentTextChanged.connect(lambda _text: self._update_rotation_preview())

        form = QFormLayout()
        form.addRow(choose_input)
        form.addRow("输入目录", self.input_label)
        form.addRow(choose_output)
        form.addRow("输出目录", self.output_label)
        form.addRow("裁剪系数", self.crop_factor)
        form.addRow("最小半径", self.min_radius)
        form.addRow("最大半径", self.max_radius)
        form.addRow("检测灵敏度", self.sensitivity)
        form.addRow("检测模式", self.detection_mode)
        form.addRow("导出格式", self.export_format)
        form.addRow("裁剪形状", self.crop_shape)
        layout.addLayout(form)
        layout.addWidget(self._build_full_image_rotation_panel())
        layout.addWidget(self._build_rotation_panel())

        buttons = [
            ("当前图重新检测", self.redetect_current),
            ("当前图重置", self.reset_current),
            ("新增圆", self.add_circle_mode),
            ("删除当前圆", self.delete_selected_circle),
            ("清空当前圆", self.clear_current_circles),
            ("撤销", self.undo),
            ("跳过当前图", self.skip_current),
            ("导出当前图", self.export_current),
            ("全部导出", self.export_all),
        ]
        for text, handler in buttons:
            button = QPushButton(text)
            button.clicked.connect(handler)
            if text == "当前图重新检测":
                self.current_redetect_button = button
            layout.addWidget(button)

        layout.addStretch(1)
        hint = QLabel("操作：滚轮缩放，右键/中键拖拽平移；左键拖动圆内移动圆心，拖动圆边调整半径。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return panel

    def _build_full_image_rotation_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("全图旋转"))
        row = QHBoxLayout()
        left = QPushButton("左转90°")
        right = QPushButton("右转90°")
        reset = QPushButton("重置")
        left.clicked.connect(lambda: self.rotate_current_image(-90))
        right.clicked.connect(lambda: self.rotate_current_image(90))
        reset.clicked.connect(self.reset_current_image_rotation)
        row.addWidget(left)
        row.addWidget(right)
        row.addWidget(reset)
        layout.addLayout(row)
        self.full_image_rotation_label = QLabel("当前：0°")
        layout.addWidget(self.full_image_rotation_label)
        return panel

    def _build_rotation_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("裁剪预览"))

        self.rotation_preview = QLabel("未选中培养皿")
        self.rotation_preview.setAlignment(Qt.AlignCenter)
        self.rotation_preview.setMinimumHeight(180)
        self.rotation_preview.setStyleSheet("background: #202224; color: #c8c8c8; border: 1px solid #555;")
        layout.addWidget(self.rotation_preview)

        self.rotation_angle = QSpinBox()
        self.rotation_angle.setRange(-180, 180)
        self.rotation_angle.setSingleStep(1)
        self.rotation_angle.setSuffix("°")
        self.rotation_angle.valueChanged.connect(self._set_selected_rotation)

        angle_row = QHBoxLayout()
        left_90 = QPushButton("-90°")
        right_90 = QPushButton("+90°")
        reset = QPushButton("重置")
        left_90.clicked.connect(lambda: self._adjust_selected_rotation(-90))
        right_90.clicked.connect(lambda: self._adjust_selected_rotation(90))
        reset.clicked.connect(lambda: self._set_rotation_control_value(0))
        angle_row.addWidget(left_90)
        angle_row.addWidget(self.rotation_angle)
        angle_row.addWidget(right_90)
        angle_row.addWidget(reset)
        layout.addLayout(angle_row)

        self.rotation_controls = [self.rotation_angle, left_90, right_90, reset]
        self._set_rotation_controls_enabled(False)
        return panel

    def choose_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择输入文件夹")
        if not folder:
            return
        self.input_folder = Path(folder)
        self.input_label.setText(str(self.input_folder))
        self.load_folder(self.input_folder)

    def choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if not folder:
            return
        self.output_folder = Path(folder)
        self.output_label.setText(str(self.output_folder))

    def load_folder(self, folder: Path) -> None:
        self._stop_detection()
        self.items = [ImageItem(path=p, status="未处理") for p in list_images(folder)]
        self.current_index = -1
        self.current_image = None
        self.undo_stack.clear()
        self._refresh_table()
        if not self.items:
            self.canvas.set_image(None)
            self._set_status("未找到支持的图片格式")
            return

        self.canvas.set_image(None)
        self._start_background_detection()

    def _start_background_detection(self) -> None:
        if not self.items:
            return
        self.detect_thread = QThread(self)
        self.detect_worker = DetectionWorker(
            [item.path for item in self.items],
            self.min_radius.value(),
            self.max_radius.value(),
            self.sensitivity.value(),
            self.detection_mode.currentText(),
        )
        self.detect_worker.moveToThread(self.detect_thread)
        self.detect_thread.started.connect(self.detect_worker.run)
        self.detect_worker.item_done.connect(self._on_detection_item_done)
        self.detect_worker.progress.connect(self._on_detection_progress)
        self.detect_worker.finished.connect(self.detect_thread.quit)
        self.detect_worker.finished.connect(self.detect_worker.deleteLater)
        self.detect_thread.finished.connect(self.detect_thread.deleteLater)
        self.detect_thread.finished.connect(self._on_detection_finished)
        self.detect_thread.start()
        self._set_status(f"已导入 {len(self.items)} 张图片，正在后台自动检测...")

    def _stop_detection(self) -> None:
        if self.detect_worker is not None:
            self.detect_worker.cancel()
        if self.detect_thread is not None and self.detect_thread.isRunning():
            self.detect_thread.quit()
            self.detect_thread.wait(1500)
        self.detect_thread = None
        self.detect_worker = None

    def _stop_current_redetect(self) -> None:
        if self.current_redetect_worker is not None:
            self.current_redetect_worker.cancel()
        if self.current_redetect_thread is not None and self.current_redetect_thread.isRunning():
            self.current_redetect_thread.quit()
            self.current_redetect_thread.wait(1500)
        self.current_redetect_thread = None
        self.current_redetect_worker = None
        if hasattr(self, "current_redetect_button"):
            self.current_redetect_button.setEnabled(True)

    @Slot(int, list, str)
    def _on_detection_item_done(self, index: int, circles: list[DishCircle], error: str) -> None:
        if index < 0 or index >= len(self.items):
            return
        item = self.items[index]
        if error:
            item.status = "需确认"
            item.error = error
        else:
            if item.image_rotation_degrees:
                original_image = read_image(item.path)
                h, w = original_image.shape[:2]
                circles = [rotate_circle_quarter_turn(circle, w, h, item.image_rotation_degrees) for circle in circles]
            item.set_detected_circles(circles)
        self._refresh_table()
        if index == self.current_index and not item.manual_adjusted:
            self.canvas.set_image(self.current_image, item.circles)
            self._update_rotation_preview()

    @Slot(int, int)
    def _on_detection_progress(self, done: int, total: int) -> None:
        self._set_status(f"后台检测中：{done}/{total}")

    def _on_detection_finished(self) -> None:
        self.detect_thread = None
        self.detect_worker = None
        self._update_status()

    def _on_table_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        self.show_item(rows[0].row())

    def show_item(self, index: int) -> None:
        if index < 0 or index >= len(self.items):
            return
        self.current_index = index
        self.undo_stack.clear()
        item = self.items[index]
        try:
            self.current_image = apply_full_image_rotation(read_image(item.path), item.image_rotation_degrees)
            self.canvas.default_radius = float(self.min_radius.value() * 2)
            self.canvas.set_image(self.current_image, item.circles)
            self._update_full_image_rotation_label()
            self._update_status()
            self._update_rotation_preview()
        except Exception as exc:
            item.error = str(exc)
            self.current_image = None
            self.canvas.set_image(None)
            self._set_status(f"读取失败：{exc}")

    def redetect_current(self) -> None:
        item = self._current_item()
        if item is None or self.current_image is None or self.current_redetect_thread is not None:
            return
        self._push_undo()
        self.current_redetect_thread = QThread(self)
        self.current_redetect_worker = CurrentDetectionWorker(
            self.current_image.copy(),
            self.min_radius.value(),
            self.max_radius.value(),
            self.sensitivity.value(),
            self.detection_mode.currentText(),
        )
        self.current_redetect_worker.moveToThread(self.current_redetect_thread)
        self.current_redetect_thread.started.connect(self.current_redetect_worker.run)
        self.current_redetect_worker.done.connect(self._on_current_redetect_done)
        self.current_redetect_worker.finished.connect(self.current_redetect_thread.quit)
        self.current_redetect_worker.finished.connect(self.current_redetect_worker.deleteLater)
        self.current_redetect_thread.finished.connect(self.current_redetect_thread.deleteLater)
        self.current_redetect_thread.finished.connect(self._on_current_redetect_finished)
        self.current_redetect_button.setEnabled(False)
        self.current_redetect_thread.start()
        self._set_status("正在重新检测当前图...")

    @Slot(list, str)
    def _on_current_redetect_done(self, circles: list[DishCircle], error: str) -> None:
        item = self._current_item()
        if item is None:
            return
        if error:
            item.error = error
            item.status = "需确认"
            self._set_status(f"重新检测失败：{error}")
            return
        item.set_detected_circles(circles)
        self.canvas.set_image(self.current_image, item.circles)
        self._refresh_table()
        self._update_rotation_preview()
        self._set_status(f"重新检测完成：{len(circles)} 个培养皿")

    def _on_current_redetect_finished(self) -> None:
        self.current_redetect_thread = None
        self.current_redetect_worker = None
        self.current_redetect_button.setEnabled(True)

    def reset_current(self) -> None:
        item = self._current_item()
        if item is None:
            return
        self._push_undo()
        item.reset()
        self.canvas.set_image(self.current_image, item.circles)
        self._refresh_table()
        self._update_rotation_preview()
        self._update_status()

    def add_circle_mode(self) -> None:
        if self._current_item() is None:
            return
        self._push_undo()
        self.canvas.add_mode = True
        self._set_status("新增圆模式：请在图片上点击培养皿中心")

    def delete_selected_circle(self) -> None:
        item = self._current_item()
        idx = self.canvas.selected_index
        if item is None or idx < 0 or idx >= len(item.circles):
            return
        self._push_undo()
        item.circles.pop(idx)
        item.manual_adjusted = True
        item.circles = sort_circles(item.circles)
        self.canvas.set_image(self.current_image, item.circles)
        self._refresh_table()
        self._update_rotation_preview()
        self._update_status()

    def clear_current_circles(self) -> None:
        item = self._current_item()
        if item is None or not item.circles:
            return
        self._push_undo()
        item.circles.clear()
        item.manual_adjusted = True
        item.status = "需确认"
        self.canvas.set_image(self.current_image, item.circles)
        self._refresh_table()
        self._update_rotation_preview()
        self._update_status()

    def undo(self) -> None:
        item = self._current_item()
        if item is None or not self.undo_stack:
            return
        item.circles = self.undo_stack.pop()
        item.manual_adjusted = True
        self.canvas.set_image(self.current_image, item.circles)
        self._refresh_table()
        self._update_rotation_preview()
        self._update_status()

    def skip_current(self) -> None:
        item = self._current_item()
        if item is None:
            return
        item.status = "跳过"
        self._refresh_table()
        self._update_status()

    def export_current(self) -> None:
        item = self._current_item()
        if item is None:
            return
        base_name, accepted = QInputDialog.getText(self, "导出当前图", "请输入导出文件名：", text=item.path.stem)
        if not accepted or not base_name.strip():
            return
        self._export_items([item], base_name.strip())

    def export_all(self) -> None:
        self._export_items(self.items)

    def _export_items(self, items: list[ImageItem], base_name_override: str | None = None) -> None:
        if not items:
            return
        try:
            service = ExportService(self.crop_factor.value(), self.export_format.currentText(), self.crop_shape.currentText())
            out_dir = service.resolve_output_dir(self.input_folder, self.output_folder)
            log_path = service.export_items(items, out_dir, base_name_override)
            self.output_folder = out_dir
            self.output_label.setText(str(out_dir))
            self._refresh_table()
            self._set_status(f"导出完成，记录表：{log_path}")
            QMessageBox.information(self, "导出完成", f"输出目录：{out_dir}\n处理记录表：{log_path}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            self._set_status(f"导出失败：{exc}")

    def _on_circles_changed(self) -> None:
        item = self._current_item()
        if item is None:
            return
        item.manual_adjusted = True
        item.status = "需确认"
        self._refresh_table()
        self._update_rotation_preview()
        self._update_status()

    def _mark_manual(self) -> None:
        item = self._current_item()
        if item:
            item.manual_adjusted = True

    def _finish_circle_edit(self) -> None:
        item = self._current_item()
        if item is None:
            return
        item.circles = sort_circles(item.circles)
        self.canvas.circles = item.circles
        self._refresh_table()
        self._sync_rotation_control()
        self._update_rotation_preview()
        self._update_status()

    def _push_undo(self) -> None:
        item = self._current_item()
        if item is None:
            return
        self.undo_stack.append([c.copy() for c in item.circles])
        if len(self.undo_stack) > 30:
            self.undo_stack.pop(0)

    def _current_item(self) -> ImageItem | None:
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    def _current_circle(self) -> DishCircle | None:
        item = self._current_item()
        if item is None:
            return None
        index = self.canvas.selected_index
        if 0 <= index < len(item.circles):
            return item.circles[index]
        return None

    def rotate_current_image(self, delta_degrees: int) -> None:
        item = self._current_item()
        if item is None or self.current_image is None:
            return
        h, w = self.current_image.shape[:2]
        item.image_rotation_degrees = (item.image_rotation_degrees + delta_degrees) % 360
        item.circles = [rotate_circle_quarter_turn(circle, w, h, delta_degrees) for circle in item.circles]
        item.original_circles = [rotate_circle_quarter_turn(circle, w, h, delta_degrees) for circle in item.original_circles]
        item.manual_adjusted = True
        item.status = "需确认"
        self.current_image = apply_full_image_rotation(self.current_image, delta_degrees)
        self.canvas.set_image(self.current_image, item.circles)
        self._refresh_table()
        self._update_full_image_rotation_label()
        self._update_rotation_preview()
        self._update_status()

    def reset_current_image_rotation(self) -> None:
        item = self._current_item()
        if item is None or self.current_image is None:
            return
        if item.image_rotation_degrees == 0:
            return
        self.rotate_current_image(-item.image_rotation_degrees)

    def _update_full_image_rotation_label(self) -> None:
        item = self._current_item()
        degrees = item.image_rotation_degrees if item is not None else 0
        self.full_image_rotation_label.setText(f"当前：{degrees}°")

    def _on_selection_changed(self, _index: int) -> None:
        self._sync_rotation_control()
        self._update_rotation_preview()

    def _sync_rotation_control(self) -> None:
        circle = self._current_circle()
        self._set_rotation_controls_enabled(circle is not None)
        self.rotation_angle.blockSignals(True)
        self.rotation_angle.setValue(circle.rotation_degrees if circle is not None else 0)
        self.rotation_angle.blockSignals(False)

    def _set_rotation_controls_enabled(self, enabled: bool) -> None:
        for control in self.rotation_controls:
            control.setEnabled(enabled)

    def _set_rotation_control_value(self, value: int) -> None:
        self.rotation_angle.setValue(self._normalize_rotation(value))

    def _adjust_selected_rotation(self, delta: int) -> None:
        self._set_rotation_control_value(self.rotation_angle.value() + delta)

    def _set_selected_rotation(self, value: int) -> None:
        circle = self._current_circle()
        item = self._current_item()
        if circle is None or item is None:
            return
        circle.rotation_degrees = self._normalize_rotation(value)
        circle.manual_adjusted = True
        item.manual_adjusted = True
        item.status = "需确认"
        self._refresh_table()
        self._update_rotation_preview()
        self._update_status()

    def _update_rotation_preview(self, *_args) -> None:
        circle = self._current_circle()
        if circle is None or self.current_image is None:
            self.rotation_preview.setText("未选中培养皿")
            self.rotation_preview.setPixmap(QPixmap())
            return
        cropped, _side = crop_dish_image(
            self.current_image,
            circle,
            self.crop_factor.value(),
            self.crop_shape.currentText(),
        )
        data, width, height, bytes_per_line = bgr_to_qimage_data(cropped)
        qimage = QImage(data, width, height, bytes_per_line, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimage)
        self.rotation_preview.setPixmap(
            pixmap.scaled(self.rotation_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _normalize_rotation(self, value: int) -> int:
        normalized = int(value) % 360
        if normalized > 180:
            normalized -= 360
        return normalized

    def _refresh_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            self.table.setItem(row, 0, QTableWidgetItem(item.filename))
            self.table.setItem(row, 1, QTableWidgetItem(item.status))
            self.table.setItem(row, 2, QTableWidgetItem(str(item.count)))
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)

    def _update_status(self, *_args) -> None:
        item = self._current_item()
        if item is None:
            self._set_status("就绪")
            return
        selected = self.canvas.selected_circle_number()
        selected_text = str(selected) if selected else "无"
        self._set_status(f"当前：{item.filename} | 培养皿数量：{item.count} | 选中编号：{selected_text} | 状态：{item.status}")

    def _set_status(self, text: str) -> None:
        self.status.setText(text)
