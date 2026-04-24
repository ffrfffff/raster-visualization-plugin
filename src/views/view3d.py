"""3D 可旋转视图"""
import math
from PyQt6.QtWidgets import QWidget, QToolTip
from PyQt6.QtCore import Qt, QPointF, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QPolygonF, QFontMetrics, QImage
from typing import List, Optional, Tuple
from ..models.config import RasterConfig
from ..models.triangle import Triangle, RasterizedTriangle
from ..renderers.software_rasterizer import SoftwareRasterizer
from ..utils.geometry import generate_msaa_sample_positions


class View3D(QWidget):
    """3D 可旋转视图"""

    def __init__(self):
        super().__init__()
        self.config: Optional[RasterConfig] = None
        self.triangles: List[Triangle] = []
        self.rasterized_results: List[RasterizedTriangle] = []
        self.rasterizer: Optional[SoftwareRasterizer] = None

        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.view_mode = "Top"
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.free_rotate = False

        self._last_pos = None
        self.selected_msaa_pixel: Optional[Tuple[int, int]] = None
        self._pixel_image: Optional[QImage] = None
        self._pixel_image_msaa: Optional[QImage] = None
        self._pixel_image_dirty = True

        self.show_axes = True
        self.show_grid = True
        self.show_tiles = True
        self.show_scissor = True
        self.show_clip = True
        self.show_depth_surface = True
        self.show_rt_surface = True
        self.show_raster_pixels = True
        self.show_msaa_samples = True
        self.show_tile_labels = True
        self.show_pixel_coords = True
        self.show_tile_pixel_axes = True
        self.show_vertex_labels = True
        self.show_coverage_mask = True

        self.setMinimumSize(300, 200)
        self.setMouseTracking(True)

    def set_config(self, config: RasterConfig):
        self.config = config
        self.rasterizer = SoftwareRasterizer(config)
        self._pixel_image_dirty = True
        self.update()

    def set_triangles(self, triangles: List[Triangle], rasterized: Optional[List[RasterizedTriangle]] = None):
        self.triangles = triangles
        self.rasterized_results = rasterized or []
        self._pixel_image_dirty = True
        self.update()

    def set_rasterized_results(self, rasterized: List[RasterizedTriangle]):
        self.rasterized_results = rasterized
        self._pixel_image_dirty = True
        self.update()

    def _is_flat_top_view(self) -> bool:
        return all(abs(v) < 0.001 for v in (self.rot_x, self.rot_y, self.rot_z))

    def _screen_to_top_view_rect(self) -> QRect:
        sw = self.config.screen_width
        sh = self.config.screen_height
        p0 = self._project(0, 0, 0)
        p1 = self._project(sw, sh, 0)
        x = min(p0[0], p1[0])
        y = min(p0[1], p1[1])
        w = abs(p1[0] - p0[0])
        h = abs(p1[1] - p0[1])
        return QRect(int(x), int(y), max(1, int(w)), max(1, int(h)))

    def _visible_screen_bounds(self, pad: int = 2) -> Tuple[int, int, int, int]:
        if not self.config or not self._is_flat_top_view():
            return (0, 0, self.config.screen_width if self.config else 0, self.config.screen_height if self.config else 0)
        top_left = self._screen_point_from_view(0, 0) or (0, 0)
        bottom_right = self._screen_point_from_view(self.width(), self.height()) or (self.config.screen_width, self.config.screen_height)
        min_x = max(0, int(math.floor(min(top_left[0], bottom_right[0]))) - pad)
        min_y = max(0, int(math.floor(min(top_left[1], bottom_right[1]))) - pad)
        max_x = min(self.config.screen_width, int(math.ceil(max(top_left[0], bottom_right[0]))) + pad)
        max_y = min(self.config.screen_height, int(math.ceil(max(top_left[1], bottom_right[1]))) + pad)
        return (min_x, min_y, max_x, max_y)

    def _rebuild_pixel_image(self):
        if not self.config or not self.rasterized_results:
            self._pixel_image = None
            self._pixel_image_msaa = None
            self._pixel_image_dirty = False
            return

        sw = self.config.screen_width
        sh = self.config.screen_height
        img = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor(0, 0, 0, 0))

        for result in self.rasterized_results:
            color = result.triangle.color
            for (px, py), ratio in result.coverage_ratio.items():
                if 0 <= px < sw and 0 <= py < sh:
                    img.setPixelColor(px, py, QColor(color[0], color[1], color[2], int(210 * ratio)))
        self._pixel_image = img

        if self.config.msaa > 1 and self.rasterizer:
            img_msaa = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
            img_msaa.fill(QColor(0, 0, 0, 0))
            for (px, py), (r, g, b) in self.rasterizer.resolve_msaa(self.rasterized_results).items():
                if 0 <= px < sw and 0 <= py < sh:
                    img_msaa.setPixelColor(px, py, QColor(r, g, b, 205))
            self._pixel_image_msaa = img_msaa
        else:
            self._pixel_image_msaa = None

        self._pixel_image_dirty = False

    def _normalize(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        if not self.config:
            return (x, y, z)

        max_dim = max(self.config.screen_width, self.config.screen_height)
        nx = ((x - self.config.screen_width / 2) / max_dim) * 2
        ny = ((self.config.screen_height / 2 - y) / max_dim) * 2
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

    def _projected_polygon(self, points: List[Tuple[float, float, float]]) -> QPolygonF:
        polygon = QPolygonF()
        for x, y, z in points:
            sx, sy = self._project(x, y, z)
            polygon.append(QPointF(sx, sy))
        return polygon

    def _draw_projected_line(self, painter: QPainter, p0: Tuple[float, float, float], p1: Tuple[float, float, float]):
        x0, y0 = self._project(*p0)
        x1, y1 = self._project(*p1)
        painter.drawLine(int(x0), int(y0), int(x1), int(y1))

    def _draw_projected_rect(self, painter: QPainter, x: float, y: float, w: float, h: float, z: float = 0.0):
        polygon = self._projected_polygon([
            (x, y, z),
            (x + w, y, z),
            (x + w, y + h, z),
            (x, y + h, z),
        ])
        painter.drawPolygon(polygon)

    def _projected_pixel_size(self) -> float:
        if not self.config:
            return 1.0
        p00 = self._project(0, 0, 0)
        p10 = self._project(1, 0, 0)
        p01 = self._project(0, 1, 0)
        dx = math.hypot(p10[0] - p00[0], p10[1] - p00[1])
        dy = math.hypot(p01[0] - p00[0], p01[1] - p00[1])
        return max(0.1, (dx + dy) * 0.5)

    def _screen_point_from_view(self, vx: float, vy: float) -> Optional[Tuple[float, float]]:
        if not self.config:
            return None
        if any(abs(v) > 0.001 for v in (self.rot_x, self.rot_y, self.rot_z)):
            return None
        scale = min(self.width(), self.height()) * 0.36 * self.zoom
        if scale == 0:
            return None
        cx = self.width() / 2 + self.pan_x
        cy = self.height() / 2 + self.pan_y
        nx = (vx - cx) / scale
        ny = (cy - vy) / scale
        max_dim = max(self.config.screen_width, self.config.screen_height)
        sx = self.config.screen_width / 2 + (nx * max_dim / 2)
        sy = self.config.screen_height / 2 - (ny * max_dim / 2)
        return (sx, sy)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(22, 24, 32))

        if not self.config:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No configuration")
            return

        self._draw_background_panel(painter)

        if self.show_raster_pixels:
            self._draw_raster_pixels(painter)

        if self.show_grid or self.show_tiles:
            self._draw_tile_grid(painter)

        if self.show_pixel_coords:
            self._draw_pixel_grid_and_labels(painter)

        if self.show_tile_labels:
            self._draw_tile_labels(painter)

        if self.show_tile_pixel_axes:
            self._draw_tile_pixel_axes(painter)

        if self.show_depth_surface:
            self._draw_depth_surface(painter)

        if self.show_rt_surface:
            self._draw_rt_surface(painter)

        if self.show_clip:
            self._draw_clip_region(painter)

        if self.show_scissor:
            self._draw_scissor(painter)

        ordered = sorted(
            enumerate(self.triangles),
            key=lambda item: sum(self._transform(v[0], v[1], v[2])[2] for v in item[1].vertices) / 3,
        )
        for index, triangle in ordered:
            self._draw_triangle(painter, triangle, index)

        if self.show_msaa_samples:
            self._draw_msaa_samples(painter)

        self._draw_screen_border(painter)

        if self.show_axes:
            self._draw_axes(painter)

        self._draw_overlay(painter)

    def _draw_background_panel(self, painter: QPainter):
        sw = self.config.screen_width
        sh = self.config.screen_height
        polygon = self._projected_polygon([
            (0, 0, 0),
            (sw, 0, 0),
            (sw, sh, 0),
            (0, sh, 0),
        ])

        painter.setBrush(QBrush(QColor(55, 60, 76, 95)))
        painter.setPen(QPen(QColor(95, 105, 130), 1))
        painter.drawPolygon(polygon)

    def _draw_raster_pixels(self, painter: QPainter):
        if not self.rasterized_results:
            return

        if self._is_flat_top_view():
            if self._pixel_image_dirty:
                self._rebuild_pixel_image()
            draw_img = self._pixel_image_msaa if (self.config.msaa > 1 and self._pixel_image_msaa) else self._pixel_image
            if draw_img:
                painter.drawImage(self._screen_to_top_view_rect(), draw_img)
            return

        min_x, min_y, max_x, max_y = self._visible_screen_bounds()
        total_pixels = sum(len(result.covered_pixels) for result in self.rasterized_results)
        step = max(1, total_pixels // 18000)
        counter = 0

        if self.config.msaa > 1 and self.rasterizer:
            resolved = self.rasterizer.resolve_msaa(self.rasterized_results)
            for (px, py), (r, g, b) in resolved.items():
                if not (min_x <= px < max_x and min_y <= py < max_y):
                    continue
                counter += 1
                if counter % step != 0:
                    continue
                painter.setBrush(QBrush(QColor(r, g, b, 205)))
                painter.setPen(Qt.PenStyle.NoPen)
                self._draw_projected_rect(painter, px, py, 1, 1, 0)
            return

        for result in self.rasterized_results:
            color = result.triangle.color
            for (px, py), ratio in result.coverage_ratio.items():
                if not (min_x <= px < max_x and min_y <= py < max_y):
                    continue
                counter += 1
                if counter % step != 0:
                    continue
                painter.setBrush(QBrush(QColor(color[0], color[1], color[2], int(210 * ratio))))
                painter.setPen(Qt.PenStyle.NoPen)
                self._draw_projected_rect(painter, px, py, 1, 1, 0)

    def _draw_tile_grid(self, painter: QPainter):
        sw = self.config.screen_width
        sh = self.config.screen_height
        tw = self.config.tile_width
        th = self.config.tile_height

        painter.setPen(QPen(QColor(75, 82, 105), 1))
        for i in range(self.config.tile_count_x + 1):
            x = min(i * tw, sw)
            self._draw_projected_line(painter, (x, 0, 0), (x, sh, 0))
        for j in range(self.config.tile_count_y + 1):
            y = min(j * th, sh)
            self._draw_projected_line(painter, (0, y, 0), (sw, y, 0))

    def _draw_tile_labels(self, painter: QPainter):
        pixel_size = self._projected_pixel_size()
        if pixel_size * min(self.config.tile_width, self.config.tile_height) < 12:
            return

        tw = self.config.tile_width
        th = self.config.tile_height
        painter.setFont(QFont("Consolas", max(7, min(10, int(pixel_size * 2)))))
        painter.setPen(QPen(QColor(135, 140, 165)))
        fm = QFontMetrics(painter.font())

        for i in range(self.config.tile_count_x):
            for j in range(self.config.tile_count_y):
                sx, sy = self._project(i * tw + tw / 2, j * th + th / 2, 0)
                label = f"({i},{j})"
                painter.drawText(int(sx - fm.horizontalAdvance(label) / 2), int(sy + fm.height() / 3), label)

    def _draw_tile_pixel_axes(self, painter: QPainter):
        pixel_size = self._projected_pixel_size()
        if pixel_size * min(self.config.tile_width, self.config.tile_height) < 10:
            return

        sw = self.config.screen_width
        sh = self.config.screen_height
        tw = self.config.tile_width
        th = self.config.tile_height
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QPen(QColor(150, 155, 180)))

        for i in range(self.config.tile_count_x + 1):
            x = min(i * tw, sw)
            sx, sy = self._project(x, 0, 0)
            painter.drawText(int(sx - 10), int(sy - 5), str(x))
        for j in range(self.config.tile_count_y + 1):
            y = min(j * th, sh)
            sx, sy = self._project(0, y, 0)
            painter.drawText(int(sx - 32), int(sy + 4), str(y))

    def _draw_pixel_grid_and_labels(self, painter: QPainter):
        pixel_size = self._projected_pixel_size()
        if pixel_size < 4.0:
            return

        min_x, min_y, max_x, max_y = self._visible_screen_bounds()
        if not self._is_flat_top_view():
            max_lines = 260
            if (max_x - min_x) + (max_y - min_y) > max_lines:
                return

        painter.setPen(QPen(QColor(48, 52, 65), 1))
        for px in range(min_x, max_x + 1):
            self._draw_projected_line(painter, (px, min_y, 0), (px, max_y, 0))
        for py in range(min_y, max_y + 1):
            self._draw_projected_line(painter, (min_x, py, 0), (max_x, py, 0))

        if pixel_size < 14.0 or not self.rasterized_results:
            return

        painter.setFont(QFont("Consolas", max(6, min(9, int(pixel_size / 2.5)))))
        painter.setPen(QPen(QColor(115, 120, 145)))
        fm = QFontMetrics(painter.font())
        drawn = 0
        for result in self.rasterized_results:
            for px, py in result.covered_pixels:
                if drawn >= 800:
                    return
                if not (min_x <= px < max_x and min_y <= py < max_y):
                    continue
                label = f"{px},{py}"
                label_w = fm.horizontalAdvance(label)
                label_h = fm.height()
                if pixel_size <= label_w + 4 or pixel_size <= label_h + 2:
                    continue
                sx, sy = self._project(px + 0.5, py + 0.5, 0)
                painter.drawText(int(sx - label_w / 2), int(sy + label_h / 3), label)
                drawn += 1

    def _draw_depth_surface(self, painter: QPainter):
        w = self.config.depth_surface_width
        h = self.config.depth_surface_height
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(80, 150, 255), 2, Qt.PenStyle.DashLine))
        self._draw_projected_rect(painter, 0, 0, w, h, 0.006)
        sx, sy = self._project(0, h, 0.006)
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QPen(QColor(120, 180, 255)))
        painter.drawText(int(sx + 4), int(sy + 12), f"Depth Surf({w}x{h})")

    def _draw_rt_surface(self, painter: QPainter):
        w = self.config.rt_width
        h = self.config.rt_height
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(210, 110, 255), 2, Qt.PenStyle.DashLine))
        self._draw_projected_rect(painter, 0, 0, w, h, 0.008)
        sx, sy = self._project(0, h, 0.008)
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QPen(QColor(230, 150, 255)))
        painter.drawText(int(sx + 4), int(sy + 24), f"RT({w}x{h})")

    def _draw_clip_region(self, painter: QPainter):
        cx, cy, cw, ch = self.config.clip_region
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 200, 0), 2))
        self._draw_projected_rect(painter, cx, cy, cw, ch, 0.01)
        sx, sy = self._project(cx, cy, 0.01)
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QPen(QColor(255, 220, 60)))
        painter.drawText(int(sx + 4), int(sy - 4), f"Clip({cx},{cy},{cw},{ch})")

    def _draw_scissor(self, painter: QPainter):
        sx0, sy0, sw, sh = self.config.scissor
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 255, 200), 2))
        self._draw_projected_rect(painter, sx0, sy0, sw, sh, 0.015)
        sx, sy = self._project(sx0, sy0, 0.015)
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QPen(QColor(70, 255, 220)))
        painter.drawText(int(sx + 4), int(sy + 12), f"Scissor({sx0},{sy0},{sw},{sh})")

    def _draw_triangle(self, painter: QPainter, triangle: Triangle, index: int):
        color = QColor(triangle.color[0], triangle.color[1], triangle.color[2])
        points = [self._project(v[0], v[1], v[2]) for v in triangle.vertices]

        polygon = QPolygonF()
        for sx, sy in points:
            polygon.append(QPointF(sx, sy))

        painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 75)))
        painter.setPen(QPen(color.lighter(125), 2))
        painter.drawPolygon(polygon)

        for v in triangle.vertices:
            base = self._project(v[0], v[1], 0)
            tip = self._project(v[0], v[1], v[2])
            painter.setPen(QPen(QColor(180, 185, 205, 90), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(base[0]), int(base[1]), int(tip[0]), int(tip[1]))

        painter.setBrush(QBrush(color.lighter(125)))
        painter.setPen(QPen(QColor(245, 245, 245), 1))
        painter.setFont(QFont("Consolas", 8))
        for k, v in enumerate(triangle.vertices):
            sx, sy = self._project(v[0], v[1], v[2])
            painter.drawEllipse(int(sx - 5), int(sy - 5), 10, 10)
            if self.show_vertex_labels:
                painter.setPen(QPen(color.lighter(140)))
                painter.drawText(int(sx + 8), int(sy - 8), f"V{k}({v[0]:.0f},{v[1]:.0f},z={v[2]:.2f})")
                painter.setPen(QPen(QColor(245, 245, 245), 1))

        avg_sx = sum(p[0] for p in points) / 3
        avg_sy = sum(p[1] for p in points) / 3
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.setPen(QPen(color.lighter(140)))
        painter.drawText(int(avg_sx + 12), int(avg_sy - 12), f"T{index}")

    def _draw_msaa_samples(self, painter: QPainter):
        if not self.config:
            return
        msaa_positions = generate_msaa_sample_positions(self.config.msaa)
        self._draw_msaa_pattern_legend(painter, msaa_positions, self._selected_msaa_mask())

    def _draw_screen_border(self, painter: QPainter):
        sw = self.config.screen_width
        sh = self.config.screen_height
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(170, 175, 195), 2))
        self._draw_projected_rect(painter, 0, 0, sw, sh, 0.02)
        sx, sy = self._project(0, 0, 0.02)
        painter.setFont(QFont("Arial", 9))
        painter.setPen(QPen(QColor(210, 212, 225)))
        painter.drawText(int(sx), int(sy - 6), f"Screen {sw}x{sh}")

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

    def _selected_msaa_mask(self) -> Optional[int]:
        if not self.selected_msaa_pixel or not self.config:
            return None
        px, py = self.selected_msaa_pixel
        mask = 0
        best_depths = {}
        for result in self.rasterized_results:
            for sample_idx, depth in result.sample_depths.get((px, py), {}).items():
                if sample_idx not in best_depths or depth < best_depths[sample_idx]:
                    best_depths[sample_idx] = depth
                    mask |= (1 << sample_idx)
        return mask

    def _draw_msaa_pattern_legend(self, painter: QPainter, msaa_positions: list, selected_mask: Optional[int] = None):
        legend_size = 112
        margin = 12
        x0 = self.width() - legend_size - margin
        y0 = margin

        painter.setBrush(QBrush(QColor(20, 22, 28, 220)))
        painter.setPen(QPen(QColor(150, 160, 180), 1))
        painter.drawRect(x0, y0, legend_size, legend_size + 28)

        painter.setPen(QPen(QColor(235, 235, 235)))
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        title = f"{self.config.msaa}x MSAA samples"
        if self.selected_msaa_pixel:
            title = f"Pixel {self.selected_msaa_pixel} samples"
        painter.drawText(x0 + 8, y0 + 17, title)

        cell_x = x0 + 18
        cell_y = y0 + 30
        cell_size = 76
        painter.setBrush(QBrush(QColor(45, 48, 58)))
        painter.setPen(QPen(QColor(110, 120, 140), 1))
        painter.drawRect(cell_x, cell_y, cell_size, cell_size)

        for idx, (sx, sy) in enumerate(msaa_positions):
            px = cell_x + sx * cell_size
            py = cell_y + sy * cell_size
            if selected_mask is None:
                fill = QColor(255, 210, 90)
                outline = QColor(30, 30, 30)
                text_color = QColor(255, 255, 255)
            elif (selected_mask >> idx) & 1:
                fill = QColor(235, 45, 45)
                outline = QColor(255, 230, 230)
                text_color = QColor(255, 255, 255)
            else:
                fill = QColor(0, 0, 0)
                outline = QColor(180, 180, 180)
                text_color = QColor(220, 220, 220)
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(outline, 1))
            painter.drawEllipse(int(px - 5), int(py - 5), 10, 10)
            painter.setPen(QPen(text_color))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(int(px + 7), int(py - 5), str(idx))

        if selected_mask is not None:
            painter.setPen(QPen(QColor(220, 220, 225)))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(x0 + 8, y0 + legend_size + 21, f"mask=0b{selected_mask:0{self.config.msaa}b}")

    def _draw_overlay(self, painter: QPainter):
        mode = "Free drag" if self.free_rotate else "Fixed/buttons"
        total_pixels = sum(len(r.covered_pixels) for r in self.rasterized_results)
        painter.setPen(QPen(QColor(220, 220, 225)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(10, 20, f"Mode: {self.view_mode} | Rot XYZ: ({self.rot_x:.0f}, {self.rot_y:.0f}, {self.rot_z:.0f}) | Zoom: {self.zoom:.2f}")
        painter.drawText(10, 36, f"Input: {mode} | Raster pixels: {total_pixels} | MSAA: {self.config.msaa}x")

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
        elif event.button() == Qt.MouseButton.LeftButton:
            self._show_hover_info(event, select=True)

    def mouseMoveEvent(self, event):
        if self.free_rotate and self._last_pos and event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.pos().x() - self._last_pos.x()
            dy = event.pos().y() - self._last_pos.y()
            self.rotate_y(dx * 0.5)
            self.rotate_x(dy * 0.5)
            self._last_pos = event.pos()
        else:
            self._show_hover_info(event)

    def mouseReleaseEvent(self, event):
        self._last_pos = None

    def _show_hover_info(self, event, select: bool = False):
        screen_pos = self._screen_point_from_view(event.pos().x(), event.pos().y())
        if not screen_pos or not self.config:
            return
        sx, sy = screen_pos
        if 0 <= sx < self.config.screen_width and 0 <= sy < self.config.screen_height:
            tile_x = int(sx) // self.config.tile_width
            tile_y = int(sy) // self.config.tile_height
            if select:
                self.selected_msaa_pixel = (int(sx), int(sy))
                self.update()
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"Pixel: ({int(sx)}, {int(sy)})\nTile: ({tile_x}, {tile_y})"
            )

    def wheelEvent(self, event):
        mouse_pos = event.position()
        center_x = self.width() / 2 + self.pan_x
        center_y = self.height() / 2 + self.pan_y
        rel_x = mouse_pos.x() - center_x
        rel_y = mouse_pos.y() - center_y

        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        old_zoom = self.zoom
        self.zoom *= factor
        self.zoom = max(0.1, min(50.0, self.zoom))
        actual_factor = self.zoom / old_zoom if old_zoom else 1.0

        self.pan_x += rel_x * (1 - actual_factor)
        self.pan_y += rel_y * (1 - actual_factor)
        self.update()

    def reset_view(self):
        self.set_view_top()
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
        self._set_view("X-Y", 0.0, 0.0, 0.0)

    def set_view_back(self):
        self._set_view("X-Y Back", 0.0, 180.0, 0.0)

    def set_view_left(self):
        self._set_view("Y-Z Side", 0.0, 90.0, 0.0)

    def set_view_right(self):
        self._set_view("Y-Z Side", 0.0, -90.0, 0.0)

    def set_view_top(self):
        self._set_view("Top", 0.0, 0.0, 0.0)

    def set_view_bottom(self):
        self._set_view("Bottom", 180.0, 0.0, 0.0)

    def set_view_xz_side(self):
        self._set_view("X-Z Side", 90.0, 0.0, 0.0)

    def set_view_yz_side(self):
        self._set_view("Y-Z Side", 0.0, 90.0, 0.0)

    def set_view_perspective(self):
        self._set_view("Free 3D", 35.0, -45.0, 0.0)

    def toggle_tiles(self, show: bool):
        self.show_tiles = show
        self.update()

    def toggle_scissor(self, show: bool):
        self.show_scissor = show
        self.update()

    def toggle_clip(self, show: bool):
        self.show_clip = show
        self.update()

    def toggle_depth_surface(self, show: bool):
        self.show_depth_surface = show
        self.update()

    def toggle_rt_surface(self, show: bool):
        self.show_rt_surface = show
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
