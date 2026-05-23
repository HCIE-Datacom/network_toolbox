"""Module registry - import and register all feature modules here."""

from .ntp_client import NTPClientModule
from .ntp_server import NTPServerModule
from .ftp_server import FTPServerModule
from .ping_test import PingTestModule
from .subnet_calc import SubnetCalcModule

# Registration order = sidebar display order.
# To add a new feature: import its class and append to this list.
# To remove a feature: delete its import and entry.
MODULE_REGISTRY = [
    NTPClientModule,
    NTPServerModule,
    FTPServerModule,
    PingTestModule,
    SubnetCalcModule,
]
