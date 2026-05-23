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
