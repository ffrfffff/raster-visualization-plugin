from typing import List, Tuple, Dict, Set
from ..models.config import RasterConfig
from ..models.triangle import Triangle, RasterizedTriangle
from ..utils.geometry import (
    point_in_triangle,
    interpolate_depth,
    get_triangle_bounds,
    generate_msaa_sample_positions,
)


class SoftwareRasterizer:
    """软件光栅化器

    实现基本的三角形光栅化算法，包括：
    - 扫描线光栅化
    - 深度插值
    - MSAA 支持
    """

    def __init__(self, config: RasterConfig):
        self.config = config

    def rasterize_triangle(self, triangle: Triangle) -> RasterizedTriangle:
        """光栅化单个三角形"""
        result = RasterizedTriangle(triangle=triangle)

        vertices = triangle.vertices
        v0 = (vertices[0][0], vertices[0][1])
        v1 = (vertices[1][0], vertices[1][1])
        v2 = (vertices[2][0], vertices[2][1])

        # 获取三角形边界框
        min_x, min_y, max_x, max_y = get_triangle_bounds(vertices)

        # 应用 scissor 和 clip region 限制
        clip_x, clip_y, clip_w, clip_h = self.config.clip_region
        scissor_x, scissor_y, scissor_w, scissor_h = self.config.scissor

        min_x = max(min_x, max(clip_x, scissor_x))
        min_y = max(min_y, max(clip_y, scissor_y))
        max_x = min(max_x, min(clip_x + clip_w, scissor_x + scissor_w))
        max_y = min(max_y, min(clip_y + clip_h, scissor_y + scissor_h))

        # 限制在屏幕范围内
        min_x = max(min_x, 0)
        min_y = max(min_y, 0)
        max_x = min(max_x, self.config.screen_width)
        max_y = min(max_y, self.config.screen_height)

        # MSAA 采样位置
        msaa_positions = generate_msaa_sample_positions(self.config.msaa)

        # 遍历边界框内的所有像素
        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                covered_samples = 0
                sample_depths = []

                for sx, sy in msaa_positions:
                    sample_x = x + sx
                    sample_y = y + sy

                    if point_in_triangle((sample_x, sample_y), v0, v1, v2):
                        covered_samples += 1
                        depth = interpolate_depth(
                            (sample_x, sample_y),
                            vertices[0], vertices[1], vertices[2]
                        )
                        sample_depths.append(depth)

                if covered_samples > 0:
                    result.covered_pixels.add((x, y))

                    # 平均深度
                    avg_depth = sum(sample_depths) / len(sample_depths)
                    result.depth_values[(x, y)] = avg_depth
                    result.msaa_samples[(x, y)] = sample_depths

        return result

    def rasterize_triangles(self, triangles: List[Triangle]) -> List[RasterizedTriangle]:
        """光栅化多个三角形"""
        return [self.rasterize_triangle(t) for t in triangles]

    def get_tile_coverage(self, rasterized_triangles: List[RasterizedTriangle]) -> Dict[Tuple[int, int], Set[int]]:
        """获取每个 tile 被哪些三角形覆盖

        返回: {(tile_x, tile_y): {triangle_indices}}
        """
        tile_coverage: Dict[Tuple[int, int], Set[int]] = {}

        for idx, result in enumerate(rasterized_triangles):
            for px, py in result.covered_pixels:
                tile_x = px // self.config.tile_width
                tile_y = py // self.config.tile_height
                key = (tile_x, tile_y)
                if key not in tile_coverage:
                    tile_coverage[key] = set()
                tile_coverage[key].add(idx)

        return tile_coverage

    def update_config(self, config: RasterConfig):
        """更新配置"""
        self.config = config