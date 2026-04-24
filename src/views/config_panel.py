from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QSpinBox, QComboBox, QLabel, QPushButton
)
from PyQt6.QtCore import pyqtSignal
from ..models.config import RasterConfigModel


class ConfigPanel(QWidget):
    """配置参数面板"""

    config_changed = pyqtSignal()

    def __init__(self, config_model: RasterConfigModel):
        super().__init__()
        self.config_model = config_model
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # MSAA 配置
        msaa_group = QGroupBox("MSAA")
        msaa_layout = QHBoxLayout(msaa_group)
        self.msaa_combo = QComboBox()
        self.msaa_combo.addItems(["1x", "2x", "4x", "8x", "16x"])
        self.msaa_combo.setCurrentIndex(0)
        msaa_layout.addWidget(QLabel("Samples:"))
        msaa_layout.addWidget(self.msaa_combo)
        layout.addWidget(msaa_group)

        # Screen Size
        screen_group = QGroupBox("Screen Size")
        screen_layout = QHBoxLayout(screen_group)
        self.screen_width_spin = QSpinBox()
        self.screen_width_spin.setRange(1, 4096)
        self.screen_width_spin.setValue(800)
        self.screen_height_spin = QSpinBox()
        self.screen_height_spin.setRange(1, 4096)
        self.screen_height_spin.setValue(600)
        screen_layout.addWidget(QLabel("W:"))
        screen_layout.addWidget(self.screen_width_spin)
        screen_layout.addWidget(QLabel("H:"))
        screen_layout.addWidget(self.screen_height_spin)
        layout.addWidget(screen_group)

        # Depth Surface Size
        depth_group = QGroupBox("Depth Surface Size")
        depth_layout = QHBoxLayout(depth_group)
        self.depth_width_spin = QSpinBox()
        self.depth_width_spin.setRange(1, 4096)
        self.depth_width_spin.setValue(800)
        self.depth_height_spin = QSpinBox()
        self.depth_height_spin.setRange(1, 4096)
        self.depth_height_spin.setValue(600)
        depth_layout.addWidget(QLabel("W:"))
        depth_layout.addWidget(self.depth_width_spin)
        depth_layout.addWidget(QLabel("H:"))
        depth_layout.addWidget(self.depth_height_spin)
        layout.addWidget(depth_group)

        # RT Size
        rt_group = QGroupBox("Render Target Size")
        rt_layout = QHBoxLayout(rt_group)
        self.rt_width_spin = QSpinBox()
        self.rt_width_spin.setRange(1, 4096)
        self.rt_width_spin.setValue(800)
        self.rt_height_spin = QSpinBox()
        self.rt_height_spin.setRange(1, 4096)
        self.rt_height_spin.setValue(600)
        rt_layout.addWidget(QLabel("W:"))
        rt_layout.addWidget(self.rt_width_spin)
        rt_layout.addWidget(QLabel("H:"))
        rt_layout.addWidget(self.rt_height_spin)
        layout.addWidget(rt_group)

        # Clip Region
        clip_group = QGroupBox("Clip Region")
        clip_layout = QVBoxLayout(clip_group)
        clip_row1 = QHBoxLayout()
        self.clip_x_spin = QSpinBox()
        self.clip_x_spin.setRange(0, 4096)
        self.clip_x_spin.setValue(0)
        self.clip_y_spin = QSpinBox()
        self.clip_y_spin.setRange(0, 4096)
        self.clip_y_spin.setValue(0)
        clip_row1.addWidget(QLabel("X:"))
        clip_row1.addWidget(self.clip_x_spin)
        clip_row1.addWidget(QLabel("Y:"))
        clip_row1.addWidget(self.clip_y_spin)
        clip_row2 = QHBoxLayout()
        self.clip_w_spin = QSpinBox()
        self.clip_w_spin.setRange(1, 4096)
        self.clip_w_spin.setValue(800)
        self.clip_h_spin = QSpinBox()
        self.clip_h_spin.setRange(1, 4096)
        self.clip_h_spin.setValue(600)
        clip_row2.addWidget(QLabel("W:"))
        clip_row2.addWidget(self.clip_w_spin)
        clip_row2.addWidget(QLabel("H:"))
        clip_row2.addWidget(self.clip_h_spin)
        clip_layout.addLayout(clip_row1)
        clip_layout.addLayout(clip_row2)
        layout.addWidget(clip_group)

        # Scissor
        scissor_group = QGroupBox("Scissor")
        scissor_layout = QVBoxLayout(scissor_group)
        scissor_row1 = QHBoxLayout()
        self.scissor_x_spin = QSpinBox()
        self.scissor_x_spin.setRange(0, 4096)
        self.scissor_x_spin.setValue(0)
        self.scissor_y_spin = QSpinBox()
        self.scissor_y_spin.setRange(0, 4096)
        self.scissor_y_spin.setValue(0)
        scissor_row1.addWidget(QLabel("X:"))
        scissor_row1.addWidget(self.scissor_x_spin)
        scissor_row1.addWidget(QLabel("Y:"))
        scissor_row1.addWidget(self.scissor_y_spin)
        scissor_row2 = QHBoxLayout()
        self.scissor_w_spin = QSpinBox()
        self.scissor_w_spin.setRange(1, 4096)
        self.scissor_w_spin.setValue(800)
        self.scissor_h_spin = QSpinBox()
        self.scissor_h_spin.setRange(1, 4096)
        self.scissor_h_spin.setValue(600)
        scissor_row2.addWidget(QLabel("W:"))
        scissor_row2.addWidget(self.scissor_w_spin)
        scissor_row2.addWidget(QLabel("H:"))
        scissor_row2.addWidget(self.scissor_h_spin)
        scissor_layout.addLayout(scissor_row1)
        scissor_layout.addLayout(scissor_row2)
        layout.addWidget(scissor_group)

        # Tile Size
        tile_group = QGroupBox("Tile Size")
        tile_layout = QHBoxLayout(tile_group)
        self.tile_width_spin = QSpinBox()
        self.tile_width_spin.setRange(1, 256)
        self.tile_width_spin.setValue(16)
        self.tile_height_spin = QSpinBox()
        self.tile_height_spin.setRange(1, 256)
        self.tile_height_spin.setValue(16)
        tile_layout.addWidget(QLabel("W:"))
        tile_layout.addWidget(self.tile_width_spin)
        tile_layout.addWidget(QLabel("H:"))
        tile_layout.addWidget(self.tile_height_spin)
        layout.addWidget(tile_group)

        # 应用按钮
        self.apply_btn = QPushButton("Apply Changes")
        layout.addWidget(self.apply_btn)

        layout.addStretch()

        self.setMaximumWidth(250)

    def _connect_signals(self):
        self.apply_btn.clicked.connect(self._apply_config)

    def _apply_config(self):
        msaa_values = [1, 2, 4, 8, 16]
        msaa = msaa_values[self.msaa_combo.currentIndex()]

        self.config_model.update_config(
            msaa=msaa,
            screen_width=self.screen_width_spin.value(),
            screen_height=self.screen_height_spin.value(),
            depth_surface_width=self.depth_width_spin.value(),
            depth_surface_height=self.depth_height_spin.value(),
            rt_width=self.rt_width_spin.value(),
            rt_height=self.rt_height_spin.value(),
            clip_region=(
                self.clip_x_spin.value(),
                self.clip_y_spin.value(),
                self.clip_w_spin.value(),
                self.clip_h_spin.value()
            ),
            scissor=(
                self.scissor_x_spin.value(),
                self.scissor_y_spin.value(),
                self.scissor_w_spin.value(),
                self.scissor_h_spin.value()
            ),
            tile_width=self.tile_width_spin.value(),
            tile_height=self.tile_height_spin.value(),
        )

    def sync_from_model(self):
        """从模型同步配置到 UI"""
        config = self.config_model.config

        msaa_values = [1, 2, 4, 8, 16]
        idx = msaa_values.index(config.msaa) if config.msaa in msaa_values else 0
        self.msaa_combo.setCurrentIndex(idx)

        self.screen_width_spin.setValue(config.screen_width)
        self.screen_height_spin.setValue(config.screen_height)
        self.depth_width_spin.setValue(config.depth_surface_width)
        self.depth_height_spin.setValue(config.depth_surface_height)
        self.rt_width_spin.setValue(config.rt_width)
        self.rt_height_spin.setValue(config.rt_height)
        self.clip_x_spin.setValue(config.clip_region[0])
        self.clip_y_spin.setValue(config.clip_region[1])
        self.clip_w_spin.setValue(config.clip_region[2])
        self.clip_h_spin.setValue(config.clip_region[3])
        self.scissor_x_spin.setValue(config.scissor[0])
        self.scissor_y_spin.setValue(config.scissor[1])
        self.scissor_w_spin.setValue(config.scissor[2])
        self.scissor_h_spin.setValue(config.scissor[3])
        self.tile_width_spin.setValue(config.tile_width)
        self.tile_height_spin.setValue(config.tile_height)