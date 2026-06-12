# LocalCommandCenter 代码阅读指南

更新时间：2026-06-12  
目标：指导你系统读完 `local-gateway/` 全部代码，而不是只看入口文件

## 1. 先定阅读原则

这套代码不适合“按文件名字母顺序”读，也不适合“从前端一路点到后端”。正确方式是：

1. 先建立系统地图
2. 再读主业务链路
3. 再读扩展能力
4. 最后读兼容层、脚本和测试

否则很容易在大文件里迷路，或者把兼容接口误判成主设计。

## 2. 你需要达到的阅读结果

读完之后，你至少要能回答这 12 个问题：

1. 应用启动时初始化了哪些系统？
2. 主数据库有哪些表，谁在创建它们？
3. `task_service.py` 为什么会成为整个系统的枢纽？
4. AI 对话里 tool call 是怎么落到本地 service 的？
5. 批量任务规划和普通 chat agent 分别走哪条链？
6. 邮件系统的数据模型、同步、自动回信、草稿发送分别在哪？
7. `mail_service.py` 和 `services/mail/*` 的关系是什么？
8. 前端的真实入口是 React 还是 `static/index.html`？
9. `Download.jsx` 为什么其实是邮件工作台？
10. 哪些模块是平台能力，哪些模块是业务能力？
11. 哪些测试是核心回归测试？
12. 代码里哪些地方最值得重构？

如果这 12 个问题答不出来，说明你还没真正读通。

## 3. 推荐阅读顺序

### 第一轮：30 分钟，先建立全局地图

只读这些文件，不深挖实现：

1. `local-gateway/main.py`
2. `local-gateway/config.py`
3. `local-gateway/models/schemas.py`
4. `local-gateway/README.md`
5. `local-gateway/frontend/package.json`
6. `local-gateway/frontend/vite.config.js`

这一轮的目标：

- 确认后端、前端、数据库、Docker、AI、测试各自存在
- 确认 React 前端会打包到 `static/`
- 确认这不是单一任务管理器，而是多子系统合体

这一轮不要试图记字段，只需要画出你的第一版脑图。

## 4. 第二轮：后端主干

### 阅读顺序

1. `main.py`
2. `routers/task_manager.py`
3. `services/task_service.py`
4. `routers/dashboard.py`
5. `routers/advanced_features.py`
6. `services/tag_service.py`
7. `services/subtask_service.py`
8. `services/pomodoro_service.py`
9. `services/note_service.py`
10. `services/habit_service.py`
11. `services/calendar_sync_service.py`
12. `services/notification_service.py`

### 这一轮你要关注什么

#### 4.1 先看启动期依赖

在 `main.py` 里看清楚：

- `ensure_dirs()`
- `task_service.init_db()`
- `mail_service.init_mail_db()`
- `mail_service.start_mail_polling_scheduler()`
- `sync_engine.initialize()`
- `setup_scheduler()`
- `restore_all_reminders()`

这一步决定了全系统依赖关系。

#### 4.2 再看任务系统是怎么向外扩张的

`task_service.py` 是整个系统的第一主枢纽。阅读时按这个顺序：

1. `_schema`
2. `init_db()`
3. `add_task / update_task / delete_task / complete_task`
4. `get_weekly_plan / get_pending_tasks / get_all_tasks`
5. `analyze_tasks / batch_add_tasks`
6. `get_task_detail / get_dashboard_stats`
7. 辅助函数 `_normalize_time`、`_check_conflicts`、`_calc_next_reminder`

要带着这几个问题读：

- 为什么下载记录和操作日志也放在 `task_service.py`？
- 为什么它既管 CRUD，又管统计，又管编排？
- 这会让未来重构从哪里下手？

#### 4.3 看增强能力如何围绕任务系统附着

后面的标签、子任务、番茄钟、笔记、习惯、日历，本质上都在给“任务工作台”加侧翼。

阅读时重点看：

- 各服务如何建表
- 各服务是否直接操作同一个 `tasks.db`
- `advanced_features.py` 如何把这些能力聚合成 API

### 第二轮产出

读完你应该能自己画出这条链：

```text
Task API
-> task_service
-> SQLite
-> notification/calendar/tag/subtask/pomodoro/note/habit 辅助服务
```

## 5. 第三轮：搜索、下载、沙盒、安全

### 阅读顺序

1. `routers/file_search.py`
2. `services/unified_search_service.py`
3. `services/fulltext_search_service.py`
4. `routers/safe_downloader.py`
5. `services/download_service.py`
6. `routers/sandbox_executor.py`
7. `services/sandbox_service.py`
8. `services/security_service.py`
9. `services/time_service.py`

### 这一轮重点

#### 5.1 搜索已经有两层历史

先看：

- `search_service.py` 是旧文件搜索
- `unified_search_service.py` 是当前统一入口
- `fulltext_search_service.py` 是内容索引增强

重点分清：

- 哪些是新主路径
- 哪些只是兼容包装

#### 5.2 下载服务要看“同步小文件 + 队列大文件”

重点看：

- URL SSRF 校验
- 文件名净化
- 大文件进入队列
- 下载历史如何入库
- 带宽限制与状态存储在哪里

#### 5.3 沙盒服务要看“边界”而不是“命令”

重点看：

- 镜像选择
- 容器生命周期
- 动态文件注入
- 输入文件挂载白名单
- 输出文件回拷

#### 5.4 安全服务要认真读

`security_service.py` 是整个仓库里高风险逻辑的守门员之一，必须细读：

- SSRF 防护
- shell command token 校验
- 本地命令白名单
- safe subprocess
- HTML 转义
- SQL 更新列白名单

这部分读不细，后面 AI/shell/mail 的边界都看不稳。

## 6. 第四轮：AI 对话与 AI 规划

这是第二条主线，也是最容易误读的一块。

### 阅读顺序

1. `routers/chat.py`
2. `services/ai_service.py`
3. `routers/ai_planning.py`
4. `services/ai_planning_service.py`

### 6.1 先分清两类 AI

你必须先分清：

- `ai_service.py`
  - 是聊天代理
  - 面向对话、function calling、streaming、shell、code interpreter

- `ai_planning_service.py`
  - 是任务规划器
  - 面向 preview、variant、replan、估时、建议

它们都叫 AI，但职责完全不同。

### 6.2 `ai_service.py` 的建议阅读顺序

按这个顺序读：

1. 顶部工具 schema
2. system prompt
3. `chat()`
4. `_call_ai()`
5. `_execute_tool()`
6. `_execute_code_interpreter()`
7. `_execute_shell()`
8. `chat_stream()`
9. 会话持久化相关函数

阅读重点：

- tool schema 如何映射到本地服务
- 历史消息怎么保存
- stream 与非 stream 是否共享主要逻辑
- shell 与 code interpreter 的权限边界是什么

### 6.3 `ai_planning_service.py` 的建议阅读顺序

按这个顺序：

1. `decompose_task`
2. `generate_task_plan`
3. `preview_task_plan`
4. `confirm_task_plan`
5. `replan_tasks`
6. `replan_tasks_with_acceptance`
7. `_collect_calendar_load`
8. `_build_variant_plan`
9. `_extract_conflict_chain`
10. `estimate_task_time`
11. `get_smart_suggestions`
12. `analyze_task_patterns`

这里重点不是“每个函数都看懂到行”，而是先搞清：

- 它的输入输出结构
- 哪些是规则算法
- 哪些地方借助 LLM
- preview -> confirm -> replan 的状态流是什么

## 7. 第五轮：邮件子系统

邮件子系统建议单独拿半天到一天读，不要和别的模块混读。

### 阅读顺序

1. `routers/mail.py`
2. `routers/mail_api.py`
3. `routers/mail_portal.py`
4. `services/mail_service.py`
5. `services/mail/facade.py`
6. `services/mail/schema.py`
7. `services/mail/accounts.py`
8. `services/mail/threads.py`
9. `services/mail/messages.py`
10. `services/mail/drafts.py`
11. `services/mail/parsing.py`
12. `services/mail/automation.py`
13. `services/mail/sync.py`
14. `services/mail/runtime.py`
15. `services/mail/utils.py`

### 7.1 先看聚合层和兼容层

你要先确认：

- `routers/mail.py` 只是路由聚合
- `mail_service.py` 只是服务兼容入口
- `facade.py` 才是邮件子系统公开面

否则你会在 `mail_service.py` 上浪费时间。

### 7.2 再看 schema 和账户层

重点看：

- 邮件表怎么建
- 账户和文件夹怎么存
- 连接测试在哪里做

### 7.3 再看线程层

`threads.py` 是邮件业务中心，必须细读。

建议按顺序：

1. row -> dict 转换函数
2. `find_existing_thread_id`
3. `create_thread`
4. `refresh_thread_state`
5. `list_mail_threads`
6. `get_mail_thread`
7. `get_mail_dashboard`
8. `mark_thread_read / move_thread_to_folder / set_thread_decision_status`

### 7.4 自动化层最后读

`automation.py` 放后面读，因为它依赖你先理解：

- 线程结构
- 草稿结构
- 账户策略
- parser 输出

重点看：

- 自动策略如何判定
- 自动建任务如何调用任务系统
- 自动生成回复草稿如何串 AI
- agent run 如何留痕

### 7.5 邮件 Portal 是一条独立支线

`mail_portal.py` + `mail_portal_render.py` 是一条“从邮件链接回到系统”的特殊入口。

读的时候要注意：

- token 校验
- portal 页面是 server-rendered HTML，不是 React 页面
- 这是移动或外部触达路径，不是主 SPA 路由

## 8. 第六轮：同步、加密、工作流、平台能力

### 阅读顺序

1. `routers/sync.py`
2. `services/sync_service.py`
3. `routers/encryption.py`
4. `services/e2e_encryption.py`
5. `routers/webhooks.py`
6. `services/webhook_service.py`
7. `routers/workflows.py`
8. `services/workflow_service.py`
9. `routers/shortcuts.py`
10. `services/shortcut_service.py`
11. `routers/mobile.py`
12. `routers/voice.py`
13. `services/voice_service.py`

### 这一轮读法

别追求每个细节先读透，重点看：

- 它们都依赖哪些基础服务
- 是不是会改主数据库
- 是不是主要在扩展“平台接入面”

理解上把它们放到“平台能力层”，不要和核心任务/邮件/AI 主线混为一谈。

## 9. 第七轮：前端

前端建议用“外壳 -> 页面 -> 组件 -> hook -> 工具函数”的顺序。

### 阅读顺序

1. `frontend/src/main.jsx`
2. `frontend/src/App.jsx`
3. `frontend/src/components/Sidebar.jsx`
4. `frontend/src/components/TopBar.jsx`
5. `frontend/src/hooks/useApi.js`
6. `frontend/src/pages/Dashboard.jsx`
7. `frontend/src/pages/Tasks.jsx`
8. `frontend/src/pages/AiChat.jsx`
9. `frontend/src/pages/Download.jsx`
10. `frontend/src/pages/Settings.jsx`
11. `frontend/src/pages/Calendar.jsx`
12. `frontend/src/pages/Notes.jsx`
13. `frontend/src/pages/Habits.jsx`
14. `frontend/src/pages/Workflows.jsx`
15. `frontend/src/pages/Sync.jsx`
16. `frontend/src/pages/Sandbox.jsx`
17. `frontend/src/components/chat/*`
18. `frontend/src/components/maildesk/*`
19. `frontend/src/hooks/useMailDesk*.js`
20. `frontend/src/contexts/*`
21. `frontend/src/utils/*`

### 9.1 前端先抓页面职责

读页面文件时先回答：

- 这个页面在系统里的业务定位是什么？
- 它主要依赖哪些 API？
- 页面是否已经拆分出 hooks？

### 9.2 必须重点读的 4 个页面

#### `Tasks.jsx`（1740 行）

这是前端最重的业务页面。重点看：

- 周视图
- 全部任务视图
- 任务详情抽屉
- 任务表单
- 快捷动作如何落到后端

#### `AiChat.jsx`（1185 行）

重点看：

- 对话消息状态
- 流式处理
- 配置面板
- 规划草稿与 mission board
- viewer modal

#### `Download.jsx`

虽然名字叫 Download，但实际是邮件工作台。

阅读时要先在脑子里重命名成：

`MailDesk.jsx`

否则很容易误判。

#### `Dashboard.jsx`

重点看：

- 它如何组合任务、风险、日志、建议
- 它是“今日面板”，不是单纯统计页

### 9.3 邮件工作台的正确读法

邮件工作台已经被拆成：

- 页面：`Download.jsx`
- hook：`useMailDeskState.js` 等
- 组件：`MailRailPanel`、`OpenLetterPanel`、`MailControlGrid` 等

正确顺序：

1. `Download.jsx`
2. `useMailDeskState.js`
3. `useMailDeskData.js`
4. `useMailDeskAccountActions.js`
5. `useMailDeskThreadActions.js`
6. `useMailDeskPollingActions.js`
7. `useMailDeskComposer.js`
8. `useMailDeskDerivedState.js`
9. 组件文件

### 9.4 Chat 组件的正确读法

正确顺序：

1. `AiChat.jsx`
2. `aiChatShared.js`
3. `AiChatMissionBoard.jsx`
4. `AiChatPlanningPreview.jsx`
5. `AiChatManuscriptPage.jsx`
6. `ChatMessageBubble.jsx`
7. `AssistantMarkdown.jsx`
8. `markdown.js`

## 10. 第八轮：测试

测试不是最后“有空再看”，而是阅读闭环的一部分。

### 推荐顺序

1. `test/test_api.py`
2. `test/test_services.py`
3. `test/test_security.py`
4. `test/test_unified_search.py`
5. `test/test_ai_planning_flow.py`
6. `test/test_ai_planning_calendar.py`
7. 邮件相关 9 个测试文件
8. 前端 maildesk 组件与 hook 测试

### 怎么用测试辅助阅读

读每个复杂 service 时都问：

- 它的 happy path 测了吗？
- 边界条件测了吗？
- 风险点测了吗？
- API 和 service 的职责边界测了吗？

尤其邮件和安全两块，测试能直接告诉你作者最担心哪里出错。

## 11. 建议你做 4 张阅读图

### 图 1：启动图

画出：

```text
main.py
-> init_db
-> init_mail_db
-> sync_engine.initialize
-> notification scheduler
```

### 图 2：任务系统图

画出：

```text
task_manager router
-> task_service
-> tags/subtasks/pomodoro/notes/habits/calendar/notification
```

### 图 3：AI 系统图

画出：

```text
chat router
-> ai_service
-> LLM
-> tool dispatch
-> local services / shell / code interpreter
```

### 图 4：邮件系统图

画出：

```text
mail_api router
-> mail_service/facade
-> accounts/threads/drafts/messages/sync/runtime/automation
```

没有这 4 张图，你读完很快会散掉。

## 12. 读大文件的方法

这个仓库里几份大文件必须单独处理：

- `services/task_service.py`
- `services/ai_service.py`
- `services/mail/threads.py`
- `services/mail/automation.py`
- `services/ai_planning_service.py`
- `frontend/src/pages/Tasks.jsx`
- `frontend/src/pages/AiChat.jsx`
- `frontend/src/pages/Dashboard.jsx`

读法统一：

1. 先看 imports
2. 再看顶层常量/配置
3. 再列出所有公开函数
4. 再按调用频率排序
5. 最后才读细节实现

不要一上来从第 1 行读到最后一行。

## 13. 你应该重点标记的重构热点

阅读时建议你单独记下这些热点：

1. `task_service.py` 过重，已经混合了多类职责
2. `ai_service.py` 同时管 prompt、调用、工具执行、历史持久化、流式输出
3. `Download.jsx` 文件名与真实业务失配
4. `README` 与真实结构不一致
5. 兼容层较多，主路径需要更明确的 package 边界
6. 任务系统与其他业务共享单库，边界比较松

这些不是现在必须改，但它们决定你之后怎么切重构单。

## 14. 一个可执行的完整阅读计划

如果你要“读完全部代码”，建议按 5 天安排。

### 第 1 天

- `main.py`
- `config.py`
- `models/schemas.py`
- `routers/task_manager.py`
- `services/task_service.py`

目标：读通后端主骨架。

### 第 2 天

- `advanced_features.py`
- `note/habit/pomodoro/tag/subtask/calendar/notification` 相关服务
- `file_search/download/sandbox/security`

目标：读通效率系统和基础工具能力。

### 第 3 天

- `chat.py`
- `ai_service.py`
- `ai_planning.py`
- `ai_planning_service.py`

目标：读通 AI 两条主线。

### 第 4 天

- 全套邮件 router
- `mail_service.py`
- `services/mail/*`

目标：把邮件系统单独吃透。

### 第 5 天

- 前端 `App.jsx`
- 主要页面
- maildesk hooks/components
- 测试

目标：把 UI 和 API 对齐，并用测试补完理解。

## 15. 最后一个建议

真正读完这套代码，不是“每个文件都看过一次”，而是做到三件事：

1. 你能从任意一个页面动作追到后端 service
2. 你能从任意一个核心 service 找到对应路由和测试
3. 你能指出当前主路径、兼容路径和遗留路径

只要做到这三点，后续不管是修 bug、加功能还是做重构，你都不会再靠猜。
