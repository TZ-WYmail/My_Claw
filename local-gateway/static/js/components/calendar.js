/* local-gateway/static/js/components/calendar.js */
import { apiGet, apiPost, toast } from '../api.js';
import { escapeHtml } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('calendar', () => ({
    loading: true,
    error: null,
    year: 2026,
    month: 4,
    weeks: [],
    monthLabel: '',

    // Day modal
    showDayModal: false,
    selectedDay: null,
    selectedEvents: [],

    // New event form
    showNewEventForm: false,
    newEvent: { title: '', description: '', event_date: '', event_type: 'reminder', color: '#0a84ff' },

    colors: ['#0a84ff', '#30d158', '#ff9f0a', '#ff453a', '#bf5af2', '#ffd60a', '#5e5ce6', '#ff375f'],

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'calendar') this.load();
      });
      if (Alpine.store('view').current === 'calendar') await this.load();
    },

    async load() {
      this.loading = true;
      this.error = null;
      try {
        const data = await apiGet(`/api/advanced/calendar/view?year=${this.year}&month=${this.month}`);
        if (data.status !== 'success') throw new Error(data.message);
        this.weeks = data.weeks || [];
        this.monthLabel = `${data.year}年${data.month}月`;
      } catch (e) {
        this.error = e.message;
        toast('加载日历失败', 'error');
      } finally {
        this.loading = false;
      }
    },

    prevMonth() {
      this.month--;
      if (this.month < 1) { this.month = 12; this.year--; }
      this.load();
    },

    nextMonth() {
      this.month++;
      if (this.month > 12) { this.month = 1; this.year++; }
      this.load();
    },

    goToday() {
      const now = new Date();
      this.year = now.getFullYear();
      this.month = now.getMonth() + 1;
      this.load();
    },

    openDay(day) {
      this.selectedDay = day;
      this.selectedEvents = (day.events || []).slice();
      this.newEvent.event_date = day.date;
      this.showDayModal = true;
      this.showNewEventForm = false;
    },

    closeDayModal() {
      this.showDayModal = false;
      this.selectedDay = null;
      this.selectedEvents = [];
      this.showNewEventForm = false;
    },

    openNewEventForm() {
      this.newEvent = {
        title: '', description: '',
        event_date: this.selectedDay?.date || '',
        event_type: 'reminder',
        color: '#0a84ff',
      };
      this.showNewEventForm = true;
    },

    closeNewEventForm() {
      this.showNewEventForm = false;
    },

    async createEvent() {
      if (!this.newEvent.title) {
        toast('请输入事件标题', 'error');
        return;
      }
      try {
        const data = await apiPost('/api/advanced/calendar/events', {
          title: this.newEvent.title,
          description: this.newEvent.description,
          event_date: this.newEvent.event_date,
          event_type: this.newEvent.event_type,
          color: this.newEvent.color,
        });
        if (data.status !== 'success') throw new Error(data.message || '创建失败');
        toast('事件已创建', 'success');
        this.showNewEventForm = false;
        await this.load();
        // Re-open the same day with fresh events
        if (this.selectedDay) {
          const freshDay = this.findDayInWeeks(this.selectedDay.date);
          if (freshDay) {
            this.selectedDay = freshDay;
            this.selectedEvents = (freshDay.events || []).slice();
          }
        }
      } catch (e) {
        toast('创建事件失败', 'error');
      }
    },

    async deleteEvent(eventId) {
      if (!confirm('确定删除此事件？')) return;
      try {
        const resp = await fetch(`/api/advanced/calendar/events/${eventId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.status !== 'success') throw new Error(data.message);
        toast('事件已删除', 'success');
        this.selectedEvents = this.selectedEvents.filter(e => e.event_id !== eventId);
        await this.load();
        // Re-open the same day
        if (this.selectedDay) {
          const freshDay = this.findDayInWeeks(this.selectedDay.date);
          if (freshDay) {
            this.selectedDay = freshDay;
            this.selectedEvents = (freshDay.events || []).slice();
          }
        }
      } catch (e) {
        toast('删除失败', 'error');
      }
    },

    findDayInWeeks(dateStr) {
      for (const week of this.weeks) {
        for (const day of week) {
          if (day.date === dateStr) return day;
        }
      }
      return null;
    },

    eventTypeLabel(type) {
      const map = { reminder: '提醒', meeting: '会议', task: '任务', birthday: '生日', holiday: '假期', other: '其他' };
      return map[type] || type || '其他';
    },

    formatDate(dateStr) {
      if (!dateStr) return '';
      try {
        const d = new Date(dateStr);
        return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
      } catch { return dateStr; }
    },

    escapeHtml: escapeHtml,
  }));
});
