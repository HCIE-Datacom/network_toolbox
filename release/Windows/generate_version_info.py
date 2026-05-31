"""
NetTool - Network Toolbox
Version: V100R009C00SPC500
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Generate a PyInstaller-compatible Windows version resource file.
"""

import os
import re
import sys
from pathlib import Path


DEFAULT_VERSION = "V100R009C00SPC500"
VERSION_PATTERN = re.compile(r"^V(\d+)R(\d+)C(\d+)SPC(\d+)$")


def main():
    version = os.environ.get("NETTOOL_VERSION", DEFAULT_VERSION)
    match = VERSION_PATTERN.match(version)
    if not match:
        raise SystemExit(f"Invalid NETTOOL_VERSION: {version}")

    numeric_version = ", ".join(str(int(part)) for part in match.groups())
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "version_info_build.txt")
    output.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({numeric_version}),
    prodvers=({numeric_version}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Tang Wenbo'),
          StringStruct('FileDescription', 'NetTool Network Toolbox'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'NetTool'),
          StringStruct('OriginalFilename', 'NetTool-{version}.exe'),
          StringStruct('ProductName', 'NetTool'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    print(f"Generated {output} for {version}")


if __name__ == "__main__":
    main()
