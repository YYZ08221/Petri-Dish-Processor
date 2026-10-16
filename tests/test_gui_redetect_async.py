import os

import numpy as np
from PySide6.QtWidgets import QApplication

import src.gui.main_window as main_window_module
from src.gui.main_window import MainWindow
from src.models.image_item import ImageItem


def test_redetect_current_starts_background_worker_without_calling_detect_directly(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("redetect_current must not run detection on the GUI thread")

    monkeypatch.setattr(main_window_module, "detect_dishes", fail_if_called)
    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"placeholder")

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.items = [ImageItem(path=image_path)]
    window.current_index = 0
    window.current_image = np.zeros((100, 100, 3), dtype=np.uint8)

    window.redetect_current()

    assert window.current_redetect_thread is not None
    window._stop_current_redetect()
    window.close()
    app.processEvents()
