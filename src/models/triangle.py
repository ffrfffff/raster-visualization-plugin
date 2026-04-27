from dataclasses import dataclass, field
from typing import List, Tuple, Set, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal
import random


@dataclass
class Triangle:
    """三角形数据结构

    vertices: 三个顶点坐标 (x, y, z)，屏幕像素空间，z ∈ [-1, 1]
    color: RGB 颜色值
    """
    vertices: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (100.0, 100.0, 0.0),
        (200.0, 100.0, 0.5),
        (150.0, 200.0, -0.3)
    ])
    color: Tuple[int, int, int] = (255, 0, 0)

    def __post_init__(self):
        if len(self.vertices) != 3:
            raise ValueError("Triangle must have exactly 3 vertices")

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """返回三角形边界框 (min_x, min_y, max_x, max_y)"""
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def depth_range(self) -> Tuple[float, float]:
        """返回深度范围 (min_z, max_z)"""
        zs = [v[2] for v in self.vertices]
        return (min(zs), max(zs))


@dataclass
class RasterizedTriangle:
    """光栅化后的三角形结果

    MSAA 详解:
    - coverage_mask: 每个 pixel 的 sample 覆盖掩码，bit i = 1 表示 sample i 被覆盖
    - sample_depths: 每个 pixel 的每个 sample 的深度值 (仅被覆盖的 sample)
    - pixel_center_depth: 像素中心插值的深度 (Pixel Shader 执行位置)
    - coverage_ratio: 被覆盖 sample 数 / 总 sample 数，用于 resolve
    """
    triangle: Triangle
    covered_pixels: Set[Tuple[int, int]] = field(default_factory=set)
    depth_values: Dict[Tuple[int, int], float] = field(default_factory=dict)
    msaa_samples: Dict[Tuple[int, int], List[float]] = field(default_factory=dict)
    coverage_mask: Dict[Tuple[int, int], int] = field(default_factory=dict)
    sample_depths: Dict[Tuple[int, int], Dict[int, float]] = field(default_factory=dict)
    pixel_center_depth: Dict[Tuple[int, int], float] = field(default_factory=dict)
    coverage_ratio: Dict[Tuple[int, int], float] = field(default_factory=dict)


class TriangleListModel(QObject):
    """三角形列表模型，支持信号通知"""
    triangles_changed = pyqtSignal()
    triangle_added = pyqtSignal(int)
    triangle_removed = pyqtSignal(int)
    triangle_updated = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._triangles: List[Triangle] = []

    @property
    def triangles(self) -> List[Triangle]:
        return self._triangles

    def add_triangle(self, triangle: Optional[Triangle] = None) -> int:
        if triangle is None:
            colors = [
                (255, 0, 0), (0, 255, 0), (0, 0, 255),
                (255, 255, 0), (255, 0, 255), (0, 255, 255),
            ]
            offset = len(self._triangles) * 50
            triangle = Triangle(
                vertices=[
                    (100 + offset, 100 + offset, 0.0),
                    (200 + offset, 100 + offset, 0.3),
                    (150 + offset, 200 + offset, -0.2)
                ],
                color=colors[len(self._triangles) % len(colors)]
            )
        self._triangles.append(triangle)
        idx = len(self._triangles) - 1
        self.triangle_added.emit(idx)
        self.triangles_changed.emit()
        return idx

    def remove_triangle(self, index: int):
        if 0 <= index < len(self._triangles):
            self._triangles.pop(index)
            self.triangle_removed.emit(index)
            self.triangles_changed.emit()

    def update_triangle(self, index: int, triangle: Triangle):
        if 0 <= index < len(self._triangles):
            self._triangles[index] = triangle
            self.triangle_updated.emit(index)
            self.triangles_changed.emit()

    def set_triangles(self, triangles: List[Triangle]):
        self._triangles = list(triangles)
        self.triangles_changed.emit()

    def clear(self):
        self._triangles.clear()
        self.triangles_changed.emit()

    def get_triangle(self, index: int) -> Optional[Triangle]:
        if 0 <= index < len(self._triangles):
            return self._triangles[index]
        return None