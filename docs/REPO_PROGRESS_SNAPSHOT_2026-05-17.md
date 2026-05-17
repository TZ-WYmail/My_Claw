# 仓库进度快照

日期：2026-05-18  
分支：`main`  
相对远端状态：`ahead 1`

---

## 1. 当前仓库状态

- 当前工作树干净，可继续进入下一阶段整理。
- 2026-05-18 已将此前累计的邮件与前端改造提交推送到远端，当前仅剩 1 个本地未推送提交。
- 最近一轮工作重点已经从前端书信台补测，转入邮件子系统后端边界收口。

最近 8 个提交：

- `e6c4c7e` `refactor(mail): declare explicit facade exports`
- `68f5f37` `refactor(mail): encapsulate polling runtime state`
- `9e696b7` `refactor(mail): split portal rendering from routes`
- `4f7b9a0` `refactor(security): unify local command execution path`
- `3f967c8` `docs(repo): refresh progress snapshot and analysis`
- `c5b725f` `test(maildesk): cover polling and thread hooks`
- `8eba74f` `test(maildesk): cover derived and account hooks`
- `4455343` `test(maildesk): cover shared mail rendering`

---

## 2. 已完成的阶段成果

### 2.1 书信台前端能力

当前 Mail Desk 已经不是单纯的邮件列表页，而是具备一个完整工作台雏形：

- 活跃线程横向 rail 视图已经替代纵向超长列表
- 打开的线程具备更完整的 Open Letter 细节区
- 草稿已改为书信式预览，而非仅表单字段堆叠
- 增加了线程快照条，便于快速回看上下文
- 增加了“direct mail evidence”解释，能说明为何系统判断这是一封直达用户的信
- 增加了自动策略结果模拟，前端可以提示切换策略后该信将如何处理
- 增加了“邮件转任务”的引导式 composer
- 增加了 agent run 记录与轮询结果展示能力
- `useMailDeskState` 已从超长单体下沉为编排层，核心交互拆进多个 hook
- 已为 `MailRailPanel`、`MailControlGrid`、`OpenLetterPanel` 以及邮件工作台核心 hook 补上前端 smoke / behavior 测试

### 2.2 邮件子系统后端能力

当前邮件系统已经形成可运行的本地域模型：

- 邮件账户、文件夹、线程、消息、草稿、同步记录、代理执行记录
- SMTP/IMAP 账户配置与测试
- IMAP 拉信与线程聚合
- 线程级启发式分析
- 回复草稿生成
- 线程转任务
- Portal 移动处理页
- 后台轮询配置与手动执行

最近新增的结构治理进度：

- 已把 AI shell 与 workflow `exec_command` 的本地命令校验与执行收敛为共享安全入口
- 已把邮件 Portal 路由中的 HTML 渲染抽离到独立 renderer 文件
- 已把邮件轮询运行态从模块级全局状态收敛到 `MailPollingRuntime` 对象
- 已把 `services.mail.facade` 从 `import *` 改成显式 `__all__` 导出

### 2.3 文档清理

上一轮已清理一批临时规划文档，保留了仍有参考价值的邮件系统文档。

当前仍保留的顶层有效文档：

- [AI_ADVISER_BOOK_SPREAD_IMPLEMENTATION_PLAN.md](/data/sda/tanzheng/Desktop/My_Claw/docs/AI_ADVISER_BOOK_SPREAD_IMPLEMENTATION_PLAN.md)
- [MAIL_DESK_FEATURE_MATRIX_2026-05-17.md](/data/sda/tanzheng/Desktop/My_Claw/docs/MAIL_DESK_FEATURE_MATRIX_2026-05-17.md)
- [MAIL_SUBSYSTEM_REFACTOR_PLAN_2026-05-17.md](/data/sda/tanzheng/Desktop/My_Claw/docs/MAIL_SUBSYSTEM_REFACTOR_PLAN_2026-05-17.md)
- [MAIL_SYSTEM_IMPLEMENTATION_ANALYSIS_2026-05-17.md](/data/sda/tanzheng/Desktop/My_Claw/docs/MAIL_SYSTEM_IMPLEMENTATION_ANALYSIS_2026-05-17.md)
- [MAIL_SYSTEM_NEXT_PHASE_ROADMAP_2026-05-17.md](/data/sda/tanzheng/Desktop/My_Claw/docs/MAIL_SYSTEM_NEXT_PHASE_ROADMAP_2026-05-17.md)

---

## 3. 当前结构性现状

### 3.1 已经改善的部分

- 邮件子系统已经做过第一轮拆分，`services.mail_service` 退化为兼容门面。
- 邮件子系统最近又完成了第二轮边界收口中的三步：安全执行入口统一、Portal 渲染层拆离、polling runtime 对象化。
- `services.mail.facade` 已明确 public API 列表，邮件公开面第一次以显式导出形式固定下来。
- 书信台前端体验已经从“普通列表页”提升到“线程工作台”层级。
- 邮件测试已经从单一大测试文件拆到多份领域测试文件。

### 3.2 仍然明显的压力点

- 后端仍有多个超长核心模块没有完成第二轮拆分。
- 前端仍存在几个过大的页面/状态中心文件。
- API、页面渲染、后台运行态、自动化执行边界还不够清晰。
- 配置、运行态、部署产物仍存在双重来源或耦合过深的问题。
- 构建产物与静态入口同目录，仍然会制造提交流程噪音。

---

## 4. 当前高风险热点

按文件规模与职责集中度看，以下文件是下一阶段最需要持续处理的热点：

- [ai_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/ai_service.py)
- [ai_planning_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/ai_planning_service.py)
- [task_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/task_service.py)
- [mail_portal.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/routers/mail_portal.py)
- [mail_portal_render.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/routers/mail_portal_render.py)
- [mail_api.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/routers/mail_api.py)
- [mail_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail_service.py)
- [AiChat.jsx](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/frontend/src/pages/AiChat.jsx)
- [Tasks.jsx](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/frontend/src/pages/Tasks.jsx)
- [useMailDeskState.js](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/frontend/src/hooks/useMailDeskState.js)

对应行数概览：

- `Tasks.jsx`: 1740
- `ai_planning_service.py`: 1587
- `ai_service.py`: 1354
- `task_service.py`: 1391
- `AiChat.jsx`: 1185
- `mail/threads.py`: 797
- `Dashboard.jsx`: 742
- `workflow_service.py`: 443
- `security_service.py`: 364
- `mail_portal_render.py`: 265
- `mail/runtime.py`: 245
- `mail_portal.py`: 181
- `mail/facade.py`: 171
- `useMailDeskState.js`: 410
- `mail_api.py`: 279

---

## 5. 测试现状

- `local-gateway/test` 目录当前共有 31 个顶层文件。
- 其中邮件相关测试 9 个，已经覆盖账户、自动化、草稿、门面、解析、运行态、同步、线程、工具函数。
- 前端邮件工作台已有 8 个针对组件和 hook 的测试文件，已经覆盖 rail、Open Letter、Control Grid、shared render、derived state、account actions、polling actions、thread actions。
- 邮件运行态测试已进一步覆盖 runtime 对象的启停与顶层失败写回。
- 邮件门面测试已覆盖显式 `__all__` 导出。
- 测试基础比早期原型阶段明显更好，但对跨模块集成、失败恢复、并发运行态的覆盖仍偏弱。

邮件相关测试文件：

- `test_mail_accounts.py`
- `test_mail_automation.py`
- `test_mail_drafts.py`
- `test_mail_facade.py`
- `test_mail_parsing.py`
- `test_mail_runtime.py`
- `test_mail_sync.py`
- `test_mail_threads.py`
- `test_mail_utils.py`

---

## 6. 本次记录后的下一步建议

当前最值得进入的阶段不是回到堆功能，而是继续沿邮件子系统做第二轮收口，并逐步把这套方法复制到 AI / task / frontend 大模块。  
本次快照配套的深入审查文档见：

- [REPOSITORY_DEEP_ANALYSIS_2026-05-17.md](/data/sda/tanzheng/Desktop/My_Claw/docs/REPOSITORY_DEEP_ANALYSIS_2026-05-17.md)
