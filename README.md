# My_Claw

`My_Claw` 当前的核心应用是 [`local-gateway/`](./local-gateway/)。

这个仓库现在不是早期的“5 个工具接口示例”，而是一个本地工作台平台，包含：

- task / notes / habits / pomodoro / calendar / notification
- AI chat / AI planning
- search / download / sandbox / security
- mail workspace
- sync / encryption / workflow / webhook / mobile

## 当前代码基线

- 主分支：`main`
- 当前架构状态以 `local-gateway/docs/ARCH_IMPLEMENTATION_PROGRESS_2026-06-13.md` 为准

## 从哪里开始看

如果你要快速建立当前结构认知，先读：

1. [`local-gateway/docs/PROJECT_STRUCTURE_OVERVIEW_2026-06-12.md`](./local-gateway/docs/PROJECT_STRUCTURE_OVERVIEW_2026-06-12.md)
2. [`local-gateway/docs/CODE_READING_GUIDE_2026-06-12.md`](./local-gateway/docs/CODE_READING_GUIDE_2026-06-12.md)
3. [`local-gateway/docs/ARCH_IMPLEMENTATION_PROGRESS_2026-06-13.md`](./local-gateway/docs/ARCH_IMPLEMENTATION_PROGRESS_2026-06-13.md)
4. [`local-gateway/docs/ARCH_COMPAT_BOUNDARY_CATALOG_2026-06-13.md`](./local-gateway/docs/ARCH_COMPAT_BOUNDARY_CATALOG_2026-06-13.md)

## 运行入口

后端入口在：

- [`local-gateway/main.py`](./local-gateway/main.py)

应用启动后默认服务地址：

- `http://localhost:8900`

## 重要说明

当前真实架构和一些旧描述已经有明显差异，特别是：

- `bootstrap_service` 是数据库初始化 owner
- `task_service` 已退成 compatibility facade
- `/api/search`、`/api/search/legacy`、`/api/search/fulltext` 已分属不同 router owner
- `/api/advanced/*` 已降级为 compatibility alias

如果你要继续重构，不要再把 `task_service.py`、`routers/file_search.py`、`routers/advanced_features.py` 当主实现入口。
