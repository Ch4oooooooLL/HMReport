# 系统架构

本地工作台由四个职责隔离的进程组成：

```text
PySide6 Desktop ──HTTP/WebSocket──> FastAPI Server ──SQLite
                                         ▲
                                         │ HTTP
                                    Python Worker
                                         │ TCP JSONL / loopback / token
                                         ▼
                                HyperView 2019 + Tcl
```

- Desktop 只管理项目、源文件选择、Run 和本地进程，不访问 SQLite。
- Server 是唯一业务状态写入者，并提供 Vue 静态资源、REST、WebSocket、图片和 PPTX。
- Worker 只执行 FEM、DAG、HyperView、图片和恢复任务，所有结果通过 API 提交。
- Tcl 只调用 HyperView 白名单能力，不解析 FEM、不访问数据库、不执行任意 Tcl。
- FEM/H3D 只保存绝对路径和指纹，Run 固化输入快照。

数据库启用 foreign keys、WAL、5 秒 busy timeout、短事务和 migration 版本。截图由逻辑 `Capture` 与不可覆盖的 `CaptureVersion` 组成，每个版本必须绑定 ViewState 和源指纹。

