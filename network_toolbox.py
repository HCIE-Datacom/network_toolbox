#!/usr/bin/env python3
"""
NetTool - Network Toolbox
Copyright (C) 2026 Tang Wenbo (HCIE-Datacom)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""


"""Network Toolbox - entry point (PySide6 edition)."""

import os
import sys

# Ensure the project root is in sys.path so 'core' and 'modules' are importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.app import NetworkToolboxApp
from modules import MODULE_REGISTRY


def main():
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    # Set default font for consistent cross-platform rendering
    font = QFont()
    font.setFamilies(["PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", "STHeiti", "sans-serif"])
    font.setPixelSize(13)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)

    app.setApplicationName("NetTool")
    app.setOrganizationName("NetTool")

    window = NetworkToolboxApp(MODULE_REGISTRY)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
