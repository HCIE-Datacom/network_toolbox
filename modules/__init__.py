"""
NetTool - Network Toolbox
Version: V100R008C00SPC700
Author: Tang Wenbo (HCIE-Datacom)
Copyright (C) 2026 Tang Wenbo
License: GNU General Public License v3.0 or later

Feature module registry.
"""

from .ntp_tool import NTPToolModule
from .ftp_tool import FTPToolModule
from .ping_test import PingTestModule
from .subnet_calc import SubnetCalcModule
from .cmd_generator import CmdGeneratorModule
from .iperf_tool import IperfToolModule
from .mac_lookup import MACLookupModule
from .route_tool import RouteToolModule

# Registration order = sidebar display order.
# To add a new feature: import its class and append to this list.
# To remove a feature: delete its import and entry.
MODULE_REGISTRY = [
    NTPToolModule,
    FTPToolModule,
    PingTestModule,
    SubnetCalcModule,
    CmdGeneratorModule,
    IperfToolModule,
    MACLookupModule,
    RouteToolModule,
]
