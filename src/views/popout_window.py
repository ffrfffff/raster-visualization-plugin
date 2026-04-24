"""可弹出的独立视图窗口

将视图组件放入独立 QMainWindow，支持最大化查看
"""
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QToolBar
from PyQt6.QtCore import Qt


class PopoutWindow(QMainWindow):
    """独立弹出窗口，包含一个视图组件"""

    def __init__(self, view_widget, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setGeometry(200, 200, 1000, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        self.view = view_widget

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.setCentralWidget(container)

        # 工具栏
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

    def _pan(self, direction: str):
        method = getattr(self.view, f"pan_{direction}", None)
        if method:
            method()

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

    def _reset(self):
        if hasattr(self.view, 'reset_view'):
            self.view.reset_view()
        elif hasattr(self.view, 'zoom'):
            self.view.zoom = 1.0
            self.view.offset_x = 0
            self.view.offset_y = 0
            self.view.update()
