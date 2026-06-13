# 测试报告（2026-06-13）

本文档记录当前后端回归基线，而不是早期阶段性开发记录。

## 当前回归基线

截至 2026-06-13，当前使用的主回归命令为：

```bash
conda run -n claude python -m pytest test/test_task_application.py test/test_planning_application.py test/test_mobile_application.py test/test_mobile_query_service.py test/test_sync_application.py test/test_mail_automation.py test/test_phase3.py test/test_execution_guards.py test/test_unified_search.py test/test_task_query_service.py test/test_ai_planning_flow.py test/test_runtime_state_service.py test/test_task_planning_service.py test/test_task_command_service.py test/test_services.py test/test_security.py test/test_dashboard_application.py test/test_habit_service.py test/test_advanced_application.py test/test_backend_remediation.py test/test_domain_routers.py test/test_search_routers.py test/test_architecture_guards.py -q
```

最近一次结果：

- `150 passed, 4 skipped`

这条基线覆盖的是当前主干架构，而不是把 `test/` 目录里所有历史文件一把跑完。

## 当前重点测试面

当前稳定回归主要覆盖以下几类能力：

- application 层用例编排
- task 拆分后的 command / query / detail / planning service
- domain router 薄路由边界
- search router owner 边界
- architecture guard 边界
- dashboard / mobile / sync / mail / security 等横向能力

其中，`test/test_architecture_guards.py` 目前专门锁定以下架构约束：

- 内部主链不再直接导入 `services.task_service`
- `routers/advanced_features.py` 只作为兼容别名聚合
- `/api/search`、`/api/search/legacy`、`/api/search/fulltext` 的 owner 边界固定

## 历史命名测试文件的解释

测试目录中仍存在一些带 `phase`、`advanced_features` 等历史命名的文件。这些文件名不再代表当前架构阶段划分，只是历史保留文件名。

阅读时要区分：

- 文件名是历史的
- 测试目标可以仍然有效
- 是否纳入当前常规回归，要看它是否稳定、是否依赖外部环境

## 需要独立运行的兼容 / 联调测试

以下测试不应混入当前常规离线回归基线：

### `test/test_advanced_features.py`

特点：

- 依赖本地真实服务启动在 `http://localhost:8900`
- 主要覆盖 `/api/advanced/*` 兼容路径
- 更适合作为兼容联调冒烟测试

运行方式：

```bash
# 终端 1
conda run -n claude python main.py

# 终端 2
conda run -n claude python -m pytest test/test_advanced_features.py -v
```

### `test/test_phase2.py`

特点：

- 同样依赖本地真实服务
- 覆盖 AI / notes / habits / voice 等历史联调路径
- 其中部分 AI 用例允许在缺少外部 API 配置时返回错误态

运行方式：

```bash
# 终端 1
conda run -n claude python main.py

# 终端 2
conda run -n claude python -m pytest test/test_phase2.py -v
```

## 建议的日常测试顺序

### 1. 架构边界改动后

```bash
conda run -n claude python -m pytest test/test_architecture_guards.py test/test_search_routers.py test/test_domain_routers.py -q
```

### 2. task / planning / application 改动后

```bash
conda run -n claude python -m pytest test/test_task_application.py test/test_planning_application.py test/test_task_command_service.py test/test_task_query_service.py test/test_task_planning_service.py -q
```

### 3. 合并前

执行本文件顶部列出的完整主回归命令。

## 当前结论

当前测试体系已经不再以 `task_service.py` 单体服务为中心，而是在逐步围绕：

- application 层
- 分域 service
- router owner 边界
- compatibility boundary

建立更稳定的回归基线。
