/* local-gateway/static/js/components/habits.js */
import { apiGet, apiPost, toast } from '../api.js';
import { formatTime, escapeHtml } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('habits', () => ({
    loading: true,
    error: null,
    habits: [],
    showForm: false,
    form: { name: '', description: '', frequency: 'daily', target: 1 },
    checkingInId: null,

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'habits') this.load();
      });
      if (Alpine.store('view').current === 'habits') await this.load();
    },

    async load() {
      this.loading = true;
      this.error = null;
      try {
        const data = await apiGet('/api/habits');
        const habits = data.habits || [];

        // Load streak for each habit in parallel
        this.habits = await Promise.all(habits.map(async (h) => {
          try {
            const detail = await apiGet(`/api/habits/${h.habit_id}`);
            return { ...h, streak: detail.habit?.streak || 0 };
          } catch {
            return { ...h, streak: 0 };
          }
        }));
      } catch (e) {
        this.error = e.message;
        toast('加载习惯失败', 'error');
      } finally {
        this.loading = false;
      }
    },

    async checkin(id) {
      this.checkingInId = id;
      try {
        const data = await apiPost(`/api/habits/${id}/checkin`, { count: 1, note: '' });
        if (data.status !== 'success') throw new Error(data.message || '打卡失败');
        toast('打卡成功！', 'success');

        // Refresh streak for this habit
        const habit = this.habits.find(h => h.habit_id === id);
        if (habit) {
          try {
            const detail = await apiGet(`/api/habits/${id}`);
            habit.streak = detail.habit?.streak || 0;
          } catch {}
        }
      } catch (e) {
        toast('打卡失败', 'error');
      }
      setTimeout(() => { this.checkingInId = null; }, 600);
    },

    resetForm() {
      this.form = { name: '', description: '', frequency: 'daily', target: 1 };
      this.showForm = false;
    },

    async createHabit() {
      if (!this.form.name) {
        toast('请输入习惯名称', 'error');
        return;
      }
      try {
        const data = await apiPost('/api/habits/', {
          name: this.form.name,
          description: this.form.description,
          frequency: this.form.frequency,
          target_count: this.form.target,
        });
        if (data.status !== 'success') throw new Error(data.message || '创建失败');
        toast('习惯已创建', 'success');
        this.resetForm();
        await this.load();
      } catch (e) {
        toast('创建失败', 'error');
      }
    },

    async deleteHabit(id) {
      if (!confirm('确定删除此习惯？')) return;
      this.habits = this.habits.filter(h => h.habit_id !== id);

      try {
        const resp = await fetch(`/api/habits/${id}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.status !== 'success') throw new Error(data.message);
        toast('习惯已删除', 'success');
      } catch (e) {
        toast('删除失败', 'error');
        await this.load();
      }
    },

    streakLabel(streak) {
      if (streak >= 7) return `🔥 ${streak}天`;
      if (streak >= 3) return `💪 ${streak}天`;
      return `⭐ ${streak}天`;
    },

    frequencyLabel(freq) {
      const map = { daily: '每天', weekly: '每周', monthly: '每月' };
      return map[freq] || freq;
    },

    formatTime: formatTime,
    escapeHtml: escapeHtml,
  }));
});
