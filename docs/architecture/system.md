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
- Desktop 是发布程序的顶层进程，通过 Windows Job Object 托管 Server、Worker
  以及 Worker 启动的 HyperView 进程树；正常关闭先请求优雅退出，异常退出时由
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 统一回收。
- Server 是唯一业务状态写入者，并提供 Vue 静态资源、REST、WebSocket、图片和 PPTX。
- Worker 只执行 FEM、DAG、HyperView、图片和恢复任务，所有结果通过 API 提交。
- Tcl 只调用 HyperView 白名单能力，不解析 FEM、不访问数据库、不执行任意 Tcl。
- FEM/H3D 只保存绝对路径和指纹，Run 固化输入快照。
- “重新运行”会重新校验原绝对路径、接受当前文件指纹并创建新的递增 Run；
  旧 Run 的任务、结果、截图版本和报告保持只读归档，不被新结果覆盖。

数据库启用 foreign keys、WAL、5 秒 busy timeout、短事务和 migration 版本。截图由逻辑 `Capture` 与不可覆盖的 `CaptureVersion` 组成，每个版本必须绑定 ViewState 和源指纹。
