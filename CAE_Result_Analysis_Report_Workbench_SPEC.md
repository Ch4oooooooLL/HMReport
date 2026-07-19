# CAE Result Analysis & Report Workbench
# 工程实现规格说明（SPEC）

> 文档状态：可实施  
> 目标平台：Windows 10 / Windows 11 x64  
> 首要兼容软件：Altair HyperView 2019  
> 文档版本：1.0.0  
> 日期：2026-07-19  
> 默认语言：简体中文  
> 实施方式：由 Codex 从零开始分阶段落地  

---

# 0. 文档用途

本文件是 `CAE Result Analysis & Report Workbench` 项目的主规格文档，用于指导：

- 产品边界；
- 系统架构；
- 模块职责；
- 数据模型；
- 桌面程序；
- 本地服务；
- Web 前端；
- Python Worker；
- HyperView/TCL 执行器；
- FEM 解析；
- 热点识别；
- 截图；
- 视图恢复；
- PPT 预览与导出；
- 测试；
- 打包；
- 验收。

实现过程中遵循以下优先级：

1. 本规格中的明确要求；
2. 通过自动化测试和真实 HyperView POC 验证的行为；
3. 数据可靠性与故障可恢复性；
4. 用户体验；
5. 实现便利性。

如实现需要偏离本规格，必须在：

```text
docs/decisions/
```

新增 ADR，记录：

- 原决策；
- 变更原因；
- 替代设计；
- 风险；
- 数据迁移影响；
- 回滚策略。

不得静默偏离。

---

# 1. 产品定位

## 1.1 产品名称

暂定：

```text
CAE Result Analysis & Report Workbench
```

中文名称：

```text
CAE 结果分析与报告工作台
```

## 1.2 产品定义

本系统是一个本地优先的 Windows 工程软件，用于：

- 管理有限元项目；
- 引用 FEM 与 H3D 文件；
- 执行模型信息提取；
- 执行网格、材料、属性、边界条件和工况分析；
- 调用 HyperView 批量生成结果截图；
- 自动整理应力、位移、模态及其他结果热点；
- 在 Web 工作台中审查结果；
- 恢复 HyperView 视图；
- 管理截图版本；
- 编排报告；
- 预览和导出 PPTX。

系统不是：

- HyperView 替代品；
- 求解器；
- 云端 H3D 托管平台；
- 单纯截图工具；
- 单纯 PowerPoint 模板工具。

系统定位为：

> 桌面端负责项目和任务控制，Web 端负责结果审查与报告生产，Python Worker 与 HyperView/TCL 负责后台执行。

---

# 2. 核心工作流

```text
启动桌面项目管理器
        ↓
创建项目
        ↓
选择项目工作目录
        ↓
选择 FEM
        ↓
选择 H3D
        ↓
可选选择 OUT / OP2 / Excel 等附加输入
        ↓
校验文件
        ↓
选择一个或多个任务类型
        ↓
启动 Analysis Run
        ↓
桌面端显示后台执行进度
        ↓
Python 解析 FEM
        ↓
后台启动 HyperView
        ↓
加载 H3D
        ↓
读取子工况和结果索引
        ↓
识别热点并生成多视角截图
        ↓
构建 Web 结果数据
        ↓
任务完成
        ↓
桌面端打开 Web 结果工作台
        ↓
查看模型、网格、材料、属性、边界条件、工况
        ↓
查看应力、位移、模态及其他热点
        ↓
审核图片
        ↓
恢复 HyperView 视图
        ↓
重拍或修改图例
        ↓
选择报告素材
        ↓
Web 中预览 PPT
        ↓
导出 PPTX
```

---

# 3. 产品边界

## 3.1 V1 必须实现

### 桌面项目管理器

- 创建项目；
- 编辑项目；
- 删除项目；
- 从项目列表移除；
- 打开项目目录；
- 选择 FEM；
- 选择 H3D；
- 文件有效性校验；
- 任务类型多选；
- 创建 Analysis Run；
- 启动任务；
- 暂停任务；
- 恢复任务；
- 取消任务；
- 重试失败任务；
- 显示总体进度；
- 显示阶段进度；
- 显示当前任务；
- 显示 Worker 状态；
- 显示 HyperView 状态；
- 强制终止失效 HyperView；
- 打开 Web 结果；
- 打开日志；
- 导出诊断包。

### 本地应用服务

- 提供 REST API；
- 提供 WebSocket 事件；
- 保存项目；
- 保存 Run；
- 保存任务；
- 保存结果数据；
- 保存截图和截图版本；
- 保存审核信息；
- 保存报告文档；
- 唯一写入 SQLite；
- 向桌面端和 Web 前端提供一致数据。

### Python Worker

- 执行 FEM 解析；
- 启动和管理 HyperView；
- 与 Tcl 通信；
- 执行任务 DAG；
- 提取模型信息；
- 提取网格信息；
- 提取材料和属性；
- 提取边界条件；
- 提取子工况定义；
- 索引 H3D；
- 执行应力热点；
- 执行位移热点；
- 生成标准截图；
- 校验图片；
- 提交结果；
- 崩溃恢复；
- 支持 Fake HyperView。

### HyperView/TCL

- 自动打开 H3D；
- 查询 subcase；
- 查询 simulation；
- 查询 result type；
- 查询 result component；
- 设置 contour；
- 设置 averaging；
- 设置 deformation；
- 设置 transparency；
- 设置 component 显隐；
- 设置标准视角；
- fit；
- 局部定位；
- 截图；
- 返回 ViewState；
- 恢复 ViewState；
- 心跳；
- 结构化错误。

### Web 结果工作台

- 项目概览；
- Run 概览；
- 模型信息；
- 网格信息；
- 材料和属性；
- 边界条件；
- 子工况；
- 应力热点；
- 位移热点；
- 多视角图片；
- 图片审核；
- 图片重拍；
- 图片版本；
- 恢复视图；
- 报告素材选择；
- 基础 PPT 预览；
- PPTX 导出。

## 3.2 V1 不实现

- 云端服务器；
- 用户登录；
- 权限；
- 多用户协作；
- 多工作站调度；
- 同一项目多个 HyperView 并行执行；
- 完全 Headless；
- 自动判断工程是否合格；
- 全自动报告结论；
- 所有求解器格式；
- 所有 H3D 结果类型；
- 远程浏览器访问；
- 移动端；
- macOS；
- Linux；
- 自动上传原始模型；
- 任意 Tcl 执行；
- 任意 Python 执行；
- 实时 3D Web 模型显示。

## 3.3 V2 方向

- 模态结果；
- 接触压力；
- 塑性应变；
- 焊缝热点；
- component 局部热点；
- 热点聚类去重；
- 网格质量问题定位；
- 多次 Run 对比；
- 自定义截图策略；
- 报告模板；
- PowerPoint 实际渲染预览；
- Word/PDF 导出；
- OUT 解析；
- OP2 解析。

## 3.4 V3 方向

- 中央服务器；
- 多工作站执行；
- 多用户审核；
- 组织级模板；
- 审批；
- 项目归档；
- 权限；
- 审计；
- 模型版本比较；
- 报告知识库。

---

# 4. 总体架构

## 4.1 进程结构

```text
CAEReportDesktop.exe
│
├── CAEReportServer.exe
│   ├── FastAPI
│   ├── SQLite
│   ├── WebSocket
│   ├── Vue 静态资源
│   └── 图片服务
│
├── CAEReportWorker.exe
│   ├── FEM Parser
│   ├── DAG Executor
│   ├── HyperView Session Manager
│   ├── Image Validator
│   └── Server Client
│
├── HyperView.exe
│   └── bootstrap.tcl
│
└── System Browser
    └── Vue Web Client
```

Web 工作台默认在系统浏览器中打开。

可预留后续内嵌 QWebEngineView，但 V1 不强制。

## 4.2 架构图

```text
┌──────────────────────────────────────────────────────────┐
│                  Desktop Project Manager                 │
│                    PySide6 / Qt Widgets                  │
│                                                          │
│  项目 / 文件 / 任务 / 进度 / 本地控制 / 诊断             │
└─────────────────────┬────────────────────────────────────┘
                      │ HTTP + WebSocket
                      ▼
┌──────────────────────────────────────────────────────────┐
│                  Local Application Server                │
│                  FastAPI + SQLite                        │
│                                                          │
│ 项目 / Run / Task / 结果 / 截图 / 报告 / Web API          │
└──────────────┬────────────────────────┬──────────────────┘
               │                        │
               │ HTTP / Internal API    │ HTTP / WebSocket
               ▼                        ▼
┌──────────────────────────────┐   ┌────────────────────────┐
│        Python Worker         │   │    Vue Web Client      │
│                              │   │                        │
│ FEM 解析                     │   │ 结果审查               │
│ DAG                          │   │ 图片审核               │
│ HyperView 管理               │   │ 视图恢复               │
│ 截图校验                     │   │ PPT 预览               │
└───────────────┬──────────────┘   └────────────────────────┘
                │ TCP JSONL
                ▼
┌──────────────────────────────────────────────────────────┐
│              HyperView 2019 + bootstrap.tcl              │
│                                                          │
│ H3D / Result / Contour / Camera / Visibility / Capture   │
└──────────────────────────────────────────────────────────┘
```

---

# 5. 技术栈

## 5.1 桌面项目管理器

```text
Python 3.12 x64
PySide6
Qt Widgets
QProcess
QFileDialog
QDesktopServices
QSystemTrayIcon
```

## 5.2 本地应用服务

```text
FastAPI
Uvicorn
Pydantic 2.x
SQLite
Python logging
WebSocket
```

## 5.3 Web 前端

```text
Vue 3
TypeScript
Vite
Pinia
Vue Router
Element Plus
ECharts
SortableJS
TipTap（V2 可启用）
```

## 5.4 Worker

```text
Python 3.12
Pydantic
Pillow
httpx
networkx（可选，用于 DAG）
```

DAG 也可以自行实现，不强制依赖 `networkx`。

## 5.5 FEM 解析

首版优先支持 OptiStruct / Nastran 风格 FEM。

推荐：

```text
自研流式 Parser
+
卡片级解析器
+
引用关系构建
```

不得直接把所有 FEM 行加载到 UI。

## 5.6 HyperView

```text
HyperView 2019
Tcl
TCP Socket
JSON Lines
```

## 5.7 PPT

推荐：

```text
ReportDocument JSON
+
Vue Preview
+
PptxGenJS
```

若首版打包 Node 复杂度过高，可临时采用：

```text
python-pptx
```

但最终设计仍保留统一 `ReportDocument`。

## 5.8 测试

```text
pytest
pytest-qt
pytest-asyncio
Ruff
mypy
Vitest
Playwright
```

---

# 6. 关键设计原则

## 6.1 桌面端负责项目和任务

桌面端负责：

- 创建项目；
- 删除项目；
- 文件选择；
- Run 配置；
- 任务控制；
- 进度；
- 本地进程；
- 日志和诊断。

桌面端不负责：

- 结果详情；
- 热点审查；
- 报告编排；
- PPT 页面设计。

## 6.2 Web 端负责结果和报告

Web 端负责：

- 项目结果展示；
- Run 结果展示；
- 热点详情；
- 图片审查；
- 恢复视图；
- 报告编排；
- PPT 预览；
- PPT 导出。

## 6.3 Server 是唯一业务状态源

只有 Local Application Server 可以写业务数据库。

禁止：

```text
Desktop → SQLite
Worker → SQLite
Vue → SQLite
Tcl → SQLite
```

允许：

```text
Desktop → Server API
Worker → Server API
Vue → Server API
Server → SQLite
```

## 6.4 Worker 只执行

Worker 不管理 UI，不保存最终业务状态。

## 6.5 Tcl 只控制 HyperView

Tcl 不负责：

- 项目；
- 数据库；
- FEM 文本解析；
- 任务调度；
- 报告；
- PPT。

## 6.6 H3D 与 FEM 默认只引用

- 不复制；
- 不上传；
- 不修改；
- 不删除；
- 保存绝对路径；
- 保存文件指纹。

## 6.7 每个项目支持多次 Run

```text
Project
├── Run 001
├── Run 002
└── Run 003
```

新 Run 不覆盖历史 Run。

## 6.8 截图必须绑定 ViewState

没有 ViewState 的截图不能视为完整结果。

---

# 7. 仓库结构

```text
cae-result-report-workbench/
├── README.md
├── SPEC.md
├── CHANGELOG.md
├── pyproject.toml
├── package.json
├── pnpm-workspace.yaml
├── ruff.toml
├── mypy.ini
│
├── desktop/
│   └── src/
│       └── cae_report_desktop/
│           ├── main.py
│           ├── app.py
│           ├── main_window.py
│           ├── process_supervisor.py
│           ├── server_client.py
│           ├── project_models.py
│           ├── pages/
│           ├── dialogs/
│           ├── widgets/
│           ├── services/
│           └── resources/
│
├── server/
│   └── src/
│       └── cae_report_server/
│           ├── main.py
│           ├── app.py
│           ├── api/
│           ├── websocket/
│           ├── application/
│           ├── domain/
│           ├── infrastructure/
│           ├── database/
│           ├── repositories/
│           ├── storage/
│           └── schemas/
│
├── worker/
│   └── src/
│       └── cae_report_worker/
│           ├── main.py
│           ├── worker_app.py
│           ├── server_client.py
│           ├── dag/
│           ├── executors/
│           ├── fem/
│           ├── hyperview/
│           ├── imaging/
│           ├── recovery/
│           └── schemas/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── stores/
│   │   ├── api/
│   │   ├── websocket/
│   │   ├── router/
│   │   ├── report/
│   │   ├── charts/
│   │   └── types/
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── hyperview/
│   ├── bootstrap.tcl
│   ├── protocol.tcl
│   ├── session.tcl
│   ├── model_service.tcl
│   ├── result_service.tcl
│   ├── display_service.tcl
│   ├── camera_service.tcl
│   ├── capture_service.tcl
│   ├── adapters/
│   │   └── hyperview_2019.tcl
│   └── tests/
│
├── report-exporter/
│   ├── src/
│   ├── package.json
│   └── templates/
│
├── shared/
│   ├── json-schema/
│   ├── protocol/
│   ├── constants/
│   └── test-fixtures/
│
├── migrations/
├── resources/
├── tools/
│   ├── fake_hyperview/
│   ├── create_sample_project.py
│   └── package.ps1
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── ui/
│   └── e2e/
│
└── docs/
    ├── architecture/
    ├── decisions/
    ├── protocol/
    ├── user-guide/
    └── development/
```

---

# 8. 本地工作区

默认：

```text
C:\CAEReportWorkbench
```

结构：

```text
C:\CAEReportWorkbench\
├── app\
│   ├── app.sqlite
│   ├── logs\
│   ├── runtime\
│   └── cache\
├── projects\
├── templates\
├── diagnostics\
└── crash\
```

## 8.1 项目目录

```text
projects\
└── <project_slug>_<short_id>\
    ├── project.json
    ├── project.sqlite
    ├── artifacts\
    ├── captures\
    ├── thumbnails\
    ├── reports\
    ├── exports\
    ├── logs\
    ├── cache\
    ├── runtime\
    └── backups\
```

V1 可以使用一个项目数据库。

全局数据库负责最近项目和设置。

---

# 9. 项目模型

## 9.1 Project

字段：

```text
id
name
code
product
analysis_type
solver
unit_system
description
workspace_path
status
created_at
updated_at
last_opened_at
```

状态：

```text
unconfigured
incomplete
invalid
ready
running
completed
completed_with_errors
stale
archived
```

## 9.2 ResultSource

字段：

```text
id
project_id
source_type
absolute_path
filename
extension
size_bytes
modified_time_ns
fingerprint_type
fingerprint
availability
last_verified_at
created_at
updated_at
```

source_type：

```text
fem
h3d
out
op2
xlsx
other
```

availability：

```text
unverified
available
changed
missing
unreadable
unsupported
```

## 9.3 AnalysisRun

字段：

```text
id
project_id
run_no
name
status
configuration_json
input_snapshot_json
created_at
started_at
finished_at
error_summary
```

状态：

```text
draft
queued
preparing
running
paused
cancel_requested
cancelled
completed
completed_with_errors
failed
interrupted
```

---

# 10. 文件指纹

大文件默认快速指纹：

```text
SHA-256(
    size
    + modified_time_ns
    + first_4MiB
    + last_4MiB
)
```

FEM 较小，可以默认完整 SHA-256。

H3D 默认快速指纹，完整 SHA-256 可选。

任何 Run 必须保存输入快照：

```json
{
  "fem": {
    "path": "",
    "fingerprint": ""
  },
  "h3d": {
    "path": "",
    "fingerprint": ""
  }
}
```

输入变化后，旧 Run 保持可浏览，新任务必须创建新 Run。

---

# 11. 桌面项目管理器规格

## 11.1 主界面

```text
┌───────────────────────────────────────────────────────────┐
│ 菜单：项目 / 设置 / 工具 / 帮助                           │
├──────────────┬────────────────────────────────────────────┤
│ 项目列表     │ 项目详情                                   │
│              │                                            │
│ 最近项目     │ 基本信息                                   │
│ 全部项目     │ FEM / H3D                                  │
│ 已归档       │ 任务配置                                   │
│              │ 当前 Run                                   │
│              │ 进度                                       │
├──────────────┴────────────────────────────────────────────┤
│ Server | Worker | HyperView | 当前任务                    │
└───────────────────────────────────────────────────────────┘
```

## 11.2 项目列表

显示：

- 项目名称；
- 项目编号；
- FEM；
- H3D；
- 状态；
- 最近 Run；
- 最近更新时间；
- 进度；
- Web 结果入口。

## 11.3 新建项目向导

### Step 1 基本信息

必填：

- 项目名称；
- 项目工作目录。

可选：

- 项目编号；
- 产品；
- 分析类型；
- 求解器；
- 单位制；
- 描述。

### Step 2 输入文件

必选：

- FEM；
- H3D。

可选：

- OUT；
- OP2；
- Excel。

### Step 3 校验

- 路径；
- 可读性；
- 文件大小；
- 指纹；
- FEM 格式；
- H3D 基础打开测试可选。

### Step 4 任务类型

允许多选。

### Step 5 创建

创建项目和 Draft Run。

## 11.4 项目操作

- 打开；
- 编辑；
- 删除项目数据；
- 从列表移除；
- 复制；
- 归档；
- 打开文件夹；
- 打开 FEM 所在目录；
- 打开 H3D 所在目录；
- 打开 Web 结果；
- 创建新 Run。

## 11.5 删除规则

不得删除外部 FEM/H3D。

删除项目时：

- 二次确认；
- 显示将删除内容；
- 优先移动到回收站；
- 可选择只移除列表记录。

---

# 12. 任务类型

任务类型必须作为高层业务任务，不暴露 Tcl 细节。

## 12.1 固定任务类型

### `fem.model_summary`

提取：

- 节点数；
- 单元数；
- component；
- property；
- material；
- 坐标系；
- INCLUDE；
- 模型包围盒。

### `fem.mesh_summary`

提取：

- 单元类型；
- 维度；
- component 单元数；
- 网格尺寸；
- 基础质量统计；
- 一维/二维/三维比例。

### `fem.material_property`

提取：

- 材料；
- 属性；
- component-property-material 关系；
- 壳厚；
- 未引用项。

### `fem.boundary_conditions`

提取：

- SPC；
- MPC；
- FORCE；
- MOMENT；
- GRAV；
- LOAD；
- DLOAD；
- RBE2；
- RBE3；
- CONM2；
- 接触；
- 预紧；
- 连接卡片。

### `fem.subcases`

提取：

- SUBCASE；
- LOAD；
- SPC；
- METHOD；
- NLPARM；
- 输出请求；
- 引用关系。

### `h3d.result_index`

提取：

- subcase；
- simulation；
- result type；
- result component；
- 模态；
- 时间步。

### `result.stress_hotspots`

提取：

- 最大应力；
- 前 N 热点；
- component；
- element；
- 坐标；
- 数值；
- 多视角截图。

### `result.displacement_hotspots`

提取：

- 最大位移；
- node；
- component；
- 坐标；
- 位移分量；
- 多视角截图。

### `result.modal_summary`

V1 可作为可选或隐藏功能。

### `capture.standard_views`

生成：

- 整体模型；
- 网格；
- 边界条件；
- 整体应力；
- 整体位移；
- 标准方向图。

### `report.prepare`

构建 Web 与 PPT 数据。

## 12.2 任务依赖

示例：

```text
result.stress_hotspots
└── h3d.result_index

result.displacement_hotspots
└── h3d.result_index

report.prepare
├── fem.model_summary
├── fem.mesh_summary
├── fem.boundary_conditions
├── fem.subcases
├── h3d.result_index
└── selected result tasks
```

## 12.3 自动依赖

用户选择上层任务时，系统自动加入依赖。

桌面端显示：

```text
已自动加入：
- H3D 结果索引
- 子工况索引
```

---

# 13. DAG 与任务模型

## 13.1 RunTask

字段：

```text
id
run_id
task_type
parent_task_id
status
progress_current
progress_total
progress_message
configuration_json
input_hash
output_manifest_json
attempt_count
max_attempts
created_at
started_at
finished_at
heartbeat_at
error_code
error_message
```

状态：

```text
pending
blocked
queued
running
paused
completed
completed_with_warnings
retry_wait
failed
cancelled
interrupted
skipped
```

## 13.2 子任务

热点任务需拆分为原子任务：

```text
stress hotspot analysis
├── subcase A
│   ├── identify
│   ├── global capture
│   ├── hotspot 1 iso
│   ├── hotspot 1 front
│   └── ...
└── subcase B
```

## 13.3 幂等性

每个任务保存：

```text
input fingerprint
task configuration hash
software version
script version
```

相同输入和配置可复用缓存。

## 13.4 取消

当前原子任务结束后取消。

## 13.5 暂停

当前原子任务结束后暂停。

---

# 14. 桌面端进度

## 14.1 总体

```text
总体进度：68%
已完成：82
执行中：1
等待：37
失败：2
```

## 14.2 阶段

```text
✓ 文件校验
✓ FEM 模型信息
✓ 网格统计
✓ 边界条件
✓ H3D 结果索引
● 应力热点 28/54
○ 位移热点 0/18
○ 报告数据
```

## 14.3 当前任务

```text
工况：FULL_LOAD
结果：Element Stresses / vonMises
目标：FRAME_LEFT / E123456
视角：Local Isometric
```

## 14.4 任务完成

按钮：

- 打开 Web 结果；
- 打开项目文件夹；
- 查看失败任务；
- 新建 Run；
- 重新运行失败项。

---

# 15. 本地应用服务

## 15.1 服务职责

- 业务状态；
- 项目 CRUD；
- Run；
- Task；
- 结果数据；
- 图片；
- 审核；
- 报告；
- Web API；
- WebSocket；
- Worker API；
- Desktop API；
- 数据库；
- 静态前端资源。

## 15.2 启动

Desktop 启动 Server：

```text
127.0.0.1:<dynamic_port>
```

Server 只监听 loopback。

## 15.3 健康检查

```http
GET /health
```

返回：

```json
{
  "status": "ready",
  "version": "1.0.0",
  "database": "ok",
  "worker": "connected"
}
```

---

# 16. API 设计

## 16.1 Projects

```text
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/archive
POST   /api/v1/projects/{project_id}/reveal-folder
```

## 16.2 Sources

```text
GET    /api/v1/projects/{project_id}/sources
POST   /api/v1/projects/{project_id}/sources
PATCH  /api/v1/sources/{source_id}
POST   /api/v1/sources/{source_id}/verify
POST   /api/v1/sources/{source_id}/relocate
```

## 16.3 Runs

```text
GET    /api/v1/projects/{project_id}/runs
POST   /api/v1/projects/{project_id}/runs
GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/start
POST   /api/v1/runs/{run_id}/pause
POST   /api/v1/runs/{run_id}/resume
POST   /api/v1/runs/{run_id}/cancel
POST   /api/v1/runs/{run_id}/retry-failed
```

## 16.4 Tasks

```text
GET /api/v1/runs/{run_id}/tasks
GET /api/v1/tasks/{task_id}
GET /api/v1/tasks/{task_id}/events
```

## 16.5 Model data

```text
GET /api/v1/runs/{run_id}/model-summary
GET /api/v1/runs/{run_id}/mesh-summary
GET /api/v1/runs/{run_id}/components
GET /api/v1/runs/{run_id}/materials
GET /api/v1/runs/{run_id}/properties
GET /api/v1/runs/{run_id}/boundary-conditions
GET /api/v1/runs/{run_id}/subcases
```

## 16.6 Results

```text
GET /api/v1/runs/{run_id}/result-index
GET /api/v1/runs/{run_id}/hotspots
GET /api/v1/hotspots/{hotspot_id}
```

## 16.7 Captures

```text
GET  /api/v1/hotspots/{hotspot_id}/captures
GET  /api/v1/captures/{capture_id}
POST /api/v1/captures/{capture_id}/approve
POST /api/v1/captures/{capture_id}/reject
POST /api/v1/captures/{capture_id}/recapture
POST /api/v1/captures/{capture_id}/restore-view
GET  /api/v1/capture-versions/{version_id}/image
GET  /api/v1/capture-versions/{version_id}/thumbnail
```

## 16.8 Reports

```text
GET  /api/v1/runs/{run_id}/report
PUT  /api/v1/runs/{run_id}/report
POST /api/v1/runs/{run_id}/report/generate-default
POST /api/v1/runs/{run_id}/report/export-pptx
GET  /api/v1/report-exports/{export_id}
```

---

# 17. WebSocket 事件

端点：

```text
/ws/v1/events
```

事件：

```text
server.status
worker.status
hyperview.status
project.updated
run.created
run.started
run.progress
run.paused
run.completed
run.failed
task.started
task.progress
task.completed
task.failed
capture.created
capture.updated
report.export_started
report.export_completed
```

WebSocket 只推送事件。

命令通过 REST。

---

# 18. Worker 设计

## 18.1 Worker 生命周期

```text
启动
→ 注册到 Server
→ 获取待执行 Run
→ 领取任务
→ 执行
→ 提交结果
→ 更新心跳
```

## 18.2 Server Client

Worker 通过本地 HTTP 调用 Server。

Worker 不直接写 SQLite。

## 18.3 Worker 模块

```text
worker/
├── dag_executor
├── fem_executor
├── h3d_executor
├── capture_executor
├── report_data_executor
├── hyperview_session_manager
├── image_validator
├── retry_policy
└── recovery_manager
```

## 18.4 Worker 崩溃

Server 将运行中任务标记为 interrupted。

Desktop 自动重启 Worker。

Worker 重启后恢复。

---

# 19. FEM Parser

## 19.1 支持范围

V1 优先支持：

- OptiStruct/Nastran `.fem`；
- INCLUDE；
- BEGIN BULK；
- ENDDATA；
- 基础固定/长格式；
- continuation。

## 19.2 必须解析的卡片

### 结构

```text
GRID
CTRIA3
CQUAD4
CTETRA
CPENTA
CHEXA
CBAR
CBEAM
CBUSH
RBE2
RBE3
CONM2
```

### 属性

```text
PSHELL
PCOMP
PSOLID
PBAR
PBEAM
PBUSH
```

### 材料

```text
MAT1
MAT8
```

### 载荷与约束

```text
SPC
SPC1
SPCADD
FORCE
MOMENT
GRAV
LOAD
DLOAD
MPC
MPCADD
```

### 工况

```text
SUBCASE
LOAD
SPC
METHOD
NLPARM
```

### 接触和连接

按照实际模型逐步支持。

## 19.3 解析策略

- 流式读取；
- 保留源文件行号；
- 保留 INCLUDE 来源；
- 不要求一次加载所有原始文本；
- 构建 ID 索引；
- 构建引用关系；
- 对未知卡片保留统计。

## 19.4 解析输出

```text
model summary
components
properties
materials
elements
nodes
subcases
loads
constraints
connections
include graph
warnings
```

---

# 20. 模型信息展示

Web 页面必须展示：

- 节点数；
- 单元数；
- component 数；
- property 数；
- material 数；
- 子工况数；
- INCLUDE 数；
- 一维/二维/三维单元；
- 包围盒；
- 总质量（若可计算）；
- 未引用实体；
- 解析警告。

支持：

- 搜索；
- 筛选；
- 排序；
- 导出 CSV。

---

# 21. 网格信息

V1：

- 单元类型统计；
- 维度统计；
- component 单元数；
- 平均网格尺寸；
- 边长分布；
- 三角形/四边形比例；
- 实体单元类型；
- RBE2/RBE3 数量；
- 孤立节点基础检查；
- 重复节点可选；
- 未引用节点。

V2：

- Jacobian；
- Warpage；
- Skew；
- Aspect；
- Min/Max angle；
- Taper；
- 网格质量定位。

---

# 22. 材料和属性

展示：

- material 表；
- property 表；
- component-property；
- property-material；
- 壳厚；
- 材料 E、ν、ρ；
- 未引用 material；
- 未引用 property；
- component 缺失 property；
- property 缺失 material。

---

# 23. 边界条件

分类：

- 约束；
- 载荷；
- 重力；
- 刚性连接；
- 质量点；
- 接触；
- 螺栓预紧；
- 其他连接。

展示：

- ID；
- 类型；
- 引用实体；
- 数值；
- 坐标系；
- 所属 LOAD/SPC；
- 所属 SUBCASE；
- 来源文件；
- 行号。

---

# 24. HyperView Session

## 24.1 Session 状态

```text
created
starting
waiting_for_tcl
connected
loading_h3d
indexing
ready
busy
unresponsive
crashed
stopping
stopped
failed
```

## 24.2 Session Manager

负责：

```text
start
connect
open_h3d
ensure_ready
execute
restore_view
bring_to_front
shutdown
kill
restart
```

## 24.3 启动上下文

```json
{
  "session_id": "",
  "run_id": "",
  "h3d_path": "",
  "worker_host": "127.0.0.1",
  "worker_port": 0,
  "auth_token": "",
  "protocol_version": "1.0"
}
```

通过环境变量传入 context path。

---

# 25. Worker/Tcl 协议

## 25.1 传输

```text
TCP
127.0.0.1
JSON Lines
UTF-8
```

## 25.2 握手

Tcl 主动连接 Worker。

必须提供：

- session_id；
- token；
- HyperView 版本；
- protocol version；
- capabilities。

## 25.3 命令

```text
session.ping
session.capabilities
source.open
source.status
source.index
view.apply
view.read
capture.execute
view.restore
session.shutdown
```

禁止：

```text
tcl.eval
shell.exec
file.delete
```

## 25.4 错误

统一：

```json
{
  "success": false,
  "error": {
    "code": "",
    "message": "",
    "details": {}
  }
}
```

---

# 26. H3D 索引

V1 必须提取：

- model；
- subcase；
- simulation；
- result type；
- result component；
- modal frequency；
- time/load step。

结果写入 Server。

索引必须绑定 H3D fingerprint。

---

# 27. 热点分析

## 27.1 热点定义

热点记录：

```text
id
run_id
subcase
simulation
result_type
result_component
rank
entity_type
entity_id
component_id
component_name
value
unit
coordinate
cluster_id
classification
review_status
```

## 27.2 应力热点

V1：

- 每个 subcase 最大值；
- 前 N 个候选；
- 可配置排除 component；
- 可配置 top N；
- 可配置热点间最小距离；
- 可配置 component 内 top N。

## 27.3 位移热点

- 最大位移；
- 位移合量；
- 分量；
- node；
- 坐标；
- component。

## 27.4 热点去重

V1 简化：

- 同一 component；
- 距离阈值；
- 保留最大值。

V2 增强聚类。

## 27.5 分类

Web 可标记：

```text
valid
singularity
contact_singularity
mesh_issue
boundary_issue
ignore
unknown
```

---

# 28. 截图策略

## 28.1 热点默认图片

每个热点默认生成：

- 整体定位；
- 局部等轴测；
- 前；
- 后；
- 左；
- 右；
- 顶；
- component isolate；
- component + context。

可通过任务配置减少。

## 28.2 标准图

- 整体模型；
- 网格；
- 约束；
- 载荷；
- 整体应力；
- 整体位移。

## 28.3 截图分辨率

默认：

```text
1920 × 1080
PNG
```

## 28.4 文件流程

```text
临时截图
→ 校验
→ 原子移动
→ 缩略图
→ SHA-256
→ 数据库版本
```

---

# 29. ViewState

必须保存：

```json
{
  "schema_version": 1,
  "source_fingerprint": "",
  "subcase": {},
  "simulation": {},
  "result": {},
  "contour": {
    "enabled": true,
    "averaging": "",
    "legend_min": null,
    "legend_max": null,
    "precision": 0
  },
  "deformation": {
    "enabled": false,
    "scale_mode": "",
    "scale": 1.0
  },
  "visibility": {
    "visible_components": [],
    "hidden_components": []
  },
  "target": {
    "entity_type": "",
    "entity_id": null,
    "component_id": null,
    "coordinate": null
  },
  "camera": {
    "preset": "",
    "matrix": null,
    "center": null,
    "zoom": null
  },
  "render": {
    "transparency": false,
    "legend_visible": true,
    "background": null
  }
}
```

HyperView 2019 不支持字段必须返回 null。

---

# 30. 图片与版本

## 30.1 Capture

表示逻辑图片槽位。

## 30.2 CaptureVersion

表示实际图片版本。

```text
capture
├── v001
├── v002
└── v003 current
```

## 30.3 审核状态

```text
pending
approved
rejected
recapture_requested
superseded
```

---

# 31. Web 工作台页面

## 31.1 Project Overview

- 项目；
- 输入文件；
- 最新 Run；
- 状态；
- 模型规模；
- 子工况；
- 热点；
- 图片；
- 报告。

## 31.2 Run Overview

- Run 配置；
- 输入指纹；
- 任务；
- 成功/失败；
- 软件版本；
- 日志；
- 结果摘要。

## 31.3 Model

- 模型统计；
- component；
- property；
- material；
- INCLUDE。

## 31.4 Mesh

- 单元类型；
- 网格尺寸；
- component 网格；
- 质量统计。

## 31.5 Boundary Conditions

- 约束；
- 载荷；
- 连接；
- 工况引用。

## 31.6 Subcases

每个子工况展示：

- FEM 定义；
- H3D 结果；
- 最大应力；
- 最大位移；
- 热点；
- 图片；
- 报告状态。

## 31.7 Hotspots

- 列表；
- 筛选；
- 排序；
- 审核；
- 批量操作。

## 31.8 Hotspot Detail

- 数值；
- entity；
- component；
- property；
- material；
- 坐标；
- 多视角图片；
- 版本；
- 工程说明；
- 恢复视图；
- 重拍；
- 加入报告。

## 31.9 Report

- 章节；
- 页面；
- 页面缩略图；
- PPT 预览；
- 导出。

---

# 32. 恢复 HyperView 视图

## 32.1 Web 操作

按钮：

- 恢复到后台；
- 恢复并显示 HyperView。

## 32.2 流程

```text
Web
→ Server
→ 创建高优先级 restore task
→ Worker
→ 启动/复用 HyperView
→ 加载 H3D
→ apply ViewState
→ 可选前台显示
```

## 32.3 恢复结果

```text
exact
partial
failed
```

必须显示缺失项。

---

# 33. 报告文档模型

## 33.1 ReportDocument

```json
{
  "id": "",
  "run_id": "",
  "template_id": "",
  "page_size": "LAYOUT_WIDE",
  "theme": {},
  "sections": [],
  "slides": []
}
```

## 33.2 Slide

```json
{
  "id": "",
  "title": "",
  "layout": "",
  "elements": [],
  "notes": ""
}
```

## 33.3 Element

类型：

```text
text
image
table
chart
shape
```

坐标使用统一逻辑坐标。

---

# 34. 默认 PPT 结构

```text
1. 封面
2. 项目说明
3. 计算模型
4. 网格信息
5. 材料与属性
6. 边界条件
7. 工况说明
8. 应力结果
9. 位移结果
10. 热点详情
11. 结论
12. 附录
```

用户可修改。

---

# 35. PPT 预览

Web 使用固定 16:9 画布。

支持：

- 页面缩略图；
- 页面排序；
- 添加；
- 删除；
- 复制；
- 图片替换；
- 文字编辑；
- 表格；
- 图表；
- 自动布局；
- 模板。

V1 可限制为基础布局。

---

# 36. PPT 导出

## 36.1 推荐

PptxGenJS。

## 36.2 导出流程

```text
ReportDocument
→ Export Job
→ PptxGenJS
→ PPTX
→ 保存 exports
→ Web 下载
```

## 36.3 一致性

预览与导出使用相同逻辑坐标和布局规则。

## 36.4 可选实际预览

V2：

- PowerPoint COM；
- 导出 PDF；
- 页面截图；
- 与 Web 预览比较。

---

# 37. 数据库表

至少包含：

```text
schema_migrations
settings
projects
result_sources
analysis_runs
run_tasks
task_events
model_summaries
components
nodes_summary
elements_summary
materials
properties
component_property_links
subcases
loads
constraints
connections
h3d_subcases
h3d_simulations
h3d_result_types
hotspots
captures
capture_versions
review_actions
view_restore_requests
report_documents
report_slides
report_exports
application_events
```

避免首版存储全量节点和单元明细，除非任务需要。

可按统计与按需明细分层。

---

# 38. SQLite 规则

- foreign_keys ON；
- WAL；
- busy_timeout；
- 短事务；
- Server 唯一写入；
- migration；
- 自动备份；
- integrity_check；
- 失败只读模式；
- 参数化 SQL；
- 不在事务中等待 Worker。

---

# 39. 日志

日志：

```text
desktop.jsonl
server.jsonl
worker.jsonl
project.jsonl
hyperview-session.jsonl
```

字段：

```text
timestamp
level
process
event
project_id
run_id
task_id
session_id
message
details
```

---

# 40. 错误码

至少：

```text
CONFIG_INVALID
WORKSPACE_NOT_WRITABLE
PROJECT_CREATE_FAILED
PROJECT_DELETE_FAILED
SOURCE_MISSING
SOURCE_CHANGED
SOURCE_UNREADABLE
FEM_PARSE_FAILED
FEM_INCLUDE_MISSING
H3D_INDEX_FAILED
HV_START_FAILED
HV_CONNECT_TIMEOUT
HV_LOAD_FAILED
HV_COMMAND_FAILED
HV_COMMAND_TIMEOUT
HV_SESSION_CRASHED
HV_SESSION_UNRESPONSIVE
CAPTURE_FAILED
CAPTURE_INVALID
VIEW_RESTORE_PARTIAL
VIEW_RESTORE_FAILED
REPORT_EXPORT_FAILED
DB_MIGRATION_FAILED
DB_INTEGRITY_FAILED
TASK_CANCELLED
TASK_RETRY_EXHAUSTED
```

---

# 41. 安全

- 仅 loopback；
- 随机端口；
- Session token；
- Tcl 白名单；
- 不允许任意脚本；
- 路径规范化；
- 输出限制在项目目录；
- 防路径穿越；
- 消息大小限制；
- SQL 参数化；
- 不上传 FEM/H3D；
- 不记录 token；
- 不删除原始文件。

---

# 42. 测试

## 42.1 单元测试

- Project；
- fingerprint；
- DAG；
- task state；
- parser；
- ViewState；
- hotspot clustering；
- report layout；
- API schema；
- image validator。

## 42.2 Integration

- Desktop→Server；
- Server→Worker；
- Worker→Fake HyperView；
- FEM parse；
- Run；
- Capture；
- Report export。

## 42.3 Fake HyperView

必须实现：

- handshake；
- source.open；
- source.index；
- view.apply；
- view.read；
- capture；
- restore；
- timeout；
- crash；
- partial capability。

## 42.4 UI 测试

Desktop：

- create project；
- select files；
- select tasks；
- start；
- progress；
- cancel；
- open web。

Web：

- overview；
- hotspots；
- review；
- restore；
- report；
- export。

## 42.5 E2E

真实 HyperView 2019：

- 启动；
- 打开 H3D；
- 索引；
- 应力图；
- 位移图；
- 多视角；
- 20 张连续截图；
- 恢复视图；
- 崩溃恢复；
- 中文路径；
- 机械盘 H3D + SSD 工作区。

---

# 43. POC 必须验证

Phase 0 必须验证：

1. HyperView 2019 启动命令；
2. `-tcl` 行为；
3. 自动打开 H3D；
4. 加载完成判定；
5. result index；
6. contour；
7. averaging；
8. transparency；
9. deformation；
10. component isolate；
11. standard views；
12. local fit；
13. PNG；
14. 分辨率；
15. camera read/restore；
16. lock screen；
17. minimize；
18. Remote Desktop；
19. Tcl JSON；
20. Tcl socket；
21. License 行为。

记录：

```text
docs/architecture/hyperview-2019-poc.md
```

---

# 44. 分阶段实施

## Phase 0 — HyperView POC

- Python 启动 HyperView；
- Tcl 回连；
- H3D；
- result index；
- PNG；
- ViewState；
- 记录能力。

## Phase 1 — 工程骨架

- Desktop；
- Server；
- Worker；
- Vue；
- IPC；
- logging；
- Fake HyperView；
- CI。

## Phase 2 — Project Manager

- 项目 CRUD；
- 文件选择；
- 指纹；
- 新建向导；
- 项目目录；
- Source 校验。

## Phase 3 — Run 与任务

- 任务多选；
- DAG；
- Run；
- progress；
- pause；
- cancel；
- retry。

## Phase 4 — FEM 解析

- model；
- mesh；
- material；
- property；
- boundary；
- subcase。

## Phase 5 — H3D 与截图

- index；
- stress；
- displacement；
- capture；
- ViewState；
- image validation。

## Phase 6 — Web 结果

- overview；
- model；
- mesh；
- BC；
- subcase；
- hotspot；
- capture review。

## Phase 7 — Restore View

- restore task；
- exact/partial；
- bring to front；
- recapture。

## Phase 8 — PPT

- ReportDocument；
- preview；
- default report；
- PPTX export。

## Phase 9 — Recovery & Packaging

- crash recovery；
- diagnostics；
- build；
- installer；
- clean Windows test。

---

# 45. 验收标准

## AC-001 创建项目

可创建项目，并选择 FEM/H3D。

## AC-002 不复制原始文件

项目目录不包含 FEM/H3D 副本。

## AC-003 项目删除安全

删除项目不删除外部 FEM/H3D。

## AC-004 任务多选

用户可多选任务，系统自动补依赖。

## AC-005 后台执行

HyperView 后台执行，Desktop 保持响应。

## AC-006 进度

Desktop 显示总体、阶段、当前任务。

## AC-007 FEM 信息

Web 显示节点、单元、component、property、material。

## AC-008 网格

Web 显示网格类型和统计。

## AC-009 边界条件

Web 显示载荷、约束、连接和子工况引用。

## AC-010 H3D 索引

Web 显示实际 subcase 和 result。

## AC-011 应力热点

每个选定子工况有应力热点。

## AC-012 位移热点

每个选定子工况有位移热点。

## AC-013 多视角

热点至少生成整体、局部等轴测和标准方向。

## AC-014 图片审核

Web 可批准、否决、重拍。

## AC-015 图片版本

重拍不覆盖旧版本。

## AC-016 恢复视图

Web 可恢复到 HyperView。

## AC-017 前台显示

恢复后可将 HyperView 置于前台。

## AC-018 PPT 预览

Web 可预览默认报告。

## AC-019 PPT 导出

可导出可打开的 PPTX。

## AC-020 历史 Run

新 Run 不覆盖旧 Run。

## AC-021 H3D 丢失

旧结果仍可浏览，新任务被禁止。

## AC-022 HyperView 崩溃

可检测并按策略恢复。

## AC-023 Worker 崩溃

可重启并恢复 interrupted 任务。

## AC-024 离线

无网络可完整使用。

## AC-025 安装

干净 Windows 可运行。

---

# 46. 性能目标

- Desktop 普通交互 < 200 ms；
- 项目打开不含 H3D < 2 s；
- 1000 任务列表流畅；
- 1000 缩略图延迟加载；
- WebSocket 进度延迟 < 500 ms；
- H3D 不复制；
- 截图落 SSD 工作区；
- UI 不因解析和截图阻塞。

---

# 47. Codex 实施约束

## 47.1 顺序

必须先完成 Phase 0。

不得先做大规模 UI。

## 47.2 代码

- pathlib；
- 类型标注；
- Pydantic DTO；
- 分层；
- 无 UI SQL；
- 无 Worker SQL；
- 无 Desktop subprocess 业务；
- 无 Tcl eval；
- 无万能 command；
- 无静默异常；
- 无硬编码路径；
- 无硬编码盘符；
- 无固定超长 sleep。

## 47.3 每阶段

- 测试先行；
- 实现；
- Ruff；
- mypy；
- pytest；
- Vitest；
- README；
- 可运行提交。

---

# 48. Definition of Done

V1 完成必须满足：

- Phase 0～9 完成；
- 所有 V1 验收通过；
- 真实 HyperView 2019 E2E 通过；
- 自动化测试通过；
- 无阻断缺陷；
- 数据库迁移通过；
- 安装包通过；
- FEM/H3D 不被复制；
- Desktop 任务期间响应；
- Web 可完整审查结果；
- 截图有 ViewState；
- Restore 可用；
- PPTX 可打开；
- 崩溃不丢失已完成结果；
- 用户指南、诊断指南和开发指南齐全。

---

# 49. 实施起点

Codex 第一批工作必须为：

```text
1. 初始化 monorepo
2. 建立 Server 健康检查
3. 建立 Desktop 启动 Server
4. 建立 Worker 注册
5. 建立 Fake HyperView
6. 建立 Tcl handshake
7. 真实 HyperView POC
8. 自动打开 H3D
9. 获取 result index
10. 生成 PNG
11. 记录 POC
12. 再进入 Project Manager
```

最终原则：

> 底层链路未稳定前，不允许用 UI 进度条掩盖问题。
