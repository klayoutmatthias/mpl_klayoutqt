
"""
Render to qt from agg in KLayout's QT flavor
"""

from .backend_qtagg import (    # noqa: F401, E402 # pylint: disable=W0611
    _BackendQTAgg, FigureCanvasQTAgg, FigureManagerQT, NavigationToolbar2QT,
    FigureCanvasAgg, FigureCanvasQT)


@_BackendQTAgg.export
class _BackendKLayoutQtAgg(_BackendQTAgg):
    pass

