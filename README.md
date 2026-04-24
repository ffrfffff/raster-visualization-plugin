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
- **3D View**: Combined View，默认 Top 俯视角，支持 Top / X-Z / Y-Z / X-Y / Free 3D 模式和 X/Y/Z 轴旋转

### 坐标格式
- X/Y: Q16.8 定点数（16位整数 + 8位小数）
- Z: FP32 浮点数
- 支持 Decimal / Binary / Hexadecimal 三种显示格式切换
- 顶点编辑对话框，支持格式切换和手动输入

### 交互
- 滚轮缩放（以鼠标位置为中心）
- 方向按钮和滚动条平移 Top/Depth/3D 视图
- Top View 支持输入 X/Y 坐标并定位到目标位置
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

### v0.14.0 (2026-04-24)
- 调整主 GUI 和 Popout 滚动条映射方向：滑块向左/右/上/下移动时，图像按相同方向移动
- 降低滚动条 pan 灵敏度，滚动条位移按 0.25 倍映射到视图偏移，避免拖动过快
- 滚动条与视图 pan offset 双向同步时使用同一比例，保证工具栏平移和滚动条状态一致

### v0.13.0 (2026-04-24)
- Popout 独立窗口新增右侧垂直滚动条和下侧水平滚动条，与主 GUI 的视图导航布局保持一致
- Popout 滚动条可直接调节 Top/Depth/3D 弹出视图的 pan offset
- Popout 工具栏方向按钮、Fit、1:1 操作后会同步更新滚动条位置

### v0.12.0 (2026-04-24)
- 主视图和 Depth Side View 的位置调节改为贴在视图右侧/下侧的滚动条，不再使用 GUI 顶部的上下左右方向按钮
- 切换到 3D View 时自动隐藏下方 Depth Side View，让 3D 视图占用完整主视图空间；切回 Top View 时恢复侧视图
- Popout 独立窗口会跟随主 GUI 的配置、三角形数据和显示开关更新，主 GUI 修改后弹出视图同步刷新

### v0.11.0 (2026-04-24)
- 优化 3D View 放大后的绘制性能：Top 模式 raster pixels 改用 QImage 缓存一次性绘制，避免每帧逐像素投影多边形
- 3D View 的 pixel grid、pixel 坐标标签和 MSAA sample 点改为按当前可见 screen 范围裁剪绘制
- 限制非 Top 旋转视角下的高成本逐像素/MSAA 绘制数量，降低放大和弹出窗口场景下的卡顿

### v0.10.0 (2026-04-24)
- 3D View 升级为 Combined Raster 3D View：在 3D screen 平面中叠加俯视图的 raster debug 信息
- 3D View 新增 rasterized pixels / MSAA resolve pixels 绘制，可在旋转视角下观察像素覆盖结果
- 3D View 新增 tile 网格、tile 索引、tile 坐标轴、pixel grid、clip region、scissor rect、coverage mask、MSAA sample 点和 sample pattern 预览
- Top View 的显示开关同步控制 3D View 对应图层，3D Popout 会继承 raster 图层和当前显示开关

### v0.9.0 (2026-04-24)
- 3D View 升级为 Combined View：默认进入 Top 俯视角，便于直接对齐 screen 平面
- 新增 Top / X-Z / Y-Z / X-Y / Free 3D 模式按钮，可在 3D 视图内查看俯视、侧视和平面视角
- 新增 X-15 / X+15 / Y-15 / Y+15 / Z-15 / Z+15 轴向旋转按钮，支持围绕 X/Y/Z 三轴步进旋转
- 3D 视图的弹出窗口会继承当前 Combined View 模式、X/Y/Z 旋转角度、缩放和平移

### v0.8.0 (2026-04-24)
- 3D View 坐标轴改为右下角独立方向指示器，不再覆盖 screen 平面中心
- 右下角坐标轴会跟随当前 3D 旋转角度变化，保留方向参考能力
- 坐标轴增加半透明背景框，降低与三角形/网格内容的视觉干扰

### v0.7.0 (2026-04-24)
- Top View 新增 Go X/Y 坐标定位，可输入 screen 坐标并将目标位置居中
- Top/3D 上方视图新增方向按钮平移，并根据当前 tab 控制对应视图
- Depth Side View 新增独立方向按钮平移
- 新增 Top/3D 与 Depth 的水平/垂直滚动条式位置调节
- 3D View 支持平移 offset，方向移动不会改变当前旋转角度
- Popout 工具栏新增 ←/↑/↓/→ 方向平移按钮

### v0.6.0 (2026-04-24)
- 修复 MSAA 采样点可视化不明显的问题：高缩放下每个被覆盖 pixel 会显示完整 sample pattern，而不是只看到单个覆盖点
- MSAA sample 点使用圆点和编号区分，覆盖/未覆盖 sample 使用不同填充样式
- 新增右上角 MSAA sample pattern 预览框，切换 2x/4x/8x/16x 时可直接观察采样点分布变化
- Coverage mask 显示改为完整 `0b...` 二进制形式，并按当前 MSAA sample 数补齐位数

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
