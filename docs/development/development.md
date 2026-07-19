# 开发指南

项目要求 Python 3.12+、Node 20+。执行 `pip install -e ".[dev,desktop]"` 和 `npm --prefix frontend install` 后可运行测试。

任何业务状态变化必须经过 Server API；不得从 Desktop、Worker、Vue 或 Tcl 直接写 SQLite。新的 HyperView 能力必须加入协议白名单和 Fake HyperView contract test，禁止增加 `tcl.eval`、`shell.exec` 或通用脚本入口。

每次变更至少运行：

```powershell
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\ruff.exe check .
& .\.venv\Scripts\mypy.exe
npm --prefix frontend run test
npm --prefix frontend run build
```

真实 HyperView 变更还要运行 `tools/run_hv_poc.py --h3d <fixture>`。Fake 测试不能替代真实 HyperView 2019 E2E。

