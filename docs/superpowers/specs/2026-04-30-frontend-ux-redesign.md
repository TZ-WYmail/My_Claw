# 前端 UX 系统性重构设计

**设计哲学**: Apple HIG — 清晰、顺从、纵深

---

## 第 1 节：整体布局与导航

### 现状

12 个平级标签页水平排列，无层级感，AI 对话藏在右下角浮动按钮中。所有面板通过 `display: none/block` 瞬间切换。

### 方案：侧边栏 + 主内容区

```
┌──────────┬──────────────────────────────────┐
│          │                                  │
│  侧边栏   │         主内容区                  │
│          │                                  │
│  🏠 仪表盘 │    ┌─────────────────────────┐   │
│  📋 任务   │    │                         │   │
│  📝 笔记   │    │   卡片式内容              │   │
│  🎯 习惯   │    │   毛玻璃材质的顶部栏       │   │
│  📅 日历   │    │   淡入淡出的页面切换       │   │
│  ──────── │    │                         │   │
│  🤖 AI    │    └─────────────────────────┘   │
│  ⚡ 工作流 │                                  │
│  🔄 同步   │                                  │
│  📥 下载   │                                  │
│  🔧 沙盒   │                                  │
│  ⚙️ 设置   │                                  │
│          │                                  │
└──────────┴──────────────────────────────────┘
```

**设计要点：**

- 前 5 项（仪表盘、任务、笔记、习惯、日历）为高频操作，视觉分隔线以下为低频
- 侧边栏默认展开，支持折叠为图标模式，折叠后鼠标悬停展开
- 侧边栏使用 `backdrop-filter: blur` 毛玻璃效果，与内容区建立纵深层次
- 页面切换使用 opacity + translateY(4px) 淡入淡出，时长 200-300ms
- 侧边栏底部显示当前设备连接状态指示灯

**状态指示器：**
- 侧边栏底部固定区域，显示连接状态（绿点/红点/黄点）
- 悬停显示服务版本、最后一次健康检查时间

### AI 对话作为独立一级入口

AI 对话在侧边栏中与仪表盘、任务平级，不再使用浮动按钮。

布局为三栏结构：

```
┌──────┬───────────────────┬─────────────────┐
│      │                   │                 │
│ 侧边栏│    对话区域        │   会话信息面板   │
│      │                   │   (可折叠)      │
│  🤖 ◀ │  ┌─────────────┐  │                 │
│      │  │ iMessage 式   │  │  当前模型       │
│      │  │ 对话气泡      │  │  token 用量     │
│      │  │              │  │  工具调用次数    │
│      │  │ 用户: 蓝色    │  │                 │
│      │  │ AI:   灰色    │  │  会话历史       │
│      │  └─────────────┘  │  └ 新对话按钮    │
│      │  ┌───────────────┐ │                 │
│      │  │ 输入框 ⌘Enter │ │                 │
│      │  └───────────────┘ │                 │
└──────┴───────────────────┴─────────────────┘
```

**消息样式：**

| 角色 | 样式 | 对齐 |
|------|------|------|
| 用户 | 蓝色气泡 | 右对齐 |
| AI | 浅灰气泡（深色模式: 深灰），左带 AI 图标 | 左对齐 |
| 系统/错误 | 居中，无气泡，小号文字 | 居中 |
| 工具调用 | 折叠式迷你卡片 "🔧 正在执行：创建任务..." | 左对齐 |
| 打字中 | 三点跳动动画，毛玻璃底 | 左对齐 |

**核心交互：**
- ⌘Enter 发送，Shift+Enter 换行
- ⌘K 在对话内打开命令面板，直接从对话创建任务/查询日历
- 右键消息可复制/重新生成
- 侧边栏 AI 入口下方显示最近 3 条对话标题，点击切换
- 新对话按钮在所有会话历史之上

**会话管理：**
- 右侧信息面板默认折叠显示当前模型名
- 点击展开：当前模型、token 用量、工具调用统计、历史对话列表
- 历史对话从 SQLite 读取，与后端 chat_conversations 表对应

---

## 第 2 节：动效与过渡系统

### 三个层级

**页面过渡（200-300ms）：**
- 侧边栏点击切换：当前页面 fadeOut + translateY(-4px)，新页面 fadeIn + translateY(0)，带 `cubic-bezier(0.25, 0.1, 0.25, 1.0)` 缓动
- 感觉像翻阅卡片，不是跳转页面

**微交互（150-250ms）：**

| 操作 | 动效 |
|------|------|
| 完成任务 | 勾选图标弹性放大回弹，任务行变灰划删除线 |
| 习惯打卡 | 连续天数数字弹跳 +1，火焰图标短暂发光 |
| 删除 | 卡片缩小淡出，底部滑入「已删除，可撤销」 |
| 创建笔记 | 卡片从顶部展开滑入，标题自动聚焦 |
| 切换主题 | 从点击位置扩散圆形遮罩 |

**反馈动画：**
- 骨架屏使用呼吸脉冲（opacity 0.4-0.7 波动），非 spinner
- Toast 从顶部滑入悬停，毛玻璃背景，自动消失时向上滑出
- 空状态图标轻微浮动（translateY ±4px 缓动循环）

### 缓动函数

```css
--ease-apple:  cubic-bezier(0.25, 0.1, 0.25, 1.0);   /* 快速启动，柔和收尾 */
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);      /* 弹性，用于打卡/完成 */
--ease-enter:  cubic-bezier(0.0, 0.0, 0.2, 1.0);      /* 元素入场 */
--ease-exit:   cubic-bezier(0.4, 0.0, 1.0, 1.0);      /* 元素退场 */
```

### 实现方式

所有动效用 CSS transition/animation + JS 触发 class，不引入动画库。Alpine.js 的 `x-transition` 指令处理常见的进入/离开过渡。

---

## 第 3 节：状态设计系统

每个视图都有四种状态，状态是设计的一部分：

### 加载状态

不出现全局 spinner。用**骨架屏**精确匹配真实内容布局：

```
仪表盘加载:
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│ ████  │ │ ████  │ │ ████  │ │ ████  │  ← 统计卡片骨架
│  ██   │ │  ██   │ │  ██   │ │  ██   │
└──────┘ └──────┘ └──────┘ └──────┘
┌─────────────────┐ ┌─────────────────┐
│ ████  ████      │ │ ████  ████      │  ← 列表骨架
│ ████  ████      │ │ ████  ████      │    呼吸脉冲动画
│ ████  ████      │ │ ████  ████      │
└─────────────────┘ └─────────────────┘
```

实现：CSS `background: linear-gradient(90deg, var(--skeleton-base) 25%, var(--skeleton-shine) 50%, var(--skeleton-base) 75%)` + `background-size: 200% 100%` + infinite animation。

### 空状态（首次使用）

不是「暂无数据」，而是**引导式插图 + 行动号召 + 快捷键提示**：

```
         ┌─────┐
         │ 📋  │   ← 大图标，浮动动画
         └─────┘
      还没有任务

    规划你的第一周计划
    [✨ 创建第一个任务]    ← 主按钮带呼吸光晕

    提示: 按 ⌘N 快速创建
```

每个模块的空状态文案和图标定制化，不是通用组件。

### 错误状态

两种错误分别处理：

- **局部错误**（单个操作失败）→ 顶部滑入 toast，带 retry 按钮，不影响页面其余内容
- **全局错误**（网络断开、服务不可用）→ 内容区顶部轻量横幅 + 侧边栏状态指示灯变红

### 成功状态

关键操作完成后短暂庆祝后归于平静（不打断用户流程）：
- 完成任务 → 勾选动画 + 统计数字更新
- 习惯连续 7 天 → 火焰图标弹跳
- 笔记保存 → 标题栏短暂变绿后恢复

---

## 第 4 节：组件化拆分

### 文件结构

```
static/
├── index.html              # 壳: 侧边栏 + 主内容区 + 全局元素
├── css/
│   ├── variables.css       # CSS 自定义属性（颜色/间距/圆角/缓动/阴影/字体）
│   ├── layout.css          # 侧边栏 + 主内容区布局
│   ├── components.css      # 按钮/卡片/tag/输入框/badge/modal/toast/骨架屏
│   └── animations.css      # 过渡/关键帧/动效 class
├── js/
│   ├── app.js              # Alpine.js 初始化 + 全局 store + 命令面板 + 主题
│   ├── router.js           # 视图切换 + 浏览器历史（hash-based）
│   ├── api.js              # HTTP + SSE 流式封装 + 请求去重 + 乐观更新辅助
│   ├── utils.js            # formatTime / escapeHtml / debounce 等纯函数
│   └── components/
│       ├── dashboard.js    # 仪表盘数据 + 骨架 + 空状态
│       ├── tasks.js        # 任务 CRUD + 周视图 + 乐观完成/删除
│       ├── notes.js        # 笔记编辑器 + 列表 + 标签
│       ├── habits.js       # 习惯列表 + 打卡动画 + 连续天数
│       ├── calendar.js     # 月视图日历 + 事件渲染
│       ├── ai-chat.js      # AI 对话 + 流式渲染 + 会话切换 + 配置
│       ├── workflows.js    # 工作流列表 + 执行记录
│       ├── sync.js         # 同步状态 + 手动同步
│       ├── download.js     # 下载表单 + 历史列表
│       └── sandbox.js      # 沙盒执行 + 结果展示
├── icons/                  # PWA 图标（保留现有）
├── manifest.json           # PWA manifest（保留现有）
└── sw.js                   # Service Worker（保留现有）
```

### 组件模式

每个组件以 Alpine.js `Alpine.data()` 注册，在 HTML 中通过 `x-data` 使用：

```html
<!-- index.html 中 -->
<section x-show="$store.view.current === 'tasks'" x-data="tasks" x-trap="$store.view.current === 'tasks'">
  <!-- 加载骨架 -->
  <div x-show="loading" class="skeleton-task-list">...</div>

  <!-- 空状态 -->
  <div x-show="!loading && tasks.length === 0" class="empty-state">...</div>

  <!-- 内容 -->
  <div x-show="!loading && tasks.length > 0">
    <template x-for="task in tasks" :key="task.task_id">
      <div class="task-card" x-transition>
        <!-- 任务卡片 -->
      </div>
    </template>
  </div>
</section>
```

### 全局状态（Alpine Store）

```javascript
Alpine.store('app', {
  theme: localStorage.getItem('lcc-theme') || 'dark',
  connected: false,
  version: '',
});

Alpine.store('view', {
  current: 'dashboard',    // 当前视图
  previous: null,          // 上一个视图（用于返回过渡方向）
  toggleSidebar() { ... }, // 折叠/展开侧边栏
  navigateTo(view) { ... },// 切换视图（记录历史、触发过渡）
});
```

### Router 设计

基于 hash 的轻量路由，`#/tasks`、`#/notes`、`#/chat` 等。支持：
- 浏览器前进/后退
- 深链接（直接打开到指定页面）
- 视图切换时保存/恢复滚动位置

---

## 第 5 节：CSS 变量体系

统一管理设计 token，确保深色/浅色主题一致切换：

```css
:root {
  /* 颜色 - 浅色 */
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f5f5f7;     /* Apple 式微灰背景 */
  --color-bg-tertiary: #e8e8ed;
  --color-surface: rgba(255,255,255,0.72);
  --color-text-primary: #1d1d1f;
  --color-text-secondary: #86868b;
  --color-text-tertiary: #aeaeb2;
  --color-accent: #0071e3;            /* Apple 蓝 */
  --color-accent-hover: #0077ed;
  --color-danger: #ff3b30;
  --color-success: #34c759;
  --color-warning: #ff9f0a;
  --color-border: rgba(0,0,0,0.08);
  --color-separator: rgba(0,0,0,0.12);

  /* 骨架屏 */
  --skeleton-base: #e8e8ed;
  --skeleton-shine: #f0f0f5;

  /* 间距 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  /* 圆角 */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --radius-full: 9999px;

  /* 阴影 */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.12);
  --shadow-xl: 0 20px 60px rgba(0,0,0,0.15);

  /* 毛玻璃 */
  --blur-sidebar: saturate(180%) blur(20px);

  /* 缓动（见第 2 节） */
  --ease-apple: cubic-bezier(0.25, 0.1, 0.25, 1.0);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-enter: cubic-bezier(0.0, 0.0, 0.2, 1.0);
  --ease-exit: cubic-bezier(0.4, 0.0, 1.0, 1.0);

  /* 字体 */
  --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
  --font-mono: "SF Mono", "Fira Code", monospace;

  /* 动效时长 */
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 350ms;
}

[data-theme="dark"] {
  --color-bg-primary: #000000;
  --color-bg-secondary: #1c1c1e;
  --color-bg-tertiary: #2c2c2e;
  --color-surface: rgba(28,28,30,0.72);
  --color-text-primary: #f5f5f7;
  --color-text-secondary: #98989d;
  --color-text-tertiary: #636366;
  --color-accent: #0a84ff;
  --color-accent-hover: #409cff;
  --color-border: rgba(255,255,255,0.08);
  --color-separator: rgba(255,255,255,0.12);
  --skeleton-base: #2c2c2e;
  --skeleton-shine: #3a3a3c;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.5);
  --shadow-xl: 0 20px 60px rgba(0,0,0,0.6);
}
```

---

## 第 6 节：键盘快捷键

| 快捷键 | 操作 |
|--------|------|
| ⌘K | 命令面板（全局搜索 + 快捷操作） |
| ⌘N | 新建任务 |
| ⌘J | 打开 AI 对话 |
| ⌘1-5 | 切换到前 5 个高频视图（仪表盘/任务/笔记/习惯/日历） |
| ⌘B | 折叠/展开侧边栏 |
| ⌘⇧N | 新建笔记 |
| Esc | 关闭弹窗 / 返回上一视图 |
| Space | 快速完成选中的任务 |
| ⌘Enter | 发送 AI 消息 |
| ⌘⇧T | 切换主题 |

---

## 第 7 节：落地策略

### 技术决策

| 决策 | 选择 | 原因 |
|------|------|------|
| UI 框架 | Alpine.js (~15KB) | 零构建步骤，声明式组件，x-transition 原生支持动画 |
| 附加库 | @alpinejs/collapse (~1KB) | 侧边栏折叠/面板展开收起 |
| 构建工具 | 不需要 | CDN 引入，保持现有零构建优势 |
| CSS 方案 | CSS 变量 + 常规 CSS | 不引入 PostCSS/Tailwind，保持简单 |
| 模块系统 | ES modules（type="module"） | 现代浏览器全支持，自然拆分组件 |
| 路由 | Hash-based 轻路由 | #/tasks、#/notes 等，支持浏览器前进后退 |

### 渐进式交付

本次重构分三期交付，每期独立可上线：

**第一期：基础架构（核心体验）**
- CSS 变量体系 + 主题改造
- 侧边栏布局（替换 12 个标签页）
- 视图路由（hash-based）
- 仪表盘、任务模块组件化
- 全局命令面板（⌘K）

**第二期：内容模块**
- 笔记、习惯、日历模块组件化
- 下载、沙盒、同步模块组件化
- AI 对话独立界面 + 流式渲染 + 会话管理

**第三期：打磨**
- 全局骨架屏
- 动效微调
- 键盘快捷键补全
- PWA 离线体验优化

---

## 自审清单

- [x] **占位符扫描**: 无 TBD/TODO/待定项
- [x] **内部一致性**: 动效系统、状态设计、CSS 变量、组件拆分 — 四者互补无矛盾
- [x] **范围检查**: 聚焦前端 UX 重构，不涉及后端 API 变更
- [x] **歧义检查**: 每个交互的视觉表现和行为都有明确定义
- [x] **落地可行性**: Alpine.js CDN 引入，ES modules 原生支持，无需构建工具
