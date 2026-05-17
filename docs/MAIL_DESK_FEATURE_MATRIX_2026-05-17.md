# 书信台能力矩阵

日期：2026-05-17  
范围：`local-gateway/frontend/src/pages/Download.jsx` 对应的桌面书信工作台，以及它已接通的邮件后端能力。  
目的：给下一轮开发一个明确基线，避免继续在单页内凭感觉补按钮。

---

## 1. 当前已经接通的能力

### 1.1 账户与收信控制

- 账户切换
- 信箱切换：`全部 / inbox / archive / sent / drafts`
- 手动同步收件箱
- 后台轮询单次执行
- 后台轮询配置：
  - 开关
  - 轮询信箱
  - 间隔秒数
  - 单次上限
- 轮询状态反馈：
  - 保存中状态
  - 最近成功时间
  - 最近错误
  - 本轮轮询汇总
  - 本轮轮询明细展开
- 当前账户链路检定
- 最近同步台账：
  - 状态
  - 抓取 / 新增数量
  - latest UID
  - 最近失败提示

### 1.2 线程浏览与筛选

- 线程关键词过滤
- 只看未读
- 只看待回信
- 只看待决定
- 活跃线程与归档线程分流显示
- 活跃线程采用横向翻页式 rail
- 上一封 / 下一封切换
- 当前线程局部刷新
- 归档线程不会继续占住活跃 rail

### 1.3 展开信件后的桌面动作

- 打开邮件处理页
- 复制处理页链接
- 直接使用系统邮箱继续回信 `mailto`
- 标记已读
- 归档线程
- 决策状态：
  - 恢复待决定
  - 稍后再问
  - 暂时处理完
- 回复这封信
- 一键起草
- 转成任务
- 和 AI 商量

### 1.4 草稿工作流

- 新建独立草稿
- 在线程内继续写草稿
- 只保存草稿
- 发送当前草稿
- 编辑现有草稿
- 将编辑中的草稿回退到服务器上的最新版本
- 发信后刷新线程与工作台

### 1.5 自动处理可解释性

- 展示线程分析理由 `analysis_reason`
- 展示当前决策状态 `pending / snoozed / cleared`
- 展示当前账户自动策略
- 展示策略叙述文本
- 展示最近一次 agent run：
  - 状态
  - 结果摘要
  - reason code 解释
  - 命令识别解释
  - 时间
- `auto_send` 策略的高亮风险提示
- agent ledger 支持：
  - 状态筛选
  - 局部刷新

### 1.6 邮件正文呈现

- HTML 邮件清洗后渲染
- 纯文本邮件自动识别链接
- 支持：
  - `http/https`
  - `mailto`
  - `tel`
  - `www.*`
  - 裸邮箱地址
- 附件元数据卡片展示

---

## 2. 当前前端已经解决的关键问题

- `offlineQueue.map is not a function` 已修复
- `taskWindow is not defined` 已修复
- 邮件 HTML 特殊链接无法正确渲染的问题已修复
- agent ledger 过滤后整块消失的问题已修复
- 草稿编辑缺少“回到最近保存版本”的问题已补齐
- 线程详情和 agent ledger 已支持拆分刷新
- 邮件处理页与桌面书信台的动作语义已开始对齐

---

## 3. 仍然缺失或只做到一半的部分

### 3.1 前端结构层

- `Download.jsx` 仍然过长，已经成为维护瓶颈
- 没有拆分出稳定子模块：
  - `MailControlPanel`
  - `MailThreadRail`
  - `OpenLetterPanel`
  - `MailComposerModal`
  - `MailAutomationLedger`
- 没有统一的 mail desk state hook

### 3.2 回信与草稿能力

- 没有草稿 diff / 版本历史
- 没有“放弃本地修改但保留弹窗”的显式脏状态提示
- 没有发信前摘要确认层
- 没有 send failure 的重试引导区

### 3.3 agent run 与轮询台账

- agent run 只能看列表，不能展开完整 `details`
- 轮询结果也还是摘要级，缺少每账户更细的异常上下文
- 没有“仅刷新 polling / sync / thread / agent ledger”这一类更系统化的刷新框架

### 3.4 自动化判断可解释性

- “为何被判断为 direct / non-direct” 仍未完整展开
- 没有把 `is_user_direct_mail_thread()` 的判定维度直接展示给用户
- 没有展示“若切换策略，这封信会如何处理”的模拟结果

### 3.5 测试与回归保护

- 前端还没有正式测试基建
- 当前只能依赖 `npm run build` 做编译级验证
- 尚未接入组件级交互测试
- 尚未接入桌面书信台的回归脚本

---

## 4. 下一轮最值得做的事情

按优先级建议如下。

### P1：先拆前端子系统

目标：让书信台不再继续堆在一个超长文件里。

建议拆分：

- `components/maildesk/MailControlGrid.jsx`
- `components/maildesk/MailThreadRail.jsx`
- `components/maildesk/OpenLetterPanel.jsx`
- `components/maildesk/MailComposerModal.jsx`
- `components/maildesk/MailAutomationPanel.jsx`
- `hooks/useMailDeskState.js`

### P2：补 agent run 详情展开

目标：不只告诉用户“失败了”，而是告诉用户“为什么失败、停在哪一步、涉及哪条策略”。

建议补充：

- 单条 agent run 展开
- `details.command`
- `details.policy`
- `details.reason_code`
- `draft_id`
- 是否 direct 判定

### P3：补发信确认与失败恢复

目标：让回信链路更可信。

建议补充：

- 发信前确认卡
- 发信失败时保留当前编辑态
- 一键重试发送
- 失败后回到最近已保存版本

### P4：补最小前端测试基线

目标：避免后续重构 `Download.jsx` 时再次引入明显渲染错误。

建议最小集合：

- 安装 `vitest` + `@testing-library/react`
- 覆盖：
  - 轮询配置反馈渲染
  - 当前线程刷新按钮
  - 草稿回退按钮
  - agent ledger 过滤不消失
  - `mailto` 按钮在有收件人时出现

---

## 5. 本轮结论

书信台已经从“单纯下载页残留”升级成了一个可工作的桌面邮件工作台。  
但它现在的主要瓶颈已经不再是“缺按钮”，而是：

- 文件过长
- 前端状态过于集中
- 缺少交互测试
- 自动处理解释层还不够结构化

下一轮如果继续高强度加功能，应该先拆模块，再补测试，否则维护成本会明显恶化。
