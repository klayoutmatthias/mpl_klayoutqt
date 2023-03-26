
"""
Qt binding and backend selector.

The selection logic is as follows:
- if any of PyQt6, PySide6, PyQt5, or PySide2 have already been
  imported (checked in that order), use it;
- otherwise, if the QT_API environment variable (used by Enthought) is set, use
  it to determine which binding to use;
- otherwise, use whatever the rcParams indicate.
"""

import functools
import operator
import os
import platform
import sys
import signal
import socket
import contextlib

# KLayout Qt binding flat namespace
import pya

from packaging.version import parse as parse_version

import matplotlib as mpl

# pya is a flat namespace
import pya as QtCore
import pya as QtWidgets
import pya as QtGui

def _isdeleted(obj):
  return obj._destroyed()

def _to_int(enum):
  return enum.to_i()

@functools.lru_cache(None)
def _enum(name):
  return getattr(pya, "_".join(name.split(".")[1:]))

# As KLayout's Qt bindings are generated with Qt 5.5, QLibraryInfo version
# may not be available

__version__ = "KLayout/Qt" + QtCore.QLibraryInfo.version().toString()

_version_info = tuple(QtCore.QLibraryInfo.version().segments())

if _version_info < (5, 10):
    raise ImportError(
        f"The Qt version imported is "
        f"{QtCore.QLibraryInfo.version().toString()} but Matplotlib requires "
        f"Qt>=5.10")

# Fixes issues with Big Sur
# https://bugreports.qt.io/browse/QTBUG-87014, fixed in qt 5.15.2
if (sys.platform == 'darwin' and
        parse_version(platform.mac_ver()[0]) >= parse_version("10.16") and
        _version_info < (5, 15, 2)):
    os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")

def _exec(obj):
  obj.exec_()

