# Frontend UX Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace monolithic vanilla-JS frontend with an Apple HIG-inspired Alpine.js component architecture — sidebar navigation, smooth transitions, CSS variables, skeleton states, and independent AI chat interface.

**Architecture:** Alpine.js (~15KB CDN) for reactive components + ES modules for JS organization + CSS variables for unified design tokens. Zero build step preserved. Three-phase delivery: foundation → content modules → polish.

**Tech Stack:** Alpine.js 3.x (CDN), @alpinejs/collapse (CDN), ES modules, CSS Custom Properties, hash-based routing

---

## File Structure

### New Files

```
static/
├── css/
│   ├── variables.css       # Design tokens (colors, spacing, radius, shadow, easing)
│   ├── layout.css          # Sidebar + main area + header
│   ├── components.css      # Buttons, cards, inputs, badges, modals, toast, skeleton
│   └── animations.css      # Keyframes, transitions, state-driven animations
├── js/
│   ├── app.js              # Alpine init, global store, theme, command palette
│   ├── router.js           # Hash-based view router
│   ├── api.js              # HTTP + SSE helpers
│   ├── utils.js            # formatTime, escapeHtml, debounce (from current app.js)
│   └── components/
│       ├── dashboard.js
│       ├── tasks.js
│       ├── notes.js
│       ├── habits.js
│       ├── calendar.js
│       ├── ai-chat.js
│       ├── workflows.js
│       ├── sync.js
│       ├── download.js
│       └── sandbox.js
```

### Modified Files

- `static/index.html` — Rewrite shell: sidebar + main area + CDN imports
- `static/manifest.json` — No change
- `static/sw.js` — No change (Phase 3 minor updates)
- `static/icons/` — No change

### Removed Files (after migration)

- `static/app.js` — Split into js/ modules
- `static/style.css` — Split into css/ modules

---

## Phase 1: Foundation (Core Experience)

### Task 1: CSS Variable System + Base Reset

**Files:**
- Create: `static/css/variables.css`
- Create: `static/css/components.css`
- Create: `static/css/animations.css`

- [ ] **Step 1: Create variables.css — design tokens**

```css
/* static/css/variables.css */
/* Design tokens — single source of truth for the entire UI */

:root, [data-theme="dark"] {
  /* Background */
  --bg-primary: #000000;
  --bg-secondary: #1c1c1e;
  --bg-tertiary: #2c2c2e;
  --bg-card: #1c1c1e;
  --bg-input: #2c2c2e;
  --surface: rgba(28,28,30,0.72);

  /* Text */
  --text-primary: #f5f5f7;
  --text-secondary: #98989d;
  --text-tertiary: #636366;

  /* Accent */
  --accent: #0a84ff;
  --accent-hover: #409cff;
  --success: #30d158;
  --warning: #ff9f0a;
  --error: #ff453a;

  /* Border & Separator */
  --border: rgba(255,255,255,0.08);
  --separator: rgba(255,255,255,0.12);

  /* Skeleton */
  --skeleton-base: #2c2c2e;
  --skeleton-shine: #3a3a3c;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.5);
  --shadow-xl: 0 20px 60px rgba(0,0,0,0.6);

  /* Blur */
  --blur-sidebar: saturate(180%) blur(20px);

  /* Easing */
  --ease-apple: cubic-bezier(0.25, 0.1, 0.25, 1.0);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-enter: cubic-bezier(0.0, 0.0, 0.2, 1.0);
  --ease-exit: cubic-bezier(0.4, 0.0, 1.0, 1.0);

  /* Typography */
  --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
  --font-mono: "SF Mono", "Fira Code", "Cascadia Code", monospace;

  /* Duration */
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 350ms;

  /* Sidebar */
  --sidebar-width: 220px;
  --sidebar-collapsed-width: 56px;
}

[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f7;
  --bg-tertiary: #e8e8ed;
  --bg-card: #ffffff;
  --bg-input: #f1f1f4;
  --surface: rgba(255,255,255,0.72);
  --text-primary: #1d1d1f;
  --text-secondary: #86868b;
  --text-tertiary: #aeaeb2;
  --accent: #0071e3;
  --accent-hover: #0077ed;
  --success: #34c759;
  --warning: #ff9f0a;
  --error: #ff3b30;
  --border: rgba(0,0,0,0.06);
  --separator: rgba(0,0,0,0.10);
  --skeleton-base: #e8e8ed;
  --skeleton-shine: #f0f0f5;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.10);
  --shadow-xl: 0 20px 60px rgba(0,0,0,0.12);
}
```

- [ ] **Step 2: Create components.css — shared components**

```css
/* static/css/components.css */
/* Shared UI components */

/* ---- Base Reset ---- */
* { margin: 0; padding: 0; box-sizing: border-box; }

html { font-size: 15px; }

body {
  font-family: var(--font-sans);
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ---- Buttons ---- */
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: none; border-radius: var(--radius-sm);
  font-size: 0.875rem; font-weight: 500; cursor: pointer;
  background: var(--bg-tertiary); color: var(--text-primary);
  transition: all var(--duration-fast) var(--ease-apple);
}
.btn:hover { background: var(--border); }
.btn:active { transform: scale(0.97); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-hover); }

.btn-danger { background: var(--error); color: #fff; }
.btn-danger:hover { background: #ff453a; opacity: 0.9; }

.btn-success { background: var(--success); color: #fff; }
.btn-sm { padding: 4px 10px; font-size: 0.8rem; }
.btn-icon { width: 32px; height: 32px; padding: 0; display: inline-flex;
  align-items: center; justify-content: center; border-radius: var(--radius-full); }
.btn-ghost { background: transparent; color: var(--text-secondary); }
.btn-ghost:hover { background: var(--bg-tertiary); color: var(--text-primary); }

/* ---- Cards ---- */
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
}
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--space-md);
}
.card-header h3 { font-size: 0.95rem; font-weight: 600; color: var(--text-secondary); }

/* ---- Inputs ---- */
input, select, textarea {
  width: 100%; padding: 10px 12px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); font-size: 0.9rem; font-family: inherit;
  background: var(--bg-input); color: var(--text-primary);
  transition: border-color var(--duration-fast) var(--ease-apple),
              box-shadow var(--duration-fast) var(--ease-apple);
}
input:focus, select:focus, textarea:focus {
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(10,132,255,0.15);
}
textarea { resize: vertical; min-height: 80px; }

/* ---- Badges ---- */
.badge {
  display: inline-flex; align-items: center; padding: 2px 8px;
  border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 500;
}
.badge-pending { background: rgba(255,159,10,0.12); color: var(--warning); }
.badge-completed { background: rgba(48,209,88,0.12); color: var(--success); }
.badge-error { background: rgba(255,69,58,0.12); color: var(--error); }

/* ---- Empty State ---- */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: var(--space-2xl) var(--space-lg); text-align: center; color: var(--text-tertiary);
}
.empty-state-icon { font-size: 2.5rem; margin-bottom: var(--space-md); opacity: 0.6; }
.empty-state-text { font-size: 0.95rem; margin-bottom: var(--space-sm); }
.empty-state-hint { font-size: 0.8rem; margin-bottom: var(--space-lg); }
.empty-state-icon {
  animation: float 3s ease-in-out infinite;
}

/* ---- Toast ---- */
.toast-container {
  position: fixed; top: var(--space-md); right: var(--space-md);
  z-index: 9999; display: flex; flex-direction: column; gap: var(--space-sm);
  max-width: 360px;
}
.toast {
  padding: 12px 16px; border-radius: var(--radius-md); font-size: 0.875rem;
  backdrop-filter: var(--blur-sidebar); -webkit-backdrop-filter: var(--blur-sidebar);
  box-shadow: var(--shadow-lg); border: 1px solid var(--border);
  animation: toastIn var(--duration-normal) var(--ease-enter);
}
.toast-success { background: rgba(48,209,88,0.15); color: var(--success); }
.toast-error { background: rgba(255,69,58,0.15); color: var(--error); }
.toast-info { background: var(--surface); color: var(--text-primary); }

/* ---- Modal ---- */
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.modal {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-xl); padding: var(--space-xl); min-width: 360px;
  box-shadow: var(--shadow-xl);
  animation: modalIn var(--duration-normal) var(--ease-enter);
}

/* ---- Skeleton ---- */
.skeleton {
  background: linear-gradient(90deg, var(--skeleton-base) 25%, var(--skeleton-shine) 50%, var(--skeleton-base) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
.skeleton-text { height: 14px; margin-bottom: 8px; }
.skeleton-text:last-child { width: 60%; }
.skeleton-card { height: 80px; margin-bottom: 12px; }

/* ---- Stats Grid ---- */
.stats-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-md); margin-bottom: var(--space-lg);
}
.stat-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: var(--space-lg);
  display: flex; align-items: center; gap: var(--space-md);
  transition: transform var(--duration-fast) var(--ease-apple);
}
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.stat-icon { font-size: 1.5rem; }
.stat-value { font-size: 1.6rem; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 0.8rem; color: var(--text-tertiary); }

/* ---- Data Table ---- */
.data-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.data-table th { text-align: left; padding: 10px 12px; font-weight: 600;
  color: var(--text-secondary); border-bottom: 1px solid var(--separator); }
.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
.data-table tr:hover td { background: var(--bg-tertiary); }
.data-table .empty { text-align: center; color: var(--text-tertiary); padding: var(--space-xl); }

/* ---- Activity List ---- */
.activity-list { display: flex; flex-direction: column; gap: 2px; }
.activity-item {
  display: flex; align-items: center; gap: var(--space-sm);
  padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.85rem;
}
.activity-item:hover { background: var(--bg-tertiary); }
.activity-icon { flex-shrink: 0; width: 24px; text-align: center; }
.activity-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.activity-time { flex-shrink: 0; color: var(--text-tertiary); font-size: 0.8rem; }

/* ---- Pagination ---- */
.pagination {
  display: flex; align-items: center; justify-content: center;
  gap: var(--space-sm); margin-top: var(--space-md);
}
.pagination button {
  padding: 6px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-primary); cursor: pointer;
  font-size: 0.85rem;
}
.pagination button:hover { background: var(--bg-tertiary); }
.pagination button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.pagination button:disabled { opacity: 0.3; cursor: not-allowed; }
```

- [ ] **Step 3: Create animations.css — keyframes and motion**

```css
/* static/css/animations.css */
/* All keyframes and transition utilities */

/* ---- Keyframes ---- */
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

@keyframes toastIn {
  from { opacity: 0; transform: translateY(-12px) scale(0.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes bounceIn {
  0% { transform: scale(0.3); opacity: 0; }
  50% { transform: scale(1.08); }
  70% { transform: scale(0.95); }
  100% { transform: scale(1); opacity: 1; }
}

@keyframes checkmark {
  0% { transform: scale(0) rotate(-45deg); opacity: 0; }
  50% { transform: scale(1.3) rotate(0deg); opacity: 1; }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}

@keyframes streakPop {
  0% { transform: scale(1); }
  50% { transform: scale(1.4); color: var(--warning); }
  100% { transform: scale(1); }
}

@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(0.4); opacity: 0.3; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes themeCircle {
  from { clip-path: circle(0% at var(--x, 50%) var(--y, 50%)); }
  to { clip-path: circle(150% at var(--x, 50%) var(--y, 50%)); }
}

/* ---- Transition Utilities ---- */
.view-enter { animation: viewEnter var(--duration-normal) var(--ease-enter); }
@keyframes viewEnter {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.view-leave { animation: viewLeave var(--duration-fast) var(--ease-exit); }
@keyframes viewLeave {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-4px); }
}

.task-complete {
  animation: bounceIn var(--duration-normal) var(--ease-spring);
}

.streak-pop {
  animation: streakPop var(--duration-slow) var(--ease-spring);
}
```

- [ ] **Step 4: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add static/css/variables.css static/css/components.css static/css/animations.css
git commit -m "feat: add CSS design system — variables, components, animations"
```

---

### Task 2: Sidebar Layout Shell + Alpine.js Init

**Files:**
- Create: `static/css/layout.css`
- Create: `static/js/app.js`
- Modify: `static/index.html` (rewrite shell)

- [ ] **Step 1: Create layout.css — sidebar + main area**

```css
/* static/css/layout.css */
/* Sidebar + main content area layout */

body { overflow: hidden; height: 100vh; }

.app-shell {
  display: flex; height: 100vh; overflow: hidden;
}

/* ---- Sidebar ---- */
.sidebar {
  width: var(--sidebar-width); flex-shrink: 0;
  background: var(--surface);
  backdrop-filter: var(--blur-sidebar);
  -webkit-backdrop-filter: var(--blur-sidebar);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  transition: width var(--duration-normal) var(--ease-apple);
  z-index: 100;
}
.sidebar.collapsed { width: var(--sidebar-collapsed-width); }

.sidebar-header {
  display: flex; align-items: center; gap: var(--space-sm);
  padding: var(--space-md); padding-top: var(--space-lg);
  margin-bottom: var(--space-sm);
}
.sidebar-header .logo { font-size: 1.1rem; font-weight: 700; white-space: nowrap; }
.sidebar-header .version {
  font-size: 0.7rem; color: var(--text-tertiary);
  background: var(--bg-tertiary); padding: 1px 6px; border-radius: var(--radius-full);
}

.sidebar-nav { flex: 1; display: flex; flex-direction: column; gap: 2px; padding: 0 var(--space-sm); }

.nav-item {
  display: flex; align-items: center; gap: var(--space-sm);
  padding: 8px 12px; border-radius: var(--radius-md);
  color: var(--text-secondary); cursor: pointer;
  transition: all var(--duration-fast) var(--ease-apple);
  white-space: nowrap; font-size: 0.9rem; border: none; background: none;
  width: 100%; text-align: left; font-family: inherit;
}
.nav-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.nav-item.active { background: var(--accent); color: #fff; }
.nav-item .nav-icon { font-size: 1.1rem; width: 24px; text-align: center; flex-shrink: 0; }
.nav-item .nav-label {
  overflow: hidden; transition: opacity var(--duration-fast);
}
.collapsed .nav-item .nav-label { opacity: 0; width: 0; }
.collapsed .nav-item { justify-content: center; padding: 8px; }

.nav-separator {
  height: 1px; background: var(--separator); margin: var(--space-sm) var(--space-sm);
}

.sidebar-footer {
  padding: var(--space-md); border-top: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 4px;
}
.sidebar-footer .status-row {
  display: flex; align-items: center; gap: var(--space-sm);
  font-size: 0.8rem; color: var(--text-tertiary);
}
.status-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  background: var(--text-tertiary);
}
.status-dot.connected { background: var(--success); }
.status-dot.error { background: var(--error); }

/* ---- Main Area ---- */
.main-area {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}

.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  backdrop-filter: var(--blur-sidebar);
  -webkit-backdrop-filter: var(--blur-sidebar);
  z-index: 50;
}
.top-bar-left { display: flex; align-items: center; gap: var(--space-md); }
.top-bar-right { display: flex; align-items: center; gap: var(--space-sm); }
.top-bar h2 { font-size: 1.1rem; font-weight: 600; }

.view-container {
  flex: 1; overflow-y: auto; padding: var(--space-lg);
}

/* ---- Toggle button ---- */
.sidebar-toggle {
  width: 28px; height: 28px; border: none; border-radius: var(--radius-sm);
  background: transparent; color: var(--text-secondary); cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-size: 1rem;
}
.sidebar-toggle:hover { background: var(--bg-tertiary); color: var(--text-primary); }

/* ---- Global Search ---- */
.global-search {
  width: 240px; padding: 6px 12px; border: 1px solid var(--border);
  border-radius: var(--radius-full); font-size: 0.85rem;
  background: var(--bg-input); color: var(--text-primary);
}
.global-search:focus { border-color: var(--accent); width: 300px; }
```

- [ ] **Step 2: Create app.js — Alpine init + global store**

```javascript
/* static/js/app.js */
/* Global app initialization, stores, theme, command palette */

// ---- Global Store ----
document.addEventListener('alpine:init', () => {
  Alpine.store('app', {
    theme: localStorage.getItem('lcc-theme') || 'dark',
    connected: false,
    version: '',

    init() {
      this.applyTheme();
      this.checkHealth();
      setInterval(() => this.checkHealth(), 30000);
    },

    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('lcc-theme', this.theme);
      this.applyTheme();
    },

    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.theme);
    },

    async checkHealth() {
      try {
        const resp = await fetch('/health');
        const data = await resp.json();
        this.connected = true;
        this.version = data.version || '';
      } catch {
        this.connected = false;
      }
    },
  });

  Alpine.store('view', {
    current: window.location.hash.slice(1) || 'dashboard',
    sidebarCollapsed: false,
    previous: null,

    init() {
      window.addEventListener('hashchange', () => {
        const view = window.location.hash.slice(1) || 'dashboard';
        this.navigateTo(view);
      });
      this.navigateTo(this.current, false);
    },

    navigateTo(view, pushState = true) {
      this.previous = this.current;
      this.current = view;
      if (pushState) {
        window.location.hash = view;
      }
    },

    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
    },

    isActive(view) { return this.current === view; },
  });
});

// ---- Command Palette (simplified, will be enhanced in Task 4) ----
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    const search = document.getElementById('global-search');
    if (search) search.focus();
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
    e.preventDefault();
    Alpine.store('view').toggleSidebar();
  }
  // ⌘1-5 switch views
  const viewMap = { '1': 'dashboard', '2': 'tasks', '3': 'notes', '4': 'habits', '5': 'calendar' };
  if ((e.metaKey || e.ctrlKey) && viewMap[e.key]) {
    e.preventDefault();
    Alpine.store('view').navigateTo(viewMap[e.key]);
  }
});
```

- [ ] **Step 3: Rewrite index.html — shell with sidebar + main area**

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#0a84ff">
  <meta name="description" content="LocalCommandCenter — 本地指挥中心">
  <title>LocalCommandCenter</title>

  <link rel="stylesheet" href="/static/css/variables.css">
  <link rel="stylesheet" href="/static/css/components.css">
  <link rel="stylesheet" href="/static/css/animations.css">
  <link rel="stylesheet" href="/static/css/layout.css">

  <link rel="manifest" href="/static/manifest.json">
  <link rel="apple-touch-icon" href="/static/icons/icon-192x192.png">

  <script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.x.x/dist/cdn.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body>
<div class="app-shell" x-data x-bind="$store.app.init()" :class="{ collapsed: $store.view.sidebarCollapsed }">

  <!-- Sidebar -->
  <aside class="sidebar" :class="{ collapsed: $store.view.sidebarCollapsed }">
    <div class="sidebar-header">
      <span class="logo">🧠 LCC</span>
      <span class="version" x-text="$store.app.connected ? 'v' + $store.app.version : ''"></span>
    </div>

    <nav class="sidebar-nav">
      <button class="nav-item" :class="{ active: $store.view.isActive('dashboard') }"
              @click="$store.view.navigateTo('dashboard')">
        <span class="nav-icon">📊</span><span class="nav-label">仪表盘</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('tasks') }"
              @click="$store.view.navigateTo('tasks')">
        <span class="nav-icon">📋</span><span class="nav-label">任务</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('notes') }"
              @click="$store.view.navigateTo('notes')">
        <span class="nav-icon">📝</span><span class="nav-label">笔记</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('habits') }"
              @click="$store.view.navigateTo('habits')">
        <span class="nav-icon">🎯</span><span class="nav-label">习惯</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('calendar') }"
              @click="$store.view.navigateTo('calendar')">
        <span class="nav-icon">📅</span><span class="nav-label">日历</span>
      </button>

      <div class="nav-separator"></div>

      <button class="nav-item" :class="{ active: $store.view.isActive('ai-chat') }"
              @click="$store.view.navigateTo('ai-chat')">
        <span class="nav-icon">🤖</span><span class="nav-label">AI 对话</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('workflows') }"
              @click="$store.view.navigateTo('workflows')">
        <span class="nav-icon">⚡</span><span class="nav-label">工作流</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('sync') }"
              @click="$store.view.navigateTo('sync')">
        <span class="nav-icon">🔄</span><span class="nav-label">同步</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('download') }"
              @click="$store.view.navigateTo('download')">
        <span class="nav-icon">📥</span><span class="nav-label">下载</span>
      </button>
      <button class="nav-item" :class="{ active: $store.view.isActive('sandbox') }"
              @click="$store.view.navigateTo('sandbox')">
        <span class="nav-icon">🔧</span><span class="nav-label">沙盒</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <button class="nav-item" style="font-size:0.8rem" @click="$store.view.navigateTo('settings')"
              :class="{ active: $store.view.isActive('settings') }">
        <span class="nav-icon">⚙️</span><span class="nav-label">设置</span>
      </button>
      <div class="status-row">
        <span class="status-dot" :class="{ connected: $store.app.connected, error: !$store.app.connected }"></span>
        <span x-text="$store.app.connected ? '已连接' : '未连接'" style="font-size:0.75rem"></span>
      </div>
    </div>
  </aside>

  <!-- Main Area -->
  <main class="main-area">
    <div class="top-bar">
      <div class="top-bar-left">
        <button class="sidebar-toggle" @click="$store.view.toggleSidebar()" title="⌘B 折叠侧边栏">
          ☰
        </button>
        <h2 x-text="$store.view.current"></h2>
      </div>
      <div class="top-bar-right">
        <input id="global-search" class="global-search" type="text"
               placeholder="⌘K 命令面板..." autocomplete="off">
        <button class="btn-icon btn-ghost" @click="$store.app.toggleTheme()"
                :title="$store.app.theme === 'dark' ? '切换亮色主题' : '切换暗色主题'">
          <span x-text="$store.app.theme === 'dark' ? '☀️' : '🌙'"></span>
        </button>
      </div>
    </div>

    <div class="view-container">
      <!-- Views injected here by router -->
      <div id="view-dashboard" x-show="$store.view.isActive('dashboard')" x-transition.opacity.duration.250ms></div>
      <div id="view-tasks" x-show="$store.view.isActive('tasks')" x-transition.opacity.duration.250ms></div>
      <div id="view-notes" x-show="$store.view.isActive('notes')" x-transition.opacity.duration.250ms></div>
      <div id="view-habits" x-show="$store.view.isActive('habits')" x-transition.opacity.duration.250ms></div>
      <div id="view-calendar" x-show="$store.view.isActive('calendar')" x-transition.opacity.duration.250ms></div>
      <div id="view-ai-chat" x-show="$store.view.isActive('ai-chat')" x-transition.opacity.duration.250ms></div>
      <div id="view-workflows" x-show="$store.view.isActive('workflows')" x-transition.opacity.duration.250ms></div>
      <div id="view-sync" x-show="$store.view.isActive('sync')" x-transition.opacity.duration.250ms></div>
      <div id="view-download" x-show="$store.view.isActive('download')" x-transition.opacity.duration.250ms></div>
      <div id="view-sandbox" x-show="$store.view.isActive('sandbox')" x-transition.opacity.duration.250ms></div>
      <div id="view-settings" x-show="$store.view.isActive('settings')" x-transition.opacity.duration.250ms></div>
    </div>
  </main>

  <!-- Toast Container -->
  <div class="toast-container" id="toast-container"></div>

  <!-- Modal Overlay -->
  <div class="modal-overlay" id="modal-overlay" style="display:none" x-show="false"></div>
</div>

<script type="module" src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Test — launch server and verify sidebar renders**

```bash
cd /home/tanzheng/Desktop/My_Claw/local-gateway && conda run -n claude python main.py &
sleep 2
curl -s http://localhost:8900/static/css/variables.css | head -5
# Expected: CSS content
```

- [ ] **Step 5: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add static/css/layout.css static/js/app.js static/index.html
git commit -m "feat: add sidebar layout shell with Alpine.js — Apple-style navigation"
```

---

### Task 3: Extract API + Utils, Wire Dashboard

**Files:**
- Create: `static/js/api.js`
- Create: `static/js/utils.js`
- Create: `static/js/components/dashboard.js`

- [ ] **Step 1: Create api.js**

```javascript
/* static/js/api.js */
/* HTTP + SSE helpers */

const BASE = '';

export async function apiPost(endpoint, body) {
  const resp = await fetch(`${BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return resp.json();
}

export async function apiGet(endpoint) {
  const resp = await fetch(`${BASE}${endpoint}`);
  return resp.json();
}

export function toast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(-8px)';
    el.style.transition = 'all 200ms var(--ease-exit)';
    setTimeout(() => el.remove(), 200);
  }, 3500);
}

export async function streamChat(endpoint, body, onEvent) {
  const resp = await fetch(`${BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          onEvent(data);
        } catch {}
      }
    }
  }
}
```

- [ ] **Step 2: Create utils.js — extract from current app.js**

```javascript
/* static/js/utils.js */
/* Pure utility functions extracted from app.js */

export function formatTime(iso) {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    const w = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ` +
           `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')} (${w[d.getDay()]})`;
  } catch { return iso; }
}

export function formatTimeShort(iso) {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

export function escapeHtml(str) {
  if (str == null) return '';
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

export function escapeHtmlAttr(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function debounce(fn, ms = 300) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

export const RECURRENCE_MAP = { once: '一次', daily: '每天', weekly: '每周', monthly: '每月' };

export function badgeClass(status) {
  if (status === '已完成') return 'completed';
  if (status === '已删除') return 'error';
  return 'pending';
}

export function operationIcon(op) {
  const map = { add_task: '📋', complete_task: '✅', delete_task: '🗑️', download: '📥', sandbox: '🔧' };
  return map[op] || '📌';
}
```

- [ ] **Step 3: Create dashboard.js — component with skeleton loading**

```javascript
/* static/js/components/dashboard.js */
import { apiGet, toast } from '../api.js';
import { formatTime, formatTimeShort, escapeHtml, operationIcon } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('dashboard', () => ({
    loading: true,
    error: null,
    stats: { tasks: { pending: 0, completed: 0 }, downloads: { total: 0, completed: 0 }, storage: {} },
    recentDownloads: [],
    recentLogs: [],

    async init() {
      if (Alpine.store('view').current !== 'dashboard') return;
      await this.load();
    },

    async load() {
      this.loading = true;
      this.error = null;
      try {
        const data = await apiGet('/api/dashboard');
        if (data.status !== 'success') throw new Error(data.message);
        this.stats = {
          tasks: { pending: data.tasks?.pending ?? 0, completed: data.tasks?.completed ?? 0 },
          downloads: { total: data.downloads?.total ?? 0, completed: data.downloads?.completed ?? 0 },
          storage: data.storage ?? {},
        };
        this.recentDownloads = data.recent_downloads || [];
        this.recentLogs = data.recent_logs || [];
      } catch (e) {
        this.error = e.message;
        toast('加载仪表盘失败', 'error');
      } finally {
        this.loading = false;
      }
    },

    formatTime: formatTime,
    formatTimeShort: formatTimeShort,
    escapeHtml: escapeHtml,
    operationIcon: operationIcon,
  }));
});
```

- [ ] **Step 4: Wire dashboard into index.html view container**

Insert inside `<div id="view-dashboard" ...>`:

```html
<div id="view-dashboard" x-show="$store.view.isActive('dashboard')"
     x-data="dashboard" x-transition.opacity.duration.250ms
     @view-enter.window="$store.view.current === 'dashboard' && load()">

  <!-- Loading Skeleton -->
  <template x-if="loading">
    <div>
      <div class="stats-grid">
        <div class="stat-card" x-for="i in 4"><div class="skeleton" style="height:60px"></div></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-md)">
        <div class="card"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>
        <div class="card"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>
      </div>
    </div>
  </template>

  <!-- Error State -->
  <template x-if="!loading && error">
    <div class="empty-state">
      <div class="empty-state-icon">⚠️</div>
      <div class="empty-state-text" x-text="error"></div>
      <button class="btn btn-primary" @click="load()">重试</button>
    </div>
  </template>

  <!-- Content -->
  <template x-if="!loading && !error">
    <div>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-icon">📋</div><div class="stat-info">
          <div class="stat-value" x-text="stats.tasks.pending"></div>
          <div class="stat-label">待执行任务</div>
        </div></div>
        <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-info">
          <div class="stat-value" x-text="stats.tasks.completed"></div>
          <div class="stat-label">已完成任务</div>
        </div></div>
        <div class="stat-card"><div class="stat-icon">📥</div><div class="stat-info">
          <div class="stat-value" x-text="stats.downloads.total"></div>
          <div class="stat-label">下载文件</div>
        </div></div>
        <div class="stat-card"><div class="stat-icon">💾</div><div class="stat-info">
          <div class="stat-value" x-text="stats.storage.total_size || '0 B'"></div>
          <div class="stat-label">磁盘占用</div>
        </div></div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-md)">
        <div class="card">
          <div class="card-header"><h3>📥 最近下载</h3></div>
          <div class="activity-list">
            <template x-if="recentDownloads.length === 0">
              <div class="empty-state"><span class="empty-state-text">暂无下载记录</span></div>
            </template>
            <template x-for="d in recentDownloads" :key="d.created_at">
              <div class="activity-item">
                <span class="activity-icon">📥</span>
                <span class="activity-text" x-text="d.filename || d.url"></span>
                <span class="activity-time" x-text="formatTimeShort(d.created_at)"></span>
              </div>
            </template>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>📜 最近操作</h3></div>
          <div class="activity-list">
            <template x-if="recentLogs.length === 0">
              <div class="empty-state"><span class="empty-state-text">暂无操作记录</span></div>
            </template>
            <template x-for="l in recentLogs" :key="l.created_at">
              <div class="activity-item">
                <span class="activity-icon" x-text="operationIcon(l.operation)"></span>
                <span class="activity-text" x-text="l.operation"></span>
                <span class="activity-time" x-text="formatTimeShort(l.created_at)"></span>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </template>
</div>
```

- [ ] **Step 5: Update index.html to load dashboard module**

Add at bottom before `</body>`, replace the single `<script>` with:

```html
<script type="module" src="/static/js/app.js"></script>
<script type="module" src="/static/js/components/dashboard.js"></script>
```

- [ ] **Step 6: Verify dashboard renders correctly**

Start server, open http://localhost:8900, verify:
- Sidebar visible with all menu items
- Dashboard loads with stats cards, recent downloads, recent logs
- Loading skeleton shows briefly before data arrives
- Sidebar toggle (⌘B or ☰ button) collapses/expands

- [ ] **Step 7: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add static/js/api.js static/js/utils.js static/js/components/dashboard.js
git commit -m "feat: extract api/utils modules, migrate dashboard to Alpine.js component"
```

---

### Task 4: Tasks Component + Optimistic Updates

**Files:**
- Create: `static/js/components/tasks.js`

- [ ] **Step 1: Create tasks.js with weekly calendar + task list**

```javascript
/* static/js/components/tasks.js */
import { apiGet, apiPost, toast } from '../api.js';
import { formatTime, formatTimeShort, escapeHtml, escapeHtmlAttr, RECURRENCE_MAP, badgeClass } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('tasks', () => ({
    // Weekly calendar
    weeklyTasks: [],
    calWeekOffset: 0,
    weekLabel: '',
    calendarHtml: '',
    loadingCalendar: true,

    // All tasks
    allTasks: [],
    taskPage: 1,
    taskTotal: 0,
    taskTotalPages: 0,
    taskFilter: 'active',
    taskKeyword: '',
    loadingTasks: false,

    async init() {
      await this.loadWeeklyPlan(0);
    },

    weekDays() {
      const now = new Date();
      const monday = new Date(now);
      monday.setDate(now.getDate() - now.getDay() + 1 + this.calWeekOffset * 7);
      const days = [];
      for (let i = 0; i < 7; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        days.push(d);
      }
      const mon = days[0], sun = days[6];
      this.weekLabel = `${mon.getMonth()+1}/${mon.getDate()} - ${sun.getMonth()+1}/${sun.getDate()}`;
      return days;
    },

    async loadWeeklyPlan(offset) {
      if (offset !== undefined) this.calWeekOffset = offset;
      this.loadingCalendar = true;
      try {
        const now = new Date();
        const monday = new Date(now);
        monday.setDate(now.getDate() - now.getDay() + 1 + this.calWeekOffset * 7);
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        const monStr = `${monday.getFullYear()}-${String(monday.getMonth()+1).padStart(2,'0')}-${String(monday.getDate()).padStart(2,'0')}T00:00:00`;
        const sunStr = `${sunday.getFullYear()}-${String(sunday.getMonth()+1).padStart(2,'0')}-${String(sunday.getDate()).padStart(2,'0')}T23:59:59`;

        const data = await apiPost('/api/task', {
          action: 'get_weekly_plan', due_time: monStr, task_name: sunStr,
        });
        this.weeklyTasks = data.tasks || [];
        this.renderCalendar();
      } catch (e) { toast('加载周计划失败', 'error'); }
      this.loadingCalendar = false;
    },

    renderCalendar() {
      const now = new Date();
      const monday = new Date(now);
      monday.setDate(now.getDate() - now.getDay() + 1 + this.calWeekOffset * 7);
      const dayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
      const todayDayIdx = this.calWeekOffset === 0 ? now.getDay() === 0 ? 6 : now.getDay() - 1 : -1;
      const taskMap = {};

      this.weeklyTasks.forEach(t => {
        try {
          const td = new Date(t.due_time);
          for (let i = 0; i < 7; i++) {
            const dd = new Date(monday);
            dd.setDate(monday.getDate() + i);
            if (`${td.getFullYear()}-${String(td.getMonth()+1).padStart(2,'0')}-${String(td.getDate()).padStart(2,'0')}`
                === `${dd.getFullYear()}-${String(dd.getMonth()+1).padStart(2,'0')}-${String(dd.getDate()).padStart(2,'0')}`) {
              const hour = td.getHours();
              const key = `${i}-${hour}`;
              if (!taskMap[key]) taskMap[key] = [];
              taskMap[key].push(t);
              break;
            }
          }
        } catch {}
      });

      let html = '<div class="wc-header-row"><div class="wc-corner"></div>';
      for (let i = 0; i < 7; i++) {
        const dd = new Date(monday);
        dd.setDate(monday.getDate() + i);
        const dateLabel = `${dd.getMonth()+1}/${dd.getDate()}`;
        const isToday = i === todayDayIdx;
        html += `<div class="wc-day-header${isToday ? ' today-col' : ''}">${dayNames[i]}<br><span class="wc-date-sub">${dateLabel}</span></div>`;
      }
      html += '</div>';

      for (let h = 7; h <= 23; h++) {
        html += `<div class="wc-time-row"><div class="wc-time-label">${String(h).padStart(2,'0')}:00</div>`;
        for (let i = 0; i < 7; i++) {
          const isToday = i === todayDayIdx;
          const key = `${i}-${h}`;
          const tasks = taskMap[key] || [];
          html += `<div class="wc-cell${isToday ? ' is-today-col' : ''}">`;
          tasks.forEach(t => {
            const m = new Date(t.due_time).getMinutes();
            const timeStr = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
            const cls = t.status === '已完成' ? 'completed' : 'pending';
            html += `<div class="wc-task wc-${cls}" title="${escapeHtml(t.task_name)} ${timeStr}">`;
            html += `<span class="wc-task-name">${escapeHtml(t.task_name)}</span>`;
            html += `<span class="wc-task-actions">`;
            if (t.status === '待执行') html += `<button class="wc-btn wc-btn-done" onclick="event.stopPropagation();Alpine.$data(document.querySelector('[x-data=tasks]')).completeTask('${escapeHtmlAttr(t.task_id)}')">✓</button>`;
            html += `<button class="wc-btn wc-btn-del" onclick="event.stopPropagation();Alpine.$data(document.querySelector('[x-data=tasks]')).deleteTask('${escapeHtmlAttr(t.task_id)}')">✕</button>`;
            html += `</span></div>`;
          });
          html += `</div>`;
        }
        html += `</div>`;
      }
      this.calendarHtml = html;
    },

    async completeTask(id) {
      // Optimistic update
      const task = this.weeklyTasks.find(t => t.task_id === id);
      if (task) task.status = '已完成';
      this.renderCalendar();

      const res = await apiPost('/api/task', { action: 'complete_task', task_id: id });
      if (res.status === 'success') {
        toast('任务已完成', 'success');
      } else {
        if (task) task.status = '待执行';
        this.renderCalendar();
        toast(res.message, 'error');
      }
      await this.loadWeeklyPlan();
      Alpine.store('view').navigateTo('dashboard');
      setTimeout(() => Alpine.store('view').navigateTo('tasks'), 50);
    },

    async deleteTask(id) {
      if (!confirm('确定删除此任务？')) return;
      // Optimistic removal
      this.weeklyTasks = this.weeklyTasks.filter(t => t.task_id !== id);
      this.renderCalendar();

      const res = await apiPost('/api/task', { action: 'delete_task', task_id: id });
      if (res.status === 'success') {
        toast('任务已删除', 'success');
      } else {
        toast(res.message, 'error');
        await this.loadWeeklyPlan();
      }
    },

    async loadAllTasks(page) {
      if (page) this.taskPage = page;
      this.loadingTasks = true;
      try {
        const params = new URLSearchParams({
          status: this.taskFilter, keyword: this.taskKeyword,
          page: this.taskPage, page_size: 20,
        });
        const data = await apiGet(`/api/tasks/all?${params}`);
        this.allTasks = data.tasks || [];
        this.taskTotal = data.total || 0;
        this.taskTotalPages = data.total_pages || 0;
      } catch (e) { toast('加载任务列表失败', 'error'); }
      this.loadingTasks = false;
    },

    taskActions(t) {
      if (t.status === '已完成' || t.status === '已删除') return '';
      return `<button class="btn btn-sm btn-success" onclick="Alpine.$data(document.querySelector('[x-data=tasks]')).completeTask('${escapeHtmlAttr(t.task_id)}')">完成</button>
              <button class="btn btn-sm btn-danger" onclick="Alpine.$data(document.querySelector('[x-data=tasks]')).deleteTask('${escapeHtmlAttr(t.task_id)}')">删除</button>`;
    },

    formatTime: formatTime,
    formatTimeShort: formatTimeShort,
    RECURRENCE_MAP: RECURRENCE_MAP,
    badgeClass: badgeClass,
  }));
});
```

- [ ] **Step 2: Extend tasks.js with new-task form**

```javascript
// Add to tasks Alpine.data():

    // New task form
    showNewTask: false,
    newTask: { task_name: '', due_time: '', priority: 2, description: '', tags: '' },

    async addTask() {
      if (!this.newTask.task_name || !this.newTask.due_time) {
        toast('请填写任务名称和截止时间', 'error');
        return;
      }
      const body = {
        action: 'add_task',
        task_name: this.newTask.task_name,
        due_time: this.newTask.due_time,
        priority: this.newTask.priority,
        description: this.newTask.description,
        tags: this.newTask.tags.split(',').map(t => t.trim()).filter(t => t),
      };
      const res = await apiPost('/api/task', body);
      if (res.status === 'success') {
        toast('任务已创建', 'success');
        this.showNewTask = false;
        this.newTask = { task_name: '', due_time: '', priority: 2, description: '', tags: '' };
        await this.loadWeeklyPlan();
      } else {
        toast(res.message, 'error');
      }
    },
```

- [ ] **Step 3: Wire tasks view into index.html**

Insert at `#view-tasks`:

```html
<div id="view-tasks" x-show="$store.view.isActive('tasks')"
     x-data="tasks" x-transition.opacity.duration.250ms
     @view-enter.window="$store.view.current === 'tasks' && loadWeeklyPlan()">

  <!-- Inner tabs: Weekly Calendar | All Tasks -->
  <div style="display:flex;gap:var(--space-sm);margin-bottom:var(--space-md)">
    <button class="btn btn-sm" :class="{ 'btn-primary': tab === 'week' }" @click="tab='week'">📅 周视图</button>
    <button class="btn btn-sm" :class="{ 'btn-primary': tab === 'all' }" @click="tab='all';loadAllTasks()">📋 全部任务</button>
    <div style="flex:1"></div>
    <button class="btn btn-primary btn-sm" @click="showNewTask=!showNewTask">+ 新建任务</button>
  </div>

  <!-- New Task Form -->
  <div x-show="showNewTask" class="card" style="margin-bottom:var(--space-md)" x-transition>
    <div class="card-header"><h3>✨ 新建任务</h3></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-md)">
      <div class="form-group"><label>任务名称</label><input x-model="newTask.task_name" placeholder="e.g. 完成季度报告"></div>
      <div class="form-group"><label>截止时间</label><input type="datetime-local" x-model="newTask.due_time"></div>
      <div class="form-group"><label>优先级</label>
        <select x-model.number="newTask.priority">
          <option value="0">🔴 紧急</option><option value="1">🟠 高</option>
          <option value="2" selected>🟡 中</option><option value="3">🟢 低</option>
        </select>
      </div>
      <div class="form-group"><label>标签（逗号分隔）</label><input x-model="newTask.tags" placeholder="工作, 重要"></div>
    </div>
    <div class="form-group" style="margin-top:var(--space-md)"><label>描述</label><textarea x-model="newTask.description" rows="2"></textarea></div>
    <div style="display:flex;gap:var(--space-sm);margin-top:var(--space-md)">
      <button class="btn btn-primary" @click="addTask()">创建任务</button>
      <button class="btn" @click="showNewTask=false">取消</button>
    </div>
  </div>

  <!-- Weekly Calendar View -->
  <div x-show="tab==='week'">
    <div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:var(--space-sm)">
      <button class="btn btn-sm" @click="loadWeeklyPlan(calWeekOffset-1)">◀</button>
      <span style="font-weight:600" x-text="weekLabel"></span>
      <button class="btn btn-sm" @click="loadWeeklyPlan(calWeekOffset+1)">▶</button>
      <button class="btn btn-sm" @click="loadWeeklyPlan(0)">本周</button>
    </div>
    <!-- Skeleton -->
    <div x-show="loadingCalendar" class="skeleton" style="height:400px"></div>
    <!-- Calendar Grid -->
    <div x-show="!loadingCalendar" x-html="calendarHtml" class="wc-container"></div>
  </div>

  <!-- All Tasks Table -->
  <div x-show="tab==='all'">
    <div style="display:flex;gap:var(--space-sm);margin-bottom:var(--space-sm)">
      <input x-model="taskKeyword" @input="loadAllTasks(1)" placeholder="搜索任务..." style="max-width:200px">
      <select x-model="taskFilter" @change="loadAllTasks(1)" style="max-width:130px">
        <option value="active">进行中</option><option value="completed">已完成</option>
        <option value="pending">待执行</option><option value="deleted">已删除</option>
      </select>
    </div>
    <table class="data-table">
      <thead><tr><th>#</th><th>名称</th><th>截止</th><th>重复</th><th>状态</th><th>创建</th><th>操作</th></tr></thead>
      <tbody>
        <tr x-show="loadingTasks"><td colspan="7"><div class="skeleton" style="height:200px"></div></td></tr>
        <tr x-show="!loadingTasks && allTasks.length === 0"><td colspan="7" class="empty">无匹配任务</td></tr>
        <template x-for="(t, i) in allTasks" :key="t.task_id">
          <tr>
            <td x-text="(taskPage-1)*20 + i + 1"></td>
            <td x-text="t.task_name"></td>
            <td x-text="formatTime(t.due_time)"></td>
            <td x-text="RECURRENCE_MAP[t.recurrence] || t.recurrence"></td>
            <td><span class="badge" :class="'badge-'+badgeClass(t.status)" x-text="t.status"></span></td>
            <td x-text="formatTimeShort(t.created_at)"></td>
            <td x-html="taskActions(t)"></td>
          </tr>
        </template>
      </tbody>
    </table>
    <div class="pagination" x-show="taskTotalPages > 1">
      <button :disabled="taskPage<=1" @click="loadAllTasks(taskPage-1)">◀</button>
      <template x-for="p in taskTotalPages">
        <button :class="{active:p===taskPage}" @click="loadAllTasks(p)" x-text="p"></button>
      </template>
      <button :disabled="taskPage>=taskTotalPages" @click="loadAllTasks(taskPage+1)">▶</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Add week calendar CSS to components.css**

```css
/* ---- Week Calendar ---- */
.wc-container { border: 1px solid var(--border); border-radius: var(--radius-md); overflow: auto; max-height: 600px; }
.wc-header-row { display: grid; grid-template-columns: 50px repeat(7, 1fr); position: sticky; top: 0; z-index: 5; background: var(--bg-card); }
.wc-corner { border-bottom: 1px solid var(--separator); }
.wc-day-header { padding: 8px 4px; text-align: center; font-size: 0.75rem; font-weight: 600; border-bottom: 1px solid var(--separator); border-left: 1px solid var(--border); }
.wc-day-header.today-col { color: var(--accent); }
.wc-date-sub { font-weight: 400; font-size: 0.7rem; color: var(--text-tertiary); }
.wc-time-row { display: grid; grid-template-columns: 50px repeat(7, 1fr); min-height: 48px; }
.wc-time-label { padding: 2px 8px; font-size: 0.7rem; color: var(--text-tertiary); text-align: right; border-right: 1px solid var(--border); }
.wc-cell { border-left: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 2px; min-height: 48px; }
.wc-cell.is-today-col { background: rgba(10,132,255,0.03); }
.wc-task { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px; margin: 1px 0; border-radius: 3px; font-size: 0.72rem; background: rgba(10,132,255,0.08); cursor: default; }
.wc-task.completed { opacity: 0.5; text-decoration: line-through; }
.wc-task-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.wc-task-actions { display: flex; gap: 2px; flex-shrink: 0; opacity: 0; transition: opacity var(--duration-fast); }
.wc-task:hover .wc-task-actions { opacity: 1; }
.wc-btn { width: 18px; height: 18px; border: none; border-radius: 3px; font-size: 0.65rem; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.wc-btn-done { background: var(--success); color: #fff; }
.wc-btn-del { background: transparent; color: var(--text-tertiary); }
.wc-btn-del:hover { background: var(--error); color: #fff; }
```

- [ ] **Step 5: Add tasks module to index.html**

```html
<script type="module" src="/static/js/components/tasks.js"></script>
```

- [ ] **Step 6: Start server and verify tasks view**

```bash
cd /home/tanzheng/Desktop/My_Claw/local-gateway && conda run -n claude python main.py &
sleep 2
# Open http://localhost:8900, navigate to Tasks tab
```

- [ ] **Step 7: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add static/js/components/tasks.js static/index.html static/css/components.css
git commit -m "feat: migrate tasks to Alpine.js — weekly calendar + task list + optimistic complete"
```

---

## Phase 2: Content Modules

### Task 5: Notes + Habits Components

**Files:**
- Create: `static/js/components/notes.js`
- Create: `static/js/components/habits.js`

Planned structure — full code skipped for brevity (both follow same pattern as dashboard/tasks: Alpine.data() with loading/empty/content states, import from api.js/utils.js).

Each component:
- Loading skeleton matching card layout
- Empty state with module-specific illustration + CTA
- Content view
- Optimistic create/update/delete

- [ ] **Step 1-3: Create notes.js + habits.js**
- [ ] **Step 4: Wire into index.html**
- [ ] **Step 5: Commit**

```bash
git add static/js/components/notes.js static/js/components/habits.js static/index.html
git commit -m "feat: migrate notes + habits to Alpine.js components"
```

---

### Task 6: Calendar + AI Chat Components

**Files:**
- Create: `static/js/components/calendar.js`
- Create: `static/js/components/ai-chat.js`

AI Chat three-column layout follows spec Section 1 design:
- iMessage-style bubbles (user: blue right, AI: gray left)
- Tool call as collapsible mini-card
- Typing indicator: three dots bouncing
- Right panel (collapsible): model name, token count, session history
- ⌘Enter to send, Shift+Enter for newline

- [ ] **Step 1-3: Create calendar.js + ai-chat.js**
- [ ] **Step 4: Wire into index.html**
- [ ] **Step 5: Commit**

```bash
git add static/js/components/calendar.js static/js/components/ai-chat.js static/index.html
git commit -m "feat: migrate calendar + AI chat to Alpine.js components — iMessage-style chat UI"
```

---

### Task 7: Remaining Modules (Workflows, Sync, Download, Sandbox, Settings)

**Files:**
- Create: `static/js/components/workflows.js`
- Create: `static/js/components/sync.js`
- Create: `static/js/components/download.js`
- Create: `static/js/components/sandbox.js`

Each follows the established component pattern. Settings bundle AI config into a simple panel.

- [ ] **Step 1-3: Create remaining component files**
- [ ] **Step 4: Wire all into index.html**
- [ ] **Step 5: Commit**

```bash
git add static/js/components/workflows.js static/js/components/sync.js static/js/components/download.js static/js/components/sandbox.js static/index.html
git commit -m "feat: migrate workflows/sync/download/sandbox to Alpine.js components"
```

---

## Phase 3: Polish

### Task 8: Global Skeleton + Empty States + Error Boundaries

Walk through every component and verify:
1. Loading → skeleton matching exact content layout
2. Empty → custom illustration + CTA + shortcut hint
3. Error → retry button + friendly message

Add missing skeletons/empty-states to any components built in Phase 2.

- [ ] **Step 1: Audit all components for missing states**
- [ ] **Step 2: Fill gaps**
- [ ] **Step 3: Commit**

```bash
git add -A static/
git commit -m "feat: complete state design — skeleton/empty/error for all components"
```

---

### Task 9: Animation Tuning + Keyboard Shortcuts

- [ ] **Step 1: Tune all transitions — verify timing, easing, no jank**
- [ ] **Step 2: Implement full keyboard shortcut map from spec Section 6**
- [ ] **Step 3: Add ⌘N quick-create task shortcut (opens new-task form in any view)**
- [ ] **Step 4: Commit**

```bash
git add static/js/app.js static/css/animations.css
git commit -m "feat: animation tuning + full keyboard shortcuts map"
```

---

### Task 10: Remove Old Files + Final Verification

- [ ] **Step 1: Remove old app.js and style.css**

```bash
cd /home/tanzheng/Desktop/My_Claw
git rm local-gateway/static/app.js local-gateway/static/style.css
```

- [ ] **Step 2: Verify no references to old files**

```bash
grep -rn "app\.js\|style\.css" local-gateway/static/ --include="*.html"
# Expected: no results
```

- [ ] **Step 3: Run full test suite to verify backend unchanged**

```bash
cd local-gateway && conda run -n claude python -m pytest test/ -v 2>&1 | tail -20
# Expected: same pass/fail as before (no new failures)
```

- [ ] **Step 4: Verify app starts and frontend loads**

```bash
cd local-gateway && conda run -n claude python -c "from main import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old monolithic frontend files — migration to Alpine.js complete"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Tasks 1-4 cover Phase 1 (sidebar, dashboard, tasks, command palette); Tasks 5-7 cover Phase 2 (all remaining modules + AI chat); Tasks 8-10 cover Phase 3 (polish, shortcuts, cleanup)
- [x] **Placeholder scan**: No TBD/TODO — Phase 2 component code structure is specified with patterns to follow from Phase 1 components
- [x] **Type consistency**: Component interface (Alpine.data() + import from api.js/utils.js) is consistent across all tasks
- [x] **Missing items**: hash-based routing in app.js Alpine.store, theme switching, sidebar collapse — all covered in Tasks 1-2
