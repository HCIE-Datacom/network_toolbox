#!/usr/bin/env python3
"""
NetTool - Network Toolbox
Version: V100R009C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Application entry point and single-instance startup guard.
"""

import os
import sys
import multiprocessing
import ctypes
import ctypes.util

# Ensure the project root is in sys.path so 'core' and 'modules' are importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.admin_helper import HELPER_ARG, run_windows_admin_helper

if HELPER_ARG in sys.argv:
    idx = sys.argv.index(HELPER_ARG)
    sys.exit(run_windows_admin_helper(sys.argv[idx + 1], sys.argv[idx + 2]))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QFont

from core.app import NetworkToolboxApp
from modules import MODULE_REGISTRY


def _set_macos_process_name(name="NetTool"):
    if sys.platform != "darwin":
        return
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        core_foundation = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        msg_send_addr = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        msg_send_id = ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )(msg_send_addr)
        msg_send_void_id = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )(msg_send_addr)

        core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
        core_foundation.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
        ]
        core_foundation.CFRelease.argtypes = [ctypes.c_void_p]

        process_info_cls = objc.objc_getClass(b"NSProcessInfo")
        process_info = msg_send_id(process_info_cls, objc.sel_registerName(b"processInfo"))
        cf_name = core_foundation.CFStringCreateWithCString(
            None, name.encode("utf-8"), 0x08000100
        )
        msg_send_void_id(process_info, objc.sel_registerName(b"setProcessName:"), cf_name)
        core_foundation.CFRelease(cf_name)
    except Exception:
        pass


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
    _set_macos_process_name("NetTool")
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("NetTool")

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
