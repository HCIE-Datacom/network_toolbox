#!/usr/bin/env python3
"""Network Toolbox - entry point."""

import os
import sys

# Ensure the project root is in sys.path so 'core' and 'modules' are importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.app import NetworkToolboxApp
from modules import MODULE_REGISTRY


def main():
    app = NetworkToolboxApp(MODULE_REGISTRY)
    app.mainloop()


if __name__ == "__main__":
    main()
