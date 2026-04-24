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
- **3D View**: 正交工程视图，支持 Front/Back/Left/Right/Top/Bottom/ISO 固定视角、Yaw/Pitch 步进旋转和可选 Free Drag

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

### v0.5.0 (2026-04-24)
- 新增项目级 Claude Code Stop hook：当项目文件有改动但 README 版本日志未更新时，结束前阻止并提醒补充版本日志
- Hook 会在存在未推送提交时提醒先执行 git push，避免改动只停留在本地
- 将“每次改动最后必须总结、更新版本日志并推送”的流程固化到项目配置

### v0.4.0 (2026-04-24)
- 3D 视图改为默认正交投影，减少透视变形，固定视角更稳定
- 优化 3D 外观：增加屏幕平面底板、半透明网格、顶点到基准面的深度辅助线
- 新增 Bottom / ISO 固定视角，并保留 Front/Back/Left/Right/Top
- 新增 Yaw -15 / Yaw +15 / Pitch -15 / Pitch +15 按钮，用于水平/纵向步进旋转
- 新增 Free Drag 开关：默认关闭自由拖拽，避免误操作导致视角难以找回
- 3D Popout 继承当前主视图的视角、缩放和 Free Drag 设置

### v0.3.0 (2026-04-24)
- 性能优化：光栅化像素使用 QImage 缓存一次性绘制，替代逐像素 drawRect
- MSAA > 1x 时自动使用 resolve 图（按 coverage 混合颜色），视觉上体现抗锯齿差异
- MSAA 采样点绘制仅在高缩放(>=4x)时启用，且只绘制可见像素
- 低缩放时关闭 QPainter 抗锯齿提升性能
- 状态栏显示 MSAA 边缘像素数量

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
