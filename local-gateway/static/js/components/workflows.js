/* local-gateway/static/js/components/workflows.js */
import { apiGet, apiPost, toast } from '../api.js';
import { formatTime, formatTimeShort, escapeHtml } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('workflows', () => ({
    loading: true,
    error: null,
    workflows: [],

    // Create form
    showForm: false,
    form: { name: '', description: '', trigger_type: 'manual', trigger_config: '{}', actions: '[]' },

    // Trigger/action type metadata
    triggerTypes: [],
    actionTypes: [],

    // Execution history
    showHistory: false,
    historyWorkflowId: null,
    historyWorkflowName: '',
    historyLoading: false,
    historyItems: [],

    // Confirm delete
    confirmDeleteId: null,

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'workflows') this.load();
      });
      if (Alpine.store('view').current === 'workflows') await this.load();
    },

    async load() {
      this.loading = true;
      this.error = null;
      try {
        const data = await apiGet('/api/workflows');
        this.workflows = Array.isArray(data) ? data : (data.workflows || data.data || []);
      } catch (e) {
        this.error = e.message || '加载失败';
        toast('加载工作流失败', 'error');
      } finally {
        this.loading = false;
      }
    },

    openNewForm() {
      this.form = { name: '', description: '', trigger_type: 'manual', trigger_config: '{}', actions: '[]' };
      this.showForm = true;
    },

    async createWorkflow() {
      if (!this.form.name) {
        toast('请输入工作流名称', 'error');
        return;
      }
      let triggerConfig, actions;
      try {
        triggerConfig = JSON.parse(this.form.trigger_config);
        actions = JSON.parse(this.form.actions);
      } catch {
        toast('触发配置或动作必须是有效的 JSON', 'error');
        return;
      }
      try {
        const data = await apiPost('/api/workflows', {
          name: this.form.name,
          description: this.form.description,
          trigger_type: this.form.trigger_type,
          trigger_config: triggerConfig,
          actions: actions,
        });
        if (data.status !== 'success' && data.status !== undefined && data.status !== 'ok') {
          throw new Error(data.message || '创建失败');
        }
        toast('工作流已创建', 'success');
        this.showForm = false;
        await this.load();
      } catch (e) {
        toast('创建工作流失败', 'error');
      }
    },

    async toggleWorkflow(id) {
      const wf = this.workflows.find(w => w.id === id || w.workflow_id === id);
      const oldEnabled = wf ? wf.enabled : true;
      if (wf) wf.enabled = !wf.enabled;

      try {
        const data = await apiPost(`/api/workflows/${id}/toggle`, {});
        if (data.status !== 'success' && data.status !== 'ok' && data.status !== undefined) {
          throw new Error(data.message || '切换失败');
        }
        toast(wf?.enabled ? '工作流已启用' : '工作流已禁用', 'success');
      } catch (e) {
        if (wf) wf.enabled = oldEnabled;
        toast('切换失败', 'error');
      }
    },

    async executeWorkflow(id, e) {
      e.stopPropagation();
      const wf = this.workflows.find(w => w.id === id || w.workflow_id === id);
      toast(`正在执行「${escapeHtml(wf?.name || '')}」...`, 'info');
      try {
        const data = await apiPost(`/api/workflows/${id}/execute`, {});
        if (data.status !== 'success' && data.status !== 'ok' && data.status !== undefined) {
          throw new Error(data.message || '执行失败');
        }
        toast('工作流已执行', 'success');
      } catch (e) {
        toast('执行失败', 'error');
      }
    },

    async deleteWorkflow(id) {
      if (!confirm('确定删除此工作流？')) return;
      this.workflows = this.workflows.filter(w => (w.id !== id && w.workflow_id !== id));

      try {
        const resp = await fetch(`/api/workflows/${id}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.status !== 'success' && data.status !== 'ok' && data.status !== undefined) {
          throw new Error(data.message);
        }
        toast('工作流已删除', 'success');
      } catch (e) {
        toast('删除失败', 'error');
        await this.load();
      }
    },

    async loadHistory(id, name) {
      if (this.showHistory && this.historyWorkflowId === id) {
        this.showHistory = false;
        return;
      }
      this.historyWorkflowId = id;
      this.historyWorkflowName = name;
      this.historyLoading = true;
      try {
        const data = await apiGet(`/api/workflows/${id}/executions`);
        this.historyItems = Array.isArray(data) ? data : (data.executions || data.data || []);
        this.showHistory = true;
      } catch (e) {
        toast('加载执行历史失败', 'error');
        this.historyItems = [];
      } finally {
        this.historyLoading = false;
      }
    },

    closeHistory() {
      this.showHistory = false;
      this.historyWorkflowId = null;
      this.historyWorkflowName = '';
      this.historyItems = [];
    },

    triggerLabel(type) {
      const map = { manual: '手动', schedule: '定时', webhook: 'Webhook', event: '事件' };
      return map[type] || type || '手动';
    },

    getWorkflowId(wf) {
      return wf.id || wf.workflow_id;
    },

    statusLabel(status) {
      const map = { success: '成功', failed: '失败', running: '运行中', pending: '等待中' };
      return map[status] || status || '-';
    },

    statusClass(status) {
      if (status === 'success') return 'badge-completed';
      if (status === 'failed') return 'badge-error';
      return 'badge-pending';
    },

    formatTime: formatTime,
    formatTimeShort: formatTimeShort,
    escapeHtml: escapeHtml,
  }));
});
