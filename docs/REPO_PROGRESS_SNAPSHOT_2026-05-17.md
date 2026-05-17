# 仓库进度快照

日期：2026-05-17  
分支：`main`  
相对远端状态：`ahead 3`

---

## 1. 当前仓库状态

- 当前工作树处于干净状态，适合继续分析、改造或切下一阶段任务。
- 本地相对远端领先 3 个提交，尚未推送。
- 最近一轮工作重点集中在“书信台 / Mail Desk”前端完善与规划文档收束。

最近 8 个提交：

- `420c38c` `Simulate mail policy outcomes in desk`
- `733c36c` `Explain direct mail evidence in desk`
- `27e4ec8` `Prune obsolete planning docs`
- `e49894d` `Add mail thread snapshot strip`
- `2fb6d96` `Polish mail rail card carousel`
- `6d48eee` `Render mail desk drafts as letters`
- `1744860` `Expand mail message envelope details`
- `9b7e042` `Add guided mail task composer`

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
- 书信台前端体验已经从“普通列表页”提升到“线程工作台”层级。
- 邮件测试已经从单一大测试文件拆到多份领域测试文件。

### 3.2 仍然明显的压力点

- 后端仍有多个超长核心模块没有完成第二轮拆分。
- 前端仍存在几个过大的页面/状态中心文件。
- API、页面渲染、后台运行态、自动化执行边界还不够清晰。
- 配置、运行态、部署产物仍存在双重来源或耦合过深的问题。

---

## 4. 当前高风险热点

按文件规模与职责集中度看，以下文件是下一阶段最需要持续处理的热点：

- [ai_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/ai_service.py)
- [ai_planning_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/ai_planning_service.py)
- [task_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/task_service.py)
- [mail.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/routers/mail.py)
- [AiChat.jsx](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/frontend/src/pages/AiChat.jsx)
- [Tasks.jsx](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/frontend/src/pages/Tasks.jsx)
- [useMailDeskState.js](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/frontend/src/hooks/useMailDeskState.js)

对应行数概览：

- `Tasks.jsx`: 1740
- `ai_planning_service.py`: 1587
- `ai_service.py`: 1446
- `task_service.py`: 1391
- `AiChat.jsx`: 1185
- `useMailDeskState.js`: 975
- `mail/threads.py`: 797
- `routers/mail.py`: 707

---

## 5. 测试现状

- `local-gateway/test` 目录当前共有 30 个顶层文件。
- 其中邮件相关测试 9 个，已经覆盖账户、自动化、草稿、门面、解析、运行态、同步、线程、工具函数。
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

当前最值得进入的阶段不是继续堆功能，而是做一次全仓“问题发掘与结构诊断”，并按风险顺序形成整改路线。  
本次快照配套的深入审查文档见：

- [REPOSITORY_DEEP_ANALYSIS_2026-05-17.md](/data/sda/tanzheng/Desktop/My_Claw/docs/REPOSITORY_DEEP_ANALYSIS_2026-05-17.md)

