import json
from typing import Any, List, Tuple

from ..models.config import DISPLAY_COORD_MAX, DISPLAY_COORD_MIN, RasterConfig
from ..models.triangle import Triangle


def load_scene(path: str) -> Tuple[RasterConfig, List[Triangle]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ValueError(f"Failed to read scene file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc

    if not isinstance(data, dict):
        raise ValueError("Scene root must be a JSON object")

    config_data = _require_dict(data, "config")
    triangles_data = _require_list(data, "triangles")

    screen_width, screen_height = _parse_size(config_data, "screen_size")
    depth_width, depth_height = _parse_size(config_data, "depth_surface_size")
    rt_width, rt_height = _parse_size(config_data, "render_target_size")
    tile_width, tile_height = _parse_size(config_data, "tile_size")

    config = RasterConfig(
        msaa=_parse_msaa(config_data),
        screen_width=screen_width,
        screen_height=screen_height,
        screen_offset=_parse_optional_int(config_data, "screen_offset", 0),
        subtract_screen_offset=_parse_optional_bool(config_data, "subtract_screen_offset", False),
        depth_surface_width=depth_width,
        depth_surface_height=depth_height,
        clip_region=_parse_region(config_data, "clip_region"),
        rt_width=rt_width,
        rt_height=rt_height,
        scissor=_parse_region(config_data, "scissor"),
        tile_width=tile_width,
        tile_height=tile_height,
    )
    triangles = [_parse_triangle(item, i) for i, item in enumerate(triangles_data)]
    return config, triangles


def _require_dict(data: dict, key: str) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"'{key}' must be an object")
    return value


def _require_list(data: dict, key: str) -> list:
    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f"'{key}' must be an array")
    return value


def _parse_msaa(config: dict) -> int:
    value = config.get("msaa")
    if not isinstance(value, int) or isinstance(value, bool) or value not in (1, 2, 4, 8, 16):
        raise ValueError("config.msaa must be one of 1, 2, 4, 8, 16")
    return value


def _parse_optional_int(config: dict, key: str, default: int) -> int:
    value = config.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"config.{key} must be an integer")
    if value < DISPLAY_COORD_MIN or value > DISPLAY_COORD_MAX:
        raise ValueError(f"config.{key} must be in [{DISPLAY_COORD_MIN}, {DISPLAY_COORD_MAX}]")
    return value


def _parse_optional_bool(config: dict, key: str, default: bool) -> bool:
    value = config.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"config.{key} must be a boolean")
    return value


def _parse_size(config: dict, key: str) -> Tuple[int, int]:
    values = config.get(key)
    if not _is_int_array(values, 2):
        raise ValueError(f"config.{key} must be [width, height]")
    width, height = int(values[0]), int(values[1])
    if width <= 0 or height <= 0:
        raise ValueError(f"config.{key} width and height must be positive")
    if width > DISPLAY_COORD_MAX - DISPLAY_COORD_MIN or height > DISPLAY_COORD_MAX - DISPLAY_COORD_MIN:
        raise ValueError(f"config.{key} width and height must be <= {DISPLAY_COORD_MAX - DISPLAY_COORD_MIN}")
    return width, height


def _parse_region(config: dict, key: str) -> Tuple[int, int, int, int]:
    values = config.get(key)
    if not _is_int_array(values, 4):
        raise ValueError(f"config.{key} must be [x, y, width, height]")
    x, y, width, height = (int(v) for v in values)
    if x < DISPLAY_COORD_MIN or x > DISPLAY_COORD_MAX or y < DISPLAY_COORD_MIN or y > DISPLAY_COORD_MAX:
        raise ValueError(f"config.{key} x and y must be in [{DISPLAY_COORD_MIN}, {DISPLAY_COORD_MAX}]")
    if width <= 0 or height <= 0:
        raise ValueError(f"config.{key} width and height must be positive")
    if width > DISPLAY_COORD_MAX - DISPLAY_COORD_MIN or height > DISPLAY_COORD_MAX - DISPLAY_COORD_MIN:
        raise ValueError(f"config.{key} width and height must be <= {DISPLAY_COORD_MAX - DISPLAY_COORD_MIN}")
    return x, y, width, height


def _parse_triangle(data: Any, index: int) -> Triangle:
    if not isinstance(data, dict):
        raise ValueError(f"triangles[{index}] must be an object")

    vertices_data = data.get("vertices")
    if not isinstance(vertices_data, list) or len(vertices_data) != 3:
        raise ValueError(f"triangles[{index}].vertices must contain exactly 3 vertices")

    vertices = [_parse_vertex(vertex, index, vertex_index) for vertex_index, vertex in enumerate(vertices_data)]
    color = _parse_color(data.get("color"), index) if "color" in data else _default_color(index)
    return Triangle(vertices=vertices, color=color)


def _parse_vertex(data: Any, triangle_index: int, vertex_index: int) -> Tuple[float, float, float]:
    if not _is_number_array(data, 3):
        raise ValueError(f"triangles[{triangle_index}].vertices[{vertex_index}] must be [x, y, z]")
    x, y, z = float(data[0]), float(data[1]), float(data[2])
    if z < -1.0 or z > 1.0:
        raise ValueError(f"triangles[{triangle_index}].vertices[{vertex_index}].z must be in [-1, 1]")
    return x, y, z


def _parse_color(data: Any, triangle_index: int) -> Tuple[int, int, int]:
    if not _is_int_array(data, 3):
        raise ValueError(f"triangles[{triangle_index}].color must be [r, g, b]")
    r, g, b = (int(v) for v in data)
    if any(v < 0 or v > 255 for v in (r, g, b)):
        raise ValueError(f"triangles[{triangle_index}].color values must be in [0, 255]")
    return r, g, b


def _default_color(index: int) -> Tuple[int, int, int]:
    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (255, 0, 255), (0, 255, 255),
    ]
    return colors[index % len(colors)]


def _is_int_array(value: Any, length: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == length
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    )


def _is_number_array(value: Any, length: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == length
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
    )
