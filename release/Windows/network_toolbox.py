#!/usr/bin/env python3
"""
NetTool - Network Toolbox
Version: V100R008C00SPC700
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Application entry point and single-instance startup guard.
"""

import os
import sys
import multiprocessing

# Ensure the project root is in sys.path so 'core' and 'modules' are importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QFont

from core.app import NetworkToolboxApp
from modules import MODULE_REGISTRY


def _claim_single_instance(app):
    server_name = "NetTool.SingleInstance"
    probe = QLocalSocket()
    probe.connectToServer(server_name)
    if probe.waitForConnected(100):
        probe.close()
        return False

    QLocalServer.removeServer(server_name)
    server = QLocalServer(app)
    if not server.listen(server_name):
        return False
    app._single_instance_server = server
    return True


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
    if not _claim_single_instance(app):
        sys.exit(0)

    window = NetworkToolboxApp(MODULE_REGISTRY)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
