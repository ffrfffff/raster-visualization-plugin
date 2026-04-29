from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygonF
from typing import List, Tuple, Optional
import math
from ..models.config import RasterConfig
from ..models.triangle import Triangle, RasterizedTriangle


class DepthSideView(QWidget):
    """深度侧视图，支持缩放和平移

    横轴: 屏幕 X 坐标 (像素)
    纵轴: 深度值 [-1, 1]
    """

    def __init__(self):
        super().__init__()
        self.config: Optional[RasterConfig] = None
        self.triangles: List[Triangle] = []
        self.rasterized_results: List[RasterizedTriangle] = []

        self.margin_left = 50
        self.margin_right = 20
        self.margin_top = 30
        self.margin_bottom = 40

        # 缩放和平移
        self.zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self._last_pos = None
        self._drag_start = None
        self._drag_offset_start = None

        self.setMinimumSize(300, 200)
        self.setMouseTracking(True)

    def set_config(self, config: RasterConfig):
        self.config = config
        self.update()

    def set_triangles(self, triangles: List[Triangle], rasterized: List[RasterizedTriangle]):
        self.triangles = triangles
        self.rasterized_results = rasterized
        self.update()

    def _safe_view_coord(self, value: float) -> float:
        if not math.isfinite(value):
            return 0.0
        return max(-1_000_000.0, min(1_000_000.0, value))

    def _map_x(self, screen_x: float) -> float:
        """将屏幕 X 坐标映射到视图坐标（含缩放偏移）"""
        if not self.config:
            return self._safe_view_coord(screen_x)
        width = self.width() - self.margin_left - self.margin_right
        if self.config.screen_width <= 0:
            return self._safe_view_coord(self.margin_left + self.offset_x)
        relative_x = screen_x - self.config.coordinate_offset - self.config.screen_origin
        base = self.margin_left + (relative_x / self.config.screen_width) * width
        mapped = self.margin_left + (base - self.margin_left) * self.zoom + self.offset_x
        return self._safe_view_coord(mapped)

    def _map_y(self, depth: float) -> float:
        """将深度值 [-1, 1] 映射到视图坐标（含缩放偏移）"""
        height = self.height() - self.margin_top - self.margin_bottom
        base = self.margin_top + ((1 - depth) / 2) * height
        mapped = self.margin_top + (base - self.margin_top) * self.zoom + self.offset_y
        return self._safe_view_coord(mapped)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if not self.config:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No configuration")
            return

        # 绘制坐标轴
        painter.setPen(QPen(QColor(150, 150, 150), 1))

        y_axis_top = self.margin_top
        y_axis_bottom = self.height() - self.margin_bottom
        x_axis_left = self.margin_left
        x_axis_right = self.width() - self.margin_right

        painter.drawLine(self.margin_left, y_axis_top, self.margin_left, y_axis_bottom)
        painter.drawLine(x_axis_left, y_axis_bottom, x_axis_right, y_axis_bottom)

        # Y 轴标签
        painter.setFont(QFont("Arial", 8))
        painter.drawText(5, int(self._map_y(1.0)), "1.0")
        painter.drawText(5, int(self._map_y(0.0)), "0.0")
        painter.drawText(5, int(self._map_y(-1.0)), "-1.0")

        # Y 轴刻度线
        for d in [1.0, 0.5, 0.0, -0.5, -1.0]:
            y = int(self._map_y(d))
            painter.drawLine(x_axis_left - 3, y, x_axis_left + 3, y)
            painter.setPen(QPen(QColor(50, 50, 50), 1, Qt.PenStyle.DotLine))
            painter.drawLine(x_axis_left, y, x_axis_right, y)
            painter.setPen(QPen(QColor(150, 150, 150), 1))

        # Y 轴标题
        painter.setFont(QFont("Arial", 10))
        painter.drawText(5, self.height() // 2, "Depth")

        # X 轴标签
        screen_min_x = self.config.screen_origin + self.config.coordinate_offset
        screen_max_x = self.config.screen_origin + self.config.screen_width + self.config.coordinate_offset
        painter.drawText(int(self._map_x(screen_min_x)), y_axis_bottom + 15, str(screen_min_x))
        painter.drawText(int(self._map_x(screen_max_x)) - 30, y_axis_bottom + 15,
                         str(screen_max_x))

        # 绘制三角形深度剖面
        if self.triangles:
            for i, triangle in enumerate(self.triangles):
                color = QColor(triangle.color[0], triangle.color[1], triangle.color[2])

                finite_vertices = [v for v in triangle.vertices if math.isfinite(v[0]) and math.isfinite(v[2])]
                if not finite_vertices:
                    continue

                # 绘制填充区域
                polygon = QPolygonF()
                for v in finite_vertices:
                    x = self._map_x(v[0])
                    y = self._map_y(v[2])
                    polygon.append(QPointF(x, y))
                if polygon.size() == 3:
                    fill_color = QColor(color.red(), color.green(), color.blue(), 40)
                    painter.setBrush(QBrush(fill_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawPolygon(polygon)

                # 绘制三条边的深度线
                painter.setPen(QPen(color, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for j in range(3):
                    v0 = triangle.vertices[j]
                    v1 = triangle.vertices[(j + 1) % 3]
                    if not all(math.isfinite(value) for value in (v0[0], v0[2], v1[0], v1[2])):
                        continue
                    x0 = self._map_x(v0[0])
                    y0 = self._map_y(v0[2])
                    x1 = self._map_x(v1[0])
                    y1 = self._map_y(v1[2])
                    painter.drawLine(int(x0), int(y0), int(x1), int(y1))

                # 绘制顶点标记
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                for v in finite_vertices:
                    x = self._map_x(v[0])
                    y = self._map_y(v[2])
                    painter.drawEllipse(int(x - 5), int(y - 5), 10, 10)

                # 深度值标签
                painter.setFont(QFont("Arial", 8))
                painter.setPen(QPen(color))
                for v in finite_vertices:
                    x = self._map_x(v[0])
                    y = self._map_y(v[2])
                    painter.drawText(int(x + 10), int(y + 4), f"z={v[2]:.3f}")

                # 三角形索引
                painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                avg_x = sum(self._map_x(v[0]) for v in finite_vertices) / len(finite_vertices)
                avg_y = sum(self._map_y(v[2]) for v in finite_vertices) / len(finite_vertices)
                painter.drawText(int(avg_x + 10), int(avg_y - 10), f"T{i}")

        # 绘制像素深度点
        if self.rasterized_results:
            for result in self.rasterized_results:
                color = QColor(result.triangle.color[0], result.triangle.color[1], result.triangle.color[2], 150)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))

                pixels = list(result.covered_pixels)
                step = max(1, len(pixels) // 200)
                for idx in range(0, len(pixels), step):
                    px, py = pixels[idx]
                    if (px, py) in result.depth_values:
                        depth = result.depth_values[(px, py)]
                        x = self._map_x(px)
                        y = self._map_y(depth)
                        painter.drawEllipse(int(x - 1), int(y - 1), 2, 2)

        # 缩放信息
        painter.setPen(QPen(QColor(150, 150, 150)))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(self.width() - 100, 15, f"Zoom: {self.zoom:.1f}x")
        painter.drawText(self.width() - 150, 15, "Scroll=Zoom, Drag=Pan")

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self.zoom *= factor
        self.zoom = max(0.5, min(20.0, self.zoom))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
            self._drag_offset_start = (self.offset_x, self.offset_y)

    def mouseMoveEvent(self, event):
        if self._drag_start and event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.pos().x() - self._drag_start.x()
            dy = event.pos().y() - self._drag_start.y()
            self.offset_x = self._drag_offset_start[0] + dx
            self.offset_y = self._drag_offset_start[1] + dy
            self.update()

    def mouseReleaseEvent(self, event):
        self._drag_start = None

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

    def reset_view(self):
        self.zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.update()