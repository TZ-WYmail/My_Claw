/* local-gateway/static/js/components/tasks.js */
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

    // Tabs
    tab: 'week',

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'tasks') this.loadWeeklyPlan();
      });
      if (Alpine.store('view').current === 'tasks') await this.loadWeeklyPlan(0);
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

    formatTime: formatTime,
    formatTimeShort: formatTimeShort,
    RECURRENCE_MAP: RECURRENCE_MAP,
    badgeClass: badgeClass,
  }));
});
