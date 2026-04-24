from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QToolBar, QStatusBar,
    QCheckBox, QLabel, QMessageBox, QTabWidget, QPushButton
)
from PyQt6.QtCore import Qt
from .models.config import RasterConfigModel
from .models.triangle import Triangle, TriangleListModel
from .views.config_panel import ConfigPanel
from .views.raster_view import RasterView
from .views.depth_side_view import DepthSideView
from .views.view3d import View3D
from .views.triangle_list_panel import TriangleListPanel
from .views.popout_window import PopoutWindow
from .renderers.software_rasterizer import SoftwareRasterizer


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Raster Visualization Plugin")
        self.setGeometry(100, 100, 1400, 900)

        self.config_model = RasterConfigModel()
        self.triangle_model = TriangleListModel()
        self.rasterizer = SoftwareRasterizer(self.config_model.config)

        self._init_ui()
        self._connect_signals()

        self._popout_windows = []

        # 添加示例三角形
        self.triangle_model.add_triangle(Triangle(
            vertices=[
                (200.0, 150.0, 0.5),
                (400.0, 150.0, 0.3),
                (300.0, 350.0, -0.2)
            ],
            color=(255, 100, 100)
        ))
        self.triangle_model.add_triangle(Triangle(
            vertices=[
                (100.0, 100.0, -0.3),
                (250.0, 100.0, 0.0),
                (175.0, 250.0, 0.7)
            ],
            color=(100, 255, 100)
        ))

    def _init_ui(self):
        self._create_menu_bar()
        self._create_tool_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 左侧：配置面板
        self.config_panel = ConfigPanel(self.config_model)

        # 中间：分割器
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上方：Tab 切换俯视图和3D视图
        self.view_tabs = QTabWidget()
        self.raster_view = RasterView()
        self.raster_view.set_config(self.config_model.config)
        self.view3d = View3D()
        self.view3d.set_config(self.config_model.config)
        self.view_tabs.addTab(self.raster_view, "Top View (Raster)")
        self.view_tabs.addTab(self.view3d, "3D View")
        splitter.addWidget(self.view_tabs)

        # 下方：深度侧视图
        self.depth_view = DepthSideView()
        self.depth_view.set_config(self.config_model.config)
        splitter.addWidget(self.depth_view)
        splitter.setSizes([550, 250])

        # 右侧布局
        right_layout = QVBoxLayout()
        right_layout.addWidget(splitter)

        # 显示选项 - 第一行
        options_layout = QHBoxLayout()
        self.show_tiles_cb = QCheckBox("Tiles")
        self.show_tiles_cb.setChecked(True)
        self.show_tile_labels_cb = QCheckBox("Tile Idx")
        self.show_tile_labels_cb.setChecked(True)
        self.show_tile_axes_cb = QCheckBox("Tile Axes")
        self.show_tile_axes_cb.setChecked(True)
        self.show_pixel_coords_cb = QCheckBox("Pixel Grid")
        self.show_pixel_coords_cb.setChecked(True)
        self.show_vertex_labels_cb = QCheckBox("Vtx Labels")
        self.show_vertex_labels_cb.setChecked(True)
        self.show_coverage_mask_cb = QCheckBox("Cov Mask")
        self.show_coverage_mask_cb.setChecked(True)
        self.show_scissor_cb = QCheckBox("Scissor")
        self.show_scissor_cb.setChecked(True)
        self.show_clip_cb = QCheckBox("Clip")
        self.show_clip_cb.setChecked(True)
        self.show_pixels_cb = QCheckBox("Pixels")
        self.show_pixels_cb.setChecked(True)
        self.show_msaa_cb = QCheckBox("MSAA")
        self.show_msaa_cb.setChecked(False)

        options_layout.addWidget(self.show_tiles_cb)
        options_layout.addWidget(self.show_tile_labels_cb)
        options_layout.addWidget(self.show_tile_axes_cb)
        options_layout.addWidget(self.show_pixel_coords_cb)
        options_layout.addWidget(self.show_vertex_labels_cb)
        options_layout.addWidget(self.show_coverage_mask_cb)
        options_layout.addWidget(self.show_scissor_cb)
        options_layout.addWidget(self.show_clip_cb)
        options_layout.addWidget(self.show_pixels_cb)
        options_layout.addWidget(self.show_msaa_cb)

        options_layout.addWidget(QLabel("|"))
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedWidth(28)
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedWidth(28)
        self.zoom_fit_btn = QPushButton("Fit")
        self.zoom_reset_btn = QPushButton("1:1")
        self.popout_top_btn = QPushButton("Pop Top")
        self.popout_depth_btn = QPushButton("Pop Depth")
        self.popout_3d_btn = QPushButton("Pop 3D")
        options_layout.addWidget(self.zoom_in_btn)
        options_layout.addWidget(self.zoom_out_btn)
        options_layout.addWidget(self.zoom_fit_btn)
        options_layout.addWidget(self.zoom_reset_btn)

        options_layout.addWidget(QLabel("|"))
        options_layout.addWidget(self.popout_top_btn)
        options_layout.addWidget(self.popout_depth_btn)
        options_layout.addWidget(self.popout_3d_btn)

        # 第二行：3D 视图模式 + 开关
        options_layout2 = QHBoxLayout()
        options_layout2.addWidget(QLabel("3D:"))
        self.view3d_front_btn = QPushButton("Front")
        self.view3d_back_btn = QPushButton("Back")
        self.view3d_left_btn = QPushButton("Left")
        self.view3d_right_btn = QPushButton("Right")
        self.view3d_top_btn = QPushButton("Top")
        self.view3d_persp_btn = QPushButton("Persp")
        for btn in [self.view3d_front_btn, self.view3d_back_btn, self.view3d_left_btn,
                     self.view3d_right_btn, self.view3d_top_btn, self.view3d_persp_btn]:
            btn.setFixedWidth(42)
            options_layout2.addWidget(btn)

        options_layout2.addWidget(QLabel("|"))
        self.show_grid3d_cb = QCheckBox("3D Grid")
        self.show_grid3d_cb.setChecked(True)
        self.show_axes3d_cb = QCheckBox("3D Axes")
        self.show_axes3d_cb.setChecked(True)
        options_layout2.addWidget(self.show_grid3d_cb)
        options_layout2.addWidget(self.show_axes3d_cb)
        options_layout2.addStretch()
        right_layout.addLayout(options_layout)
        right_layout.addLayout(options_layout2)

        # 三角形列表
        self.triangle_panel = TriangleListPanel()
        right_layout.addWidget(self.triangle_panel)

        main_layout.addWidget(self.config_panel)
        main_layout.addLayout(right_layout, stretch=1)

        # 状态栏
        self.statusBar().showMessage("Ready")

    def _create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        file_menu.addAction("New", self._on_new)
        file_menu.addAction("Import Triangles...", self._on_import)
        file_menu.addAction("Export Triangles...", self._on_export)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        view_menu = menubar.addMenu("View")
        view_menu.addAction("Reset Top View Zoom", self._reset_zoom)
        view_menu.addAction("Fit Top View", self._fit_to_view)
        view_menu.addAction("Reset Depth View", self._reset_depth_view)
        view_menu.addAction("Reset 3D View", self._reset_3d_view)

        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About", self._show_about)

    def _create_tool_bar(self):
        toolbar = self.addToolBar("Main")
        toolbar.addAction("Add Triangle", self._on_add_triangle)
        toolbar.addAction("Clear All", self._on_clear_triangles)

    def _connect_signals(self):
        self.config_panel.config_changed.connect(self._on_config_changed)
        self.config_model.config_changed.connect(self._on_config_changed)

        self.triangle_model.triangles_changed.connect(self._on_triangles_changed)
        self.triangle_panel.add_requested.connect(self._on_add_triangle)
        self.triangle_panel.remove_requested.connect(self._on_remove_triangle)
        self.triangle_panel.triangle_updated.connect(self._on_triangle_updated)

        self.show_tiles_cb.toggled.connect(self.raster_view.toggle_tiles)
        self.show_tile_labels_cb.toggled.connect(self.raster_view.toggle_tile_labels)
        self.show_tile_axes_cb.toggled.connect(self.raster_view.toggle_tile_pixel_axes)
        self.show_pixel_coords_cb.toggled.connect(self.raster_view.toggle_pixel_coords)
        self.show_vertex_labels_cb.toggled.connect(self.raster_view.toggle_vertex_labels)
        self.show_coverage_mask_cb.toggled.connect(self.raster_view.toggle_coverage_mask)
        self.show_scissor_cb.toggled.connect(self.raster_view.toggle_scissor)
        self.show_clip_cb.toggled.connect(self.raster_view.toggle_clip)
        self.show_pixels_cb.toggled.connect(self.raster_view.toggle_raster_pixels)
        self.show_msaa_cb.toggled.connect(self.raster_view.toggle_msaa_samples)
        self.show_grid3d_cb.toggled.connect(lambda v: setattr(self.view3d, 'show_grid', v) or self.view3d.update())
        self.show_axes3d_cb.toggled.connect(lambda v: setattr(self.view3d, 'show_axes', v) or self.view3d.update())

        self.view3d_front_btn.clicked.connect(self.view3d.set_view_front)
        self.view3d_back_btn.clicked.connect(self.view3d.set_view_back)
        self.view3d_left_btn.clicked.connect(self.view3d.set_view_left)
        self.view3d_right_btn.clicked.connect(self.view3d.set_view_right)
        self.view3d_top_btn.clicked.connect(self.view3d.set_view_top)
        self.view3d_persp_btn.clicked.connect(self.view3d.set_view_perspective)

        self.zoom_in_btn.clicked.connect(self.raster_view.zoom_in)
        self.zoom_out_btn.clicked.connect(self.raster_view.zoom_out)
        self.zoom_fit_btn.clicked.connect(self.raster_view.fit_to_view)
        self.zoom_reset_btn.clicked.connect(self.raster_view.reset_view)

        self.popout_top_btn.clicked.connect(lambda: self._popout_view('top'))
        self.popout_depth_btn.clicked.connect(lambda: self._popout_view('depth'))
        self.popout_3d_btn.clicked.connect(lambda: self._popout_view('3d'))

    def _on_config_changed(self):
        self.rasterizer.update_config(self.config_model.config)
        self.raster_view.set_config(self.config_model.config)
        self.depth_view.set_config(self.config_model.config)
        self.view3d.set_config(self.config_model.config)
        self._update_views()

    def _on_triangles_changed(self):
        self._update_views()
        self.triangle_panel.update_triangles(self.triangle_model.triangles)

    def _on_triangle_updated(self, index: int, triangle: Triangle):
        self.triangle_model.update_triangle(index, triangle)

    def _update_views(self):
        triangles = self.triangle_model.triangles
        self.raster_view.set_triangles(triangles)
        self.view3d.set_triangles(triangles)

        results = self.rasterizer.rasterize_triangles(triangles)
        self.depth_view.set_triangles(triangles, results)

        total_pixels = sum(len(r.covered_pixels) for r in results)
        depth_ranges = [t.depth_range for t in triangles]
        if depth_ranges:
            min_depth = min(dr[0] for dr in depth_ranges)
            max_depth = max(dr[1] for dr in depth_ranges)
            self.statusBar().showMessage(
                f"Triangles: {len(triangles)} | Pixels: {total_pixels} | "
                f"Depth Range: [{min_depth:.2f}, {max_depth:.2f}]"
            )
        else:
            self.statusBar().showMessage("Ready")

    def _on_add_triangle(self):
        self.triangle_model.add_triangle()

    def _on_remove_triangle(self, index: int):
        self.triangle_model.remove_triangle(index)

    def _on_clear_triangles(self):
        self.triangle_model.clear()

    def _on_new(self):
        self.triangle_model.clear()
        self.config_model._config = self.config_model._config.__class__()
        self.config_panel.sync_from_model()
        self._on_config_changed()

    def _on_import(self):
        QMessageBox.information(self, "Import", "Import feature coming soon")

    def _on_export(self):
        QMessageBox.information(self, "Export", "Export feature coming soon")

    def _reset_zoom(self):
        self.raster_view.reset_view()

    def _fit_to_view(self):
        self.raster_view.fit_to_view()

    def _reset_depth_view(self):
        self.depth_view.reset_view()

    def _reset_3d_view(self):
        self.view3d.reset_view()

    def _popout_view(self, view_type: str):
        """弹出视图到独立窗口"""
        if view_type == 'top':
            view = RasterView()
            view.set_config(self.config_model.config)
            view.set_triangles(self.triangle_model.triangles)
            view.show_tiles = self.show_tiles_cb.isChecked()
            view.show_scissor = self.show_scissor_cb.isChecked()
            view.show_clip = self.show_clip_cb.isChecked()
            view.show_raster_pixels = self.show_pixels_cb.isChecked()
            view.show_msaa_samples = self.show_msaa_cb.isChecked()
            view.show_tile_labels = self.show_tile_labels_cb.isChecked()
            view.show_pixel_coords = self.show_pixel_coords_cb.isChecked()
            title = "Top View (Raster) - Popout"
        elif view_type == 'depth':
            view = DepthSideView()
            view.set_config(self.config_model.config)
            results = self.rasterizer.rasterize_triangles(self.triangle_model.triangles)
            view.set_triangles(self.triangle_model.triangles, results)
            title = "Depth Side View - Popout"
        elif view_type == '3d':
            view = View3D()
            view.set_config(self.config_model.config)
            view.set_triangles(self.triangle_model.triangles)
            view.show_grid = self.show_grid3d_cb.isChecked()
            view.show_axes = self.show_axes3d_cb.isChecked()
            title = "3D View - Popout"
        else:
            return

        window = PopoutWindow(view, title, self)
        window.show()
        self._popout_windows.append(window)
        window.destroyed.connect(lambda: self._popout_windows.remove(window) if window in self._popout_windows else None)

    def _show_about(self):
        QMessageBox.about(
            self, "About",
            "Raster Visualization Plugin v1.0\n\n"
            "Features:\n"
            "- Configure MSAA, screen size, tile size, etc.\n"
            "- Draw triangles and view rasterization\n"
            "- Depth side view (scroll=zoom, drag=pan)\n"
            "- 3D rotatable view (drag=rotate, scroll=zoom)\n"
            "- Q16.8 (X/Y) and FP32 (Z) coordinate editing\n"
            "- Binary / Decimal / Hexadecimal format support"
        )