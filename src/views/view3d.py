"""3D 可旋转视图"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygonF
from typing import List, Optional, Tuple
from ..models.config import RasterConfig
from ..models.triangle import Triangle


class View3D(QWidget):
    """3D 可旋转视图"""

    def __init__(self):
        super().__init__()
        self.config: Optional[RasterConfig] = None
        self.triangles: List[Triangle] = []

        self.rot_x = 35.0
        self.rot_y = -45.0
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.free_rotate = False

        self._last_pos = None

        self.show_axes = True
        self.show_grid = True

        self.setMinimumSize(300, 200)
        self.setMouseTracking(True)

    def set_config(self, config: RasterConfig):
        self.config = config
        self.update()

    def set_triangles(self, triangles: List[Triangle]):
        self.triangles = triangles
        self.update()

    def _normalize(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        if not self.config:
            return (x, y, z)

        nx = (x / self.config.screen_width) * 2 - 1
        ny = 1 - (y / self.config.screen_height) * 2
        nz = z * 0.75
        return (nx, ny, nz)

    def _transform(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        nx, ny, nz = self._normalize(x, y, z)

        rad_x = math.radians(self.rot_x)
        rad_y = math.radians(self.rot_y)

        x1 = nx * math.cos(rad_y) - nz * math.sin(rad_y)
        z1 = nx * math.sin(rad_y) + nz * math.cos(rad_y)
        y1 = ny

        y2 = y1 * math.cos(rad_x) - z1 * math.sin(rad_x)
        z2 = y1 * math.sin(rad_x) + z1 * math.cos(rad_x)
        x2 = x1

        return (x2, y2, z2)

    def _project(self, x: float, y: float, z: float) -> Tuple[float, float]:
        x2, y2, _ = self._transform(x, y, z)
        scale = min(self.width(), self.height()) * 0.36 * self.zoom
        cx = self.width() / 2 + self.pan_x
        cy = self.height() / 2 + self.pan_y
        return (cx + x2 * scale, cy - y2 * scale)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(22, 24, 32))

        if not self.config:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No configuration")
            return

        self._draw_background_panel(painter)

        if self.show_grid:
            self._draw_grid(painter)

        if self.show_axes:
            self._draw_axes(painter)

        ordered = sorted(
            enumerate(self.triangles),
            key=lambda item: sum(self._transform(v[0], v[1], v[2])[2] for v in item[1].vertices) / 3,
        )
        for index, triangle in ordered:
            self._draw_triangle(painter, triangle, index)

        self._draw_overlay(painter)

    def _draw_background_panel(self, painter: QPainter):
        sw = self.config.screen_width
        sh = self.config.screen_height
        corners = [
            self._project(0, 0, 0),
            self._project(sw, 0, 0),
            self._project(sw, sh, 0),
            self._project(0, sh, 0),
        ]

        polygon = QPolygonF()
        for sx, sy in corners:
            polygon.append(QPointF(sx, sy))

        painter.setBrush(QBrush(QColor(55, 60, 76, 70)))
        painter.setPen(QPen(QColor(95, 105, 130), 1))
        painter.drawPolygon(polygon)

    def _draw_axes(self, painter: QPainter):
        sw = self.config.screen_width
        sh = self.config.screen_height
        origin = self._project(sw / 2, sh / 2, 0)
        axis_len = 0.5

        axes = [
            ("X", QColor(255, 95, 95), self._project(sw / 2 + sw * axis_len / 2, sh / 2, 0)),
            ("Y", QColor(90, 230, 120), self._project(sw / 2, sh / 2 - sh * axis_len / 2, 0)),
            ("Z", QColor(95, 145, 255), self._project(sw / 2, sh / 2, axis_len)),
        ]

        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        for label, color, end in axes:
            painter.setPen(QPen(color, 3))
            painter.drawLine(int(origin[0]), int(origin[1]), int(end[0]), int(end[1]))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(int(end[0] - 4), int(end[1] - 4), 8, 8)
            painter.drawText(int(end[0]) + 7, int(end[1]) - 7, label)

    def _draw_grid(self, painter: QPainter):
        sw = self.config.screen_width
        sh = self.config.screen_height
        steps = 8

        painter.setPen(QPen(QColor(65, 72, 90), 1))
        for i in range(steps + 1):
            frac = i / steps
            p1 = self._project(0, sh * frac, 0)
            p2 = self._project(sw, sh * frac, 0)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

            p1 = self._project(sw * frac, 0, 0)
            p2 = self._project(sw * frac, sh, 0)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

    def _draw_triangle(self, painter: QPainter, triangle: Triangle, index: int):
        color = QColor(triangle.color[0], triangle.color[1], triangle.color[2])
        points = [self._project(v[0], v[1], v[2]) for v in triangle.vertices]

        polygon = QPolygonF()
        for sx, sy in points:
            polygon.append(QPointF(sx, sy))

        painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 85)))
        painter.setPen(QPen(color.lighter(120), 2))
        painter.drawPolygon(polygon)

        for v in triangle.vertices:
            base = self._project(v[0], v[1], 0)
            tip = self._project(v[0], v[1], v[2])
            painter.setPen(QPen(QColor(180, 185, 205, 90), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(base[0]), int(base[1]), int(tip[0]), int(tip[1]))

        painter.setBrush(QBrush(color.lighter(125)))
        painter.setPen(QPen(QColor(245, 245, 245), 1))
        for k, v in enumerate(triangle.vertices):
            sx, sy = self._project(v[0], v[1], v[2])
            painter.drawEllipse(int(sx - 5), int(sy - 5), 10, 10)
            painter.setFont(QFont("Arial", 8))
            painter.drawText(int(sx + 8), int(sy - 8), f"V{k}")

        avg_sx = sum(p[0] for p in points) / 3
        avg_sy = sum(p[1] for p in points) / 3
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.setPen(QPen(color.lighter(130)))
        painter.drawText(int(avg_sx + 12), int(avg_sy - 12), f"T{index}")

    def _draw_overlay(self, painter: QPainter):
        mode = "Free drag" if self.free_rotate else "Fixed/buttons"
        painter.setPen(QPen(QColor(220, 220, 225)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(10, 20, f"View: {self._view_name()} | Rot: ({self.rot_x:.0f}, {self.rot_y:.0f}) | Zoom: {self.zoom:.2f}")
        painter.drawText(10, 36, f"Mode: {mode} | Wheel zoom, buttons rotate")

    def _view_name(self) -> str:
        presets = {
            (0, 0): "Front",
            (0, 180): "Back",
            (0, 90): "Left",
            (0, -90): "Right",
            (90, 0): "Top",
            (-90, 0): "Bottom",
            (35, -45): "ISO",
        }
        key = (round(self.rot_x), round(self.rot_y))
        return presets.get(key, "Custom")

    def mousePressEvent(self, event):
        if self.free_rotate and event.button() == Qt.MouseButton.LeftButton:
            self._last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.free_rotate and self._last_pos and event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.pos().x() - self._last_pos.x()
            dy = event.pos().y() - self._last_pos.y()
            self.rotate_horizontal(dx * 0.5)
            self.rotate_vertical(dy * 0.5)
            self._last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        self._last_pos = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self.zoom *= factor
        self.zoom = max(0.1, min(10.0, self.zoom))
        self.update()

    def reset_view(self):
        self.set_view_perspective()
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()

    def _pan_step(self) -> float:
        return max(20.0, min(self.width(), self.height()) * 0.08)

    def pan_by(self, dx: float, dy: float):
        self.pan_x += dx
        self.pan_y += dy
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
        self.pan_x = float(x)
        self.pan_y = float(y)
        self.update()

    def get_pan_offset(self) -> Tuple[float, float]:
        return (self.pan_x, self.pan_y)

    def set_free_rotate(self, enabled: bool):
        self.free_rotate = enabled
        self._last_pos = None
        self.update()

    def rotate_horizontal(self, degrees: float):
        self.rot_y = ((self.rot_y + degrees + 180) % 360) - 180
        self.update()

    def rotate_vertical(self, degrees: float):
        self.rot_x = max(-90, min(90, self.rot_x + degrees))
        self.update()

    def set_view_front(self):
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.update()

    def set_view_back(self):
        self.rot_x = 0.0
        self.rot_y = 180.0
        self.update()

    def set_view_left(self):
        self.rot_x = 0.0
        self.rot_y = 90.0
        self.update()

    def set_view_right(self):
        self.rot_x = 0.0
        self.rot_y = -90.0
        self.update()

    def set_view_top(self):
        self.rot_x = 90.0
        self.rot_y = 0.0
        self.update()

    def set_view_bottom(self):
        self.rot_x = -90.0
        self.rot_y = 0.0
        self.update()

    def set_view_perspective(self):
        self.rot_x = 35.0
        self.rot_y = -45.0
        self.update()
