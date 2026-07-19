# 诊断指南

常见错误码：

- `SOURCE_MISSING`：源文件不存在；重新定位 FEM/H3D。
- `SOURCE_CHANGED`：路径相同但指纹变化；验证后创建新 Run。
- `FEM_PARSE_FAILED`：检查 FEM 卡片格式和 INCLUDE 路径。
- `FEM_INCLUDE_MISSING`：INCLUDE 文件不存在或不可读。
- `HV_START_FAILED`：检查 HyperView 2019 路径和许可证。
- `HV_CONNECT_TIMEOUT`：检查 Tcl 是否执行、loopback 是否被安全软件拦截。
- `H3D_INDEX_FAILED`：H3D 未加载或结果 API 不可用。
- `CAPTURE_INVALID`：图片无 ViewState、文件损坏或分辨率不符合要求。
- `VIEW_RESTORE_PARTIAL`：HyperView 2019 不支持 ViewState 的部分字段；工作台会列出缺失项。
- `REPORT_EXPORT_FAILED`：检查项目 `exports` 目录可写和图片仍存在。

日志字段统一包含 timestamp、level、process、event、project/run/task/session id、message 和 details。导出诊断包时不包含 FEM/H3D 或 session token。

