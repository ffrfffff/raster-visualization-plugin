from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QToolBar, QStatusBar,
    QCheckBox, QLabel, QMessageBox, QTabWidget, QPushButton,
    QSpinBox, QScrollBar, QGridLayout
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
        self._popout_entries = []

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

        # 中间：主视图区域 + 右侧/下侧滚动条 + 下方深度侧视图
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.main_view_container = QWidget()
        main_view_grid = QGridLayout(self.main_view_container)
        main_view_grid.setContentsMargins(0, 0, 0, 0)
        main_view_grid.setSpacing(2)

        self.view_tabs = QTabWidget()
        self.raster_view = RasterView()
        self.raster_view.set_config(self.config_model.config)
        self.view3d = View3D()
        self.view3d.set_config(self.config_model.config)
        self.view_tabs.addTab(self.raster_view, "Top View (Raster)")
        self.view_tabs.addTab(self.view3d, "3D View")

        self.main_h_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.main_h_scroll.setRange(-5000, 5000)
        self.main_h_scroll.setValue(0)
        self.main_v_scroll = QScrollBar(Qt.Orientation.Vertical)
        self.main_v_scroll.setRange(-5000, 5000)
        self.main_v_scroll.setValue(0)

        main_view_grid.addWidget(self.view_tabs, 0, 0)
        main_view_grid.addWidget(self.main_v_scroll, 0, 1)
        main_view_grid.addWidget(self.main_h_scroll, 1, 0)
        main_view_grid.setRowStretch(0, 1)
        main_view_grid.setColumnStretch(0, 1)
        splitter.addWidget(self.main_view_container)

        self.depth_container = QWidget()
        depth_grid = QGridLayout(self.depth_container)
        depth_grid.setContentsMargins(0, 0, 0, 0)
        depth_grid.setSpacing(2)
        self.depth_view = DepthSideView()
        self.depth_view.set_config(self.config_model.config)
        self.depth_h_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.depth_h_scroll.setRange(-5000, 5000)
        self.depth_h_scroll.setValue(0)
        self.depth_v_scroll = QScrollBar(Qt.Orientation.Vertical)
        self.depth_v_scroll.setRange(-5000, 5000)
        self.depth_v_scroll.setValue(0)
        depth_grid.addWidget(self.depth_view, 0, 0)
        depth_grid.addWidget(self.depth_v_scroll, 0, 1)
        depth_grid.addWidget(self.depth_h_scroll, 1, 0)
        depth_grid.setRowStretch(0, 1)
        depth_grid.setColumnStretch(0, 1)
        splitter.addWidget(self.depth_container)
        splitter.setSizes([550, 250])
        self._splitter = splitter
        self._depth_splitter_size = 250

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
        options_layout2.addWidget(QLabel("3D Combined:"))
        self.view3d_top_btn = QPushButton("Top")
        self.view3d_xz_btn = QPushButton("X-Z")
        self.view3d_yz_btn = QPushButton("Y-Z")
        self.view3d_front_btn = QPushButton("X-Y")
        self.view3d_persp_btn = QPushButton("Free 3D")
        for btn in [self.view3d_top_btn, self.view3d_xz_btn, self.view3d_yz_btn,
                     self.view3d_front_btn, self.view3d_persp_btn]:
            btn.setFixedWidth(58)
            options_layout2.addWidget(btn)

        options_layout2.addWidget(QLabel("| Rotate:"))
        self.view3d_x_neg_btn = QPushButton("X-15")
        self.view3d_x_pos_btn = QPushButton("X+15")
        self.view3d_y_neg_btn = QPushButton("Y-15")
        self.view3d_y_pos_btn = QPushButton("Y+15")
        self.view3d_z_neg_btn = QPushButton("Z-15")
        self.view3d_z_pos_btn = QPushButton("Z+15")
        for btn in [self.view3d_x_neg_btn, self.view3d_x_pos_btn,
                     self.view3d_y_neg_btn, self.view3d_y_pos_btn,
                     self.view3d_z_neg_btn, self.view3d_z_pos_btn]:
            btn.setFixedWidth(52)
            options_layout2.addWidget(btn)

        options_layout2.addWidget(QLabel("|"))
        self.free_rotate3d_cb = QCheckBox("Free Drag")
        self.free_rotate3d_cb.setChecked(False)
        self.show_grid3d_cb = QCheckBox("3D Grid")
        self.show_grid3d_cb.setChecked(True)
        self.show_axes3d_cb = QCheckBox("3D Axes")
        self.show_axes3d_cb.setChecked(True)
        options_layout2.addWidget(self.free_rotate3d_cb)
        options_layout2.addWidget(self.show_grid3d_cb)
        options_layout2.addWidget(self.show_axes3d_cb)
        options_layout2.addStretch()

        # 第三行：Top View 坐标定位
        options_layout3 = QHBoxLayout()
        options_layout3.addWidget(QLabel("Go Top X:"))
        self.goto_x_spin = QSpinBox()
        self.goto_x_spin.setRange(0, self.config_model.config.screen_width)
        self.goto_x_spin.setValue(self.config_model.config.screen_width // 2)
        self.goto_x_spin.setFixedWidth(80)
        self.goto_y_spin = QSpinBox()
        self.goto_y_spin.setRange(0, self.config_model.config.screen_height)
        self.goto_y_spin.setValue(self.config_model.config.screen_height // 2)
        self.goto_y_spin.setFixedWidth(80)
        self.goto_btn = QPushButton("Go")
        self.goto_btn.setFixedWidth(42)
        options_layout3.addWidget(self.goto_x_spin)
        options_layout3.addWidget(QLabel("Y:"))
        options_layout3.addWidget(self.goto_y_spin)
        options_layout3.addWidget(self.goto_btn)
        options_layout3.addWidget(QLabel("| Use the right and bottom scrollbars on each view to pan"))
        options_layout3.addStretch()

        right_layout.addLayout(options_layout)
        right_layout.addLayout(options_layout2)
        right_layout.addLayout(options_layout3)

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

        self.show_tiles_cb.toggled.connect(lambda checked: self._toggle_raster_layer('tiles', checked))
        self.show_tile_labels_cb.toggled.connect(lambda checked: self._toggle_raster_layer('tile_labels', checked))
        self.show_tile_axes_cb.toggled.connect(lambda checked: self._toggle_raster_layer('tile_pixel_axes', checked))
        self.show_pixel_coords_cb.toggled.connect(lambda checked: self._toggle_raster_layer('pixel_coords', checked))
        self.show_vertex_labels_cb.toggled.connect(lambda checked: self._toggle_raster_layer('vertex_labels', checked))
        self.show_coverage_mask_cb.toggled.connect(lambda checked: self._toggle_raster_layer('coverage_mask', checked))
        self.show_scissor_cb.toggled.connect(lambda checked: self._toggle_raster_layer('scissor', checked))
        self.show_clip_cb.toggled.connect(lambda checked: self._toggle_raster_layer('clip', checked))
        self.show_pixels_cb.toggled.connect(lambda checked: self._toggle_raster_layer('raster_pixels', checked))
        self.show_msaa_cb.toggled.connect(lambda checked: self._toggle_raster_layer('msaa_samples', checked))
        self.free_rotate3d_cb.toggled.connect(lambda checked: self.view3d.set_free_rotate(checked) or self._sync_popout_views())
        self.show_grid3d_cb.toggled.connect(lambda v: setattr(self.view3d, 'show_grid', v) or self.view3d.update() or self._sync_popout_views())
        self.show_axes3d_cb.toggled.connect(lambda v: setattr(self.view3d, 'show_axes', v) or self.view3d.update() or self._sync_popout_views())

        self.view3d_front_btn.clicked.connect(self.view3d.set_view_front)
        self.view3d_top_btn.clicked.connect(self.view3d.set_view_top)
        self.view3d_xz_btn.clicked.connect(self.view3d.set_view_xz_side)
        self.view3d_yz_btn.clicked.connect(self.view3d.set_view_yz_side)
        self.view3d_persp_btn.clicked.connect(self.view3d.set_view_perspective)
        self.view3d_x_neg_btn.clicked.connect(lambda: self.view3d.rotate_x(-15))
        self.view3d_x_pos_btn.clicked.connect(lambda: self.view3d.rotate_x(15))
        self.view3d_y_neg_btn.clicked.connect(lambda: self.view3d.rotate_y(-15))
        self.view3d_y_pos_btn.clicked.connect(lambda: self.view3d.rotate_y(15))
        self.view3d_z_neg_btn.clicked.connect(lambda: self.view3d.rotate_z(-15))
        self.view3d_z_pos_btn.clicked.connect(lambda: self.view3d.rotate_z(15))

        self.zoom_in_btn.clicked.connect(self.raster_view.zoom_in)
        self.zoom_out_btn.clicked.connect(self.raster_view.zoom_out)
        self.zoom_fit_btn.clicked.connect(self.raster_view.fit_to_view)
        self.zoom_reset_btn.clicked.connect(self.raster_view.reset_view)

        self.goto_btn.clicked.connect(self._goto_top_position)
        self.main_h_scroll.valueChanged.connect(lambda value: self._set_active_main_scroll('x', value))
        self.main_v_scroll.valueChanged.connect(lambda value: self._set_active_main_scroll('y', value))
        self.depth_h_scroll.valueChanged.connect(lambda value: self._set_view_scroll(self.depth_view, 'x', value))
        self.depth_v_scroll.valueChanged.connect(lambda value: self._set_view_scroll(self.depth_view, 'y', value))
        self.view_tabs.currentChanged.connect(self._on_view_tab_changed)

        self.popout_top_btn.clicked.connect(lambda: self._popout_view('top'))
        self.popout_depth_btn.clicked.connect(lambda: self._popout_view('depth'))
        self.popout_3d_btn.clicked.connect(lambda: self._popout_view('3d'))

    def _toggle_raster_layer(self, layer: str, checked: bool):
        toggle_name = f"toggle_{layer}"
        for view in (self.raster_view, self.view3d):
            method = getattr(view, toggle_name, None)
            if method:
                method(checked)
        self._sync_popout_views()

    def _active_main_view(self):
        return self.view3d if self.view_tabs.currentWidget() is self.view3d else self.raster_view

    def _goto_top_position(self):
        self.raster_view.center_on_screen_position(self.goto_x_spin.value(), self.goto_y_spin.value())
        self.view_tabs.setCurrentWidget(self.raster_view)
        self._sync_main_scroll_from_active_view()

    def _pan_view(self, view, direction: str):
        method = getattr(view, f"pan_{direction}", None)
        if method:
            method()
        if view is self.depth_view:
            self._sync_depth_scroll_from_view()
        elif view is self._active_main_view():
            self._sync_main_scroll_from_active_view()

    def _pan_active_main_view(self, direction: str):
        self._pan_view(self._active_main_view(), direction)

    def _set_active_main_scroll(self, axis: str, value: int):
        self._set_view_scroll(self._active_main_view(), axis, value)

    def _set_view_scroll(self, view, axis: str, value: int):
        if not hasattr(view, 'get_pan_offset') or not hasattr(view, 'set_pan_offset'):
            return
        x, y = view.get_pan_offset()
        if axis == 'x':
            x = value
        else:
            y = value
        view.set_pan_offset(x, y)

    def _sync_scroll_pair(self, h_scroll, v_scroll, view):
        if not hasattr(view, 'get_pan_offset'):
            return
        x, y = view.get_pan_offset()
        h_scroll.blockSignals(True)
        v_scroll.blockSignals(True)
        h_scroll.setValue(max(h_scroll.minimum(), min(h_scroll.maximum(), int(x))))
        v_scroll.setValue(max(v_scroll.minimum(), min(v_scroll.maximum(), int(y))))
        h_scroll.blockSignals(False)
        v_scroll.blockSignals(False)

    def _sync_main_scroll_from_active_view(self):
        self._sync_scroll_pair(self.main_h_scroll, self.main_v_scroll, self._active_main_view())

    def _sync_depth_scroll_from_view(self):
        self._sync_scroll_pair(self.depth_h_scroll, self.depth_v_scroll, self.depth_view)

    def _on_view_tab_changed(self, index=None):
        is_3d = self.view_tabs.currentWidget() is self.view3d
        if is_3d and self.depth_container.isVisible():
            sizes = self._splitter.sizes()
            if len(sizes) > 1 and sizes[1] > 0:
                self._depth_splitter_size = sizes[1]
            self.depth_container.hide()
        elif not is_3d and not self.depth_container.isVisible():
            self.depth_container.show()
            total = max(1, sum(self._splitter.sizes()))
            depth_size = max(160, self._depth_splitter_size)
            self._splitter.setSizes([max(300, total - depth_size), depth_size])
        self._sync_main_scroll_from_active_view()

    def _on_config_changed(self):
        self.rasterizer.update_config(self.config_model.config)
        self.raster_view.set_config(self.config_model.config)
        self.depth_view.set_config(self.config_model.config)
        self.view3d.set_config(self.config_model.config)
        self.goto_x_spin.setRange(0, self.config_model.config.screen_width)
        self.goto_y_spin.setRange(0, self.config_model.config.screen_height)
        self.goto_x_spin.setValue(min(self.goto_x_spin.value(), self.config_model.config.screen_width))
        self.goto_y_spin.setValue(min(self.goto_y_spin.value(), self.config_model.config.screen_height))
        self._update_views()

    def _on_triangles_changed(self):
        self._update_views()
        self.triangle_panel.update_triangles(self.triangle_model.triangles)

    def _on_triangle_updated(self, index: int, triangle: Triangle):
        self.triangle_model.update_triangle(index, triangle)

    def _update_views(self):
        triangles = self.triangle_model.triangles
        results = self.rasterizer.rasterize_triangles(triangles)

        self.raster_view.set_triangles(triangles)
        self.view3d.set_triangles(triangles, results)
        self.depth_view.set_triangles(triangles, results)
        self._sync_popout_views()

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

    def _copy_raster_toggles_to_view(self, view):
        for attr, checkbox in [
            ('show_tiles', self.show_tiles_cb),
            ('show_scissor', self.show_scissor_cb),
            ('show_clip', self.show_clip_cb),
            ('show_raster_pixels', self.show_pixels_cb),
            ('show_msaa_samples', self.show_msaa_cb),
            ('show_tile_labels', self.show_tile_labels_cb),
            ('show_pixel_coords', self.show_pixel_coords_cb),
            ('show_tile_pixel_axes', self.show_tile_axes_cb),
            ('show_vertex_labels', self.show_vertex_labels_cb),
            ('show_coverage_mask', self.show_coverage_mask_cb),
        ]:
            if hasattr(view, attr):
                setattr(view, attr, checkbox.isChecked())
        view.update()

    def _sync_popout_views(self):
        triangles = self.triangle_model.triangles
        results = self.rasterizer.rasterize_triangles(triangles)
        live_entries = []
        for window, view_type in self._popout_entries:
            if window not in self._popout_windows:
                continue
            view = window.view
            view.set_config(self.config_model.config)
            if view_type == 'top':
                view.set_triangles(triangles)
                self._copy_raster_toggles_to_view(view)
            elif view_type == 'depth':
                view.set_triangles(triangles, results)
            elif view_type == '3d':
                view.set_triangles(triangles, results)
                self._copy_raster_toggles_to_view(view)
                view.show_grid = self.show_grid3d_cb.isChecked()
                view.show_axes = self.show_axes3d_cb.isChecked()
                view.set_free_rotate(self.free_rotate3d_cb.isChecked())
            live_entries.append((window, view_type))
        self._popout_entries = live_entries

    def _popout_view(self, view_type: str):
        """弹出视图到独立窗口"""
        if view_type == 'top':
            view = RasterView()
            view.set_config(self.config_model.config)
            view.set_triangles(self.triangle_model.triangles)
            self._copy_raster_toggles_to_view(view)
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
            results = self.rasterizer.rasterize_triangles(self.triangle_model.triangles)
            view.set_triangles(self.triangle_model.triangles, results)
            view.show_grid = self.show_grid3d_cb.isChecked()
            view.show_axes = self.show_axes3d_cb.isChecked()
            self._copy_raster_toggles_to_view(view)
            view.set_free_rotate(self.free_rotate3d_cb.isChecked())
            view.rot_x = self.view3d.rot_x
            view.rot_y = self.view3d.rot_y
            view.rot_z = self.view3d.rot_z
            view.view_mode = self.view3d.view_mode
            view.zoom = self.view3d.zoom
            view.set_pan_offset(*self.view3d.get_pan_offset())
            title = "3D View - Popout"
        else:
            return

        window = PopoutWindow(view, title, self)
        window.show()
        self._popout_windows.append(window)
        self._popout_entries.append((window, view_type))
        window.destroyed.connect(lambda: self._on_popout_destroyed(window))

    def _on_popout_destroyed(self, window):
        if window in self._popout_windows:
            self._popout_windows.remove(window)
        self._popout_entries = [(w, t) for w, t in self._popout_entries if w is not window]

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