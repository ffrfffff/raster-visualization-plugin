from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QComboBox, QLabel, QDoubleSpinBox,
    QDialog, QFormLayout, QDialogButtonBox, QLineEdit,
    QStyledItemDelegate, QAbstractItemView
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor
from typing import List, Optional
from ..models.triangle import Triangle
from ..utils.fixed_point import (
    format_q16_8, parse_q16_8, format_fp32, parse_fp32,
    float_to_q16_8, q16_8_to_float,
)


class VertexEditDialog(QDialog):
    """顶点编辑对话框，支持 dec/bin/hex 格式"""

    def __init__(self, vertex: tuple, vertex_index: int, fmt: str = 'dec', parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Vertex {vertex_index}")
        self.fmt = fmt
        self._vertex = vertex

        layout = QFormLayout(self)

        self.x_edit = QLineEdit(format_q16_8(vertex[0], fmt))
        self.y_edit = QLineEdit(format_q16_8(vertex[1], fmt))
        self.z_edit = QLineEdit(format_fp32(vertex[2], fmt))

        # 格式提示
        self.x_label = QLabel("X (Q16.8):")
        self.y_label = QLabel("Y (Q16.8):")
        self.z_label = QLabel("Z (FP32):")

        layout.addRow(self.x_label, self.x_edit)
        layout.addRow(self.y_label, self.y_edit)
        layout.addRow(self.z_label, self.z_edit)

        # 格式切换
        fmt_layout = QHBoxLayout()
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["Decimal", "Binary", "Hexadecimal"])
        fmt_map = {'dec': 0, 'bin': 1, 'hex': 2}
        self.fmt_combo.setCurrentIndex(fmt_map.get(fmt, 0))
        self.fmt_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_layout.addWidget(QLabel("Format:"))
        fmt_layout.addWidget(self.fmt_combo)
        layout.addRow(fmt_layout)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_format_changed(self, index):
        fmt_map = {0: 'dec', 1: 'bin', 2: 'hex'}
        new_fmt = fmt_map[index]

        try:
            x = parse_q16_8(self.x_edit.text(), self.fmt)
            y = parse_q16_8(self.y_edit.text(), self.fmt)
            z = parse_fp32(self.z_edit.text(), self.fmt)

            self.x_edit.setText(format_q16_8(x, new_fmt))
            self.y_edit.setText(format_q16_8(y, new_fmt))
            self.z_edit.setText(format_fp32(z, new_fmt))
            self.fmt = new_fmt
        except ValueError:
            pass

    def get_vertex(self) -> tuple:
        try:
            x = parse_q16_8(self.x_edit.text(), self.fmt)
            y = parse_q16_8(self.y_edit.text(), self.fmt)
            z = parse_fp32(self.z_edit.text(), self.fmt)
            return (x, y, z)
        except ValueError:
            return self._vertex


class TriangleListPanel(QWidget):
    """三角形列表管理面板，支持坐标编辑和格式切换"""

    add_requested = pyqtSignal()
    remove_requested = pyqtSignal(int)
    triangle_updated = pyqtSignal(int, object)

    def __init__(self):
        super().__init__()
        self._triangles: List[Triangle] = []
        self._fmt = 'dec'
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # 格式选择
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Coordinate Format:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["Decimal", "Binary (Q16.8 / FP32)", "Hexadecimal (Q16.8 / FP32)"])
        self.fmt_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_layout.addWidget(self.fmt_combo)
        fmt_layout.addStretch()
        layout.addLayout(fmt_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "V0", "V1", "V2", "Color"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 35)
        self.table.setColumnWidth(4, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(150)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        # 按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.remove_btn = QPushButton("Remove")
        self.edit_btn = QPushButton("Edit Vertex")

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.edit_btn)
        layout.addLayout(btn_layout)

        # 连接信号
        self.add_btn.clicked.connect(self.add_requested)
        self.remove_btn.clicked.connect(self._on_remove)
        self.edit_btn.clicked.connect(self._on_edit)

    def _format_vertex(self, vertex: tuple) -> str:
        x_str = format_q16_8(vertex[0], self._fmt)
        y_str = format_q16_8(vertex[1], self._fmt)
        z_str = format_fp32(vertex[2], self._fmt)
        return f"X:{x_str}\nY:{y_str}\nZ:{z_str}"

    def _on_format_changed(self, index):
        fmt_map = {0: 'dec', 1: 'bin', 2: 'hex'}
        self._fmt = fmt_map[index]
        self.update_triangles(self._triangles)

    def _on_remove(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self.remove_requested.emit(row)

    def _on_edit(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        self._open_vertex_editor(row)

    def _on_double_click(self, index):
        row = index.row()
        col = index.column()
        if col == 4:  # Color
            from PyQt6.QtWidgets import QColorDialog
            if row < len(self._triangles):
                current_color = self._triangles[row].color
                color = QColorDialog.getColor(
                    QColor(current_color[0], current_color[1], current_color[2]),
                    self, "Select Triangle Color"
                )
                if color.isValid():
                    new_color = (color.red(), color.green(), color.blue())
                    tri = self._triangles[row]
                    new_tri = Triangle(vertices=tri.vertices, color=new_color)
                    self.triangle_updated.emit(row, new_tri)
        elif 1 <= col <= 3:  # Vertex column
            self._open_vertex_editor(row)

    def _open_vertex_editor(self, row: int):
        if row >= len(self._triangles):
            return
        tri = self._triangles[row]

        # 确定编辑哪个顶点
        selected_col = self.table.currentIndex().column()
        if 1 <= selected_col <= 3:
            vert_idx = selected_col - 1
        else:
            vert_idx = 0

        dialog = VertexEditDialog(tri.vertices[vert_idx], vert_idx, self._fmt, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_vertex = dialog.get_vertex()
            new_vertices = list(tri.vertices)
            new_vertices[vert_idx] = new_vertex
            new_tri = Triangle(vertices=new_vertices, color=tri.color)
            self.triangle_updated.emit(row, new_tri)

    def update_triangles(self, triangles: List[Triangle]):
        self._triangles = triangles
        self.table.setRowCount(len(triangles))

        for i, triangle in enumerate(triangles):
            # ID
            id_item = QTableWidgetItem(str(i))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, id_item)

            # 顶点列
            for j, vertex in enumerate(triangle.vertices):
                text = self._format_vertex(vertex)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self.table.setItem(i, j + 1, item)

            # Color
            color = triangle.color
            color_item = QTableWidgetItem(f"RGB\n({color[0]},{color[1]},{color[2]})")
            color_item.setBackground(QColor(color[0], color[1], color[2]))
            color_item.setFlags(color_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            color_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 4, color_item)

        self.table.setRowHeight(0, 60)
        for i in range(len(triangles)):
            self.table.setRowHeight(i, 60)

    def get_selected_index(self) -> int:
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            return selected_rows[0].row()
        return -1