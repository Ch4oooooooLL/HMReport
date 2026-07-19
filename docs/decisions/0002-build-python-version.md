# ADR-0002：当前发布包使用 Python 3.14 构建

## 原决策

主 spec 指定 Python 3.12 x64 作为 Desktop、Server 和 Worker 运行时。

## 当前变更

本机只安装了 Python 3.14.6，因此 2026-07-19 的首个 Windows 验证包由 Python 3.14.6 + PyInstaller 6.21 构建。项目元数据仍声明 `requires-python >= 3.12`，源代码保持 Python 3.12 语法目标，Ruff 与 mypy 也按 3.12 检查。

## 原因

在不虚构 Python 3.12 环境的前提下，先验证可执行文件、三进程协作、Vue 静态资源与完整 Fake E2E。当前包已在本机 Windows 11 通过进程级测试，但不能替代 Python 3.12 干净 Windows 验收。

## 风险、迁移与回滚

- Python 3.14 打包产物可能与最终 3.12 包在依赖体积或原生 DLL 上不同。
- 正式 V1 发布前，在 Python 3.12 x64 干净环境重新运行 `tools/package.ps1` 和验收矩阵。
- 数据库、API、JSON schema 和项目目录不依赖 Python 小版本，无数据迁移影响。
- 若 3.12 构建出现依赖问题，回滚到本次源码并只调整锁定依赖，不改变业务 schema。

