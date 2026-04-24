from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygon, QFontMetrics
from typing import List, Tuple, Optional
from ..models.config import RasterConfig
from ..models.triangle import Triangle, RasterizedTriangle
from ..renderers.software_rasterizer import SoftwareRasterizer


class RasterView(QWidget):
    """主光栅化视图

    显示：
    - 屏幕空间网格 (tile 边界 + 坐标标注)
    - 像素坐标
    - Scissor 和 Clip Region 边框
    - 三角形 + 顶点坐标标签
    - Raster 结果
    支持缩放(滚轮/按钮)和平移(中键拖拽)
    """

    def __init__(self):
        super().__init__()
        self.config: Optional[RasterConfig] = None
        self.triangles: List[Triangle] = []
        self.rasterized_results: List[RasterizedTriangle] = []
        self.rasterizer: Optional[SoftwareRasterizer] = None

        self.zoom = 1.0
        self.offset_x = 10
        self.offset_y = 10
        self.show_tiles = True
        self.show_scissor = True
        self.show_clip = True
        self.show_raster_pixels = True
        self.show_msaa_samples = False
        self.show_tile_labels = True
        self.show_pixel_coords = True
        self.show_tile_pixel_axes = True  # tile 边界的像素坐标轴刻度
        self.show_vertex_labels = True    # 三角形顶点坐标标签
        self.show_coverage_mask = True    # MSAA coverage mask 标签

        self._drag_start = None
        self._drag_offset_start = None

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)

    def set_config(self, config: RasterConfig):
        self.config = config
        self.rasterizer = SoftwareRasterizer(config)
        self._update_rasterization()
        self.update()

    def set_triangles(self, triangles: List[Triangle]):
        self.triangles = triangles
        self._update_rasterization()
        self.update()

    def _update_rasterization(self):
        if self.rasterizer and self.triangles:
            self.rasterized_results = self.rasterizer.rasterize_triangles(self.triangles)
        else:
            self.rasterized_results = []

    def _screen_to_view(self, sx: float, sy: float) -> Tuple[float, float]:
        """屏幕像素坐标 -> 视图坐标"""
        return (self.offset_x + sx * self.zoom,
                self.offset_y + sy * self.zoom)

    def _view_to_screen(self, vx: float, vy: float) -> Tuple[float, float]:
        """视图坐标 -> 屏幕像素坐标"""
        return ((vx - self.offset_x) / self.zoom,
                (vy - self.offset_y) / self.zoom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.config:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No configuration loaded")
            return

        scale = self.zoom
        ox = self.offset_x
        oy = self.offset_y
        sw = self.config.screen_width
        sh = self.config.screen_height

        # 背景
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        # 屏幕区域填充
        screen_rect = QRect(int(ox), int(oy), int(sw * scale), int(sh * scale))
        painter.fillRect(screen_rect, QColor(40, 40, 50))

        # ---- Tile 网格 + 坐标标注 ----
        if self.show_tiles:
            tw = self.config.tile_width
            th = self.config.tile_height

            for i in range(self.config.tile_count_x + 1):
                x = int(ox + i * tw * scale)
                painter.setPen(QPen(QColor(60, 60, 70), 1))
                painter.drawLine(x, int(oy), x, int(oy + sh * scale))

            for j in range(self.config.tile_count_y + 1):
                y = int(oy + j * th * scale)
                painter.setPen(QPen(QColor(60, 60, 70), 1))
                painter.drawLine(int(ox), y, int(ox + sw * scale), y)

            # Tile 索引标注 (i,j)
            if self.show_tile_labels and scale >= 0.5:
                font_size = max(7, min(11, int(8 * scale)))
                painter.setFont(QFont("Consolas", font_size))
                painter.setPen(QPen(QColor(90, 90, 110)))
                fm = QFontMetrics(painter.font())

                for i in range(self.config.tile_count_x):
                    for j in range(self.config.tile_count_y):
                        tile_cx = ox + (i * tw + tw / 2) * scale
                        tile_cy = oy + (j * th + th / 2) * scale
                        label = f"({i},{j})"
                        label_w = fm.horizontalAdvance(label)
                        label_h = fm.height()
                        tile_w_px = tw * scale
                        tile_h_px = th * scale
                        # 只在 tile 内部能放下文字时绘制
                        if tile_w_px > label_w + 4 and tile_h_px > label_h + 2:
                            painter.drawText(
                                int(tile_cx - label_w / 2),
                                int(tile_cy + label_h / 3),
                                label
                            )

            # Tile 边界像素坐标轴刻度
            if self.show_tile_pixel_axes and scale >= 0.5:
                small_font = max(6, min(9, int(7 * min(scale, 3))))
                painter.setFont(QFont("Consolas", small_font))
                fm_small = QFontMetrics(painter.font())
                painter.setPen(QPen(QColor(70, 70, 90)))

                # X 轴刻度：只在有空间放下数字时标注，否则间隔标注
                x_label_h = fm_small.height()
                if oy - x_label_h - 3 > 0:
                    step_x = max(1, (fm_small.horizontalAdvance(str(sw)) + 4) // max(1, int(tw * scale)) + 1)
                    for i in range(0, self.config.tile_count_x + 1, step_x):
                        x_pixel = i * tw
                        vx = int(ox + x_pixel * scale)
                        text = str(x_pixel)
                        tw_px = fm_small.horizontalAdvance(text)
                        painter.drawText(vx - tw_px // 2, int(oy - 3), text)

                # Y 轴刻度
                y_label_w = fm_small.horizontalAdvance(str(sh))
                if ox - y_label_w - 3 > 0:
                    step_y = max(1, (fm_small.height() + 2) // max(1, int(th * scale)) + 1)
                    for j in range(0, self.config.tile_count_y + 1, step_y):
                        y_pixel = j * th
                        vy = int(oy + y_pixel * scale)
                        text = str(y_pixel)
                        painter.drawText(int(ox - fm_small.horizontalAdvance(text) - 3), vy + x_label_h // 3, text)

        # ---- 像素坐标网格（高缩放时） ----
        if self.show_pixel_coords and scale >= 4.0:
            painter.setPen(QPen(QColor(50, 50, 55), 1))
            vis_min_x = max(0, int(-ox / scale))
            vis_min_y = max(0, int(-oy / scale))
            vis_max_x = min(sw, int((self.width() - ox) / scale) + 1)
            vis_max_y = min(sh, int((self.height() - oy) / scale) + 1)

            for px in range(vis_min_x, vis_max_x + 1):
                x = int(ox + px * scale)
                painter.drawLine(x, int(oy), x, int(oy + sh * scale))
            for py in range(vis_min_y, vis_max_y + 1):
                y = int(oy + py * scale)
                painter.drawLine(int(ox), y, int(ox + sw * scale), y)

            # 像素坐标标注 - 根据缩放级别自动选择标注方式
            if scale >= 8.0:
                coord_font = max(6, min(9, int(6 * min(scale / 8, 3))))
                painter.setFont(QFont("Consolas", coord_font))
                fm_coord = QFontMetrics(painter.font())
                painter.setPen(QPen(QColor(80, 80, 100)))

                pixel_w = scale  # 一个像素在视图中的宽度
                pixel_h = scale

                for px in range(vis_min_x, vis_max_x):
                    for py in range(vis_min_y, vis_max_y):
                        cx = ox + (px + 0.5) * scale
                        cy = oy + (py + 0.5) * scale

                        # 尝试不同格式，选择能放下的最短表示
                        full_label = f"{px},{py}"
                        label_w = fm_coord.horizontalAdvance(full_label)
                        label_h = fm_coord.height()

                        if pixel_w > label_w + 2 and pixel_h > label_h:
                            # 能放下 x,y
                            painter.drawText(int(cx - label_w / 2), int(cy + label_h / 3), full_label)
                        elif pixel_h > label_h:
                            # 只能放下 x 或 y，交替显示
                            if (px + py) % 2 == 0:
                                short = str(px)
                                sw2 = fm_coord.horizontalAdvance(short)
                                if pixel_w > sw2 + 2:
                                    painter.drawText(int(cx - sw2 / 2), int(cy + label_h / 3), short)
                            else:
                                short = str(py)
                                sw2 = fm_coord.horizontalAdvance(short)
                                if pixel_w > sw2 + 2:
                                    painter.drawText(int(cx - sw2 / 2), int(cy + label_h / 3), short)

        # ---- Clip Region ----
        if self.show_clip:
            painter.setPen(QPen(QColor(255, 200, 0), 2))
            cx, cy, cw, ch = self.config.clip_region
            painter.drawRect(
                int(ox + cx * scale), int(oy + cy * scale),
                int(cw * scale), int(ch * scale)
            )
            # 标注
            painter.setFont(QFont("Arial", 8))
            painter.setPen(QPen(QColor(255, 200, 0)))
            painter.drawText(int(ox + cx * scale + 3), int(oy + cy * scale - 3),
                             f"Clip({cx},{cy},{cw},{ch})")

        # ---- Scissor ----
        if self.show_scissor:
            painter.setPen(QPen(QColor(0, 255, 200), 2))
            sx, sy, s_width, s_height = self.config.scissor
            painter.drawRect(
                int(ox + sx * scale), int(oy + sy * scale),
                int(s_width * scale), int(s_height * scale)
            )
            painter.setFont(QFont("Arial", 8))
            painter.setPen(QPen(QColor(0, 255, 200)))
            painter.drawText(int(ox + sx * scale + 3), int(oy + sy * scale + 12),
                             f"Scissor({sx},{sy},{s_width},{s_height})")

        # ---- 光栅化像素 (MSAA coverage 可视化) ----
        if self.show_raster_pixels and self.rasterized_results:
            for result in self.rasterized_results:
                color = result.triangle.color
                tri_color = QColor(color[0], color[1], color[2])

                for px, py in result.covered_pixels:
                    ratio = result.coverage_ratio.get((px, py), 1.0)
                    # coverage ratio 控制透明度: 全覆盖=80%, 部分覆盖按比例
                    alpha = int(80 * ratio)
                    fill_color = QColor(tri_color.red(), tri_color.green(), tri_color.blue(), alpha)
                    painter.setBrush(QBrush(fill_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(
                        int(ox + px * scale), int(oy + py * scale),
                        int(max(1, scale)), int(max(1, scale))
                    )

        # ---- 三角形边框 + 顶点坐标标签 ----
        for tri_idx, triangle in enumerate(self.triangles):
            color = QColor(triangle.color[0], triangle.color[1], triangle.color[2])
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            polygon = QPolygon()
            for v in triangle.vertices:
                polygon.append(QPoint(int(ox + v[0] * scale), int(oy + v[1] * scale)))
            painter.drawPolygon(polygon)

            # 顶点圆点 + 坐标标签
            painter.setBrush(QBrush(color))
            label_font_size = max(7, min(11, int(9 * min(scale, 2))))
            painter.setFont(QFont("Consolas", label_font_size))
            for vi, v in enumerate(triangle.vertices):
                vx = int(ox + v[0] * scale)
                vy = int(oy + v[1] * scale)
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawEllipse(vx - 5, vy - 5, 10, 10)

                # 坐标标签（受开关控制）
                if self.show_vertex_labels:
                    painter.setPen(QPen(color))
                    label = f"V{vi}({v[0]:.0f},{v[1]:.0f},z={v[2]:.2f})"
                    painter.drawText(vx + 8, vy - 6, label)

        # ---- MSAA 采样点 (使用标准旋转网格位置) ----
        if self.show_msaa_samples and self.rasterized_results:
            from ..utils.geometry import generate_msaa_sample_positions
            msaa_positions = generate_msaa_sample_positions(self.config.msaa)

            for result in self.rasterized_results:
                tri_color = QColor(result.triangle.color[0], result.triangle.color[1], result.triangle.color[2])

                for px, py in result.covered_pixels:
                    coverage = result.coverage_mask.get((px, py), 0)

                    for sample_idx, (sx, sy) in enumerate(msaa_positions):
                        is_covered = (coverage >> sample_idx) & 1

                        if is_covered:
                            # 被覆盖的 sample: 实心三角形，使用三角形颜色
                            painter.setBrush(QBrush(tri_color))
                            painter.setPen(Qt.PenStyle.NoPen)
                        else:
                            # 未覆盖的 sample: 空心圆，灰色
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                            painter.setPen(QPen(QColor(100, 100, 100), 1))

                        # 缩放足够大时绘制采样点形状
                        if scale >= 6.0:
                            cx = ox + (px + sx) * scale
                            cy = oy + (py + sy) * scale
                            r = max(2, min(5, scale / 4))

                            if is_covered:
                                # 实心小方块
                                painter.drawRect(int(cx - r/2), int(cy - r/2), int(r), int(r))
                            else:
                                # 空心小圆
                                painter.drawEllipse(int(cx - r/2), int(cy - r/2), int(r), int(r))
                        else:
                            # 小缩放下用点
                            painter.setPen(Qt.PenStyle.NoPen if is_covered else QPen(QColor(100, 100, 100), 1))
                            if is_covered:
                                painter.setBrush(QBrush(tri_color))
                            painter.drawEllipse(
                                int(ox + (px + sx) * scale - 1),
                                int(oy + (py + sy) * scale - 1),
                                2, 2
                            )

                    # 高缩放时标注 coverage mask（受开关控制）
                    if self.show_coverage_mask and scale >= 10.0:
                        painter.setPen(QPen(QColor(255, 255, 200)))
                        painter.setFont(QFont("Consolas", max(7, min(10, int(scale / 3)))))
                        mask_text = f"0b{coverage:0{self.config.msaa.bit_length()}b}"
                        painter.drawText(
                            int(ox + (px + 0.5) * scale - len(mask_text) * 3),
                            int(oy + (py + 0.85) * scale),
                            mask_text
                        )

        # ---- 屏幕边框 ----
        painter.setPen(QPen(QColor(150, 150, 150), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(ox), int(oy), int(sw * scale), int(sh * scale))

        # 屏幕尺寸标注
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(int(ox), int(oy - 5),
                         f"Screen {sw}x{sh}")

        # ---- 底部信息栏 ----
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont("Arial", 10))
        info_text = f"Zoom: {self.zoom:.2f}x | Screen: {sw}x{sh} | " \
                    f"Tiles: {self.config.tile_width}x{self.config.tile_height} ({self.config.tile_count_x}x{self.config.tile_count_y}) | " \
                    f"MSAA: {self.config.msaa}x"
        if self.triangles:
            total_pixels = sum(len(r.covered_pixels) for r in self.rasterized_results)
            info_text += f" | Pixels: {total_pixels}"
        painter.drawText(10, self.height() - 8, info_text)

    def wheelEvent(self, event):
        # 以鼠标位置为中心缩放
        mouse_pos = event.position()
        old_screen = self._view_to_screen(mouse_pos.x(), mouse_pos.y())

        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.zoom *= factor
        self.zoom = max(0.1, min(50.0, self.zoom))

        # 调整偏移使鼠标位置对应同一个屏幕坐标
        new_vx, new_vy = self._screen_to_view(old_screen[0], old_screen[1])
        self.offset_x += mouse_pos.x() - new_vx
        self.offset_y += mouse_pos.y() - new_vy
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or \
           (event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._drag_start = event.pos()
            self._drag_offset_start = (self.offset_x, self.offset_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.LeftButton:
            # 点击时显示鼠标位置对应的屏幕坐标
            sx, sy = self._view_to_screen(event.pos().x(), event.pos().y())
            if self.config and 0 <= sx < self.config.screen_width and 0 <= sy < self.config.screen_height:
                tile_x = int(sx) // self.config.tile_width
                tile_y = int(sy) // self.config.tile_height
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"Pixel: ({int(sx)}, {int(sy)})\nTile: ({tile_x}, {tile_y})"
                )

    def mouseMoveEvent(self, event):
        if self._drag_start and (event.buttons() & Qt.MouseButton.MiddleButton or
                                  event.buttons() & Qt.MouseButton.LeftButton and
                                  event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            dx = event.pos().x() - self._drag_start.x()
            dy = event.pos().y() - self._drag_start.y()
            self.offset_x = self._drag_offset_start[0] + dx
            self.offset_y = self._drag_offset_start[1] + dy
            self.update()
        else:
            # 鼠标移动时更新坐标提示
            sx, sy = self._view_to_screen(event.pos().x(), event.pos().y())
            if self.config and 0 <= sx < self.config.screen_width and 0 <= sy < self.config.screen_height:
                tile_x = int(sx) // self.config.tile_width
                tile_y = int(sy) // self.config.tile_height
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"Pixel: ({int(sx)}, {int(sy)})\nTile: ({tile_x}, {tile_y})"
                )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def fit_to_view(self):
        if self.config:
            margin = 30
            self.zoom = min(
                (self.width() - 2 * margin) / self.config.screen_width,
                (self.height() - 2 * margin) / self.config.screen_height
            )
            self.offset_x = margin
            self.offset_y = margin
            self.update()

    def zoom_in(self):
        self.zoom *= 1.3
        self.zoom = min(50.0, self.zoom)
        self.update()

    def zoom_out(self):
        self.zoom /= 1.3
        self.zoom = max(0.1, self.zoom)
        self.update()

    def reset_view(self):
        self.zoom = 1.0
        self.offset_x = 10
        self.offset_y = 10
        self.update()

    def toggle_tiles(self, show: bool):
        self.show_tiles = show
        self.update()

    def toggle_scissor(self, show: bool):
        self.show_scissor = show
        self.update()

    def toggle_clip(self, show: bool):
        self.show_clip = show
        self.update()

    def toggle_raster_pixels(self, show: bool):
        self.show_raster_pixels = show
        self.update()

    def toggle_msaa_samples(self, show: bool):
        self.show_msaa_samples = show
        self.update()

    def toggle_tile_labels(self, show: bool):
        self.show_tile_labels = show
        self.update()

    def toggle_pixel_coords(self, show: bool):
        self.show_pixel_coords = show
        self.update()

    def toggle_tile_pixel_axes(self, show: bool):
        self.show_tile_pixel_axes = show
        self.update()

    def toggle_vertex_labels(self, show: bool):
        self.show_vertex_labels = show
        self.update()

    def toggle_coverage_mask(self, show: bool):
        self.show_coverage_mask = show
        self.update()