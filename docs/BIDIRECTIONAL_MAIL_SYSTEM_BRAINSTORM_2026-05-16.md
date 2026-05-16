# 双向邮件系统 Brainstorm 与设计台账

日期：2026-05-16  
适用范围：`local-gateway`  
目标：把当前“SMTP 单向通知器”升级成一套真正的双向邮件系统，让 LocalCommandCenter 不只是向用户发信，也能接收、整理、理解、起草、回应，并将邮件重新接入任务、日历、AI 与工作流。

---

## 0. 先说判断

现在仓库里的邮件能力，本质上还不是“邮件系统”，而是“邮件播报器”。

它能做的事很单纯：

- 保存 SMTP 配置
- 发送测试邮件
- 发送晨报、午报、晚报
- 发送任务开始前与截止前提醒

它不能做的事也很关键：

- 不能收信
- 不能维护会话线程
- 不能区分收件箱、草稿箱、发件箱、归档
- 不能识别“这封邮件需要回复 / 已回复 / 待跟进”
- 不能把邮件转成任务、日历事项、笔记或 AI 上下文
- 不能让用户在系统内完成一轮真实往返

所以这次设计不能停在“加 IMAP”。

目标应该是一套完整的双向书信系统：

1. 系统能发出清晰、可靠、有回执的信
2. 系统能收回真实的来信与回复
3. 系统能维持线程、状态与上下文
4. 系统能把邮件重新编入用户的行动系统
5. 系统与用户沟通时带一点浪漫主义，但不牺牲清晰和执行性

---

## 1. 现状基线

### 1.1 已有能力

后端当前文件：

- `local-gateway/services/notification_service.py`
- `local-gateway/routers/notification.py`

前端当前入口：

- `local-gateway/frontend/src/pages/Settings.jsx`

现有配置字段：

- `smtp_host`
- `smtp_port`
- `smtp_user`
- `smtp_password`
- `notify_email`
- `reminder_minutes_before`
- `reminder_due_minutes`

现有接口：

- `GET /api/notification/config`
- `POST /api/notification/config`
- `POST /api/notification/test`

### 1.2 当前问题

- 单收件人模型：只有一个 `notify_email`
- 没有收信协议配置：没有 IMAP / Gmail API / Graph API
- 没有邮箱账户模型：只有一组 SMTP 参数
- 没有邮件实体存储：只是即时发出
- 没有线程 ID、`Message-ID`、`In-Reply-To`、`References`
- 没有同步游标、未读状态、标签、归档
- 没有草稿、模板、签名、撤回策略
- 没有发送队列、重试、失败分类
- 没有将来信转成任务 / 日历 / 工作流的桥接

---

## 2. 核心方向

### 2.1 一句话定义

这套系统不应只是“收发邮件”，而应像一间带窗的书信台：外面的来信能真正抵达，里面的安排能优雅寄出，所有往返都能重新回到你的生活秩序里。

### 2.2 设计原则

- 第一原则：先保证真实可靠，再做诗意表达
- 第二原则：线程优先，任何回复都必须落在线程里
- 第三原则：邮件不是孤岛，要能转化为任务、日历、笔记和 AI 上下文
- 第四原则：浪漫主义只加在语气和质感上，不侵蚀关键信息
- 第五原则：双向不等于复杂堆叠，要有可渐进实现的分层架构

### 2.3 产品隐喻

把它设计成“书信收发台”，而不是“企业客服工单”。

空间上分成四层：

- 来信匣：外界的消息流入这里
- 草稿席：用户和 AI 在这里一起雕琢回信
- 往返信架：线程、回执、附件、行动项都在这里展开
- 星图索引：把邮件重新映射到任务、日历、工作流和笔记

---

## 3. 我建议的完整能力版图

## 3.1 收信能力

目标：

- 支持至少一种可靠收信通道
- 能定期同步或实时监听
- 能维护邮箱状态

建议支持顺序：

1. IMAP 同步
2. IMAP IDLE 或轮询增量同步
3. 第三方 API 适配器
   - Gmail API
   - Microsoft Graph

收信最少应支持：

- 收件箱同步
- 已发送同步
- 草稿同步
- 未读状态
- 已归档状态
- 线程关联
- 附件元数据

## 3.2 发信能力

目标：

- 从系统内直接发起新邮件
- 对某一线程回复
- 保存草稿
- 支持模板、签名与引用

发信最少应支持：

- 新建信件
- 回复
- 回复全部
- 转发
- 定时发送
- 草稿保存
- 重试发送
- 发送失败诊断

## 3.3 线程能力

目标：

- 任何一次往返都属于明确的线程
- 线程是邮件系统的主对象，不是消息列表的附属属性

线程至少包含：

- 主体摘要
- 参与人
- 最近往来时间
- 未读计数
- 是否需要用户回复
- 是否已有草稿
- 是否已转任务
- 是否被 AI 标记风险

## 3.4 行动化能力

这是系统的真正价值。

每封邮件都应该能被转化为以下对象之一：

- 任务
- 日历事件
- 习惯提醒
- 笔记摘录
- 工作流触发器
- AI 上下文片段

最好还能自动识别：

- 需要回复
- 需要确认
- 需要跟进
- 有明确截止时间
- 有附件待处理

## 3.5 AI 辅助能力

AI 不该替用户“自动乱回”，而应做三类辅助：

- 理解：总结来信、抽取行动项、识别日期与风险
- 起草：按用户风格生成回信草稿
- 转化：把邮件转成任务 / 日历 / 笔记

AI 的输出必须是可审阅、可修改、可拒绝的草稿，而不是直接发送。

## 3.6 通知与节奏能力

邮件系统不只是收发，还应该告诉用户：

- 有哪些邮件需要今天回复
- 哪些线程已经沉寂太久
- 哪些重要联系人尚未得到回应
- 哪些来信里的截止时间正在逼近

这部分应该反馈给：

- Dashboard 今日页
- AiChat 的上下文载入
- 日报 / 周报

---

## 4. 用户界面 Brainstorm

## 4.1 页面定位

建议新增一个独立页面：

- 视图名：`mail`
- 中文主标题建议：`书信台`
- 英文内部别名建议：`Correspondence Desk`

它不应塞进 Settings，因为它不是单纯配置项，而是一整块行动空间。

## 4.2 页面总体形态

建议使用“三栏半”结构，但视觉上仍维持地图册 / 纸面作战室体系：

- 左侧窄栏：信箱与筛选
- 中间主栏：线程列表
- 右侧主栏：当前线程正文
- 右侧下层或浮层：草稿席 / AI 回信助手

阅读体验应像在翻一叠真正的来往书信，而不是看 CRM。

## 4.3 板块设计

### 来信匣

作用：

- 选择邮箱账户
- 切换收件箱 / 已发送 / 草稿 / 归档 / 待回复
- 显示同步状态

视觉建议：

- 做成“插页索引签”
- 每个信箱像一枚标签牌，而不是普通 tabs

### 线程列

作用：

- 展示主题、摘要、发件人、最近时间、未读数、行动标记

视觉建议：

- 像一叠信封侧边
- 未回复线程用“红色封蜡”或“待回信标记”
- 已草拟未发送用“半展开信纸”提示

### 书信正文

作用：

- 展示整条往返内容
- 支持折叠引用
- 展示附件、抽取行动项、AI 摘要

视觉建议：

- 当前线程像摊开的信纸
- 每封邮件是一个时间分层的信笺
- 机器抽取的行动项不直接混进正文，而是贴在页边批注区

### 草稿席

作用：

- 用户亲自写
- 让 AI 起草
- 选择语气、签名、引用方式、定时发送

视觉建议：

- 像“写字台上的回信纸”
- 草稿编辑器要安静，不要像聊天框

### 星图索引

作用：

- 将邮件映射到任务 / 日历 / 笔记 / 工作流

视觉建议：

- 像页边索引卡
- 显示：
  - 已转任务 2 项
  - 已识别日期 1 个
  - 待确认行动项 3 个

---

## 5. “浪漫主义”应该加在哪里

用户要求“与用户沟通的时候加上浪漫主义”，我建议把它设计成一套可控的语气层，而不是让系统每封邮件都写得像抒情散文。

### 5.1 浪漫主义的正确位置

应该放在：

- 页头导语
- AI 草稿的可选风格
- 日报 / 周报的开场与收束
- 关键提醒里的轻度情绪色彩
- 任务完成、久未回信、重要回函等节点的语言气质

不应该放在：

- 标题关键字段
- 时间、截止日、联系人、附件信息
- 失败报错
- 协议和状态码

### 5.2 语气档位

建议三档：

- `plain`
  - 极简、清楚、偏工具
- `warm`
  - 温和、有人味、适合日常提醒
- `romantic`
  - 带一点月光感与书信气质，但仍然保留行动线

### 5.3 Romantic 档的语言规范

要做到：

- 比普通系统更有温度
- 仍然先说事实，再说情绪
- 一封信里的行动项必须一眼可见

避免：

- 空泛抒情
- 过长比喻
- 抢占用户自己的表达
- 在商务邮件里自作多情

### 5.4 示例

普通提醒：

> 你有 3 封待回复邮件，其中 1 封将在今天 18:00 前需要处理。

Romantic 版：

> 今天有 3 封信还停在案头，其中 1 封会在 18:00 前抵达时间的边缘。你不必仓促，只需要先回最重要的那一封。

普通日报开场：

> 今日共收到 8 封邮件，已回复 5 封。

Romantic 版：

> 今天一共来了 8 封信，你已经回出了 5 封。剩下的 3 封仍在桌角安静等你，其中有 1 封需要在今晚前给出答复。

关键约束：

- 标题行、截止时间、联系人、任务列表仍使用普通清晰格式
- Romantic 只是一层前言与收束，不覆盖骨架

---

## 6. 领域模型设计

## 6.1 MailAccount

表示一个邮箱账户。

建议字段：

- `account_id`
- `display_name`
- `email_address`
- `provider_type`
  - `smtp_imap`
  - `gmail_api`
  - `ms_graph`
- `smtp_config`
- `imap_config`
- `sync_enabled`
- `signature_mode`
- `tone_mode`
- `created_at`
- `updated_at`

## 6.2 MailboxFolder

表示信箱目录。

建议字段：

- `folder_id`
- `account_id`
- `kind`
  - `inbox`
  - `sent`
  - `drafts`
  - `archive`
  - `trash`
  - `custom`
- `remote_name`
- `sync_token`
- `last_synced_at`

## 6.3 MailThread

这是系统中心对象。

建议字段：

- `thread_id`
- `account_id`
- `subject_normalized`
- `participants`
- `snippet`
- `latest_message_at`
- `unread_count`
- `needs_reply`
- `has_draft`
- `linked_task_count`
- `linked_note_count`
- `linked_event_count`
- `risk_level`
- `romantic_priority_label`
  - 例如：`urgent`, `warm`, `waiting`

## 6.4 MailMessage

建议字段：

- `message_id`
- `thread_id`
- `remote_message_id`
- `internet_message_id`
- `direction`
  - `inbound`
  - `outbound`
- `from`
- `to`
- `cc`
- `bcc`
- `reply_to`
- `subject`
- `html_body`
- `text_body`
- `quoted_body`
- `sent_at`
- `received_at`
- `is_read`
- `is_starred`
- `is_draft`
- `delivery_status`
  - `draft`
  - `queued`
  - `sent`
  - `delivered`
  - `failed`

## 6.5 MailDraft

建议字段：

- `draft_id`
- `thread_id`
- `account_id`
- `reply_mode`
  - `new`
  - `reply`
  - `reply_all`
  - `forward`
- `subject`
- `body_html`
- `tone_mode`
- `signature`
- `scheduled_send_at`
- `ai_generated`
- `user_edited_after_ai`
- `status`

## 6.6 MailActionItem

把邮件里的行动项抽出来。

建议字段：

- `action_id`
- `message_id`
- `thread_id`
- `summary`
- `due_at`
- `assignee`
- `confidence`
- `status`
  - `suggested`
  - `accepted`
  - `dismissed`
  - `converted`
- `linked_task_id`
- `linked_event_id`

---

## 7. 后端架构建议

## 7.1 分层

建议新建下列模块：

- `services/mail/transport.py`
  - SMTP / IMAP / provider 抽象
- `services/mail/sync_service.py`
  - 拉取、增量同步、游标管理
- `services/mail/thread_service.py`
  - 线程归并与状态维护
- `services/mail/draft_service.py`
  - 草稿、发送队列、定时发送
- `services/mail/action_extractor.py`
  - 抽取待办、日期、风险
- `services/mail/bridge_service.py`
  - 任务 / 日历 / 笔记 / AI 桥接
- `services/mail/tone_service.py`
  - 模板、签名、Romantic 语气层

## 7.2 传输适配器

不要把协议直接揉在通知服务里，应该抽象成 provider：

- `SmtpImapProvider`
- `GmailApiProvider`
- `MsGraphProvider`

这样后续用户不必被 SMTP / IMAP 一条路锁死。

## 7.3 存储策略

建议本地先采用 SQLite 落地，而不是继续沿用零散 JSON。

原因：

- 线程和消息天然是关系型结构
- 需要高频筛选、排序、未读计数、按线程聚合
- 后续要做增量同步游标与索引

建议核心表：

- `mail_accounts`
- `mail_folders`
- `mail_threads`
- `mail_messages`
- `mail_drafts`
- `mail_attachments`
- `mail_action_items`
- `mail_sync_runs`

## 7.4 同步机制

建议分三层：

- `manual_sync`
  - 用户主动刷新
- `background_polling`
  - 每 2 到 5 分钟增量拉取
- `idle_or_push`
  - 条件允许时实时监听

同步回执至少要记录：

- 本次新增多少封
- 更新多少封
- 失败多少封
- 哪个 folder 失败
- 失败原因

## 7.5 发信机制

建议采用发送队列，而不是前端一点击就阻塞等待 SMTP。

发送状态：

- `draft`
- `queued`
- `sending`
- `sent`
- `failed`
- `retrying`

失败原因分类：

- 认证失败
- 网络失败
- 配额限制
- 收件人地址不合法
- provider 拒收

---

## 8. API 设计草案

## 8.1 配置与账户

- `GET /api/mail/accounts`
- `POST /api/mail/accounts`
- `PUT /api/mail/accounts/{account_id}`
- `POST /api/mail/accounts/{account_id}/test`
- `POST /api/mail/accounts/{account_id}/sync`

## 8.2 文件夹与线程

- `GET /api/mail/folders`
- `GET /api/mail/threads`
- `GET /api/mail/threads/{thread_id}`
- `POST /api/mail/threads/{thread_id}/mark-read`
- `POST /api/mail/threads/{thread_id}/archive`
- `POST /api/mail/threads/{thread_id}/star`

筛选参数建议：

- `folder`
- `account_id`
- `needs_reply`
- `unread_only`
- `linked_object_type`
- `from_contact`
- `q`

## 8.3 消息与草稿

- `GET /api/mail/messages/{message_id}`
- `POST /api/mail/drafts`
- `PUT /api/mail/drafts/{draft_id}`
- `POST /api/mail/drafts/{draft_id}/send`
- `POST /api/mail/drafts/{draft_id}/schedule`
- `DELETE /api/mail/drafts/{draft_id}`

## 8.4 AI 与行动项

- `POST /api/mail/messages/{message_id}/summarize`
- `POST /api/mail/messages/{message_id}/extract-actions`
- `POST /api/mail/threads/{thread_id}/draft-reply`
- `POST /api/mail/action-items/{action_id}/accept`
- `POST /api/mail/action-items/{action_id}/convert-task`
- `POST /api/mail/action-items/{action_id}/convert-event`

## 8.5 统计与仪表

- `GET /api/mail/dashboard`
- `GET /api/mail/sync-status`

返回建议包含：

- 今日新来信数量
- 待回复线程数
- 已起草未发送数
- 重要联系人未回复数
- 平均回复时长

---

## 9. 前端实现设计

## 9.1 路由建议

在 `App.jsx` 中新增：

- `mail`

侧边栏命名建议：

- 中文：`书信台`
- 辅助文案：`往返信件、草稿、回执与行动抽取`

## 9.2 页面模块拆分

建议页面组件：

- `MailDesk.jsx`
- `MailFoldersRail.jsx`
- `MailThreadList.jsx`
- `MailThreadViewer.jsx`
- `MailDraftComposer.jsx`
- `MailActionSidebar.jsx`
- `MailAccountDrawer.jsx`

## 9.3 快捷操作

最有价值的动作不是“看信”，而是这些：

- 一键回信
- 一键转任务
- 一键抽取日期
- 一键起草
- 一键稍后处理
- 一键归档

## 9.4 与现有页面的联动

### Dashboard

新增：

- 今日待回邮件数
- 最重要待回线程
- 长时间未回复提醒

### AiChat

新增：

- 载入某封邮件为上下文
- 针对某线程生成回复草稿
- 从某线程提炼任务与日程

### Tasks

新增：

- “来自邮件”的任务来源标记
- 任务详情中能跳回原始线程

### Notes

新增：

- 将长邮件沉淀为会议摘要 / 项目笔记

### Workflows

新增：

- 触发器：
  - 收到某类邮件
  - 某联系人来信
  - 邮件附件到达
- 动作：
  - 自动打标签
  - 生成草稿
  - 转任务
  - 发通知

---

## 10. 浪漫主义通信系统设计

这一节专门回答“不要敷衍”。

浪漫主义不该只是几句漂亮话，而应该是一种有分寸的交流气候。

## 10.1 三层语言结构

每一次系统对用户的沟通，都拆成三层：

### 第一层：事实骨架

必须清楚写出：

- 谁
- 什么事
- 何时
- 是否需要回复
- 截止时间

### 第二层：节奏引导

帮助用户决定先后：

- 先回哪一封
- 哪些可以稍后
- 哪些只是知会

### 第三层：浪漫主义外衣

只在开头或结尾轻轻点亮，不篡改核心事实。

例如：

> 今晚的信堆里，有一封比别的更急。它不需要你慌张，只需要你先把目光留给它。

然后立刻接清晰列表：

- 需优先回复：客户 A，截止 `18:00`
- 可稍后处理：内部讨论串 2 封
- 仅供阅读：周报 1 封

## 10.2 AI 回信风格

建议用户可选：

- `商务克制`
- `温和清晰`
- `书信式浪漫`

`书信式浪漫` 的边界：

- 用于私人通信、合作关系较熟、礼貌性 follow-up
- 不默认用于法务、财务、正式投诉、合同场景

## 10.3 报告类邮件模板

日报、周报、回复提醒，都可采用“短前言 + 清晰目录 + 收束句”结构。

示例：

主题：

`[LocalCommandCenter] 今日日落前待回信件 3 封`

正文开场：

> 黄昏前还有 3 封信停在桌面，其中 1 封必须在今天给出答复。其余两封可以稍后处理，但最好别让它们过夜。

正文主体：

- `18:00 前需回复`
  - 客户 A：确认交付时间
- `今晚可处理`
  - 团队讨论串：确认周会纪要
  - 供应商邮件：查看附件报价

结尾：

> 先回最重要的那一封，剩下的夜色会替你留出余地。

这就够了。不要写成整页诗。

---

## 11. 分阶段落地建议

## Phase 1：把单向通知改造成“邮件基础设施”

目标：

- 从单一 SMTP 配置升级为多账户邮件配置模型
- 引入 SQLite 存储
- 抽离 `mail` 服务层

包含：

- `MailAccount`
- `SmtpImapProvider`
- `mail_accounts` 表
- 发送队列基础

验收：

- 系统能管理至少一个双协议账户
- 仍保留现有通知发送能力

## Phase 2：读信与线程

目标：

- 收件箱同步
- 线程聚合
- 基础 UI 展示

包含：

- IMAP 增量同步
- `MailThread` / `MailMessage`
- `MailDesk` 页面初版

验收：

- 能看到收件箱
- 能点开线程
- 能标记已读 / 归档

## Phase 3：回信与草稿

目标：

- 真正完成一轮往返

包含：

- 草稿创建
- 回复 / 回复全部 / 转发
- 定时发送
- 失败重试

验收：

- 用户可从系统内对任意线程起草并发出回信
- 线程关系正确

## Phase 4：行动抽取与 AI 辅助

目标：

- 让邮件重新成为行动系统的一部分

包含：

- 抽取行动项
- 转任务 / 转日历 / 转笔记
- AI 摘要与回信草稿

验收：

- 邮件可以转成任务并追溯回原线程
- AI 草稿可编辑后发送

## Phase 5：浪漫主义语气层与高级自动化

目标：

- 在可靠性已经成立后，再加语言气候与高阶联动

包含：

- tone profiles
- 书信式模板
- 邮件触发工作流
- 联系人分层与重要度模型

验收：

- 用户可以按场景切换语气
- 报告和提醒具有稳定而不浮夸的气质

---

## 12. 我建议的优先顺序

如果你要我下一步进入实际开发，不应该先做 UI，而应该先做这条链：

1. `mail_accounts + storage + provider abstraction`
2. `imap sync + thread model`
3. `draft send queue + reply threading`
4. `mail page frontend`
5. `action extraction + AI draft reply`
6. `romantic tone layer`

原因很简单：

- 没有线程与存储，所谓双向只是幻觉
- 没有回信队列，所谓系统内回复只是一次性动作
- 没有桥接对象，邮件无法进入任务系统
- 没有边界，浪漫主义很容易变成噪音

---

## 13. 最后一句判断

真正优秀的双向邮件系统，不是“它会发信，也会收信”，而是它能把人与人的往返，重新编织回用户的行动、记忆与时间里。

信抵达时，它知道该放在哪里。  
信需要回复时，它知道该如何提醒。  
信里藏着任务时，它能把任务捞出来。  
而当系统替你开口时，它不只是像机器报告，更像一位克制而体面的书信助手。
