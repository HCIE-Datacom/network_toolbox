"""Module registry - import and register all feature modules here."""

from .ntp_tool import NTPToolModule
from .ftp_tool import FTPToolModule
from .ping_test import PingTestModule
from .subnet_calc import SubnetCalcModule

# Registration order = sidebar display order.
# To add a new feature: import its class and append to this list.
# To remove a feature: delete its import and entry.
MODULE_REGISTRY = [
    NTPToolModule,
    FTPToolModule,
    PingTestModule,
    SubnetCalcModule,
]
