from typing import List, Tuple, Dict, Set
import math
from ..models.config import MAX_RASTERIZED_BBOX_PIXELS, RasterConfig
from ..models.triangle import Triangle, RasterizedTriangle
from ..utils.geometry import (
    point_in_triangle,
    interpolate_depth,
    get_triangle_bounds,
    generate_msaa_sample_positions,
)


class SoftwareRasterizer:
    """软件光栅化器

    实现三角形光栅化算法，正确模拟 MSAA 行为：

    MSAA 核心规则:
    1. Coverage Test: 对每个 pixel 的每个 sub-sample 做三角形覆盖测试
    2. Depth Test: 对每个通过覆盖测试的 sample 做深度测试 (per-sample)
    3. Pixel Shader: 每个 pixel 只执行一次 (在像素中心插值属性)
    4. Sample Mask: 覆盖测试 + 深度测试通过的 sample 组成 coverage mask
    5. Resolve: 最终 pixel 颜色 = sum(sample_color * coverage) / msaa_count
    """

    def __init__(self, config: RasterConfig):
        self.config = config

    def rasterize_triangle(self, triangle: Triangle) -> RasterizedTriangle:
        """光栅化单个三角形，正确模拟 MSAA"""
        result = RasterizedTriangle(triangle=triangle)

        if any(not math.isfinite(component) for vertex in triangle.vertices for component in vertex):
            return result

        source_vertices = triangle.vertices
        coord_offset = self.config.coordinate_offset
        vertices = [
            (vertex[0] - coord_offset, vertex[1] - coord_offset, vertex[2])
            for vertex in source_vertices
        ]
        v0 = (vertices[0][0], vertices[0][1])
        v1 = (vertices[1][0], vertices[1][1])
        v2 = (vertices[2][0], vertices[2][1])

        min_x, min_y, max_x, max_y = get_triangle_bounds(vertices)

        # 应用 scissor 和 clip region 限制
        clip_x, clip_y, clip_w, clip_h = self.config.clip_region
        scissor_x, scissor_y, scissor_w, scissor_h = self.config.scissor

        min_x = max(min_x, max(clip_x, scissor_x))
        min_y = max(min_y, max(clip_y, scissor_y))
        max_x = min(max_x, min(clip_x + clip_w, scissor_x + scissor_w))
        max_y = min(max_y, min(clip_y + clip_h, scissor_y + scissor_h))

        screen_min_x = self.config.screen_min_x
        screen_min_y = self.config.screen_min_y
        screen_max_x = self.config.screen_max_x
        screen_max_y = self.config.screen_max_y

        min_x = max(min_x, screen_min_x)
        min_y = max(min_y, screen_min_y)
        max_x = min(max_x, screen_max_x)
        max_y = min(max_y, screen_max_y)

        if max_x <= min_x or max_y <= min_y:
            return result

        bbox_pixels = (max_x - min_x) * (max_y - min_y)
        if bbox_pixels > MAX_RASTERIZED_BBOX_PIXELS:
            return result

        msaa_positions = generate_msaa_sample_positions(self.config.msaa)
        msaa_count = self.config.msaa

        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                # --- Pixel Shader 执行位置: 像素中心 ---
                pixel_center = (x + 0.5, y + 0.5)
                pixel_center_depth = interpolate_depth(
                    pixel_center, vertices[0], vertices[1], vertices[2]
                )

                # --- MSAA Coverage Test: 逐 sample 检测覆盖 ---
                coverage = 0  # bitmask
                covered_sample_depths: Dict[int, float] = {}

                for sample_idx, (sx, sy) in enumerate(msaa_positions):
                    sample_pos = (x + sx, y + sy)

                    if point_in_triangle(sample_pos, v0, v1, v2):
                        coverage |= (1 << sample_idx)
                        sample_depth = interpolate_depth(
                            sample_pos, vertices[0], vertices[1], vertices[2]
                        )
                        covered_sample_depths[sample_idx] = sample_depth

                # 任何 sample 被覆盖，该 pixel 就被处理
                if coverage > 0:
                    result.covered_pixels.add((x, y))
                    result.coverage_mask[(x, y)] = coverage
                    result.sample_depths[(x, y)] = covered_sample_depths
                    result.pixel_center_depth[(x, y)] = pixel_center_depth

                    # 兼容旧字段
                    sample_depths_list = list(covered_sample_depths.values())
                    result.msaa_samples[(x, y)] = sample_depths_list
                    result.depth_values[(x, y)] = sum(sample_depths_list) / len(sample_depths_list)
                    result.coverage_ratio[(x, y)] = bin(coverage).count('1') / msaa_count

        return result

    def rasterize_triangles(self, triangles: List[Triangle]) -> List[RasterizedTriangle]:
        """光栅化多个三角形"""
        return [self.rasterize_triangle(t) for t in triangles]

    def get_tile_coverage(self, rasterized_triangles: List[RasterizedTriangle]) -> Dict[Tuple[int, int], Set[int]]:
        """获取每个 tile 被哪些三角形覆盖"""
        tile_coverage: Dict[Tuple[int, int], Set[int]] = {}

        for idx, result in enumerate(rasterized_triangles):
            if self.config.tile_width <= 0 or self.config.tile_height <= 0:
                continue
            for px, py in result.covered_pixels:
                tile_x = (px - self.config.screen_origin) // self.config.tile_width
                tile_y = (py - self.config.screen_origin) // self.config.tile_height
                key = (tile_x, tile_y)
                if key not in tile_coverage:
                    tile_coverage[key] = set()
                tile_coverage[key].add(idx)

        return tile_coverage

    def resolve_msaa(self, rasterized_triangles: List[RasterizedTriangle]) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
        """MSAA Resolve: 将多个三角形的结果合并到最终像素颜色

        模拟深度测试 + coverage merge:
        - 每个 sample 保留深度最大的三角形颜色
        - Resolve 时按 coverage 比例混合
        """
        # 每个 sample 的最终颜色 (triangle_index, depth)
        sample_results: Dict[Tuple[int, int, int], Tuple[int, float]] = {}  # (px, py, sample_idx) -> (tri_idx, depth)
        pixel_triangles: Dict[Tuple[int, int], Set[int]] = {}  # (px, py) -> involved triangles

        for tri_idx, result in enumerate(rasterized_triangles):
            for (px, py), sample_depths in result.sample_depths.items():
                if (px, py) not in pixel_triangles:
                    pixel_triangles[(px, py)] = set()
                pixel_triangles[(px, py)].add(tri_idx)

                for sample_idx, depth in sample_depths.items():
                    key = (px, py, sample_idx)
                    if key not in sample_results or depth > sample_results[key][1]:
                        sample_results[key] = (tri_idx, depth)

        # Resolve
        msaa_count = self.config.msaa
        resolved: Dict[Tuple[int, int], Tuple[int, int, int]] = {}

        for (px, py), tri_indices in pixel_triangles.items():
            r_total, g_total, b_total = 0.0, 0.0, 0.0

            for sample_idx in range(msaa_count):
                key = (px, py, sample_idx)
                if key in sample_results:
                    tri_idx = sample_results[key][0]
                    color = rasterized_triangles[tri_idx].triangle.color
                    r_total += color[0]
                    g_total += color[1]
                    b_total += color[2]

            covered_samples = sum(1 for si in range(msaa_count) if (px, py, si) in sample_results)
            if covered_samples > 0:
                r = int(r_total / msaa_count)
                g = int(g_total / msaa_count)
                b = int(b_total / msaa_count)
                resolved[(px, py)] = (min(255, r), min(255, g), min(255, b))

        return resolved

    def update_config(self, config: RasterConfig):
        self.config = config