# Raster Visualization Plugin

光栅化（Rasterization）过程可视化工具，用于理解图形渲染管线中三角形的光栅化行为。

## 快速开始

```bash
pip install PyQt6 numpy
python main.py
```

## 功能

### 配置参数图形化显示
- MSAA (1x/2x/4x/8x/16x)，使用标准旋转网格（Rotated Grid）采样模式
- Screen Size / Depth Surface Size / Render Target Size
- Clip Region / Scissor Rect
- Tile 大小

### 三角形光栅化
- 多三角形绘制，不同颜色区分
- 软件光栅化器（基于重心坐标插值）
- 深度插值 (FP32)
- MSAA Coverage Test per-sample，Coverage Mask 可视化
- MSAA Resolve（深度测试 + 按覆盖率混合颜色）

### 视图
- **Top View**: 俯视图，显示 tile 网格、scissor/clip 区域、光栅化像素、顶点坐标
- **Depth Side View**: 深度侧视图（X轴=屏幕坐标，Y轴=深度[-1,1]）
- **3D View**: 可旋转3D视图，支持 Front/Back/Left/Right/Top/Perspective 预设模式

### 坐标格式
- X/Y: Q16.8 定点数（16位整数 + 8位小数）
- Z: FP32 浮点数
- 支持 Decimal / Binary / Hexadecimal 三种显示格式切换
- 顶点编辑对话框，支持格式切换和手动输入

### 交互
- 滚轮缩放（以鼠标位置为中心）
- 中键/Shift+左键拖拽平移
- 鼠标悬停显示像素坐标和 tile 索引
- Pop Top/Depth/3D 按钮弹出独立窗口
- 多个显示开关：Tiles、Tile Idx、Tile Axes、Pixel Grid、Vtx Labels、Cov Mask、Scissor、Clip、Pixels、MSAA

## 项目结构

```
├── main.py                          # 应用入口
├── requirements.txt
├── src/
│   ├── main_window.py               # 主窗口
│   ├── models/
│   │   ├── config.py                # 配置数据模型
│   │   └── triangle.py              # 三角形数据模型
│   ├── views/
│   │   ├── config_panel.py          # 配置参数面板
│   │   ├── raster_view.py           # 俯视图（光栅化结果）
│   │   ├── depth_side_view.py       # 深度侧视图
│   │   ├── view3d.py                # 3D 可旋转视图
│   │   ├── triangle_list_panel.py   # 三角形列表管理
│   │   └── popout_window.py         # 弹出独立窗口
│   ├── renderers/
│   │   └── software_rasterizer.py   # 软件光栅化器
│   └── utils/
│       ├── geometry.py              # 几何计算 + MSAA采样位置
│       └── fixed_point.py           # Q16.8 / FP32 格式转换
```

## 版本日志

### v0.2.0 (2026-04-23)
- 修正 MSAA 实现：使用标准旋转网格（Rotated Grid）采样位置
- 新增 Coverage Mask 可视化：被覆盖/未覆盖的 sample 用不同形状和颜色标注
- 新增 MSAA Resolve：per-sample 深度测试 + 按覆盖率混合颜色
- 新增坐标显示开关：Tile Idx、Tile Axes、Pixel Grid、Vtx Labels、Cov Mask 独立控制
- 修复坐标标注溢出：根据缩放级别自动选择标注方式（完整坐标/交替X,Y/省略）
- 新增 3D 视图预设模式：Front/Back/Left/Right/Top/Perspective 按钮
- 修复 3D 坐标轴在投影后不垂直的问题
- 新增 Popout 功能：每个视图可弹出独立窗口放大查看

### v0.1.0 (2026-04-23)
- 初始版本
- 配置参数图形化显示（MSAA、screen size、depth surface、clip region、rt size、scissor、tile）
- 三角形绘制及光栅化结果显示
- 深度侧视图（X轴=屏幕坐标，Y轴=深度[-1,1]）
- 3D 可旋转视图
- Q16.8 (X/Y) 和 FP32 (Z) 坐标编辑，支持 dec/bin/hex 格式切换
- 视图缩放/平移支持
