/* local-gateway/static/js/components/download.js */
import { apiGet, apiPost, toast } from '../api.js';
import { formatTime, escapeHtml } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('download', () => ({
    loading: true,
    error: null,
    queue: [],

    // New download form
    form: { url: '', filename: '', category: '' },

    // Bandwidth
    bandwidth: null,
    showBandwidth: false,
    bandwidthLimit: '',

    // Polling
    pollTimer: null,

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'download') this.onViewActive();
      });
      if (Alpine.store('view').current === 'download') await this.onViewActive();
    },

    async onViewActive() {
      await this.load();
      this.startPolling();
    },

    startPolling() {
      this.stopPolling();
      this.pollTimer = setInterval(() => this.loadQueueOnly(), 3000);
    },

    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
    },

    async load() {
      this.loading = true;
      this.error = null;
      try {
        const [queueData, bwData] = await Promise.all([
          apiGet('/api/download/queue').catch(() => null),
          apiGet('/api/download/bandwidth').catch(() => null),
        ]);
        this.queue = Array.isArray(queueData) ? queueData : (queueData?.queue || queueData?.data || []);
        this.bandwidth = bwData?.status === 'success' ? (bwData.data || bwData) : bwData;
        if (this.bandwidth?.limit !== undefined) {
          this.bandwidthLimit = String(this.bandwidth.limit);
        }
      } catch (e) {
        this.error = e.message || '加载失败';
        toast('加载下载队列失败', 'error');
      } finally {
        this.loading = false;
      }
    },

    async loadQueueOnly() {
      try {
        const data = await apiGet('/api/download/queue');
        this.queue = Array.isArray(data) ? data : (data?.queue || data?.data || []);
      } catch {
        // Silently fail on poll
      }
    },

    async startDownload() {
      if (!this.form.url) {
        toast('请输入下载 URL', 'error');
        return;
      }
      try {
        const body = { url: this.form.url };
        if (this.form.filename) body.filename = this.form.filename;
        if (this.form.category) body.category = this.form.category;
        const data = await apiPost('/api/download', body);
        if (data.status !== 'success' && data.status !== 'ok') {
          throw new Error(data.message || '添加失败');
        }
        toast('下载已添加', 'success');
        this.form = { url: '', filename: '', category: '' };
        await this.loadQueueOnly();
      } catch (e) {
        toast('添加下载失败', 'error');
      }
    },

    async pauseJob(jobId) {
      try {
        const data = await apiPost(`/api/download/pause/${jobId}`, {});
        if (data.status !== 'success' && data.status !== 'ok') {
          throw new Error(data.message || '暂停失败');
        }
        toast('已暂停', 'success');
        await this.loadQueueOnly();
      } catch (e) {
        toast('暂停失败', 'error');
      }
    },

    async resumeJob(jobId) {
      try {
        const data = await apiPost(`/api/download/resume/${jobId}`, {});
        if (data.status !== 'success' && data.status !== 'ok') {
          throw new Error(data.message || '恢复失败');
        }
        toast('已恢复', 'success');
        await this.loadQueueOnly();
      } catch (e) {
        toast('恢复失败', 'error');
      }
    },

    async cancelJob(jobId) {
      if (!confirm('确定取消此下载？')) return;
      try {
        const data = await apiPost(`/api/download/cancel/${jobId}`, {});
        if (data.status !== 'success' && data.status !== 'ok') {
          throw new Error(data.message || '取消失败');
        }
        toast('已取消', 'success');
        this.queue = this.queue.filter(j => (j.id !== jobId && j.job_id !== jobId));
      } catch (e) {
        toast('取消失败', 'error');
      }
    },

    async saveBandwidth() {
      try {
        const limit = parseInt(this.bandwidthLimit);
        const data = await apiPost('/api/download/bandwidth', { limit: isNaN(limit) ? 0 : limit });
        if (data.status !== 'success' && data.status !== 'ok') {
          throw new Error(data.message || '设置失败');
        }
        toast('带宽限制已更新', 'success');
        this.showBandwidth = false;
        const bwData = await apiGet('/api/download/bandwidth');
        this.bandwidth = bwData?.status === 'success' ? (bwData.data || bwData) : bwData;
      } catch (e) {
        toast('设置带宽限制失败', 'error');
      }
    },

    getJobId(job) {
      return job.id || job.job_id;
    },

    progressPercent(job) {
      if (!job) return 0;
      if (job.progress !== undefined) return Math.min(100, Math.max(0, job.progress));
      if (job.total && job.downloaded) return Math.min(100, Math.round((job.downloaded / job.total) * 100));
      return 0;
    },

    statusLabel(status) {
      const map = { pending: '等待中', downloading: '下载中', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' };
      return map[status] || status || '-';
    },

    statusClass(status) {
      if (status === 'completed') return 'badge-completed';
      if (status === 'failed' || status === 'cancelled') return 'badge-error';
      if (status === 'downloading') return 'badge-pending';
      return 'badge-pending';
    },

    statusIcon(status) {
      if (status === 'downloading') return '⏳';
      if (status === 'completed') return '✅';
      if (status === 'failed') return '❌';
      if (status === 'paused') return '⏸️';
      if (status === 'cancelled') return '🚫';
      return '📥';
    },

    canPause(job) {
      const s = job.status;
      return s === 'downloading' || s === 'pending' || s === 'queued';
    },

    canResume(job) {
      return job.status === 'paused';
    },

    canCancel(job) {
      return job.status === 'downloading' || job.status === 'pending' || job.status === 'paused' || job.status === 'queued';
    },

    formatTime: formatTime,
    escapeHtml: escapeHtml,
  }));
});
