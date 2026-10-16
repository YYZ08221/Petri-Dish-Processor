"""Verify imports, offscreen GUI construction, and a temporary crop export."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
import pandas
import PIL
import tifffile
from PySide6.QtWidgets import QApplication

from src.core.image_io import read_image, save_image
from src.gui.main_window import MainWindow
from src.models.circle import DishCircle
from src.models.image_item import ImageItem
from src.services.export_service import ExportService


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.close()
    app.processEvents()
    with TemporaryDirectory(prefix='cbl-check-') as directory:
        root = Path(directory)
        source = root / 'synthetic.png'
        image = np.full((100, 100, 3), 100, dtype=np.uint8)
        cv2.circle(image, (50, 50), 30, (230, 230, 230), 2)
        save_image(source, image)
        item = ImageItem(path=source, circles=[DishCircle(50, 50, 30)])
        log = ExportService(export_format='png').export_items(
            [item], root / 'out', base_name_override='check'
        )
        if read_image(root / 'out' / 'check.png').size == 0 or not log.is_file():
            raise RuntimeError('Export smoke check failed.')
    print('PASS: dependencies, offscreen GUI, crop export, and CSV log')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
