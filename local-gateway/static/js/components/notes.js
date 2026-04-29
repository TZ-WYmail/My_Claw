/* local-gateway/static/js/components/notes.js */
import { apiGet, apiPost, toast } from '../api.js';
import { formatTime, escapeHtml } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('notes', () => ({
    loading: true,
    error: null,
    notes: [],
    total: 0,
    keyword: '',
    showForm: false,
    editingId: null,
    form: { title: '', content: '', tags: '' },

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'notes') this.load();
      });
      if (Alpine.store('view').current === 'notes') await this.load();
    },

    async load() {
      this.loading = true;
      this.error = null;
      try {
        const params = new URLSearchParams({ keyword: this.keyword });
        const data = await apiGet(`/api/notes?${params}`);
        this.notes = data.notes || [];
        this.total = data.total || 0;
      } catch (e) {
        this.error = e.message;
        toast('加载笔记失败', 'error');
      } finally {
        this.loading = false;
      }
    },

    contentPreview(content) {
      if (!content) return '';
      return content.length > 100 ? content.substring(0, 100) + '...' : content;
    },

    resetForm() {
      this.form = { title: '', content: '', tags: '' };
      this.editingId = null;
      this.showForm = false;
    },

    openNewForm() {
      this.editingId = null;
      this.form = { title: '', content: '', tags: '' };
      this.showForm = true;
    },

    async saveNote() {
      if (!this.form.title) {
        toast('请输入笔记标题', 'error');
        return;
      }
      const tags = this.form.tags.split(',').map(t => t.trim()).filter(t => t);
      try {
        if (this.editingId) {
          const resp = await fetch(`/api/notes/${this.editingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: this.form.title, content: this.form.content, tags }),
          });
          const data = await resp.json();
          if (data.status !== 'success') throw new Error(data.message || '更新失败');
          toast('笔记已更新', 'success');
        } else {
          const data = await apiPost('/api/notes/', { title: this.form.title, content: this.form.content, tags });
          if (data.status !== 'success') throw new Error(data.message || '创建失败');
          toast('笔记已创建', 'success');
        }
        this.resetForm();
        await this.load();
      } catch (e) {
        toast(this.editingId ? '更新失败' : '创建失败', 'error');
      }
    },

    editNote(note) {
      this.editingId = note.note_id;
      this.form = {
        title: note.title,
        content: note.content || '',
        tags: (note.tags || []).join(', '),
      };
      this.showForm = true;
    },

    async deleteNote(id) {
      if (!confirm('确定删除此笔记？')) return;
      const removed = this.notes.filter(n => n.note_id === id);
      this.notes = this.notes.filter(n => n.note_id !== id);
      this.total = Math.max(0, this.total - 1);

      try {
        const resp = await fetch(`/api/notes/${id}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.status !== 'success') throw new Error(data.message);
        toast('笔记已删除', 'success');
      } catch (e) {
        toast('删除失败', 'error');
        await this.load();
      }
    },

    formatTime: formatTime,
    escapeHtml: escapeHtml,
  }));
});
