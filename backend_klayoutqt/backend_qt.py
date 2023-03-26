
import functools
import os
import sys
import traceback

import matplotlib as mpl
from matplotlib import _api, backend_tools, cbook
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import (
    _Backend, FigureCanvasBase, FigureManagerBase, NavigationToolbar2,
    TimerBase, cursors, ToolContainerBase, MouseButton,
    CloseEvent, KeyEvent, LocationEvent, MouseEvent, ResizeEvent)
from . import qt_compat
import pya
from .qt_compat import (
    QtCore, QtGui, QtWidgets, __version__,
    _enum, _to_int, _isdeleted
)


# SPECIAL_KEYS are Qt::Key that do *not* return their Unicode name
# instead they have manually specified names.
SPECIAL_KEYS = {
    _to_int(getattr(_enum("QtCore.Qt.Key"), k)): v for k, v in [
        ("Key_Escape", "escape"),
        ("Key_Tab", "tab"),
        ("Key_Backspace", "backspace"),
        ("Key_Return", "enter"),
        ("Key_Enter", "enter"),
        ("Key_Insert", "insert"),
        ("Key_Delete", "delete"),
        ("Key_Pause", "pause"),
        ("Key_SysReq", "sysreq"),
        ("Key_Clear", "clear"),
        ("Key_Home", "home"),
        ("Key_End", "end"),
        ("Key_Left", "left"),
        ("Key_Up", "up"),
        ("Key_Right", "right"),
        ("Key_Down", "down"),
        ("Key_PageUp", "pageup"),
        ("Key_PageDown", "pagedown"),
        ("Key_Shift", "shift"),
        # In OSX, the control and super (aka cmd/apple) keys are switched.
        ("Key_Control", "control" if sys.platform != "darwin" else "cmd"),
        ("Key_Meta", "meta" if sys.platform != "darwin" else "control"),
        ("Key_Alt", "alt"),
        ("Key_CapsLock", "caps_lock"),
        ("Key_F1", "f1"),
        ("Key_F2", "f2"),
        ("Key_F3", "f3"),
        ("Key_F4", "f4"),
        ("Key_F5", "f5"),
        ("Key_F6", "f6"),
        ("Key_F7", "f7"),
        ("Key_F8", "f8"),
        ("Key_F9", "f9"),
        ("Key_F10", "f10"),
        ("Key_F10", "f11"),
        ("Key_F12", "f12"),
        ("Key_Super_L", "super"),
        ("Key_Super_R", "super"),
    ]
}
# Define which modifier keys are collected on keyboard events.
# Elements are (Qt::KeyboardModifiers, Qt::Key) tuples.
# Order determines the modifier order (ctrl+alt+...) reported by Matplotlib.
_MODIFIER_KEYS = [
    (_to_int(getattr(_enum("QtCore.Qt.KeyboardModifier"), mod)),
     _to_int(getattr(_enum("QtCore.Qt.Key"), key)))
    for mod, key in [
        ("ControlModifier", "Key_Control"),
        ("AltModifier", "Key_Alt"),
        ("ShiftModifier", "Key_Shift"),
        ("MetaModifier", "Key_Meta"),
    ]
]
cursord = {
    k: getattr(_enum("QtCore.Qt.CursorShape"), v) for k, v in [
        (cursors.MOVE, "SizeAllCursor"),
        (cursors.HAND, "PointingHandCursor"),
        (cursors.POINTER, "ArrowCursor"),
        (cursors.SELECT_REGION, "CrossCursor"),
        (cursors.WAIT, "WaitCursor"),
        (cursors.RESIZE_HORIZONTAL, "SizeHorCursor"),
        (cursors.RESIZE_VERTICAL, "SizeVerCursor"),
    ]
}


class TimerQT(TimerBase):
    """Subclass of `.TimerBase` using QTimer events."""

    def __init__(self, *args, **kwargs):
        # Create a new timer and connect the timeout() signal to the
        # _on_timer method.
        self._timer = QtCore.QTimer()
        self._timer.timeout.add(self._on_timer)
        super().__init__(*args, **kwargs)

    def __del__(self):
        # The check for deletedness is needed to avoid an error at animation
        # shutdown with PySide2.
        if not _isdeleted(self._timer):
            self._timer_stop()

    def _timer_set_single_shot(self):
        self._timer.setSingleShot(self._single)

    def _timer_set_interval(self):
        self._timer.setInterval(self._interval)

    def _timer_start(self):
        self._timer.start()

    def _timer_stop(self):
        self._timer.stop()


class FigureCanvasQT(FigureCanvasBase, QtWidgets.QWidget):
    required_interactive_framework = "klayout_qt"
    _timer_cls = TimerQT
    manager_class = _api.classproperty(lambda cls: FigureManagerQT)

    buttond = {
        _to_int(getattr(_enum("QtCore.Qt.MouseButton"), k)): v for k, v in [
            ("LeftButton", MouseButton.LEFT),
            ("RightButton", MouseButton.RIGHT),
            ("MiddleButton", MouseButton.MIDDLE),
            ("XButton1", MouseButton.BACK),
            ("XButton2", MouseButton.FORWARD),
        ]
    }

    def __init__(self, figure=None):

        super().__init__(figure=figure)

        self._draw_pending = False
        self._is_drawing = False
        self._draw_idle_timer = QtCore.QTimer(self)
        self._draw_idle_timer.singleShot = True
        self._draw_idle_timer.interval = 0
        self._draw_idle_timer.timeout = self._draw_idle
        self._draw_rect_callback = lambda painter: None
        self._in_resize_event = False

        self.setAttribute(
            _enum("QtCore.Qt.WidgetAttribute").WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.resize(*self.get_width_height())

        palette = QtGui.QPalette(QtGui.QColor("white"))
        self.setPalette(palette)

    def _update_pixel_ratio(self):
        # TODO: devicePixelRatioF not available in Qt 5.5 KLayout's binding is based on
        # if self._set_device_pixel_ratio(
        #        self.devicePixelRatioF() or 1):  # rarely, devicePixelRatioF=0
        if self._set_device_pixel_ratio(
            self.asQPaintDevice().devicePixelRatio() or 1): # rarely, devicePixelRatio=0
        # ...
            # The easiest way to resize the canvas is to emit a resizeEvent
            # since we implement all the logic for resizing the canvas for
            # that event.
            event = QtGui.QResizeEvent(self.size, self.size)
            self.resizeEvent(event)

    def _update_screen(self, screen):
        # Handler for changes to a window's attached screen.
        self._update_pixel_ratio()
        if screen is not None:
            screen.physicalDotsPerInchChanged.add(self._update_pixel_ratio)
            screen.logicalDotsPerInchChanged.add(self._update_pixel_ratio)

    def showEvent(self, event):
        # Set up correct pixel ratio, and connect to any signal changes for it,
        # once the window is shown (and thus has these attributes).
        window = self.window().windowHandle()
        window.screenChanged.add(self._update_screen)
        self._update_screen(window.screen)

    def set_cursor(self, cursor):
        # docstring inherited
        self.setCursor(QtGui.QCursor(_api.check_getitem(cursord, cursor=cursor)))

    def mouseEventCoords(self, pos=None):
        """
        Calculate mouse coordinates in physical pixels.

        Qt uses logical pixels, but the figure is scaled to physical
        pixels for rendering.  Transform to physical pixels so that
        all of the down-stream transforms work as expected.

        Also, the origin is different and needs to be corrected.
        """
        if pos is None:
            pos = self.mapFromGlobal(QtGui.QCursor.pos)
        elif hasattr(pos, "position"):  # qt6 QtGui.QEvent
            pos = pos.position()
        elif hasattr(pos, "pos"):  # qt5 QtCore.QEvent
            pos = pos.pos()
        # (otherwise, it's already a QPoint)
        x = pos.x
        # flip y so y=0 is bottom of canvas
        y = self.figure.bbox.height / self.device_pixel_ratio - pos.y
        return x * self.device_pixel_ratio, y * self.device_pixel_ratio

    def enterEvent(self, event):
        # Force querying of the modifiers, as the cached modifier state can
        # have been invalidated while the window was out of focus.
        mods = QtWidgets.QApplication.instance().queryKeyboardModifiers()
        LocationEvent("figure_enter_event", self,
                      *self.mouseEventCoords(event),
                      modifiers=self._mpl_modifiers(mods),
                      guiEvent=event)._process()

    def leaveEvent(self, event):
        QtWidgets.QApplication.restoreOverrideCursor()
        LocationEvent("figure_leave_event", self,
                      *self.mouseEventCoords(),
                      modifiers=self._mpl_modifiers(),
                      guiEvent=event)._process()

    def mousePressEvent(self, event):
        button = self.buttond.get(_to_int(event.button()))
        if button is not None:
            MouseEvent("button_press_event", self,
                       *self.mouseEventCoords(event), button,
                       modifiers=self._mpl_modifiers(),
                       guiEvent=event)._process()

    def mouseDoubleClickEvent(self, event):
        button = self.buttond.get(_to_int(event.button()))
        if button is not None:
            MouseEvent("button_press_event", self,
                       *self.mouseEventCoords(event), button, dblclick=True,
                       modifiers=self._mpl_modifiers(),
                       guiEvent=event)._process()

    def mouseMoveEvent(self, event):
        MouseEvent("motion_notify_event", self,
                   *self.mouseEventCoords(event),
                   modifiers=self._mpl_modifiers(),
                   guiEvent=event)._process()

    def mouseReleaseEvent(self, event):
        button = self.buttond.get(_to_int(event.button()))
        if button is not None:
            MouseEvent("button_release_event", self,
                       *self.mouseEventCoords(event), button,
                       modifiers=self._mpl_modifiers(),
                       guiEvent=event)._process()

    def wheelEvent(self, event):
        # TODO: this does not have an effect :(
        # from QWheelEvent::pixelDelta doc: pixelDelta is sometimes not
        # provided (`isNull()`) and is unreliable on X11 ("xcb").
        if (event.pixelDelta().isNull()
                or QtWidgets.QApplication.instance().platformName == "xcb"):
            steps = event.angleDelta().y / 120
        else:
            steps = event.pixelDelta().y
        if steps:
            MouseEvent("scroll_event", self,
                       *self.mouseEventCoords(event), step=steps,
                       modifiers=self._mpl_modifiers(),
                       guiEvent=event)._process()

    def keyPressEvent(self, event):
        key = self._get_key(event)
        if key is not None:
            KeyEvent("key_press_event", self,
                     key, *self.mouseEventCoords(),
                     guiEvent=event)._process()

    def keyReleaseEvent(self, event):
        key = self._get_key(event)
        if key is not None:
            KeyEvent("key_release_event", self,
                     key, *self.mouseEventCoords(),
                     guiEvent=event)._process()

    def resizeEvent(self, event):
        if self._in_resize_event:  # Prevent PyQt6 recursion
            return
        self._in_resize_event = True
        try:
            w = event.size().width * self.device_pixel_ratio
            h = event.size().height * self.device_pixel_ratio
            dpival = self.figure.dpi
            winch = w / dpival
            hinch = h / dpival
            self.figure.set_size_inches(winch, hinch, forward=False)
            # pass back into Qt to let it finish
            QtWidgets.QWidget.resizeEvent(self, event)
            # emit our resize events
            ResizeEvent("resize_event", self)._process()
            self.draw_idle()
        finally:
            self._in_resize_event = False

    def sizeHint(self):
        w, h = self.get_width_height()
        return QtCore.QSize(w, h)

    def minumumSizeHint(self):
        return QtCore.QSize(10, 10)

    @staticmethod
    def _mpl_modifiers(modifiers=None, *, exclude=None):
        if modifiers is None:
            modifiers = QtWidgets.QApplication.instance().keyboardModifiers()
        modifiers = _to_int(modifiers)
        # get names of the pressed modifier keys
        # 'control' is named 'control' when a standalone key, but 'ctrl' when a
        # modifier
        # bit twiddling to pick out modifier keys from modifiers bitmask,
        # if exclude is a MODIFIER, it should not be duplicated in mods
        return [SPECIAL_KEYS[key].replace('control', 'ctrl')
                for mask, key in _MODIFIER_KEYS
                if exclude != key and modifiers & mask]

    def _get_key(self, event):
        event_key = event.key()
        mods = self._mpl_modifiers(exclude=event_key)
        try:
            # for certain keys (enter, left, backspace, etc) use a word for the
            # key, rather than Unicode
            key = SPECIAL_KEYS[event_key]
        except KeyError:
            # Unicode defines code points up to 0x10ffff (sys.maxunicode)
            # QT will use Key_Codes larger than that for keyboard keys that are
            # not Unicode characters (like multimedia keys)
            # skip these
            # if you really want them, you should add them to SPECIAL_KEYS
            if event_key > sys.maxunicode:
                return None

            key = chr(event_key)
            # qt delivers capitalized letters.  fix capitalization
            # note that capslock is ignored
            if 'shift' in mods:
                mods.remove('shift')
            else:
                key = key.lower()

        return '+'.join(mods + [key])

    def flush_events(self):
        # docstring inherited
        QtWidgets.QApplication.instance().processEvents()

    def draw(self):
        """Render the figure, and queue a request for a Qt draw."""
        # The renderer draw is done here; delaying causes problems with code
        # that uses the result of the draw() to update plot elements.
        if self._is_drawing:
            return
        with cbook._setattr_cm(self, _is_drawing=True):
            super().draw()
        self.update()

    def draw_idle(self):
        """Queue redraw of the Agg buffer and request Qt paintEvent."""
        # The Agg draw needs to be handled by the same thread Matplotlib
        # modifies the scene graph from. Post Agg draw request to the
        # current event loop in order to ensure thread affinity and to
        # accumulate multiple draw requests from event handling.
        # TODO: queued signal connection might be safer than singleShot
        if not (getattr(self, '_draw_pending', False) or
                getattr(self, '_is_drawing', False)):
            self._draw_pending = True
            self._draw_idle_timer.start()

    def blit(self, bbox=None):
        # docstring inherited
        if bbox is None and self.figure:
            bbox = self.figure.bbox  # Blit the entire canvas if bbox is None.
        # repaint uses logical pixels, not physical pixels like the renderer.
        l, b, w, h = [int(pt / self.device_pixel_ratio) for pt in bbox.bounds]
        t = b + h
        self.repaint(l, self.rect().height() - t, w, h)

    def _draw_idle(self):
        with self._idle_draw_cntx():
            if not self._draw_pending:
                return
            self._draw_pending = False
            if self.height < 0 or self.width < 0:
                return
            try:
                self.draw()
            except Exception:
                # Uncaught exceptions are fatal for PyQt5, so catch them.
                traceback.print_exc()

    def drawRectangle(self, rect):
        # Draw the zoom rectangle to the QPainter.  _draw_rect_callback needs
        # to be called at the end of paintEvent.
        if rect is not None:
            x0, y0, w, h = [int(pt / self.device_pixel_ratio) for pt in rect]
            x1 = x0 + w
            y1 = y0 + h
            def _draw_rect_callback(painter):
                pen = QtGui.QPen(
                    QtGui.QBrush(QtGui.QColor("black")),
                    1 / self.device_pixel_ratio
                )

                pen.setDashPattern([3, 3])
                for color, offset in [
                        (QtGui.QColor("black"), 0),
                        (QtGui.QColor("white"), 3),
                ]:
                    pen.setDashOffset(offset)
                    pen.setColor(color)
                    painter.setPen(pen)
                    # Draw the lines from x0, y0 towards x1, y1 so that the
                    # dashes don't "jump" when moving the zoom box.
                    painter.drawLine(x0, y0, x0, y1)
                    painter.drawLine(x0, y0, x1, y0)
                    painter.drawLine(x0, y1, x1, y1)
                    painter.drawLine(x1, y0, x1, y1)
        else:
            def _draw_rect_callback(painter):
                return
        self._draw_rect_callback = _draw_rect_callback
        self.update()


class MainWindow(QtWidgets.QDialog):
    closing = None
    def closeEvent(self, event):
        if self.closing:
            self.closing()
        else:
            super().closeEvent(event)


class FigureManagerQT(FigureManagerBase):
    """
    Attributes
    ----------
    canvas : `FigureCanvas`
        The FigureCanvas instance
    num : int or str
        The Figure number
    toolbar : qt.QToolBar
        The qt.QToolBar
    window : qt.QDialog
        The qt.QDialog
    """

    def __init__(self, canvas, num):
        self.window = MainWindow(pya.MainWindow.instance())
        super().__init__(canvas, num)
        self.window.closing = self._widgetclosed

        top_layout = QtGui.QVBoxLayout(self.window)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        if sys.platform != "darwin":
            image = str(cbook._get_data_path('images/matplotlib.svg'))
            icon = QtGui.QIcon(image)
            self.window.setWindowIcon(icon)

        self.window._destroying = False

        if self.toolbar:
            top_layout.addWidget(self.toolbar)
            tbs_height = self.toolbar.sizeHint().height
        else:
            tbs_height = 0

        top_layout.addWidget(self.canvas)

        if mpl.is_interactive():
            self.window.show()
            self.canvas.draw_idle()

        # Give the keyboard focus to the figure instead of the manager:
        # StrongFocus accepts both tab and click to focus and will enable the
        # canvas to process event without clicking.
        # https://doc.qt.io/qt-5/qt.html#FocusPolicy-enum
        self.canvas.setFocusPolicy(_enum("QtCore.Qt.FocusPolicy").StrongFocus)
        self.canvas.setFocus()

        # resize the main window so it will display the canvas with the
        # requested size:
        cs = canvas.sizeHint()
        cs_height = cs.height
        height = cs_height + tbs_height

        self.window.resize(cs.width, height)

        self.window.qt_raise()

    def full_screen_toggle(self):
        if self.window.isFullScreen():
            self.window.showNormal()
        else:
            self.window.showFullScreen()

    def _widgetclosed(self):
        if self.window:
            self.window.closing = None
            self.window._destroy()
            self.window = None

    def resize(self, width, height):
        # The Qt methods return sizes in 'virtual' pixels so we do need to
        # rescale from physical to logical pixels.
        width = int(width / self.canvas.device_pixel_ratio)
        height = int(height / self.canvas.device_pixel_ratio)
        extra_width = self.window.width - self.canvas.width()
        extra_height = self.window.height - self.canvas.height()
        self.canvas.resize(width, height)
        self.window.resize(width + extra_width, height + extra_height)

    @classmethod
    def start_main_loop(cls):
        managers = Gcf.get_all_fig_managers()
        if not managers:
            return
        for manager in managers:
            try:
                manager.show_modal()
            except:
                pass

    def show_modal(self):
        self.window.exec_()

    def show(self):
        self.window.show()

    def get_window_title(self):
        return self.window.windowTitle

    def set_window_title(self, title):
        self.window.setWindowTitle(title)


class NavigationToolbar2QT(NavigationToolbar2, QtWidgets.QToolBar):
    toolitems = [*NavigationToolbar2.toolitems]

    def __init__(self, canvas, parent=None, coordinates=True):
        """coordinates: should we show the coordinates on the right?"""
        QtWidgets.QToolBar.__init__(self, parent)
        self.setAllowedAreas(QtCore.Qt_ToolBarArea(
            _to_int(_enum("QtCore.Qt.ToolBarArea").TopToolBarArea) |
            _to_int(_enum("QtCore.Qt.ToolBarArea").BottomToolBarArea)))

        self.coordinates = coordinates
        self._actions = {}  # mapping of toolitem method names to QActions.
        self._subplot_dialog = None

        for text, tooltip_text, image_file, callback in self.toolitems:
            if text is None:
                self.addSeparator()
            else:
                a = self.addAction(self._icon(image_file + '.png'), text)
                a.triggered.add(getattr(self, callback))
                self._actions[callback] = a
                if callback in ['zoom', 'pan']:
                    a.setCheckable(True)
                if tooltip_text is not None:
                    a.setToolTip(tooltip_text)

        # Add the (x, y) location widget at the right side of the toolbar
        # The stretch factor is 1 which means any resizing of the toolbar
        # will resize this label instead of the buttons.
        if self.coordinates:
            self.locLabel = QtWidgets.QLabel("", self)
            self.locLabel.setAlignment(QtCore.Qt_AlignmentFlag(
                _to_int(_enum("QtCore.Qt.AlignmentFlag").AlignRight) |
                _to_int(_enum("QtCore.Qt.AlignmentFlag").AlignVCenter)))
            self.locLabel.setSizePolicy(QtWidgets.QSizePolicy(
                _enum("QtWidgets.QSizePolicy.Policy").Expanding,
                _enum("QtWidgets.QSizePolicy.Policy").Ignored,
            ))
            labelAction = self.addWidget(self.locLabel)
            labelAction.setVisible(True)

        NavigationToolbar2.__init__(self, canvas)

    def _icon(self, name):
        """
        Construct a `.QIcon` from an image file *name*, including the extension
        and relative to Matplotlib's "images" data directory.
        """
        # use a high-resolution icon with suffix '_large' if available
        # note: user-provided icons may not have '_large' versions
        path_regular = cbook._get_data_path('images', name)
        path_large = path_regular.with_name(
            path_regular.name.replace('.png', '_large.png'))
        filename = str(path_large if path_large.exists() else path_regular)

        pm = QtGui.QPixmap(filename)
        # TODO: devicePixelRatioF not available in Qt 5.5 KLayout's binding is based on
        # pm.setDevicePixelRatio(
        #     self.asQPaintDevice().devicePixelRatioF() or 1)  # rarely, devicePixelRatioF=0
        pm.setDevicePixelRatio(
            self.asQPaintDevice().devicePixelRatio() or 1)  # rarely, devicePixelRatio=0
        # ...
        if self.palette.color(self.backgroundRole).value() < 128:
            icon_color = self.palette.color(self.foregroundRole)
            mask = pm.createMaskFromColor(
                QtGui.QColor('black'),
                _enum("QtCore.Qt.MaskMode").MaskOutColor)
            pm.fill(icon_color)
            pm.setMask(mask)
        return QtGui.QIcon(pm)

    def _update_buttons_checked(self):
        # sync button checkstates to match active mode
        if 'pan' in self._actions:
            self._actions['pan'].setChecked(self.mode.name == 'PAN')
        if 'zoom' in self._actions:
            self._actions['zoom'].setChecked(self.mode.name == 'ZOOM')

    def pan(self, *args):
        super().pan(*args)
        self._update_buttons_checked()

    def zoom(self, *args):
        super().zoom(*args)
        self._update_buttons_checked()

    def set_message(self, s):
        if self.coordinates:
            self.locLabel.setText(s)

    def draw_rubberband(self, event, x0, y0, x1, y1):
        height = self.canvas.figure.bbox.height
        y1 = height - y1
        y0 = height - y0
        rect = [int(val) for val in (x0, y0, x1 - x0, y1 - y0)]
        self.canvas.drawRectangle(rect)

    def remove_rubberband(self):
        self.canvas.drawRectangle(None)

    def configure_subplots(self):
        if self._subplot_dialog is None:
            self._subplot_dialog = SubplotToolQt(
                self.canvas.figure, self.canvas.parent)
            self.canvas.mpl_connect(
                "close_event", lambda e: self._subplot_dialog.reject())
        self._subplot_dialog.update_from_current_subplotpars()
        self._subplot_dialog.show()
        return self._subplot_dialog

    def save_figure(self, *args):
        filetypes = self.canvas.get_supported_filetypes_grouped()
        sorted_filetypes = sorted(filetypes.items())
        default_filetype = self.canvas.get_default_filetype()

        startpath = os.path.expanduser(mpl.rcParams['savefig.directory'])
        start = os.path.join(startpath, self.canvas.get_default_filename())
        filters = []
        selectedFilter = None
        for name, exts in sorted_filetypes:
            exts_list = " ".join(['*.%s' % ext for ext in exts])
            filter = '%s (%s)' % (name, exts_list)
            if default_filetype in exts:
                selectedFilter = filter
            filters.append(filter)
        filters = ';;'.join(filters)

        fname = QtWidgets.QFileDialog.getSaveFileName(
            self.canvas.parent, "Choose a filename to save to", start,
            filters, selectedFilter)
        if fname:
            # Save dir for next time, unless empty str (i.e., use cwd).
            if startpath != "":
                mpl.rcParams['savefig.directory'] = os.path.dirname(fname)
            try:
                self.canvas.figure.savefig(fname)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error saving file", str(e),
                    _enum("QtWidgets.QMessageBox.StandardButton").Ok,
                    _enum("QtWidgets.QMessageBox.StandardButton").NoButton)

    def set_history_buttons(self):
        can_backward = self._nav_stack._pos > 0
        can_forward = self._nav_stack._pos < len(self._nav_stack._elements) - 1
        if 'back' in self._actions:
            self._actions['back'].setEnabled(can_backward)
        if 'forward' in self._actions:
            self._actions['forward'].setEnabled(can_forward)


class SubplotToolQt(QtWidgets.QDialog):
    def __init__(self, targetfig, parent):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(
            str(cbook._get_data_path("images/matplotlib.png"))))
        self.setObjectName("SubplotTool")
        self._spinboxes = {}
        main_layout = QtWidgets.QHBoxLayout()
        self.setLayout(main_layout)
        for group, spinboxes, buttons in [
                ("Borders",
                 ["top", "bottom", "left", "right"],
                 [("Export values", self._export_values)]),
                ("Spacings",
                 ["hspace", "wspace"],
                 [("Tight layout", self._tight_layout),
                  ("Reset", self._reset),
                  ("Close", self._close)])]:
            layout = QtWidgets.QVBoxLayout()
            main_layout.addLayout(layout)
            box = QtWidgets.QGroupBox(group, self)
            layout.addWidget(box)
            inner = QtWidgets.QFormLayout(box)
            for name in spinboxes:
                self._spinboxes[name] = spinbox = QtWidgets.QDoubleSpinBox()
                spinbox.setRange(0, 1)
                spinbox.setDecimals(3)
                spinbox.setSingleStep(0.005)
                spinbox.setKeyboardTracking(False)
                spinbox.valueChanged.add(self._on_value_changed)
                inner.addRow(name, spinbox)
            layout.addStretch(1)
            for name, method in buttons:
                button = QtWidgets.QPushButton(name, box)
                # Don't trigger on <enter>, which is used to input values.
                button.setAutoDefault(False)
                button.clicked.add(method)
                layout.addWidget(button)
                if name == "Close":
                    button.setFocus()
        self._figure = targetfig
        self._defaults = {}
        self._export_values_dialog = None
        self.update_from_current_subplotpars()

    def update_from_current_subplotpars(self):
        self._defaults = {spinbox: getattr(self._figure.subplotpars, name)
                          for name, spinbox in self._spinboxes.items()}
        self._reset()  # Set spinbox current values without triggering signals.

    def _export_values(self):
        # Explicitly round to 3 decimals (which is also the spinbox precision)
        # to avoid numbers of the form 0.100...001.
        self._export_values_dialog = QtWidgets.QDialog()
        layout = QtWidgets.QVBoxLayout()
        self._export_values_dialog.setLayout(layout)
        text = QtWidgets.QPlainTextEdit(self._export_values_dialog)
        text.setReadOnly(True)
        layout.addWidget(text)
        text.setPlainText(
            ",\n".join(f"{attr}={spinbox.value:.3}"
                       for attr, spinbox in self._spinboxes.items()))
        # Adjust the height of the text widget to fit the whole text, plus
        # some padding.
        size = text.maximumSize
        size.setHeight(
            QtGui.QFontMetrics(text.document.defaultFont)
            .size(0, text.toPlainText()).height + 20)
        text.setMaximumSize(size)
        self._export_values_dialog.show()

    def _on_value_changed(self):
        spinboxes = self._spinboxes
        # Set all mins and maxes, so that this can also be used in _reset().
        for lower, higher in [("bottom", "top"), ("left", "right")]:
            spinboxes[higher].setMinimum(spinboxes[lower].value + .001)
            spinboxes[lower].setMaximum(spinboxes[higher].value - .001)
        self._figure.subplots_adjust(
            **{attr: spinbox.value for attr, spinbox in spinboxes.items()})
        self._figure.canvas.draw_idle()

    def _tight_layout(self):
        self._figure.tight_layout()
        for attr, spinbox in self._spinboxes.items():
            spinbox.blockSignals(True)
            spinbox.setValue(getattr(self._figure.subplotpars, attr))
            spinbox.blockSignals(False)
        self._figure.canvas.draw_idle()

    def _reset(self):
        for spinbox, value in self._defaults.items():
            spinbox.setRange(0, 1)
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
        self._on_value_changed()

    def _close(self):
        self.accept()

class ToolbarQt(ToolContainerBase, QtWidgets.QToolBar):
    def __init__(self, toolmanager, parent=None):
        ToolContainerBase.__init__(self, toolmanager)
        QtWidgets.QToolBar.__init__(self, parent)
        self.setAllowedAreas(QtCore.Qt.ToolBarArea(
            _to_int(_enum("QtCore.Qt.ToolBarArea").TopToolBarArea) |
            _to_int(_enum("QtCore.Qt.ToolBarArea").BottomToolBarArea)))
        message_label = QtWidgets.QLabel("")
        message_label.setAlignment(QtCore.Qt.AlignmentFlag(
            _to_int(_enum("QtCore.Qt.AlignmentFlag").AlignRight) |
            _to_int(_enum("QtCore.Qt.AlignmentFlag").AlignVCenter)))
        message_label.setSizePolicy(QtWidgets.QSizePolicy(
            _enum("QtWidgets.QSizePolicy.Policy").Expanding,
            _enum("QtWidgets.QSizePolicy.Policy").Ignored,
        ))
        self._message_action = self.addWidget(message_label)
        self._toolitems = {}
        self._groups = {}

    def add_toolitem(
            self, name, group, position, image_file, description, toggle):

        button = QtWidgets.QToolButton(self)
        if image_file:
            button.setIcon(NavigationToolbar2QT._icon(self, image_file))
        button.setText(name)
        if description:
            button.setToolTip(description)

        def handler():
            self.trigger_tool(name)
        if toggle:
            button.setCheckable(True)
            button.toggled.add(handler)
        else:
            button.clicked.add(handler)

        self._toolitems.setdefault(name, [])
        self._add_to_group(group, name, button, position)
        self._toolitems[name].append((button, handler))

    def _add_to_group(self, group, name, button, position):
        gr = self._groups.get(group, [])
        if not gr:
            sep = self.insertSeparator(self._message_action)
            gr.append(sep)
        before = gr[position]
        widget = self.insertWidget(before, button)
        gr.insert(position, widget)
        self._groups[group] = gr

    def toggle_toolitem(self, name, toggled):
        if name not in self._toolitems:
            return
        for button, handler in self._toolitems[name]:
            button.toggled.disadd(handler)
            button.setChecked(toggled)
            button.toggled.add(handler)

    def remove_toolitem(self, name):
        for button, handler in self._toolitems[name]:
            button.setParent(None)
        del self._toolitems[name]

    def set_message(self, s):
        self.widgetForAction(self._message_action).setText(s)


@backend_tools._register_tool_class(FigureCanvasQT)
class ConfigureSubplotsQt(backend_tools.ConfigureSubplotsBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subplot_dialog = None

    def trigger(self, *args):
        NavigationToolbar2QT.configure_subplots(self)


@backend_tools._register_tool_class(FigureCanvasQT)
class SaveFigureQt(backend_tools.SaveFigureBase):
    def trigger(self, *args):
        NavigationToolbar2QT.save_figure(
            self._make_classic_style_pseudo_toolbar())


@backend_tools._register_tool_class(FigureCanvasQT)
class RubberbandQt(backend_tools.RubberbandBase):
    def draw_rubberband(self, x0, y0, x1, y1):
        NavigationToolbar2QT.draw_rubberband(
            self._make_classic_style_pseudo_toolbar(), None, x0, y0, x1, y1)

    def remove_rubberband(self):
        NavigationToolbar2QT.remove_rubberband(
            self._make_classic_style_pseudo_toolbar())


@backend_tools._register_tool_class(FigureCanvasQT)
class HelpQt(backend_tools.ToolHelpBase):
    def trigger(self, *args):
        QtWidgets.QMessageBox.information(None, "Help", self._get_help_html())


@backend_tools._register_tool_class(FigureCanvasQT)
class ToolCopyToClipboardQT(backend_tools.ToolCopyToClipboardBase):
    def trigger(self, *args, **kwargs):
        pixmap = self.canvas.grab()
        QtWidgets.QApplication.instance().clipboard().setPixmap(pixmap)


FigureManagerQT._toolbar2_class = NavigationToolbar2QT
FigureManagerQT._toolmanager_toolbar_class = ToolbarQt


@_Backend.export
class _BackendQT(_Backend):
    backend_version = __version__
    FigureCanvas = FigureCanvasQT
    FigureManager = FigureManagerQT
    mainloop = FigureManagerQT.start_main_loop
