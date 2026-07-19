# ADR-0001：Web 工作台保持 Vue 3 与本地部署

## 决策

遵循主 spec 使用 Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus 和 ECharts。Web 资源由 loopback FastAPI 服务提供，不部署到云端。

## 原因

V1 明确不实现云服务、登录、远程浏览器访问和原始模型上传。本地部署也确保 FEM/H3D 不离开工作站。

## 风险与回滚

前端包体较大，后续通过按路由拆包优化；API 与 ReportDocument 为稳定边界，可替换渲染层而不迁移业务数据库。

