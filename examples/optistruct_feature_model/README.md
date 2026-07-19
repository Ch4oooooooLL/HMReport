# OptiStruct 综合功能测试模型

该目录的模型由 `tools/generate_optistruct_feature_model.py` 确定性生成，用于同时验证：

- HMReport 的 FEM 模型、component、property、material、网格、边界条件和 subcase 解析；
- HyperView/H3D 的结果索引、应力与位移热点、component 隔离和多视角截图；
- OptiStruct 2019+ 的静力、重力、模态、非线性静力和模态频响求解。

模型采用 mm-N-MPa-tonne-s 单位制，包含 CBAR、CBEAM、CBUSH、CTRIA3、CQUAD4、CTETRA、CPENTA、CHEXA、RBE2、RBE3 和 CONM2。材料同时覆盖 MAT1 与 MAT8，属性覆盖 PBAR、PBEAM、PBUSH、PSHELL、PCOMP 和 PSOLID。

## 生成

在仓库根目录运行：

```powershell
& .\.venv\Scripts\python.exe .\tools\generate_optistruct_feature_model.py
```

默认生成：

- `optistruct_feature_model.fem`：可直接提交给 OptiStruct 的单文件模型；
- `optistruct_feature_model.manifest.json`：覆盖项、数量和预期诊断清单。

如需专门测试 INCLUDE 递归解析：

```powershell
& .\.venv\Scripts\python.exe .\tools\generate_optistruct_feature_model.py `
  --output .\examples\optistruct_feature_model\optistruct_feature_model_split.fem `
  --split-includes
```

## 求解

将 `optistruct_feature_model.fem` 提交给 OptiStruct。成功后把同名 `.h3d` 与 `.fem` 一起选入 HMReport。建议在工作台中勾选全部 FEM、H3D、热点、标准视图和报告任务。

当前生成结果已使用 OptiStruct 2019 build `0960190med33190` 实际求解验证：6 个子工况全部完成，非线性工况收敛，并成功生成可供 HyperView 使用的 H3D。

模型有意保留未引用的 property 199 和 material 99，用于测试诊断展示；它们不会参与求解，也不是模型错误。

生成的 `.fem`、`.inc` 和 manifest 是可重建测试产物，不进入 Git；生成器、说明和自动化测试应进入版本控制。
