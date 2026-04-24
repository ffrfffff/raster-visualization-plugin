from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygon, QFontMetrics, QImage
from typing import List, Tuple, Optional
from ..models.config import RasterConfig
from ..models.triangle import Triangle, RasterizedTriangle
from ..renderers.software_rasterizer import SoftwareRasterizer
from ..utils.geometry import generate_msaa_sample_positions


class RasterView(QWidget):
    """主光栅化视图 - 使用 QImage 缓存优化性能"""

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
        self.show_tile_pixel_axes = True
        self.show_vertex_labels = True
        self.show_coverage_mask = True

        # QImage 缓存：光栅化像素图
        self._pixel_image: Optional[QImage] = None
        self._pixel_image_msaa: Optional[QImage] = None  # MSAA resolved 图
        self._pixel_image_dirty = True

        self._drag_start = None
        self._drag_offset_start = None

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)

    def set_config(self, config: RasterConfig):
        self.config = config
        self.rasterizer = SoftwareRasterizer(config)
        self._pixel_image_dirty = True
        self._update_rasterization()
        self.update()

    def set_triangles(self, triangles: List[Triangle]):
        self.triangles = triangles
        self._pixel_image_dirty = True
        self._update_rasterization()
        self.update()

    def _update_rasterization(self):
        if self.rasterizer and self.triangles:
            self.rasterized_results = self.rasterizer.rasterize_triangles(self.triangles)
        else:
            self.rasterized_results = []
        self._pixel_image_dirty = True

    def _rebuild_pixel_image(self):
        """将光栅化结果渲染到 QImage 缓存，避免每帧逐像素 drawRect"""
        if not self.config or not self.rasterized_results:
            self._pixel_image = None
            self._pixel_image_msaa = None
            return

        sw = self.config.screen_width
        sh = self.config.screen_height

        # 基础像素图 (带 coverage ratio 控制透明度)
        img = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor(0, 0, 0, 0))

        for result in self.rasterized_results:
            color = result.triangle.color
            for (px, py), ratio in result.coverage_ratio.items():
                alpha = int(200 * ratio)
                c = QColor(color[0], color[1], color[2], alpha)
                img.setPixelColor(px, py, c)

        self._pixel_image = img

        # MSAA resolved 图
        if self.config.msaa > 1:
            resolved = self.rasterizer.resolve_msaa(self.rasterized_results)
            img_msaa = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
            img_msaa.fill(QColor(0, 0, 0, 0))
            for (px, py), (r, g, b) in resolved.items():
                img_msaa.setPixelColor(px, py, QColor(r, g, b, 200))
            self._pixel_image_msaa = img_msaa
        else:
            self._pixel_image_msaa = None

        self._pixel_image_dirty = False

    def _screen_to_view(self, sx: float, sy: float) -> Tuple[float, float]:
        return (self.offset_x + sx * self.zoom, self.offset_y + sy * self.zoom)

    def _view_to_screen(self, vx: float, vy: float) -> Tuple[float, float]:
        return ((vx - self.offset_x) / self.zoom, (vy - self.offset_y) / self.zoom)

    def paintEvent(self, event):
        painter = QPainter(self)
        # 低缩放关闭抗锯齿提升性能
        if self.zoom < 4.0:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        else:
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

        # ---- 光栅化像素 (QImage 一次性绘制) ----
        if self.show_raster_pixels and self.rasterized_results:
            if self._pixel_image_dirty:
                self._rebuild_pixel_image()

            # MSAA>1 时使用 resolved 图，否则用基础 coverage 图
            draw_img = self._pixel_image_msaa if (self.config.msaa > 1 and self._pixel_image_msaa) else self._pixel_image
            if draw_img:
                target_rect = QRect(int(ox), int(oy), int(sw * scale), int(sh * scale))
                painter.drawImage(target_rect, draw_img)

        # ---- Tile 网格 ----
        if self.show_tiles:
            tw = self.config.tile_width
            th = self.config.tile_height

            pen_grid = QPen(QColor(60, 60, 70), 1)
            painter.setPen(pen_grid)
            for i in range(self.config.tile_count_x + 1):
                x = int(ox + i * tw * scale)
                painter.drawLine(x, int(oy), x, int(oy + sh * scale))
            for j in range(self.config.tile_count_y + 1):
                y = int(oy + j * th * scale)
                painter.drawLine(int(ox), y, int(ox + sw * scale), y)

            # Tile 索引标注
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
                        if tw * scale > label_w + 4 and th * scale > label_h + 2:
                            painter.drawText(int(tile_cx - label_w / 2), int(tile_cy + label_h / 3), label)

            # Tile 像素坐标轴刻度
            if self.show_tile_pixel_axes and scale >= 0.5:
                small_font = max(6, min(9, int(7 * min(scale, 3))))
                painter.setFont(QFont("Consolas", small_font))
                fm_small = QFontMetrics(painter.font())
                painter.setPen(QPen(QColor(70, 70, 90)))

                x_label_h = fm_small.height()
                if oy - x_label_h - 3 > 0:
                    step_x = max(1, (fm_small.horizontalAdvance(str(sw)) + 4) // max(1, int(tw * scale)) + 1)
                    for i in range(0, self.config.tile_count_x + 1, step_x):
                        x_pixel = i * tw
                        vx = int(ox + x_pixel * scale)
                        text = str(x_pixel)
                        tw_px = fm_small.horizontalAdvance(text)
                        painter.drawText(vx - tw_px // 2, int(oy - 3), text)

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
                painter.drawLine(x, int(max(oy, oy)), x, int(min(oy + sh * scale, oy + sh * scale)))
            for py in range(vis_min_y, vis_max_y + 1):
                y = int(oy + py * scale)
                painter.drawLine(int(ox), y, int(ox + sw * scale), y)

            if scale >= 8.0:
                coord_font = max(6, min(9, int(6 * min(scale / 8, 3))))
                painter.setFont(QFont("Consolas", coord_font))
                fm_coord = QFontMetrics(painter.font())
                painter.setPen(QPen(QColor(80, 80, 100)))

                pixel_w = scale
                pixel_h = scale

                for px in range(vis_min_x, vis_max_x):
                    for py in range(vis_min_y, vis_max_y):
                        cx = ox + (px + 0.5) * scale
                        cy = oy + (py + 0.5) * scale
                        full_label = f"{px},{py}"
                        label_w = fm_coord.horizontalAdvance(full_label)
                        label_h = fm_coord.height()

                        if pixel_w > label_w + 2 and pixel_h > label_h:
                            painter.drawText(int(cx - label_w / 2), int(cy + label_h / 3), full_label)
                        elif pixel_h > label_h:
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
            painter.setBrush(Qt.BrushStyle.NoBrush)
            cx, cy, cw, ch = self.config.clip_region
            painter.drawRect(int(ox + cx * scale), int(oy + cy * scale), int(cw * scale), int(ch * scale))
            painter.setFont(QFont("Arial", 8))
            painter.setPen(QPen(QColor(255, 200, 0)))
            painter.drawText(int(ox + cx * scale + 3), int(oy + cy * scale - 3), f"Clip({cx},{cy},{cw},{ch})")

        # ---- Scissor ----
        if self.show_scissor:
            painter.setPen(QPen(QColor(0, 255, 200), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            sx, sy, s_width, s_height = self.config.scissor
            painter.drawRect(int(ox + sx * scale), int(oy + sy * scale), int(s_width * scale), int(s_height * scale))
            painter.setFont(QFont("Arial", 8))
            painter.setPen(QPen(QColor(0, 255, 200)))
            painter.drawText(int(ox + sx * scale + 3), int(oy + sy * scale + 12), f"Scissor({sx},{sy},{s_width},{s_height})")

        # ---- 三角形边框 + 顶点 ----
        for tri_idx, triangle in enumerate(self.triangles):
            color = QColor(triangle.color[0], triangle.color[1], triangle.color[2])
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            polygon = QPolygon()
            for v in triangle.vertices:
                polygon.append(QPoint(int(ox + v[0] * scale), int(oy + v[1] * scale)))
            painter.drawPolygon(polygon)

            painter.setBrush(QBrush(color))
            label_font_size = max(7, min(11, int(9 * min(scale, 2))))
            painter.setFont(QFont("Consolas", label_font_size))
            for vi, v in enumerate(triangle.vertices):
                vx = int(ox + v[0] * scale)
                vy = int(oy + v[1] * scale)
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawEllipse(vx - 5, vy - 5, 10, 10)
                if self.show_vertex_labels:
                    painter.setPen(QPen(color))
                    painter.drawText(vx + 8, vy - 6, f"V{vi}({v[0]:.0f},{v[1]:.0f},z={v[2]:.2f})")

        # ---- MSAA 采样点 + sample pattern 预览 ----
        if self.show_msaa_samples and self.config:
            msaa_positions = generate_msaa_sample_positions(self.config.msaa)

            if self.rasterized_results and scale >= 3.0:
                vis_min_x = max(0, int(-ox / scale))
                vis_min_y = max(0, int(-oy / scale))
                vis_max_x = min(sw, int((self.width() - ox) / scale) + 1)
                vis_max_y = min(sh, int((self.height() - oy) / scale) + 1)

                marker_size = max(4.0, min(10.0, scale * 0.32))
                label_samples = scale >= 12.0

                for result in self.rasterized_results:
                    tri_color = QColor(result.triangle.color[0], result.triangle.color[1], result.triangle.color[2])

                    visible_pixels = [(px, py) for px, py in result.covered_pixels
                                      if vis_min_x <= px < vis_max_x and vis_min_y <= py < vis_max_y]

                    for px, py in visible_pixels:
                        coverage = result.coverage_mask.get((px, py), 0)

                        for sample_idx, (sx, sy) in enumerate(msaa_positions):
                            is_covered = (coverage >> sample_idx) & 1

                            cx = ox + (px + sx) * scale
                            cy = oy + (py + sy) * scale
                            r = marker_size

                            if is_covered:
                                painter.setBrush(QBrush(tri_color.lighter(125)))
                                painter.setPen(QPen(QColor(255, 255, 255), 1))
                            else:
                                painter.setBrush(QBrush(QColor(25, 25, 25, 180)))
                                painter.setPen(QPen(QColor(180, 180, 180), 1))
                            painter.drawEllipse(int(cx - r / 2), int(cy - r / 2), int(r), int(r))

                            if label_samples:
                                painter.setFont(QFont("Consolas", max(6, min(9, int(scale / 5)))))
                                painter.setPen(QPen(QColor(255, 255, 255) if is_covered else QColor(210, 210, 210)))
                                painter.drawText(int(cx + r / 2 + 1), int(cy - r / 2 - 1), str(sample_idx))

                        if self.show_coverage_mask and scale >= 8.0:
                            painter.setPen(QPen(QColor(255, 255, 200)))
                            painter.setFont(QFont("Consolas", max(6, min(9, int(scale / 4)))))
                            mask_text = f"0b{coverage:0{self.config.msaa}b}"
                            painter.drawText(
                                int(ox + (px + 0.05) * scale),
                                int(oy + (py + 0.95) * scale),
                                mask_text
                            )

            self._draw_msaa_pattern_legend(painter, msaa_positions)

        # ---- 屏幕边框 ----
        painter.setPen(QPen(QColor(150, 150, 150), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(ox), int(oy), int(sw * scale), int(sh * scale))

        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(int(ox), int(oy - 5), f"Screen {sw}x{sh}")

        # ---- 底部信息 ----
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont("Arial", 10))
        msaa_text = f"MSAA: {self.config.msaa}x"
        if self.config.msaa > 1:
            # 统计边缘像素
            edge_count = sum(1 for r in self.rasterized_results
                            for ratio in r.coverage_ratio.values() if ratio < 1.0)
            msaa_text += f" (edge pixels: {edge_count})"
        info_text = f"Zoom: {self.zoom:.2f}x | Screen: {sw}x{sh} | " \
                    f"Tiles: {self.config.tile_width}x{self.config.tile_height} ({self.config.tile_count_x}x{self.config.tile_count_y}) | " \
                    f"{msaa_text}"
        if self.triangles:
            total_pixels = sum(len(r.covered_pixels) for r in self.rasterized_results)
            info_text += f" | Pixels: {total_pixels}"
        painter.drawText(10, self.height() - 8, info_text)

    def _draw_msaa_pattern_legend(self, painter: QPainter, msaa_positions: list):
        legend_size = 112
        margin = 12
        x0 = self.width() - legend_size - margin
        y0 = margin

        painter.setBrush(QBrush(QColor(20, 22, 28, 220)))
        painter.setPen(QPen(QColor(150, 160, 180), 1))
        painter.drawRect(x0, y0, legend_size, legend_size + 28)

        painter.setPen(QPen(QColor(235, 235, 235)))
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.drawText(x0 + 8, y0 + 17, f"{self.config.msaa}x MSAA samples")

        cell_x = x0 + 18
        cell_y = y0 + 30
        cell_size = 76
        painter.setBrush(QBrush(QColor(45, 48, 58)))
        painter.setPen(QPen(QColor(110, 120, 140), 1))
        painter.drawRect(cell_x, cell_y, cell_size, cell_size)

        for idx, (sx, sy) in enumerate(msaa_positions):
            px = cell_x + sx * cell_size
            py = cell_y + sy * cell_size
            painter.setBrush(QBrush(QColor(255, 210, 90)))
            painter.setPen(QPen(QColor(30, 30, 30), 1))
            painter.drawEllipse(int(px - 4), int(py - 4), 8, 8)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(int(px + 6), int(py - 5), str(idx))

    def wheelEvent(self, event):
        mouse_pos = event.position()
        old_screen = self._view_to_screen(mouse_pos.x(), mouse_pos.y())

        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.zoom *= factor
        self.zoom = max(0.1, min(50.0, self.zoom))

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
            self.zoom = min((self.width() - 2 * margin) / self.config.screen_width,
                            (self.height() - 2 * margin) / self.config.screen_height)
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

    def center_on_screen_position(self, x: float, y: float):
        if not self.config:
            return
        x = max(0.0, min(float(self.config.screen_width), float(x)))
        y = max(0.0, min(float(self.config.screen_height), float(y)))
        self.offset_x = self.width() / 2 - x * self.zoom
        self.offset_y = self.height() / 2 - y * self.zoom
        self.update()

    def _pan_step(self) -> float:
        return max(20.0, min(self.width(), self.height()) * 0.08)

    def pan_by(self, dx: float, dy: float):
        self.offset_x += dx
        self.offset_y += dy
        self.update()

    def pan_left(self):
        self.pan_by(self._pan_step(), 0)

    def pan_right(self):
        self.pan_by(-self._pan_step(), 0)

    def pan_up(self):
        self.pan_by(0, self._pan_step())

    def pan_down(self):
        self.pan_by(0, -self._pan_step())

    def set_pan_offset(self, x: float, y: float):
        self.offset_x = float(x)
        self.offset_y = float(y)
        self.update()

    def get_pan_offset(self) -> Tuple[float, float]:
        return (self.offset_x, self.offset_y)

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