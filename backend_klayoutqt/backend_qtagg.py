"""
Render to qt from agg.
"""

from matplotlib.transforms import Bbox

from .qt_compat import _enum
from matplotlib.backends.backend_agg import FigureCanvasAgg
from .backend_qt import QtCore, QtGui, _BackendQT, FigureCanvasQT
from .backend_qt import (  # noqa: F401 # pylint: disable=W0611
    FigureManagerQT, NavigationToolbar2QT)


class FigureCanvasQTAgg(FigureCanvasAgg, FigureCanvasQT):

    def paintEvent(self, event):
        """
        Copy the image from the Agg canvas to the qt.drawable.

        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        self._draw_idle()  # Only does something if a draw is pending.

        # If the canvas does not have a renderer, then give up and wait for
        # FigureCanvasAgg.draw(self) to be called.
        if not hasattr(self, 'renderer'):
            return

        painter = QtGui.QPainter(self.asQPaintDevice())
        try:
            # See documentation of QRect: bottom() and right() are off
            # by 1, so use left() + width() and top() + height().
            rect = event.rect()
            # scale rect dimensions using the screen dpi ratio to get
            # correct values for the Figure coordinates (rather than
            # QT5's coords)
            width = rect.width * self.device_pixel_ratio
            height = rect.height * self.device_pixel_ratio
            left, top = self.mouseEventCoords(rect.topLeft)
            # shift the "top" by the height of the image to get the
            # correct corner for our coordinate system
            bottom = top - height
            # same with the right side of the image
            right = left + width
            # create a buffer using the image bounding box
            bbox = Bbox([[left, bottom], [right, top]])
            data = bytes(self.copy_from_bbox(bbox))
            painter.eraseRect(rect)  # clear the widget canvas
            qimage = QtGui.QImage(data, right - left, top - bottom,
                                  _enum("QtGui.QImage.Format").Format_RGBA8888)
            qimage.setDevicePixelRatio(self.device_pixel_ratio)
            # set origin using original QT coordinates
            origin = QtCore.QPoint(rect.left, rect.top)
            painter.drawImage(origin, qimage)

            self._draw_rect_callback(painter)
        finally:
            painter.end()

    def print_figure(self, *args, **kwargs):
        super().print_figure(*args, **kwargs)
        self.draw()


@_BackendQT.export
class _BackendQTAgg(_BackendQT):
    FigureCanvas = FigureCanvasQTAgg

