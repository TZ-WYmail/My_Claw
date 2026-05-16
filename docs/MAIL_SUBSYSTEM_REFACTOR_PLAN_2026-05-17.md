# 邮件子系统重构规划

日期：2026-05-17  
目标：将当前超长的 [mail_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail_service.py) 重构为独立、可维护、可扩展的邮件子系统，同时保持现有 API 和前端功能连续可用。

补充进度：

- 邮件子系统内部模块拆分已完成第一轮收口
- `services.mail_service` 已退化为兼容门面层
- 相关测试已按领域拆分，不再由单一超长测试文件承载

---

## 1. 当前问题

当前邮件实现已经具备不少真实能力：

- 账户与文件夹模型
- IMAP 拉信与 SMTP 发信
- 线程归并与状态推断
- 自动回信策略
- Portal 处理页
- 邮件转任务
- 附件元数据
- 后台轮询

但这些能力全部堆在一个约 3000 行的服务文件里，已经形成明显结构债务：

- 单文件职责过多，修改一处容易影响全局
- 内部函数耦合很深，难以独立测试
- 路由层只能依赖一个“大总管”模块
- 新能力会继续堆叠，后续维护成本会快速上升
- 代码审阅和定位问题的成本已经偏高

结论：邮件能力现在应该作为一个独立子系统对待，而不是继续把功能追加到一个文件里。

---

## 2. 重构原则

本次重构不应该追求“漂亮拆文件”本身，而应该保证下面几条：

### 2.1 先稳兼容，再做深拆

外部调用方当前很多：

- [mail.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/routers/mail.py)
- [main.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/main.py)
- [test_mail_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/test/test_mail_service.py)

所以不能第一步就大面积改导入路径。  
第一阶段必须保留 `services.mail_service` 作为兼容门面。

### 2.2 按领域拆，不按“随便分段”拆

不能只是把 3000 行机械切成 4 个文件。  
应该按稳定领域边界拆分：

- 基础配置与 schema
- 解析与内容处理
- 账户与文件夹
- 线程与消息
- 草稿与发信
- 自动代理
- 同步与轮询

### 2.3 每一阶段都必须可回归验证

每次拆分后至少保证：

- `pytest -q local-gateway/test/test_mail_service.py` 通过
- 路由层不需要同步大改
- 前端书信台不出现回归

### 2.4 先保持函数式兼容，再考虑类化

当前实现以模块函数为主。  
短期内不要强行引入过重的 service class / repository class 体系。  
第一轮目标是“模块化与解耦”，不是做一套过度设计的新框架。

---

## 3. 目标结构

建议将邮件能力重组为：

```text
local-gateway/services/mail/
  __init__.py
  facade.py
  schema.py
  runtime.py
  utils.py
  parsing.py
  accounts.py
  threads.py
  drafts.py
  automation.py
  sync.py
```

同时保留：

```text
local-gateway/services/mail_service.py
```

但它在重构后应退化为兼容门面，例如：

- 统一 `from services.mail.facade import *`
- 暴露旧测试和旧路由仍然依赖的符号

这样可以做到：

- 外部接口基本不变
- 内部实现已完成分层
- 可以逐步推动调用方改为 `services.mail`

---

## 4. 模块职责规划

## 4.1 `schema.py`

职责：

- 保存 `_SCHEMA`
- 保存默认文件夹映射
- 保存 portal secret、轮询配置路径等静态定义
- 保存 schema migration 逻辑

应该包含：

- `_SCHEMA`
- `_DEFAULT_FOLDERS`
- `_MAIL_PORTAL_SECRET`
- `_MAIL_POLLING_CONFIG_FILE`
- `init_mail_db()`
- `_ensure_mail_schema_migrations()`

当前进度：

- 已完成第一轮抽离
- 当前已实际承载以下能力：
  - `SCHEMA_SQL`
  - `DEFAULT_FOLDERS`
  - `MAIL_POLLING_CONFIG_FILE`
  - `init_mail_db()`
  - `ensure_mail_schema_migrations()`

兼容策略：

- `init_mail_db()` 仍通过 `services.mail_service.init_mail_db()` 对外暴露
- 数据库路径继续运行时跟随 `services.mail_service.DB_PATH`

目的：

- 让数据库结构变更集中管理
- 避免 schema 常量散落在主服务逻辑里

## 4.2 `runtime.py`

职责：

- 管理运行时状态
- 管理后台轮询状态与循环

应该包含：

- `_mail_polling_state`
- `_mail_polling_task`
- `_load_mail_polling_config()`
- `_save_mail_polling_config()`
- `get_mail_polling_status()`
- `update_mail_polling_config()`
- `start_mail_polling_scheduler()`
- `stop_mail_polling_scheduler()`
- `run_mail_polling_once()`
- `_mail_polling_loop()`

当前进度：

- 已完成第一轮抽离
- 当前已实际承载以下能力：
  - `_mail_polling_state`
  - `_mail_polling_task`
  - `_load_mail_polling_config()`
  - `_save_mail_polling_config()`
  - `get_mail_polling_status()`
  - `update_mail_polling_config()`
  - `start_mail_polling_scheduler()`
  - `stop_mail_polling_scheduler()`
  - `run_mail_polling_once()`
  - `_mail_polling_loop()`

兼容策略：

- 轮询执行时仍运行时回接 `services.mail_service.sync_mail_account`
- 因此现有轮询测试里的 monkeypatch 方式无需调整

目的：

- 将“生命周期状态”从业务逻辑中抽出
- 后续若要加入更多后台任务，这里就是运行时入口

## 4.3 `utils.py`

职责：

- 保存无副作用的小工具函数

应该包含：

- `_now_iso()`
- `_normalize_subject()`
- `_json_dumps()`
- `_json_loads()`
- `_mask_secret()`
- `_clean_snippet()`
- `_normalize_message_id()`
- `_extract_reference_ids()`
- `_build_outgoing_message_id()`
- `build_mail_portal_token()`
- `verify_mail_portal_token()`
- `_resolve_mail_gateway_base_url()`
- `build_mail_portal_links()`

目的：

- 把纯工具函数从领域流程里剥离
- 降低跨模块 import 时的循环依赖风险

## 4.4 `parsing.py`

职责：

- 处理原始邮件解析与 AI 起草前的内容准备

应该包含：

- `_decode_mime_header()`
- `_extract_address_list()`
- `_parse_email_datetime()`
- `_extract_mail_bodies()`
- `_extract_mail_attachments()`
- `_parse_imap_message()`
- `_extract_mail_command()`
- `_build_mail_action_card()`
- `_generate_ai_reply_content()`

目的：

- 将“内容理解与组装”从数据库流程中分离

## 4.5 `accounts.py`

职责：

- 账户、文件夹、通知账户映射

应该包含：

- `_account_from_row()`
- `list_mail_accounts()`
- `get_mail_account()`
- `create_mail_account()`
- `update_mail_account()`
- `delete_mail_account()`
- `list_mail_folders()`
- `_get_mail_account_raw()`
- `ensure_mail_account_from_notification_config()`
- `_ensure_default_folders()`
- `_get_folder_id()`
- `_get_folder_row()`
- `test_mail_account_connection()`

目的：

- 账户域与线程域分开
- 后续如果要支持 OAuth 或多账户健康状态，这里有清晰承载点

## 4.6 `threads.py`

职责：

- 线程、消息、附件、台账查询
- 状态推断与线程归并

应该包含：

- `_thread_from_row()`
- `_message_from_row()`
- `_draft_from_row()`
- `_attachment_from_row()`
- `_agent_run_from_row()`
- `_attach_portal_links_to_thread()`
- `_find_existing_thread_id()`
- `_create_thread()`
- `_refresh_thread_state()`
- `_infer_mail_analysis()`
- `_extract_due_time_from_thread()`

当前进度：

- 已完成第一轮抽离
- 当前已实际承载以下能力：
  - `_thread_from_row()`
  - `_message_from_row()`
  - `_draft_from_row()`
  - `_attachment_from_row()`
  - `_agent_run_from_row()`
  - `_attach_portal_links_to_thread()`
  - `_find_existing_thread_id()`
  - `_create_thread()`
  - `_refresh_thread_state()`
  - `_infer_mail_analysis()`
  - `list_mail_threads()`
  - `get_mail_thread()`
  - `get_mail_dashboard()`
  - `mark_thread_read()`
  - `move_thread_to_folder()`

当前策略：

- `services.mail_service` 仍保留同名兼容入口
- 旧调用方和测试暂时无需改导入路径
- 下一轮再继续抽离“草稿/发信”和“自动化/同步”

目的：

- 把“线程是核心对象”这件事代码层面坐实

## 4.7 `drafts.py`

职责：

- 草稿创建、更新、发送、回复起草

应该包含：

- `create_mail_draft()`
- `update_mail_draft()`
- `send_mail_draft()`
- `generate_reply_draft_for_thread()`

当前进度：

- 已完成第一轮抽离
- 当前已实际承载以下能力：
  - `create_mail_draft()`
  - `update_mail_draft()`
  - `send_mail_draft()`

兼容策略：

- 发信逻辑仍兼容 `services.mail_service` 上的 `asyncio` 与 `smtplib` monkeypatch
- 现有测试无需调整
- `generate_reply_draft_for_thread()` 仍暂留在兼容门面，下一轮可继续并入草稿域或自动化域

目的：

- 把“写信”和“收信/归并”分开

## 4.7A `messages.py`

职责：

- 邮件入库
- 线程归并入口
- 附件元数据落库

应该包含：

- `ingest_mail_message()`

当前进度：

- 已完成第一轮抽离
- 当前已实际承载以下能力：
  - `ingest_mail_message()`

兼容策略：

- 路由层、同步模块与旧测试仍通过 `services.mail_service.ingest_mail_message()` 使用该能力
- 外部调用方暂时无需改导入路径

## 4.8 `automation.py`

职责：

- 自动回信代理
- 自动处理判断与 agent run 记录

应该包含：

- `_has_agent_run()`
- `_record_agent_run()`
- `_normalize_auto_mail_policy()`
- `_is_user_direct_mail_thread()`
- `auto_handle_incoming_mail()`

当前进度：

- 已完成第一轮抽离
- 当前已实际承载以下能力：
  - `list_mail_agent_runs()`
  - `create_task_from_mail_thread()`
  - `generate_reply_draft_for_thread()`
  - `_has_agent_run()`
  - `_record_agent_run()`
  - `_normalize_auto_mail_policy()`
  - `_is_user_direct_mail_thread()`
  - `auto_handle_incoming_mail()`

兼容策略：

- AI 起草、命令提取、行动卡构建仍运行时跟随 `services.mail_service` 上的兼容别名
- 现有 monkeypatch 测试无需修改

目的：

- 让 AI 代理逻辑成为单独策略层
- 后面若引入更复杂的协商策略，不会继续污染线程和同步代码

## 4.9 `sync.py`

职责：

- IMAP 同步流程与同步运行记录

应该包含：

- `_create_sync_run()`
- `_finish_sync_run()`
- `get_mail_sync_status()`
- `sync_mail_account()`

当前进度：

- 已完成第一轮抽离
- 当前已实际承载以下能力：
  - `_create_sync_run()`
  - `_finish_sync_run()`
  - `reanalyze_mail_threads()`
  - `get_mail_sync_status()`
  - `sync_mail_account()`

兼容策略：

- IMAP 解析、`asyncio.to_thread`、`imaplib`、`ingest_mail_message()`、`auto_handle_incoming_mail()` 仍通过运行时引用回接 `services.mail_service`
- 轮询调度现已迁入 `runtime.py`

目的：

- 将“远程邮箱拉取”从本地领域处理分开
- 未来若要加入附件按需下载、Sent/Drafts 同步，这里是自然入口

## 4.10 `facade.py`

职责：

- 对外统一导出邮件子系统公共函数

当前进度：

- 已新增 [facade.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail/facade.py)
- 当前先承担统一导出层，兼容门面已基本收口
- 向外维持一套稳定 API

作用：

- 路由只依赖 facade
- `mail_service.py` 只依赖 facade
- 后续内部重构不会继续外溢

---

## 5. 分阶段执行方案

## Phase 0：规划与冻结边界

目标：

- 先把重构边界写清楚，不立刻动所有代码

交付：

- 本文档
- 明确模块职责
- 明确兼容策略

状态：

- 当前阶段

## Phase 1：建立子系统骨架，但不改变外部调用

目标：

- 创建 `services/mail/`
- 建立 `facade.py`
- 保留 `services/mail_service.py`

动作：

- 新建邮件子系统目录
- 先放 `__init__.py` 与 `facade.py`
- `mail_service.py` 保持原功能不变，暂不大拆

验收：

- 外部 import 路径全部不变
- 测试通过

## Phase 2：先拆无副作用模块

目标：

- 最先拆出最安全的部分

优先拆分顺序：

1. `utils.py`
2. `schema.py`
3. `parsing.py`

状态：

- 已完成

## 6. 当前测试结构

为了配合子系统化，测试已从单文件结构拆为按领域组织：

```text
local-gateway/test/
  conftest.py
  test_mail_facade.py
  test_mail_runtime.py
  test_mail_accounts.py
  test_mail_threads.py
  test_mail_drafts.py
  test_mail_automation.py
```

当前说明：

- `conftest.py`
  - 承载共享数据库 fixture `temp_mail_db`
- `test_mail_facade.py`
  - 只验证 `services.mail_service` 兼容门面仍暴露关键符号
- `test_mail_runtime.py`
  - 承载轮询配置与轮询执行聚合测试
- `test_mail_accounts.py`
  - 承载账户与默认文件夹逻辑
- `test_mail_threads.py`
  - 承载入库、线程归并、附件元数据与台账状态逻辑
- `test_mail_drafts.py`
  - 承载草稿生成、编辑、发送与状态转换
- `test_mail_automation.py`
  - 承载自动回信策略、agent run 记录与线程详情中的代理结果展示

当前收益：

- 测试边界与生产模块边界基本对齐
- `test_mail_service.py` 这种“大总管测试文件”已被移除
- 后续继续重构内部模块时，回归定位会更直接

当前验证结果：

- `conda run -n claude pytest -q ...`：22 passed
- `python -m compileall ...`：通过

## 7. 下一阶段建议

下一轮不建议继续机械拆文件，而应转向两个更有价值的方向：

### 7.1 收口兼容门面的 monkeypatch 依赖

当前多个子模块仍会在运行时回读 `services.mail_service` 上的兼容符号，例如：

- `asyncio.to_thread`
- `imaplib`
- `smtplib`
- `_generate_ai_reply_content`

这是为了兼容旧测试与旧调用方式，当前是合理的。  
但下一阶段可以考虑引入更显式的依赖注入层，减少模块对兼容门面的反向依赖。

当前进度补充：

- 已新增 [compat.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail/compat.py)
- 已将以下重复运行时桥接逻辑统一收口到 compat 层：
  - `DB_PATH`
  - `asyncio`
  - `smtplib`
  - `imaplib`
  - 通用 `get_runtime_attr(...)`
- 已清理 `accounts.py`、`automation.py`、`drafts.py`、`messages.py`、`runtime.py`、`schema.py`、`threads.py` 中重复的本地映射函数
- `drafts.py` 发送后写入已发件箱时，不再反向依赖 `mail_service._get_folder_id`，改为直接调用账户域函数

当前仍保留的兼容反向依赖：

- 当前仅剩 [compat.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail/compat.py) 作为单点兼容桥接层会触达 `services.mail_service`

保留原因：

- 旧测试与运行时 monkeypatch 仍需要一个稳定的兼容入口
- 但这种触达已经被限制在单个 compat 模块内，不再分散在各个业务域模块里

本轮进一步收口：

- [sync.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail/sync.py) 已不再回取整个 `mail_service` 模块
- 现改为通过显式运行时入口解析：
  - `ingest_mail_message`
  - `auto_handle_incoming_mail`
- 这样保留了 monkeypatch 兼容性，同时把依赖面从“整个兼容门面模块”收窄为“两项明确能力”

本轮验证结果：

- `conda run -n claude pytest -q ...`：22 passed
- `python -m compileall services/mail services/mail_service.py`：通过

### 7.2 为邮件子系统补更细颗粒度测试

现在的测试拆分已经足够支持继续开发，但还有空间：

- 为 `parsing.py` 增加纯解析单测
- 为 `utils.py` 增加 token / link 构造单测
- 为 `sync.py` 增加更多异常路径测试
- 为 `automation.py` 增加“需用户确认”与“自动发送失败”的边界覆盖

这样后续再清理内部依赖时，信心会更高。

原因：

- 这些模块副作用少
- 不直接改数据库流程主干
- 适合作为第一批低风险迁移

验收：

- `mail_service.py` 明显缩短
- 测试仍通过

## Phase 3：拆账户域和线程域

目标：

- 把最核心的数据访问和状态处理稳定拆开

顺序：

1. `accounts.py`
2. `threads.py`

原因：

- 这两块是整个系统的基础结构
- 也是后续 drafts / sync / automation 最依赖的部分

验收：

- 线程查询、账户查询、状态刷新行为不回退
- 前端书信台主要功能正常

## Phase 4：拆草稿与自动代理

目标：

- 把“回信生成”和“自动回信策略”分离

顺序：

1. `drafts.py`
2. `messages.py`
3. `automation.py`

原因：

- 自动代理逻辑目前最容易继续膨胀
- 必须尽快从线程与同步逻辑中剥离

验收：

- 自动策略测试通过
- 书信台起草、发送、台账显示不回退

## Phase 5：拆同步与轮询

目标：

- 把远程邮箱拉取、sync run、后台轮询独立成基础设施层

模块：

- `sync.py`
- `runtime.py`

验收：

- `main.py` 仍能正常启动轮询
- 手动同步和后台轮询都正常

## Phase 6：把 `mail_service.py` 收缩为兼容门面

目标：

- 不再保留核心实现
- 只保留兼容导出

最终形态：

- `mail_service.py` 只作为旧路径适配器
- 主要逻辑全部转入 `services/mail/`

当前状态更新：

- 当前 [mail_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail_service.py) 已只剩 schema 初始化与兼容导出
- 真实业务逻辑已基本迁出到 `services/mail/` 子模块
- 现阶段 [mail_service.py](/data/sda/tanzheng/Desktop/My_Claw/local-gateway/services/mail_service.py) 已进一步收缩为纯兼容导入层与兼容别名层

验收：

- 旧路由、旧测试不需要立即重写
- 新代码阅读入口转移到子系统目录

---

## 6. 兼容策略

重构期间保持：

- `from services import mail_service` 仍可用
- `import services.mail_service as mail_service` 仍可用
- 测试文件暂不需要立即重写

建议兼容方式：

```python
# local-gateway/services/mail_service.py
from services.mail.facade import *  # noqa
```

如果测试依赖内部符号：

- 第一阶段在 `facade.py` 中继续显式导出这些内部兼容符号
- 待测试重构完成后，再逐步收紧导出面

---

## 7. 风险与注意事项

## 7.1 最大风险：循环依赖

当前很多函数互相调用，例如：

- 线程查询依赖草稿
- 自动代理依赖线程与草稿
- 同步依赖解析与入库
- 轮询依赖账户和同步

应对方式：

- 公共工具只从 `utils.py` 提供
- 数据库 schema 只从 `schema.py` 提供
- 跨域调用优先在函数内部局部 import，而不是顶层互相引用

## 7.2 第二风险：测试依赖内部实现

现有测试里不只是调用公开 API，还 monkeypatch 了内部对象：

- `mail_service.asyncio.to_thread`
- `mail_service.smtplib.SMTP_SSL`
- `mail_service.notification_config`
- `mail_service._get_mail_account_raw`

所以 facade 阶段必须保留这些兼容暴露。

## 7.3 第三风险：重构时误改运行时状态

后台轮询、通知映射账户、portal token 都有运行时副作用。  
这些部分必须在独立阶段拆，不能和线程重构混在一轮里做。

---

## 8. 每阶段验收基线

每一阶段至少执行：

1. `pytest -q local-gateway/test/test_mail_service.py`
2. `python -m compileall local-gateway/services local-gateway/routers`
3. `npm run build`

若阶段涉及页面行为，再补：

4. 手工检查书信台主要路径
5. 手工检查设置页中的 `NOTIFY NETWORK` 与邮件策略联动

---

## 9. 推荐实施顺序

如果从今天开始实际动手，建议顺序如下：

1. 建立 `services/mail/` 子系统骨架与 facade
2. 迁移 `utils.py`、`schema.py`、`parsing.py`
3. 迁移 `accounts.py`
4. 迁移 `threads.py`
5. 迁移 `drafts.py`
6. 迁移 `messages.py`
7. 迁移 `automation.py`
8. 迁移 `sync.py` 与 `runtime.py`
9. 将 `mail_service.py` 收缩为兼容门面

这样做的好处是：

- 先拆低风险部分
- 最后才碰最重的轮询与同步
- 每步都可回退

---

## 10. 下一步执行建议

下一步不要直接“大拆完”。  
应该进入 **Phase 1 + Phase 2**：

- 创建 `services/mail/`
- 建立 `facade.py`
- 先迁移 `utils.py`、`schema.py`、`parsing.py`
- 保证外部 import 不变

这是当前最稳、最干净的起步方式。
