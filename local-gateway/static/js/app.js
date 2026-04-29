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
