/* local-gateway/static/js/components/sync.js */
import { apiGet, apiPost, toast } from '../api.js';
import { formatTime } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('sync', () => ({
    loading: true,
    error: null,

    // Sync status
    status: null,

    // Devices
    devices: [],

    // Offline queue
    offlineQueue: [],

    // Active operation tracking
    syncing: false,
    syncType: '',

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'sync') this.load();
      });
      if (Alpine.store('view').current === 'sync') await this.load();
    },

    async load() {
      this.loading = true;
      this.error = null;
      try {
        const [statusData, devicesData, queueData] = await Promise.all([
          apiGet('/api/sync/status').catch(() => null),
          apiGet('/api/sync/devices').catch(() => null),
          apiGet('/api/sync/offline/queue').catch(() => null),
        ]);
        this.status = statusData?.status === 'success' ? (statusData.data || statusData) : statusData;
        this.devices = Array.isArray(devicesData) ? devicesData : (devicesData?.devices || devicesData?.data || []);
        this.offlineQueue = Array.isArray(queueData) ? queueData : (queueData?.queue || queueData?.data || []);
      } catch (e) {
        this.error = e.message || '加载失败';
        toast('加载同步状态失败', 'error');
      } finally {
        this.loading = false;
      }
    },

    async doSync(type) {
      this.syncing = true;
      this.syncType = type;
      const endpoint = type === 'push' ? '/api/sync/push'
        : type === 'pull' ? '/api/sync/pull'
        : '/api/sync/full';
      try {
        const data = await apiPost(endpoint, {});
        if (data.status !== 'success' && data.status !== 'ok') {
          throw new Error(data.message || '同步失败');
        }
        const label = type === 'push' ? '推送' : type === 'pull' ? '拉取' : '全量同步';
        toast(`${label}成功`, 'success');
        await this.load();
      } catch (e) {
        toast('同步失败', 'error');
      } finally {
        this.syncing = false;
        this.syncType = '';
      }
    },

    async syncOffline() {
      this.syncing = true;
      this.syncType = 'offline';
      try {
        const data = await apiPost('/api/sync/offline/sync', {});
        if (data.status !== 'success' && data.status !== 'ok') {
          throw new Error(data.message || '同步失败');
        }
        toast('离线队列已同步', 'success');
        await this.load();
      } catch (e) {
        toast('离线同步失败', 'error');
      } finally {
        this.syncing = false;
        this.syncType = '';
      }
    },

    lastSyncLabel() {
      if (!this.status) return '从未同步';
      const ts = this.status.last_sync || this.status.last_sync_time;
      if (!ts) return '从未同步';
      return formatTime(ts);
    },

    connectedDevicesCount() {
      if (!Array.isArray(this.devices)) return 0;
      return this.devices.filter(d => d.is_online || d.status === 'online' || d.last_heartbeat).length;
    },

    totalDevicesCount() {
      return Array.isArray(this.devices) ? this.devices.length : 0;
    },

    formatTime: formatTime,
  }));
});
