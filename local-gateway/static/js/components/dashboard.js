/* local-gateway/static/js/components/dashboard.js */
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
