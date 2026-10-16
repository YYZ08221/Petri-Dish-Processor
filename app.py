from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("培养皿图片批量处理系统")
    window = MainWindow()
    window.resize(1400, 850)
    window.show()
    return app.exec()


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))
    raise SystemExit(main())
