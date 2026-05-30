"""
NetTool - Network Toolbox
Version: V100R008C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Base class used by all NetTool feature modules.
"""

class ToolModule:
    """Base class for a toolbox feature module.

    Subclass this to create a new feature. Each module must define:
      - name: str           (sidebar button label)
      - icon: str           (semantic key for the shared drawn icon system)
      - description: str    (subtitle text below the page title)
      - build(parent)       (build the UI into parent QWidget)
      - on_show()           (optional, called when page becomes visible)
      - on_hide()           (optional, called when page is hidden)

    parent passed to build() is a QWidget.
    self.app is the NetworkToolboxApp (QMainWindow) instance.
    """

    name: str = "Untitled"
    icon: str = "?"
    description: str = ""
    disabled: bool = False
    disabled_text: str = ""

    def __init__(self, app):
        """app: the NetworkToolboxApp instance, provides after() etc."""
        self.app = app

    def build(self, parent):
        """Build UI content into the given parent QWidget."""
        raise NotImplementedError

    def on_show(self):
        """Called when this module's page is shown."""
        pass

    def on_hide(self):
        """Called when this module's page is hidden."""
        pass
