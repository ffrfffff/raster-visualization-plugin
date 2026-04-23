"""3D 可旋转视图

使用 QPainter 进行 3D 投影绘制，支持鼠标旋转
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygonF
from typing import List, Optional, Tuple
from ..models.config import RasterConfig
from ..models.triangle import Triangle


class View3D(QWidget):
    """3D 可旋转视图

    显示三角形的三维形态，支持鼠标旋转、缩放
    X/Y 为屏幕像素坐标，Z 为深度 [-1, 1]
    """

    def __init__(self):
        super().__init__()
        self.config: Optional[RasterConfig] = None
        self.triangles: List[Triangle] = []

        # 旋转角度
        self.rot_x = 30.0
        self.rot_y = -45.0
        self.zoom = 1.0

        # 鼠标拖拽
        self._last_pos = None

        # 坐标轴显示
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

    def _project(self, x: float, y: float, z: float) -> Tuple[float, float]:
        """将 3D 坐标投影到 2D 屏幕坐标

        X: 屏幕像素 (0 ~ screen_width)
        Y: 屏幕像素 (0 ~ screen_height)
        Z: 深度 [-1, 1]
        """
        if not self.config:
            return (x, y)

        # 归一化到 [-1, 1] 范围
        nx = (x / self.config.screen_width) * 2 - 1
        ny = (y / self.config.screen_height) * 2 - 1
        nz = z

        # 旋转
        rad_x = math.radians(self.rot_x)
        rad_y = math.radians(self.rot_y)

        # 绕 Y 轴旋转
        x1 = nx * math.cos(rad_y) - nz * math.sin(rad_y)
        z1 = nx * math.sin(rad_y) + nz * math.cos(rad_y)
        y1 = ny

        # 绕 X 轴旋转
        y2 = y1 * math.cos(rad_x) - z1 * math.sin(rad_x)
        z2 = y1 * math.sin(rad_x) + z1 * math.cos(rad_x)
        x2 = x1

        # 透视投影
        fov = 2.0
        depth = z2 + fov
        if depth < 0.1:
            depth = 0.1

        scale = fov / depth * self.zoom * 150
        cx = self.width() / 2
        cy = self.height() / 2

        sx = cx + x2 * scale
        sy = cy - y2 * scale

        return (sx, sy)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        painter.fillRect(self.rect(), QColor(25, 25, 35))

        if not self.config:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No configuration")
            return

        # 绘制坐标轴
        if self.show_axes:
            self._draw_axes(painter)

        # 绘制网格平面
        if self.show_grid:
            self._draw_grid(painter)

        # 绘制三角形
        for i, triangle in enumerate(self.triangles):
            self._draw_triangle(painter, triangle, i)

        # 绘制信息
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(10, 20, f"Rot: ({self.rot_x:.0f}, {self.rot_y:.0f}) Zoom: {self.zoom:.2f}")
        painter.drawText(10, 35, "Drag to rotate, Scroll to zoom")

    def _draw_axes(self, painter: QPainter):
        """绘制 X/Y/Z 坐标轴"""
        origin = self._project(0, 0, 0)
        axis_len = 0.5

        # X 轴 (红色)
        x_end = self._project(self.config.screen_width * axis_len + self.config.screen_width / 2,
                              self.config.screen_height / 2, 0)
        painter.setPen(QPen(QColor(255, 80, 80), 2))
        painter.drawLine(int(origin[0]), int(origin[1]), int(x_end[0]), int(x_end[1]))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(int(x_end[0]) + 5, int(x_end[1]) - 5, "X")

        # Y 轴 (绿色)
        y_end = self._project(self.config.screen_width / 2,
                              self.config.screen_height * (0.5 - axis_len), 0)
        painter.setPen(QPen(QColor(80, 255, 80), 2))
        painter.drawLine(int(origin[0]), int(origin[1]), int(y_end[0]), int(y_end[1]))
        painter.drawText(int(y_end[0]) + 5, int(y_end[1]) - 5, "Y")

        # Z 轴 (蓝色)
        z_end = self._project(self.config.screen_width / 2,
                              self.config.screen_height / 2, axis_len * 2)
        painter.setPen(QPen(QColor(80, 80, 255), 2))
        painter.drawLine(int(origin[0]), int(origin[1]), int(z_end[0]), int(z_end[1]))
        painter.drawText(int(z_end[0]) + 5, int(z_end[1]) - 5, "Z")

    def _draw_grid(self, painter: QPainter):
        """绘制 XY 平面网格"""
        painter.setPen(QPen(QColor(50, 50, 60), 1))
        steps = 4
        for i in range(steps + 1):
            frac = i / steps
            # 水平线
            p1 = self._project(0, self.config.screen_height * frac, 0)
            p2 = self._project(self.config.screen_width, self.config.screen_height * frac, 0)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
            # 垂直线
            p1 = self._project(self.config.screen_width * frac, 0, 0)
            p2 = self._project(self.config.screen_width * frac, self.config.screen_height, 0)
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

    def _draw_triangle(self, painter: QPainter, triangle: Triangle, index: int):
        """绘制 3D 三角形"""
        color = QColor(triangle.color[0], triangle.color[1], triangle.color[2])

        # 填充面
        points = []
        for v in triangle.vertices:
            sx, sy = self._project(v[0], v[1], v[2])
            points.append((sx, sy))

        polygon = QPolygonF()
        from PyQt6.QtCore import QPointF
        for sx, sy in points:
            polygon.append(QPointF(sx, sy))

        fill_color = QColor(color.red(), color.green(), color.blue(), 60)
        painter.setBrush(QBrush(fill_color))
        painter.setPen(QPen(color, 2))
        painter.drawPolygon(polygon)

        # 绘制边
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(color, 2))
        for i in range(3):
            j = (i + 1) % 3
            painter.drawLine(int(points[i][0]), int(points[i][1]),
                             int(points[j][0]), int(points[j][1]))

        # 绘制顶点
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        for k, v in enumerate(triangle.vertices):
            sx, sy = self._project(v[0], v[1], v[2])
            painter.drawEllipse(int(sx - 5), int(sy - 5), 10, 10)

        # 顶点标签
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QPen(QColor(255, 255, 255)))
        for k, v in enumerate(triangle.vertices):
            sx, sy = self._project(v[0], v[1], v[2])
            label = f"V{k}"
            painter.drawText(int(sx + 8), int(sy - 8), label)

        # 三角形索引
        avg_sx = sum(p[0] for p in points) / 3
        avg_sy = sum(p[1] for p in points) / 3
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.setPen(QPen(color))
        painter.drawText(int(avg_sx + 12), int(avg_sy - 12), f"T{index}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self._last_pos and event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.pos().x() - self._last_pos.x()
            dy = event.pos().y() - self._last_pos.y()

            self.rot_y += dx * 0.5
            self.rot_x += dy * 0.5
            self.rot_x = max(-90, min(90, self.rot_x))

            self._last_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self._last_pos = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self.zoom *= factor
        self.zoom = max(0.1, min(10.0, self.zoom))
        self.update()

    def reset_view(self):
        self.rot_x = 30.0
        self.rot_y = -45.0
        self.zoom = 1.0
        self.update()
