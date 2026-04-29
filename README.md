# Raster Visualization Plugin

光栅化（Rasterization）过程可视化工具，用于理解图形渲染管线中三角形的光栅化行为。

## 快速开始

```bash
pip install PyQt6 numpy
python main.py
```

## 功能说明


### 输入/输出目录
- 工程根目录提供 `input/` 和 `output/` 两个固定目录，并通过 `.gitkeep` 保留空目录结构。
- `input/` 用于放置待导入文件，例如 JSON 场景文件、PB dump `.sv/.txt/.pb` 文件；GUI 导入对话框默认从该目录打开。
- `output/` 用于保存导出文件，例如 `File > Export PB Dump...` 生成的 `.sv` 文件；GUI 导出对话框默认写入该目录。
- 两个目录中的实际数据文件默认不提交到 git，只提交目录本身，方便放置本地验证资料。

### 配置参数面板
- **MSAA**: 支持 1x / 2x / 4x / 8x / 16x，采样点使用标准旋转网格（Rotated Grid）模式。
- **Screen Size**: 配置屏幕空间宽高，是 Top View / 3D View 中 screen 平面的基础范围。
- **Depth Surface Size**: 配置 depth surface 宽高，可通过 `Depth Surf` 开关在 Top View / 3D View / Popout 中显示边界。
- **Render Target Size**: 配置 render target 宽高，可通过 `RT Surf` 开关在 Top View / 3D View / Popout 中显示边界。
- **Clip Region**: 配置裁剪区域 `(x, y, width, height)`，在视图中用黄色边框显示。
- **Scissor Rect**: 配置 scissor 区域 `(x, y, width, height)`，在视图中用青色边框显示。
- **Tile Size**: 配置 tile 宽高，并自动计算横纵 tile 数量。

### 三角形管理与坐标编辑
- 支持多个三角形同时绘制，每个三角形使用不同颜色区分。
- 三角形列表展示每个三角形的三个顶点坐标。
- 支持新增、删除、清空三角形。
- 支持在 GUI 中手动编辑顶点坐标。
- X/Y 坐标使用 Q16.8 定点格式（16 位整数 + 8 位小数）。
- Z 坐标使用 FP32 浮点格式，深度范围显示为 `[-1, 1]`。
- 顶点编辑支持 Decimal / Binary / Hexadecimal 三种格式切换。
- 坐标显示会根据当前格式自动转换，便于对照硬件/协议中的定点或浮点表示。

### 场景 JSON 导入
- 支持通过 `File > Import Scene...` 读取 JSON 场景文件，一次性导入完整配置和全部三角形。
- JSON 中可配置 MSAA、Screen Size、Depth Surface Size、Render Target Size、Clip Region、Scissor Rect 和 Tile Size。
- JSON 中可配置多个三角形，每个三角形包含 3 个 screen-space 顶点 `[x, y, z]`，并可选配置 RGB 颜色。
- 导入后会自动同步配置面板、三角形列表、Top View、Depth Side View、3D View 和已打开的 Popout 窗口。

#### JSON 坐标进制说明
- 标准 JSON number 只支持十进制，不能直接写 `0x...` 或 `0b...` 作为数字。
- 如果需要在 JSON 文件中表达二进制或十六进制，建议使用字符串形式，例如 `"0x00006400"` 或 `"0b000000000110010000000000"`。
- X/Y 建议按 Q16.8 定点格式解析：十进制数字表示 screen-space float；字符串形式的 `0x...` / `0b...` 可表示 Q16.8 bit pattern。
- Z 建议按 FP32 解析：十进制数字表示普通浮点值；字符串形式的 `0x...` / `0b...` 可表示 FP32 bit pattern。
- 当前版本的 JSON 导入实现只读取十进制 JSON number；二进制/十六进制字符串格式作为后续扩展约定记录。

示例：

```json
{
  "config": {
    "msaa": 4,
    "screen_size": [800, 600],
    "depth_surface_size": [800, 600],
    "render_target_size": [800, 600],
    "clip_region": [0, 0, 800, 600],
    "scissor": [0, 0, 800, 600],
    "tile_size": [16, 16]
  },
  "triangles": [
    {
      "vertices": [[100, 100, 0.0], [200, 100, 0.3], [150, 200, -0.2]],
      "color": [255, 0, 0]
    }
  ]
}
```

分进制坐标写法示例（后续扩展约定）：

```json
{
  "vertices": [
    ["0x00006400", "0x00006400", "0x00000000"],
    ["0x0000c800", "0x00006400", "0x3e99999a"],
    ["0b000000001001011000000000", "0b000000001100100000000000", "0xbe4ccccd"]
  ],
  "color": [255, 0, 0]
}
```

### 软件光栅化器
- 使用屏幕空间三角形进行软件光栅化。
- 使用 edge function 判断像素或 sample 是否落入三角形。
- 使用重心坐标进行深度插值。
- 支持 per-pixel coverage ratio 统计。
- 支持 per-sample coverage test 和 per-sample depth 记录。
- 支持 coverage mask 输出，并在选中像素的右上角 MSAA sample pattern 预览框中显示。
- 支持 MSAA resolve：根据 sample 覆盖率和深度结果混合颜色。
- 状态栏显示三角形数量、光栅化像素数量和深度范围。


### PB Dump 导入/导出 v1
- 支持通过 `File > Import PB Dump...` 导入 Doc1-like 硬件验证环境 dump。
- 支持解析 `randomized_3d_memory[frag_vce][primitive_block_addr+N] = 256'h...;` 形式的 256-bit SystemVerilog memory word。
- `256'h...` 的最右侧是 bit0，字段按低 bit 到高 bit 对齐；插件内部按这个规则拆分和重新打包。
- PB 生成规则独立维护在 `src/utils/pb_rules.py`，后续可继续扩展条件规则，例如根据控制变量决定某些 word 是否生成。
- 状态块字段表按 `gpu_isp_pds_bif_pkg` 的 packed struct 展开：PDS、ISP、vertex varying/position format、point pitch 都逐字段列出。
- 支持 24-bit `index_data_s`：`ix_index_0`、AB flag、reserved0、`ix_index_1`、BC flag、reserved1、`ix_index_2`、CA flag、BF flag 按结构体顺序打包。
- v1 紧凑打包 state block、`point_pitch` / `index_data_s` 和 `original_position_coord`：`isp_state_word_fa/fb/ba/bb` 按 fa、fb、ba、bb 顺序写入；`this_is_point_primblk` 在独立 `pb_instruction` 随机块中生成，`pb_instruction` 表格同时输出 `primitive_block_instruction` 和 `primblk_cfg` 字段；为 1 时显示并写入 `point_pitch`、不显示 `index_data`，为 0 时显示并写入 `index_data`、不显示 `point_pitch`；index mode 下每个 `index_data_s` 为 24 bit，全部写完后按 `align_up(index_data_start_bit + primitive_count * 24, 32)` 计算 `original_position_coord` 起点，因此 padding 随 primitive 数量自动变化，不是固定 16 bit；每个顶点占 80 bit，X/Y 为 24-bit signed Q16.8，Z 为 32-bit FP32。
- 导入时优先使用 `index_data_s` 还原 primitive 与顶点索引关系；没有 index table 时才回退为每 3 个顶点组成一个三角形。
- 支持通过 `File > Export PB Dump...` 从当前 GUI 三角形生成 Doc1-like dump，导出文件使用统一表格：`field / values / note` 三列，值为 `n'hxxx` 格式，子字段缩进显示，非 integral 行把 schema 名称显示在 field 列；最后写最终 `256'h...` memory dump。
- 导出时 `pds_state_word0` 和 `pds_state_word1` 每次随机生成 32-bit 值，填充到字段表和最终 memory dump。
- 当前 v1 是模板化反解析，不生成完整硬件可用的 control stream、primitive instruction header 或 visibility config。

### MSAA 可视化
- 支持 1x / 2x / 4x / 8x / 16x MSAA 切换。
- MSAA 采样点使用旋转网格分布，便于观察不同 MSAA 模式下 sample 位置差异。
- 右上角 MSAA sample pattern 预览框默认开启，不再提供单独显示开关。
- 不再在每个 pixel 内重复绘制 sample 点和 coverage mask，避免高缩放或大面积三角形下绘制过重。
- 点击 Top View 或 3D View 中的像素后，右上角 MSAA sample pattern 会显示该像素各 sample 的命中状态。
- 被选中像素的 sample 命中时显示红色，未命中时显示黑色，并显示对应 coverage mask。
- sample 点显示编号，方便对照 coverage mask bit 位。
- MSAA > 1x 时，光栅化像素可显示 resolve 后的颜色结果。

### Top View（俯视光栅视图）
- 显示 screen 平面、tile 网格、三角形边框、顶点、光栅化像素和右上角默认开启的 MSAA sample pattern 预览框。
- 显示 Screen / Depth Surface / Render Target / Clip / Scissor 等不同边界。
- 支持 tile index 显示，例如 `(tile_x, tile_y)`。
- 支持 tile 边界上的像素坐标刻度。
- 支持高缩放下显示 pixel grid 和 pixel 坐标。
- 像素坐标会根据格子大小自动裁剪或简化，避免文字挤出 pixel。
- 不再提供 `Cov Mask` 和 `MSAA` 显示开关；coverage mask 和 MSAA sample 命中状态统一在右上角默认预览框中查看。
- 鼠标悬停显示当前 pixel 坐标和 tile 索引。
- 鼠标点击 screen 内像素后，右上角 MSAA sample 预览框会显示该像素 sample 命中/未命中状态。
- 支持输入 `Go Top X/Y`，把指定 screen 坐标定位到视图中心。

### Depth Side View（深度侧视图）
- 使用 X 轴表示 screen X 坐标。
- 使用 Y 轴表示深度值，范围为 `[-1, 1]`。
- 显示三角形顶点的深度位置和三角形深度剖面。
- 显示光栅化像素对应的插值深度点。
- 支持滚轮缩放和拖拽平移。
- 支持右侧/下侧滚动条调节视图位置。
- Popout 后仍支持独立缩放和平移。

### 3D View（Combined Raster 3D View）
- 3D View 是合并视图：在 3D screen 平面上叠加 Top View 的 raster debug 信息。
- 默认进入 Top 俯视角，便于和 Top View 对齐观察。
- 支持 Top / X-Z / Y-Z / X-Y / Free 3D 固定视角模式。
- 支持 X-15 / X+15 / Y-15 / Y+15 / Z-15 / Z+15 轴向步进旋转。
- 支持 Free Drag 开关，开启后可用鼠标自由旋转，默认关闭以避免误操作。
- 支持正交投影，减少透视变形，便于对齐 screen 平面。
- 支持右下角独立 X/Y/Z 坐标轴指示器，不遮挡 screen 内容。
- 支持 screen 平面底板、tile 网格、tile index、tile 坐标轴、pixel grid、clip、scissor、Depth Surface、RT Surface、raster pixels 和右上角默认开启的 MSAA sample pattern 预览。
- 非正方形 screen 使用统一比例归一化，保证 3D View 中 pixel 不被拉伸。
- 3D 像素坐标会按当前格子显示空间裁剪，放不下时自动隐藏，避免挤出格子。
- 滚轮缩放以鼠标当前位置为锚点，和 Top View 一样保持鼠标下的内容位置稳定。
- 支持右侧/下侧滚动条平移视图。

### 显示开关
- **Tiles**: 显示或隐藏 tile 网格。
- **Tile Idx**: 显示或隐藏 tile 索引。
- **Tile Axes**: 显示或隐藏 tile 边界像素坐标刻度。
- **Pixel Grid**: 显示或隐藏 pixel grid 和 pixel 坐标。
- **Vtx Labels**: 显示或隐藏顶点坐标标签。
- **Scissor**: 显示或隐藏 scissor rect。
- **Clip**: 显示或隐藏 clip region。
- **Depth Surf**: 显示或隐藏 depth surface size 边界。
- **RT Surf**: 显示或隐藏 render target size 边界。
- **Pixels**: 显示或隐藏光栅化像素/resolve 像素。
- **3D Grid**: 显示或隐藏 3D View 的网格层。
- **3D Axes**: 显示或隐藏 3D View 右下角坐标轴。
- **Free Drag**: 控制 3D View 是否允许鼠标自由拖拽旋转。

### 缩放、平移与定位
- Top View 和 3D View 支持滚轮缩放，并以鼠标位置为缩放锚点。
- Depth Side View 支持滚轮缩放。
- Top View 支持中键拖拽或 `Shift + 左键` 拖拽平移。
- Depth Side View 支持左键拖拽平移。
- 主 GUI 的 Top/3D 区域右侧和下侧有滚动条，可直接调节当前主视图位置。
- Depth Side View 右侧和下侧有独立滚动条，可调节深度视图位置。
- 滚动条方向与图像移动方向一致，并降低了映射灵敏度，避免拖动过快。
- `Fit` 可将 Top View 缩放到适合窗口大小。
- `1:1` 可重置 Top View 缩放和平移。
- `Go Top X/Y` 可输入 screen 坐标并定位到目标位置。

### Popout 独立窗口
- 支持 `Pop Top`、`Pop Depth`、`Pop 3D` 将三个视图弹出到独立窗口。
- Popout 窗口带有自己的 toolbar，可执行 Zoom In、Zoom Out、Fit、1:1、方向平移和 Close。
- Popout 窗口带有右侧/下侧滚动条，布局与主 GUI 保持一致。
- 主 GUI 中修改配置、三角形数据或显示开关后，已弹出的 Popout 视图会同步更新。
- 3D Popout 会继承主 3D View 的视角模式、X/Y/Z 旋转角度、缩放和平移状态。

### 性能优化
- Top View 的光栅化像素使用 QImage 缓存一次性绘制，避免每帧逐像素 drawRect。
- 3D View 在 Top 模式下的 raster pixels 也使用 QImage 缓存绘制。
- 高缩放下只绘制当前可见 screen 范围内的 pixel grid 和坐标标签，MSAA sample 只保留右上角默认预览框，避免逐像素重复绘制 sample 点和 coverage mask。
- 配置 Apply 使用批量更新和单次刷新，Top View / 3D View / Popout 复用同一份光栅化结果，减少重复计算。
- 非 Top 旋转视角限制高成本逐像素/MSAA 绘制数量，减少卡顿。
- 低缩放时关闭部分抗锯齿以提升绘制性能。

### 当前限制与后续方向
- 当前三角形输入以 screen-space 顶点为主。
- PB Dump 已接入 Doc1-like v1 解析/反解析，可用于状态块字段、index data、顶点坐标 round-trip 和可视化验证。
- 完整硬件 PB / 3D display list / prim instruction header / visibility config 语义解析仍在后续扩展中。
- 后续可扩展为从 PB 序列更新 depth buffer、depth test 和最终可见性结果。
- 后续可增加保存/加载场景、导入导出三角形和更完整的硬件命令解析。

## 项目结构

```
├── main.py                          # 应用入口
├── requirements.txt
├── input/                         # 本地导入文件目录，内容不入库
├── output/                        # 本地导出文件目录，内容不入库
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
│       ├── fixed_point.py           # Q16.8 / FP32 格式转换
│       ├── scene_io.py              # JSON 场景导入
│       ├── pb_rules.py              # PB Dump 字段/生成规则
│       └── pb_io.py                 # PB Dump v1 解析/反解析
```

## 版本日志

### v1.4.6 (2026-04-29)
- PB 导入后的 GUI 绘制会跳过非有限坐标/深度，并对超大视图坐标做安全裁剪，避免验证 dump 中出现 `nan`、异常 FP32 深度或超大坐标时导致 Qt 绘图参数溢出；解析表仍保留原始字段值。
- index mode 下所有 `index_data_s` 解析/写入完成后，会把 `original_position_coord` 起点向后对齐到 32-bit 边界，公式为 `coord_start_bit = align_up(index_data_start_bit + primitive_count * 24, 32)`；padding 由 primitive 数量自动决定，例如当前样例中需要跳过 16 bit padding，解析表显示为 `index_data_to_coord_alignment`，方便对照 memory bit layout。
- PB 导入解析现在复用导出侧紧凑布局规则，通过 `get_filtered_state_block_members()` 计算 state block 长度，GUI 导入时会先询问 primitive 数量和 vertex 数量，解析严格按输入数量确定 `index_data` 结束位置和读取的 `original_position_coord` 数量，不再用 `vf_vertex_total` 或 memory 长度反推数量；如果 `index_data` 引用超出已输入 vertex 数量的索引，解析表仍会输出，GUI 只跳过无法绘制的 primitive，保证隐藏 state word 不占 memory 空间且 `fa/fb/ba/bb` 顺序一致。
- packed struct 子字段按 SystemVerilog 声明顺序从高 bit 到低 bit 拆分和拼接；`index_data_s` 按协议定义从最低位到最高位拆分为 `ix_index_0`、`ix_edge_flag_ab`、reserved、`ix_index_1` 等字段，确保解析表、导出表与 `randomized_3d_memory` 的父字段值一致。
- PB 导出仍由 `pb_instruction` 中的 `this_is_point_primblk` 控制 `point_pitch` 与 `index_data` 互斥，导出时 `ispa_objtype` 与 `this_is_point_primblk` 保持一致。
- PB 导入根据 `ispa_objtype` 字段判断 `point_pitch` 与 `index_data` 的互斥关系：`ispa_objtype` 为 2、3、4、6 时使用 `point_pitch`，其他值使用 `index_data`。
- 纯 `randomized_3d_memory` dump 无法从 `ispa_objtype` 推断模式时，会按 point/index 两种 compact payload layout 尝试推断。
- PB 导入时自动输出解析后的 PB 字段表到 `output/parsed_*.sv`，包含 state block 字段表、payload 表和坐标表，便于逐字段对照。
- `256'h...` literal 导入兼容 `x/z/?` unknown 位并按 0 处理；超过 256-bit 的 sized literal 按低 256-bit 截取。

### v1.4.5 (2026-04-28)
- `prim_header` 父值改为严格按 `{cs_type, cs_isp_state_size, cs_prim_total, cs_mask_fmt, cs_prim_base_pres, cs_prim_base_offset}` 拼接，父字段本身不再独立随机。
- `prim_mask_word0`、`prim_mask_word1`、`prim_mask_word2` 同样由各自子字段拼接生成，避免父子值不一致。
- 修复 stop hook 对 `git status --short` 路径的解析，避免 ` M README.md` 被误读成 `EADME.md` 后错误拦截。

### v1.4.4 (2026-04-28)
- 拆分 `pb_instruction` 随机、PB memory 随机和约束逻辑，导出流程改为先随机 `primitive_block_instruction`，再基于其中的 `this_is_point_primblk` 随机 PB payload。
- `prim_header` 父行现在显示由 `cs_type`、`cs_isp_state_size`、`cs_prim_total`、`cs_mask_fmt`、`cs_prim_base_pres`、`cs_prim_base_offset` 按顺序拼成的 32-bit 值。
- `pb_instruction` 表格父节点行不再输出类型名和 `@...` 标注，只保留层级名称和 `-` 占位。
- `primitive_block_instruction`、`primblk_cfg` 和 `prim_header` 中除外部控制信号 `this_is_point_primblk` 外的字段按各自 bit 宽随机生成，不再使用固定默认值。
- 调整 `pb_instruction` 表格层级：`primblk_cfg` 缩进显示在 `primitive_block_instruction` 下，`primblk_start_byte_base_low_addr` 起的字段回到 `primitive_block_instruction` 层级。
- PB 导出新增完整 `pb_instruction random block` 表格，包含 `primitive_block_instruction` 以及其子层级 `primblk_cfg`。
- `primitive_block_instruction` 表输出 `vf_vertex_total`、`cs_prim_total`、`cs_mask_fmt`、`this_is_point_primblk`、PDS/ISP/vertex varying 相关控制字段。
- `primblk_cfg` 作为 `primitive_block_instruction` 的子层级输出 MSAA/fragment/context 地址配置、随机 rate 配置、state word 存在标志、primitive header 和 primitive mask words；这些 instruction/config 字段按各自 bit 宽独立随机生成，并先于 PB memory 随机完成。
- `this_is_point_primblk` 继续作为 PB 外部 instruction 控制信号，驱动 `point_pitch` 与 `index_data` 的互斥显示和写入。

### v1.4.3 (2026-04-28)
- 新增独立 `pb_instruction` 随机块，输出外部控制信号 `this_is_point_primblk`。
- `this_is_point_primblk=1` 时 PB payload 显示/写入 `point_pitch`，不显示/不写入 `index_data`。
- `this_is_point_primblk=0` 时 PB payload 显示/写入 `index_data`，不显示/不写入 `point_pitch`。
- `original_position_coord` 会紧跟当前 payload（`point_pitch` 或 `index_data`）后写入，保持表格和 `randomized_3d_memory` 一致。

### v1.4.2 (2026-04-28)
- PB state block 生成改为和表格显示一致的紧凑顺序，被规则隐藏的 state word 不再占用 `randomized_3d_memory` 中的隐形空间。
- `isp_state_word_fa/fb/ba/bb` 按 fa、fb、ba、bb 顺序写入 memory 和表格，保证 `fa` 在 `fb` 上方、`ba` 在 `bb` 上方。
- `point_pitch` 后直接衔接 `index_data`，消除 `point_pitch` 和 `p[0]` 之间来自隐藏 state words 的额外数据。

### v1.4.1 (2026-04-28)
- PB 导出的 `original_position_coord` 改为紧跟 `index_data` 后连续写入，移除 Doc1 固定偏移带来的中间 padding word。
- PB memory dump 现在按 `pds_state_word0` 到 `original_position_coord` 的字段顺序紧凑生成，表格和 `randomized_3d_memory` 保持一致。
- PB 导入支持读取新表格中的 `p[n]` 和 `v[n]` 行，保证紧凑格式可以 round-trip。

### v1.4.0 (2026-04-28)
- 移除 `DEFAULT_TEMPLATE_WORDS` 预定义模板值，所有 memory word 初始化为 0 后按需随机化
- 新增 `_randomize_vertex_format()` 函数，随机化 vertex format 和 point pitch 的所有子字段
- 现在所有 state block 字段（pds_state、isp_state、vertex_varying_comp_size、vertex_position_comp_format_word_zero/one、point_pitch）全部独立随机化
- 修复 `vertex_position_comp_format_word_zero` 缺少 `cs_isp_comp_format_y2` 字段的问题，从 28-bit 修正为 32-bit

### v1.3.0 (2026-04-28)
- PB 导出新增条件规则引擎，根据控制字字段动态决定 state block members 的存在性和可见性
- **规则1**: `isp_miscenable=1` 时 `isp_state_word_misc` 存在并随机化，否则不显示
- **规则2**: `isp_miscenable=1` 且 `dbt_op!=0` 时 `isp_state_word_dbmin` 和 `isp_state_word_dbmax` 存在并随机化
- **规则3**: `isp_samplemaskenable` / `isp_dbenable` / `isp_scenable` 任一为 1 时 `isp_state_word_csc` 存在并随机化
- **规则4**: `isp_twosided=1` 时 `isp_state_word_ba` 存在；`isp_bpres=1` 时 `isp_state_word_bb` 也存在
- **规则5**: `isp_twosided=0` 时 index_data 中所有 primitive 的 `ix_bf_flag` 强制为 0
- **规则6**: `isp_bpres=1` 时 `isp_state_word_fb` 存在并随机化
- **规则7**: `pds_state` 和 `isp_state` 的所有 dword 默认随机化，每个子字段独立随机
- 随机化机制改进：每个 struct 子字段（如 `pds_fragment_addr`、`reserved`、`pds_douti` 等）分别调用 `random.getrandbits(width)` 独立随机，不再对整个 word 统一随机
- 新增 `get_filtered_state_block_members()` 函数根据规则过滤可见 members
- 新增 `enforce_bf_flag_zero()` 函数强制执行 bf_flag=0 规则
- 导出表格会根据规则自动隐藏不存在的 word，例如 `isp_miscenable=0` 时不显示 `isp_state_word_misc` / `dbmin` / `dbmax`

### v1.2.3 (2026-04-28)
- PB 导出表格统一为 `field / values / note` 三列：去掉 type、bits、hex 列，值合并为 `n'hxxx` 格式。
- 非 integral 行将 schema 名称显示在 field 列，原始 field 名移到 note。
- 子字段不再带父前缀（如 `pds_w0.pds_fragment_addr` 简化为 `pds_fragment_addr`）。
- schema 名称去掉 `_s` 和 `_word` 后缀显示。
- `index_data` 区域用 `p[n]` 表示 primitive，`original_position_coord` 区域用 `v[n]` 表示顶点、`x[n]/y[n]/z[n]` 表示坐标分量。
- 导出时 `pds_state_word0` 和 `pds_state_word1` 随机生成 32-bit 值，填充到字段表和 `randomized_3d_memory`。

### v1.2.2 (2026-04-28)
- 将 PB 字段 schema 和生成规则拆分到 `src/utils/pb_rules.py`，便于后续扩展条件生成规则。
- PB 导出格式改为无注释表格，去掉重复的 `width=` / `value=` 文本，并用缩进表示 word 与子字段层级。
- 保持 `index_data_s` 与坐标表 round-trip 校验，导出仍包含最终 256-bit memory dump。

### v1.2.1 (2026-04-28)
- PB Dump 解析/反解析改为按 `gpu_isp_pds_bif_pkg` packed struct schema 展开状态块字段。
- 新增 `index_data_s` 表生成与解析，导入时按 index data 还原每个 primitive 的 3 个顶点索引。
- PB 导出现在包含状态块字段表、index data 表、original_position_coord 表和最终 256-bit memory dump，方便逐字段对齐验证。

### v1.2.0 (2026-04-27)
- 新增 PB Dump 导入/导出 v1，支持 Doc1-like 硬件验证环境 256-bit memory dump。
- 正确按 `256'h...` 右侧低 bit 的规则解析和生成 `primitive_block_addr+N` memory word。
- 支持 80-bit `original_position_coord` 顶点格式：X/Y 为 24-bit signed Q16.8，Z 为 32-bit FP32。
- 导入 PB dump 后自动同步三角形列表、Top/Depth/3D 视图和 Popout；导出包含字段表、坐标表和最终 memory dump，便于插件 round-trip 和逐项对齐验证。
- `.gitignore` 已排除 Doc1 原始文档和解包目录，避免临时验证资料进入版本库。
- 当前 PB 反解析为 Doc1 模板化 v1，不保证生成完整硬件可执行 PB/control stream。
- 输入/输出目录内容通过 `.gitignore` 排除，只保留 `input/.gitkeep` 和 `output/.gitkeep`，导入默认读 `input/`，导出默认写 `output/`。

### v1.1.0 (2026-04-27)
- 新增 JSON 场景导入功能，可通过 `File > Import Scene...` 一次性读取完整配置和全部三角形
- JSON 导入支持 MSAA、screen/depth surface/render target、clip、scissor、tile size 等配置项
- JSON 导入支持多个三角形的 3 个顶点和可选 RGB 颜色，导入后自动同步配置面板、三角形列表、Top/Depth/3D 和 Popout
- README 补充 JSON 文件中二进制/十六进制坐标需用字符串表示的说明，并记录 X/Y Q16.8、Z FP32 的后续扩展约定

### v1.0.2 (2026-04-24)
- 移除 GUI 中的 `Cov Mask` 和 `MSAA` 显示开关，右上角 MSAA sample pattern 预览框改为默认一直显示
- README 功能说明同步移除已废弃的显示开关描述，并明确 coverage mask / sample 命中状态统一在右上角预览框查看
- 配置面板 Apply 改为批量更新配置，只触发一次主视图刷新，避免一次配置修改重复光栅化多次
- Top View、3D View 和 Popout 同步复用同一份光栅化结果，减少配置修改和弹窗同步时的重复计算

### v1.0.1 (2026-04-24)
- MSAA 显示简化为只在右上角 sample pattern 预览框展示，不再在每个 pixel 内重复绘制 sample 点和 coverage mask
- 点击 Top View 或 3D View 的像素后，右上角预览框继续用红色/黑色显示选中像素 sample 命中状态，并显示 coverage mask
- README 同步更新 MSAA、Top View、3D View、显示开关和性能优化说明

### v1.0.0 (2026-04-24)
- 发布 1.0.0：完成配置可视化、三角形编辑、软件光栅化、MSAA、Top/Depth/3D 视图、Popout、滚动条导航和性能优化等核心功能
- Top View 和 3D View 新增点击像素查看 MSAA sample 命中状态，右上角 sample pattern 用红色表示命中、黑色表示未命中
- 选中像素后 MSAA sample pattern 会显示对应 coverage mask，便于对照 sample 编号和 coverage bit 位

### v0.18.0 (2026-04-24)
- 将 `.claude/` 加入 `.gitignore`，避免本地 Claude Code 配置和 hook 文件继续提交到仓库
- 从 Git 索引移除已跟踪的 `.claude/settings.json` 和 `.claude/hooks/require_changelog_and_push.py`，保留本地文件不删除

### v0.17.0 (2026-04-24)
- README 功能说明扩展为完整使用文档，覆盖配置面板、三角形管理、软件光栅化、MSAA、Top/Depth/3D 视图、显示开关、交互、Popout 和性能优化
- README 新增当前限制与后续方向，记录 PB / display list / depth buffer 等后续扩展目标
- README 补充 Depth Surf / RT Surf、3D 像素比例修正、Popout 同步和滚动条导航等最新功能说明

### v0.16.0 (2026-04-24)
- 新增 Depth Surf 和 RT Surf 两个独立显示开关，不再把 surface 显示合并为单一开关
- Top View 和 3D View 新增 Depth Surface Size / Render Target Size 边界可视化，并同步支持 Popout 独立窗口
- 修正 3D View 的 screen 归一化比例，避免非正方形 screen 下像素显示被拉伸
- 3D View 像素坐标文字改为按格子实际显示空间裁剪，避免坐标挤出 pixel 格子

### v0.15.0 (2026-04-24)
- 3D View 滚轮缩放改为以鼠标当前位置为锚点，和 Top View 一样保持鼠标下的内容位置稳定
- 3D View 缩放时会同步补偿 pan offset，避免只围绕视图中心缩放导致画面漂移

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
