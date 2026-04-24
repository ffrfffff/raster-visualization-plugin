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

        self.rot_x = 90.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.view_mode = "Top"
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
        return self._rotate_vector(nx, ny, nz)

    def _rotate_vector(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        rad_x = math.radians(self.rot_x)
        rad_y = math.radians(self.rot_y)
        rad_z = math.radians(self.rot_z)

        y1 = y * math.cos(rad_x) - z * math.sin(rad_x)
        z1 = y * math.sin(rad_x) + z * math.cos(rad_x)
        x1 = x

        x2 = x1 * math.cos(rad_y) + z1 * math.sin(rad_y)
        z2 = -x1 * math.sin(rad_y) + z1 * math.cos(rad_y)
        y2 = y1

        x3 = x2 * math.cos(rad_z) - y2 * math.sin(rad_z)
        y3 = x2 * math.sin(rad_z) + y2 * math.cos(rad_z)
        z3 = z2

        return (x3, y3, z3)

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
        origin = (self.width() - 82, self.height() - 62)
        axis_len = 34

        axes = [
            ("X", QColor(255, 95, 95), self._transform_axis(1, 0, 0, axis_len)),
            ("Y", QColor(90, 230, 120), self._transform_axis(0, 1, 0, axis_len)),
            ("Z", QColor(95, 145, 255), self._transform_axis(0, 0, 1, axis_len)),
        ]

        painter.setBrush(QBrush(QColor(20, 22, 28, 180)))
        painter.setPen(QPen(QColor(110, 120, 145), 1))
        painter.drawRoundedRect(self.width() - 128, self.height() - 118, 112, 102, 6, 6)

        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        for label, color, (dx, dy) in axes:
            end_x = origin[0] + dx
            end_y = origin[1] + dy
            painter.setPen(QPen(color, 3))
            painter.drawLine(int(origin[0]), int(origin[1]), int(end_x), int(end_y))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(int(end_x - 4), int(end_y - 4), 8, 8)
            painter.drawText(int(end_x) + 6, int(end_y) - 6, label)

        painter.setBrush(QBrush(QColor(230, 230, 235)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(origin[0] - 3), int(origin[1] - 3), 6, 6)

    def _transform_axis(self, x: float, y: float, z: float, axis_len: float) -> Tuple[float, float]:
        x2, y2, _ = self._rotate_vector(x, y, z)
        return (x2 * axis_len, -y2 * axis_len)

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
        painter.drawText(10, 20, f"Mode: {self.view_mode} | Rot XYZ: ({self.rot_x:.0f}, {self.rot_y:.0f}, {self.rot_z:.0f}) | Zoom: {self.zoom:.2f}")
        painter.drawText(10, 36, f"Input: {mode} | Default mode is Top, buttons rotate around X/Y/Z axes")

    def _view_name(self) -> str:
        return self.view_mode

    def _set_view(self, mode: str, rot_x: float, rot_y: float, rot_z: float = 0.0):
        self.view_mode = mode
        self.rot_x = rot_x
        self.rot_y = rot_y
        self.rot_z = rot_z
        self.update()

    def mousePressEvent(self, event):
        if self.free_rotate and event.button() == Qt.MouseButton.LeftButton:
            self._last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.free_rotate and self._last_pos and event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.pos().x() - self._last_pos.x()
            dy = event.pos().y() - self._last_pos.y()
            self.rotate_y(dx * 0.5)
            self.rotate_x(dy * 0.5)
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

    def rotate_x(self, degrees: float):
        self.view_mode = "Custom"
        self.rot_x = ((self.rot_x + degrees + 180) % 360) - 180
        self.update()

    def rotate_y(self, degrees: float):
        self.view_mode = "Custom"
        self.rot_y = ((self.rot_y + degrees + 180) % 360) - 180
        self.update()

    def rotate_z(self, degrees: float):
        self.view_mode = "Custom"
        self.rot_z = ((self.rot_z + degrees + 180) % 360) - 180
        self.update()

    def rotate_horizontal(self, degrees: float):
        self.rotate_y(degrees)

    def rotate_vertical(self, degrees: float):
        self.rotate_x(degrees)

    def set_view_front(self):
        self._set_view("X-Y Front", 0.0, 0.0, 0.0)

    def set_view_back(self):
        self._set_view("X-Y Back", 0.0, 180.0, 0.0)

    def set_view_left(self):
        self._set_view("Y-Z Side", 0.0, 90.0, 0.0)

    def set_view_right(self):
        self._set_view("Y-Z Side", 0.0, -90.0, 0.0)

    def set_view_top(self):
        self._set_view("Top", 90.0, 0.0, 0.0)

    def set_view_bottom(self):
        self._set_view("Bottom", -90.0, 0.0, 0.0)

    def set_view_xz_side(self):
        self._set_view("X-Z Side", 0.0, 0.0, 0.0)

    def set_view_yz_side(self):
        self._set_view("Y-Z Side", 0.0, 90.0, 0.0)

    def set_view_perspective(self):
        self._set_view("Free 3D", 35.0, -45.0, 0.0)
