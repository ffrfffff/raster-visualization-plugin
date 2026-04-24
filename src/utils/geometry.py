from typing import Tuple
import numpy as np


def edge_function(v0: Tuple[float, float], v1: Tuple[float, float], p: Tuple[float, float]) -> float:
    """计算点 p 相对于边 v0->v1 的有向面积

    返回值 > 0 表示点在边的左侧（三角形内部，如果顶点按逆时针排列）
    """
    return (p[0] - v0[0]) * (v1[1] - v0[1]) - (p[1] - v0[1]) * (v1[0] - v0[0])


def point_in_triangle(p: Tuple[float, float],
                      v0: Tuple[float, float],
                      v1: Tuple[float, float],
                      v2: Tuple[float, float]) -> bool:
    """判断点 p 是否在三角形 v0, v1, v2 内部"""
    d0 = edge_function(v0, v1, p)
    d1 = edge_function(v1, v2, p)
    d2 = edge_function(v2, v0, p)

    has_same_sign = (d0 >= 0 and d1 >= 0 and d2 >= 0) or (d0 <= 0 and d1 <= 0 and d2 <= 0)
    return has_same_sign


def barycentric_coordinates(p: Tuple[float, float],
                            v0: Tuple[float, float],
                            v1: Tuple[float, float],
                            v2: Tuple[float, float]) -> Tuple[float, float, float]:
    """计算点 p 在三角形 v0, v1, v2 中的重心坐标"""
    area = edge_function(v0, v1, v2)
    if abs(area) < 1e-10:
        return (0.0, 0.0, 0.0)

    w0 = edge_function(v1, v2, p) / area
    w1 = edge_function(v2, v0, p) / area
    w2 = edge_function(v0, v1, p) / area

    return (w0, w1, w2)


def interpolate_depth(p: Tuple[float, float],
                      v0: Tuple[float, float, float],
                      v1: Tuple[float, float, float],
                      v2: Tuple[float, float, float]) -> float:
    """使用重心坐标插值计算点 p 的深度值"""
    bary = barycentric_coordinates(p, (v0[0], v0[1]), (v1[0], v1[1]), (v2[0], v2[1]))
    return bary[0] * v0[2] + bary[1] * v1[2] + bary[2] * v2[2]


def get_triangle_bounds(vertices: list) -> Tuple[int, int, int, int]:
    """获取三角形在屏幕空间的整数边界框"""
    xs = [int(v[0]) for v in vertices]
    ys = [int(v[1]) for v in vertices]
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def generate_msaa_sample_positions(msaa_level: int) -> list:
    """生成 MSAA 采样点位置（像素内的相对位置）

    返回列表中的每个元素是 (x_offset, y_offset)，范围 [0, 1]
    使用标准旋转网格 (Rotated Grid) 采样模式
    """
    if msaa_level == 1:
        return [(0.5, 0.5)]

    if msaa_level == 2:
        # 2x MSAA: 对角线排列
        return [(0.25, 0.25), (0.75, 0.75)]

    if msaa_level == 4:
        # 4x MSAA: 标准旋转网格 (Rotated Grid)
        # 这是 D3D/OpenGL 标准的 4x MSAA 采样模式
        return [
            (0.125, 0.625),  # Sample 0
            (0.375, 0.125),  # Sample 1
            (0.625, 0.875),  # Sample 2
            (0.875, 0.375),  # Sample 3
        ]

    if msaa_level == 8:
        # 8x MSAA: 标准旋转网格
        return [
            (0.0625, 0.5625),  # Sample 0
            (0.1875, 0.0625),  # Sample 1
            (0.3125, 0.8125),  # Sample 2
            (0.4375, 0.3125),  # Sample 3
            (0.5625, 0.6875),  # Sample 4
            (0.6875, 0.1875),  # Sample 5
            (0.8125, 0.9375),  # Sample 6
            (0.9375, 0.4375),  # Sample 7
        ]

    if msaa_level == 16:
        # 16x MSAA: 标准旋转网格
        return [
            (0.03125, 0.53125),
            (0.09375, 0.03125),
            (0.15625, 0.78125),
            (0.21875, 0.28125),
            (0.28125, 0.65625),
            (0.34375, 0.15625),
            (0.40625, 0.90625),
            (0.46875, 0.40625),
            (0.53125, 0.59375),
            (0.59375, 0.09375),
            (0.65625, 0.84375),
            (0.71875, 0.34375),
            (0.78125, 0.71875),
            (0.84375, 0.21875),
            (0.90625, 0.96875),
            (0.96875, 0.46875),
        ]

    return [(0.5, 0.5)]