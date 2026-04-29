/* local-gateway/static/js/app.js */
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
    viewNames: {
      dashboard: '仪表盘', tasks: '任务', notes: '笔记', habits: '习惯',
      calendar: '日历', 'ai-chat': 'AI 对话', workflows: '工作流',
      sync: '同步', download: '下载', sandbox: '沙盒', settings: '设置',
    },

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

// ---- Keyboard Shortcuts ----
document.addEventListener('keydown', (e) => {
  const key = e.key.toLowerCase();
  const meta = e.metaKey || e.ctrlKey;
  const shift = e.shiftKey;

  // Escape — close modal / go back
  if (key === 'escape') {
    // Let individual components handle their own escape behavior
    // Fire a custom event so any open modal can catch it
    document.dispatchEvent(new CustomEvent('escape-pressed'));
    return;
  }

  // ⌘K — command palette (focus global search)
  if (meta && key === 'k') {
    e.preventDefault();
    const search = document.getElementById('global-search');
    if (search) search.focus();
    return;
  }

  // ⌘B — toggle sidebar
  if (meta && key === 'b') {
    e.preventDefault();
    Alpine.store('view').toggleSidebar();
    return;
  }

  // ⌘J — open AI chat
  if (meta && key === 'j') {
    e.preventDefault();
    Alpine.store('view').navigateTo('ai-chat');
    return;
  }

  // ⌘N — new task (navigate to tasks)
  if (meta && !shift && key === 'n') {
    e.preventDefault();
    Alpine.store('view').navigateTo('tasks');
    return;
  }

  // ⌘⇧N — new note (navigate to notes)
  if (meta && shift && key === 'n') {
    e.preventDefault();
    Alpine.store('view').navigateTo('notes');
    return;
  }

  // ⌘⇧T — toggle theme
  if (meta && shift && key === 't') {
    e.preventDefault();
    Alpine.store('app').toggleTheme();
    return;
  }

  // ⌘1-5 — switch views
  const viewMap = { '1': 'dashboard', '2': 'tasks', '3': 'notes', '4': 'habits', '5': 'calendar' };
  if (meta && viewMap[key]) {
    e.preventDefault();
    Alpine.store('view').navigateTo(viewMap[key]);
  }
});
