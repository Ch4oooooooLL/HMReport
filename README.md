# CAE 结果分析与报告工作台

面向 Windows 10/11 与 HyperView 2019 的本地优先 CAE 项目、结果审查和 PPT 报告工作台。

项目由四个隔离进程组成：PySide6 桌面项目管理器、FastAPI 本地服务、Python Worker、HyperView/Tcl；Vue 3 工作台由本地服务提供。Server 是 SQLite 的唯一写入者，FEM/H3D 始终只保存外部绝对路径和指纹，不复制、不修改、不删除源文件。

## 开发启动

```powershell
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e ".[dev,desktop]"
npm --prefix frontend install
npm --prefix frontend run build
& .\.venv\Scripts\cae-report-server.exe --workspace .\workspace
```

另开终端启动 Worker：

```powershell
$env:CAE_REPORT_FAKE_HV = "1"
& .\.venv\Scripts\cae-report-worker.exe --server http://127.0.0.1:8765
```

桌面端会自动启动/复用 Server 和 Worker：

```powershell
& .\.venv\Scripts\cae-report-desktop.exe
```

## 验证

```powershell
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\ruff.exe check .
& .\.venv\Scripts\mypy.exe
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

使用 `python tools/create_sample_project.py` 可生成外部 FEM/H3D 占位输入并跑通 Fake HyperView 链路。真实 HyperView POC 见 `docs/architecture/hyperview-2019-poc.md`。

## 发布包

运行 `tools/package.ps1` 生成 Windows 发布包。用户直接运行压缩包根目录的
`CAEReportDesktop.exe`；`CAEReportServer` 和 `CAEReportWorker` 是内部进程目录，需与主程序保持相对位置。

原始 spec 仅保留在源码仓库中，不进入发布压缩包。
