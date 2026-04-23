from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygon, QTransform
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

            # Tile 坐标标注（缩放足够大时显示）
            if self.show_tile_labels and scale >= 0.5:
                font_size = max(7, min(11, int(8 * scale)))
                painter.setFont(QFont("Consolas", font_size))
                painter.setPen(QPen(QColor(90, 90, 110)))

                for i in range(self.config.tile_count_x):
                    for j in range(self.config.tile_count_y):
                        tile_cx = ox + (i * tw + tw / 2) * scale
                        tile_cy = oy + (j * th + th / 2) * scale
                        label = f"({i},{j})"
                        # 只在 tile 内部能放下文字时绘制
                        if tw * scale > 30 and th * scale > 14:
                            painter.drawText(
                                int(tile_cx - len(label) * font_size / 2.5),
                                int(tile_cy + font_size / 3),
                                label
                            )

                # Tile 像素坐标标注（缩放足够大时在 tile 边标注起止像素）
                if scale >= 1.0:
                    small_font = max(6, min(9, int(7 * min(scale, 3))))
                    painter.setFont(QFont("Consolas", small_font))
                    painter.setPen(QPen(QColor(70, 70, 90)))
                    for i in range(self.config.tile_count_x + 1):
                        x_pixel = i * tw
                        vx = int(ox + x_pixel * scale)
                        painter.drawText(vx - 10, int(oy - 3), str(x_pixel))
                    for j in range(self.config.tile_count_y + 1):
                        y_pixel = j * th
                        vy = int(oy + y_pixel * scale)
                        painter.drawText(int(ox - 30), vy + 4, str(y_pixel))

        # ---- 像素坐标网格（高缩放时） ----
        if self.show_pixel_coords and scale >= 4.0:
            # 绘制像素边界
            painter.setPen(QPen(QColor(50, 50, 55), 1))
            # 只绘制可见区域的像素线
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

            # 像素坐标标注（缩放很大时每个像素标注）
            if scale >= 8.0:
                coord_font = max(6, min(9, int(6 * min(scale / 8, 3))))
                painter.setFont(QFont("Consolas", coord_font))
                painter.setPen(QPen(QColor(80, 80, 100)))
                for px in range(vis_min_x, vis_max_x):
                    for py in range(vis_min_y, vis_max_y):
                        cx = ox + (px + 0.5) * scale
                        cy = oy + (py + 0.5) * scale
                        painter.drawText(int(cx - 12), int(cy + 3), f"{px},{py}")

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

        # ---- 光栅化像素 ----
        if self.show_raster_pixels and self.rasterized_results:
            for result in self.rasterized_results:
                color = result.triangle.color
                fill_color = QColor(color[0], color[1], color[2], 80)
                painter.setBrush(QBrush(fill_color))
                painter.setPen(Qt.PenStyle.NoPen)

                for px, py in result.covered_pixels:
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

                # 坐标标签
                painter.setPen(QPen(color))
                label = f"V{vi}({v[0]:.0f},{v[1]:.0f},z={v[2]:.2f})"
                painter.drawText(vx + 8, vy - 6, label)

        # ---- MSAA 采样点 ----
        if self.show_msaa_samples and self.rasterized_results and self.config.msaa > 1:
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            for result in self.rasterized_results:
                for px, py in result.covered_pixels:
                    for sx, sy in [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)][:self.config.msaa]:
                        painter.drawEllipse(
                            int(ox + (px + sx) * scale - 1),
                            int(oy + (py + sy) * scale - 1),
                            2, 2
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