from dataclasses import dataclass, field
from typing import Tuple
from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class RasterConfig:
    """光栅化配置参数"""
    msaa: int = 1
    screen_width: int = 800
    screen_height: int = 600
    depth_surface_width: int = 800
    depth_surface_height: int = 600
    clip_region: Tuple[int, int, int, int] = (0, 0, 800, 600)
    rt_width: int = 800
    rt_height: int = 600
    scissor: Tuple[int, int, int, int] = (0, 0, 800, 600)
    tile_width: int = 16
    tile_height: int = 16

    @property
    def tile_count_x(self) -> int:
        if self.tile_width <= 0:
            return 0
        return (self.screen_width + self.tile_width - 1) // self.tile_width

    @property
    def tile_count_y(self) -> int:
        if self.tile_height <= 0:
            return 0
        return (self.screen_height + self.tile_height - 1) // self.tile_height

    @property
    def msaa_levels(self) -> list:
        return [1, 2, 4, 8, 16]


class RasterConfigModel(QObject):
    """可观察的配置模型，支持信号通知"""
    config_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._config = RasterConfig()

    @property
    def config(self) -> RasterConfig:
        return self._config

    def set_config(self, config: RasterConfig):
        self._config = config
        self.config_changed.emit()

    def update_config(
        self,
        msaa: int,
        screen_width: int,
        screen_height: int,
        depth_surface_width: int,
        depth_surface_height: int,
        rt_width: int,
        rt_height: int,
        clip_region: Tuple[int, int, int, int],
        scissor: Tuple[int, int, int, int],
        tile_width: int,
        tile_height: int,
    ):
        self._config.msaa = msaa
        self._config.screen_width = screen_width
        self._config.screen_height = screen_height
        self._config.depth_surface_width = depth_surface_width
        self._config.depth_surface_height = depth_surface_height
        self._config.rt_width = rt_width
        self._config.rt_height = rt_height
        self._config.clip_region = clip_region
        self._config.scissor = scissor
        self._config.tile_width = tile_width
        self._config.tile_height = tile_height
        self.config_changed.emit()

    def update_msaa(self, value: int):
        self._config.msaa = value
        self.config_changed.emit()

    def update_screen_size(self, width: int, height: int):
        self._config.screen_width = width
        self._config.screen_height = height
        self.config_changed.emit()

    def update_depth_surface_size(self, width: int, height: int):
        self._config.depth_surface_width = width
        self._config.depth_surface_height = height
        self.config_changed.emit()

    def update_clip_region(self, x: int, y: int, w: int, h: int):
        self._config.clip_region = (x, y, w, h)
        self.config_changed.emit()

    def update_rt_size(self, width: int, height: int):
        self._config.rt_width = width
        self._config.rt_height = height
        self.config_changed.emit()

    def update_scissor(self, x: int, y: int, w: int, h: int):
        self._config.scissor = (x, y, w, h)
        self.config_changed.emit()

    def update_tile_size(self, width: int, height: int):
        self._config.tile_width = width
        self._config.tile_height = height
        self.config_changed.emit()