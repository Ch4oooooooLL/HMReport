# HyperView 2019 POC

## 结论

2026-07-19 在本机 Altair HyperView 2019 上完成了第一层真实验证：

- 可执行文件：`C:\Program Files\Altair\2019\hw\bin\win64\hw.exe`
- 启动参数：`/clientconfig hwpost.dat -tcl hyperview/bootstrap.tcl`
- Tcl 脚本能读取环境变量传入的 JSON context；
- Tcl 能主动连接 Worker 在 `127.0.0.1` 上建立的随机端口；
- session token、session id、协议版本和 capabilities 握手通过；
- `session.ping` 返回 `ready` 和 `HyperView 2019`；
- `session.shutdown` 后 HyperView 正常退出；
- 实测启动到握手完成为 3.242 秒。

实测输出保存在本地、Git 忽略的 `runtime/poc/handshake-result.json`。

## 已验证能力矩阵

| POC 项 | 状态 | 证据/备注 |
|---|---|---|
| HyperView 2019 启动命令 | 通过 | 本机真实进程 |
| `-tcl` 行为 | 通过 | `bootstrap.tcl` 被执行 |
| Tcl TCP socket | 通过 | 主动回连随机 loopback 端口 |
| Tcl JSON Lines | 通过 | handshake、ping、shutdown |
| Session token | 通过 | 随机 32-byte token，日志不记录 token |
| 命令白名单 | 通过 | 协议层拒绝 `tcl.eval` 等任意命令 |
| 自动打开 H3D | 待真实 H3D | 当前工作区未发现可用 H3D |
| 加载完成判定 | 待真实 H3D | 需要实际模型 |
| result index | 待真实 H3D | 需要实际 subcase/result 数据 |
| contour / averaging | 待真实 H3D | Tcl adapter 已留独立服务边界 |
| transparency / deformation | 待真实 H3D | 同上 |
| component isolate / standard views / local fit | 待真实 H3D | 同上 |
| 1920×1080 PNG | Fake 通过，真实待验 | Fake 图片校验和版本链已自动测试 |
| camera read/restore | Fake 通过，真实待验 | 不支持字段必须返回 `null`/partial |
| lock screen / minimize / Remote Desktop | 待现场 | 需目标工作站环境 |
| License 行为 | 启动通过 | 批量长任务占用/释放仍需 H3D 压测 |

## 重现

```powershell
& .\.venv\Scripts\python.exe .\tools\run_hv_poc.py
```

有真实 H3D 后：

```powershell
& .\.venv\Scripts\python.exe .\tools\run_hv_poc.py --h3d D:\model\result.h3d
```

第二条命令会继续验证 `source.open`、`source.index`、PNG 和 `view.read`。H3D 只引用，不会复制、修改或删除。

## 已修复的 POC 问题

最初使用双引号拼接 Tcl 正则和 JSON 数组，`[[:space:]]` 与 `[...]` 被 Tcl 当作命令替换。现已统一使用花括号正则/JSON 字面量或先存入变量后再插值，并审计了全部协议响应。

