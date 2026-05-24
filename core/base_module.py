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

"""ToolModule - base class for all toolbox features."""


class ToolModule:
    """Base class for a toolbox feature module.

    Subclass this to create a new feature. Each module must define:
      - name: str           (sidebar button label)
      - icon: str           (emoji icon for sidebar)
      - description: str    (subtitle text below the page title)
      - build(parent)       (build the UI into parent frame)
      - on_show()           (optional, called when page becomes visible)
      - on_hide()           (optional, called when page is hidden)
    """

    name: str = "Untitled"
    icon: str = "?"
    description: str = ""
    disabled: bool = False
    disabled_text: str = ""

    def __init__(self, app):
        """app: the NetworkToolboxApp instance, available for after() etc."""
        self.app = app

    def build(self, parent):
        """Build UI content into the given parent CTkFrame."""
        raise NotImplementedError

    def on_show(self):
        """Called when this module's page is shown."""
        pass

    def on_hide(self):
        """Called when this module's page is hidden."""
        pass
