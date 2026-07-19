# HyperView 2019 POC

## 结论

2026-07-19 在本机 Altair HyperView 2019 上完成了握手和真实 FEM/H3D
业务链路验证：

- 可执行文件：`C:\Program Files\Altair\2019\hw\bin\win64\hw.exe`
- 启动参数：`/clientconfig hwpost.dat -tcl hyperview/bootstrap.tcl`
- Tcl 脚本能读取环境变量传入的 JSON context；
- Tcl 能主动连接 Worker 在 `127.0.0.1` 上建立的随机端口；
- session token、session id、协议版本和 capabilities 握手通过；
- `session.ping` 返回 `ready` 和 `HyperView 2019`；
- `session.shutdown` 后 HyperView 正常退出；
- 实测启动到握手完成为 3.242 秒。
- 实际 H3D 可加载并索引出 6 个 subcase、37 个 simulation 和 6 个 result type；
- 实际查询得到最大 von Mises 应力 2084 MPa、最大位移 3120 mm；
- 53 张真实截图均为 1920×1080，四个标准方向的图像校验和不同；
- 包含中文项目名的会话目录可以启动，不再把 `context.json` 绝对路径解码成乱码。
- `-b` 无界面批处理模式可以完成索引、结果查询和 PNG 捕获；
- Run 完成后会话自动退出；重拍/恢复动作按需启动独立会话并在动作后退出。

实测输出保存在本地、Git 忽略的 `runtime/poc/handshake-result.json`。

## 已验证能力矩阵

| POC 项 | 状态 | 证据/备注 |
|---|---|---|
| HyperView 2019 启动命令 | 通过 | 本机真实进程 |
| `-b` 后台批处理 | 通过 | 无 GUI 完成 53 张真实捕获 |
| `-tcl` 行为 | 通过 | `bootstrap.tcl` 被执行 |
| Tcl TCP socket | 通过 | 主动回连随机 loopback 端口 |
| Tcl JSON Lines | 通过 | handshake、ping、shutdown |
| Session token | 通过 | 随机 32-byte token，日志不记录 token |
| 命令白名单 | 通过 | 协议层拒绝 `tcl.eval` 等任意命令 |
| 自动打开 H3D | 通过 | `optistruct_feature_model.h3d` 实机加载 |
| 加载完成判定 | 通过 | `source.open`、`source.status` 实机返回 |
| result index | 通过 | 6 subcase、37 simulation、6 result type |
| contour / result query | 部分通过 | contour 和 top-N 数值通过；averaging 尚未实机验证 |
| transparency / deformation | 待实现/待验 | 本轮未改变这两类显示状态 |
| component isolate / context / local fit | 通过 | 组件 pool/ID 解析、Mask 隔离、透明上下文、局部 fit 和跨视图状态复位均已实机验证 |
| 1920×1080 PNG | 通过 | 53 张真实图片尺寸通过，方向视图校验和不同 |
| camera read/restore | 部分通过 | preset 可恢复；matrix 和 legend precision 返回 partial |
| lock screen / minimize / Remote Desktop | 待现场 | 需目标工作站环境 |
| License 行为 | 单次流程通过 | 批量长任务占用/释放仍需 H3D 压测 |

## 重现

```powershell
& .\.venv\Scripts\python.exe .\tools\run_hv_poc.py
```

使用真实 H3D：

```powershell
& .\.venv\Scripts\python.exe .\tools\run_hv_poc.py --h3d D:\model\result.h3d
```

第二条命令会验证 `source.open`、`source.index`、`result.query_max`、标准方向 PNG
和 `view.read`。H3D 只引用，不会复制、修改或删除。

组件截图专项验证：

```powershell
& .\.venv\Scripts\python.exe .\tools\verify_component_capture_real.py
```

该命令使用真实 HyperView 2019 生成 global、local、front/right/top、
component isolate 和 component context 图片，校验 1920×1080 PNG，并要求
global/isolate/context 以及标准方向的关键图片哈希互不相同。

## 已修复的 POC 问题

最初使用双引号拼接 Tcl 正则和 JSON 数组，`[[:space:]]` 与 `[...]` 被 Tcl 当作命令替换。现已统一使用花括号正则/JSON 字面量或先存入变量后再插值，并审计了全部协议响应。

HyperView 2019 Tcl 在中文项目目录下会使用旧代码页解码环境变量中的绝对路径。
Worker 现让 HyperView 以会话目录为工作目录，并仅通过环境变量传递 ASCII
相对文件名 `context.json`。

Tcl socket 使用非阻塞 `fileevent + vwait` 事件循环，前台诊断模式不会因等待
Worker 命令而阻塞 HyperView 事件处理。发布环境默认追加 `-b`；设置
`CAE_REPORT_HYPERVIEW_BACKGROUND=0` 可用于前台诊断。Worker 从 Server 的任务
完成响应取得 Run 终态并释放会话，交互式重拍和视图恢复则使用一次性会话。
