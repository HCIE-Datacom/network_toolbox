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

"""Module registry - import and register all feature modules here."""

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
