"""可弹出的独立视图窗口

将视图组件放入独立 QMainWindow，支持最大化查看
"""
from PyQt6.QtWidgets import QMainWindow, QWidget, QToolBar, QGridLayout, QScrollBar
from PyQt6.QtCore import Qt


class PopoutWindow(QMainWindow):
    """独立弹出窗口，包含一个视图组件"""

    SCROLL_PAN_SCALE = 0.25

    def __init__(self, view_widget, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setGeometry(200, 200, 1000, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        self.view = view_widget

        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.view, 0, 0)

        self.h_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.h_scroll.setRange(-5000, 5000)
        self.v_scroll = QScrollBar(Qt.Orientation.Vertical)
        self.v_scroll.setRange(-5000, 5000)
        layout.addWidget(self.v_scroll, 0, 1)
        layout.addWidget(self.h_scroll, 1, 0)
        layout.setRowStretch(0, 1)
        layout.setColumnStretch(0, 1)
        self.setCentralWidget(container)

        self.h_scroll.valueChanged.connect(lambda value: self._set_view_scroll('x', value))
        self.v_scroll.valueChanged.connect(lambda value: self._set_view_scroll('y', value))
        self._sync_scrollbars_from_view()

        toolbar = QToolBar("View Controls")
        self.addToolBar(toolbar)
        toolbar.addAction("Zoom In", self._zoom_in)
        toolbar.addAction("Zoom Out", self._zoom_out)
        toolbar.addAction("Fit", self._fit)
        toolbar.addAction("1:1", self._reset)
        toolbar.addSeparator()
        toolbar.addAction("←", lambda: self._pan('left'))
        toolbar.addAction("↑", lambda: self._pan('up'))
        toolbar.addAction("↓", lambda: self._pan('down'))
        toolbar.addAction("→", lambda: self._pan('right'))
        toolbar.addSeparator()
        toolbar.addAction("Close", self.close)

    def _set_view_scroll(self, axis: str, value: int):
        if not hasattr(self.view, 'get_pan_offset') or not hasattr(self.view, 'set_pan_offset'):
            return
        x, y = self.view.get_pan_offset()
        offset = -value * self.SCROLL_PAN_SCALE
        if axis == 'x':
            x = offset
        else:
            y = offset
        self.view.set_pan_offset(x, y)

    def _sync_scrollbars_from_view(self):
        if not hasattr(self.view, 'get_pan_offset'):
            return
        x, y = self.view.get_pan_offset()
        self.h_scroll.blockSignals(True)
        self.v_scroll.blockSignals(True)
        self.h_scroll.setValue(max(self.h_scroll.minimum(), min(self.h_scroll.maximum(), int(-x / self.SCROLL_PAN_SCALE))))
        self.v_scroll.setValue(max(self.v_scroll.minimum(), min(self.v_scroll.maximum(), int(-y / self.SCROLL_PAN_SCALE))))
        self.h_scroll.blockSignals(False)
        self.v_scroll.blockSignals(False)

    def _pan(self, direction: str):
        method = getattr(self.view, f"pan_{direction}", None)
        if method:
            method()
            self._sync_scrollbars_from_view()

    def _zoom_in(self):
        if hasattr(self.view, 'zoom_in'):
            self.view.zoom_in()
        elif hasattr(self.view, 'zoom'):
            self.view.zoom *= 1.3
            self.view.update()

    def _zoom_out(self):
        if hasattr(self.view, 'zoom_out'):
            self.view.zoom_out()
        elif hasattr(self.view, 'zoom'):
            self.view.zoom /= 1.3
            self.view.zoom = max(0.1, self.view.zoom)
            self.view.update()

    def _fit(self):
        if hasattr(self.view, 'fit_to_view'):
            self.view.fit_to_view()
            self._sync_scrollbars_from_view()

    def _reset(self):
        if hasattr(self.view, 'reset_view'):
            self.view.reset_view()
            self._sync_scrollbars_from_view()
        elif hasattr(self.view, 'zoom'):
            self.view.zoom = 1.0
            if hasattr(self.view, 'set_pan_offset'):
                self.view.set_pan_offset(0, 0)
            else:
                self.view.offset_x = 0
                self.view.offset_y = 0
                self.view.update()
            self._sync_scrollbars_from_view()
