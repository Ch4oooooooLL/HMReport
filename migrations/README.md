# Database migrations

当前 schema version 为 2。可执行迁移由 `cae_report_server.database` 在 Server 启动时、单写连接内幂等执行，并记录到 `schema_migrations`。V2 起新增迁移应拆为独立 SQL 文件并保持旧数据库的前向升级测试。

