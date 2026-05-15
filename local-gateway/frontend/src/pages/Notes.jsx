import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort } from '../utils/format';

export default function Notes({ quickAction, clearQuickAction, onOpenTask }) {
  const { loading, request } = useApi();
  const toast = useToast();
  const [notes, setNotes] = useState([]);
  const [keyword, setKeyword] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null); // note object being edited
  const [form, setForm] = useState({ title: '', content: '', tags: '', task_id: '' });

  useEffect(() => {
    if (quickAction?.type === 'create_note') {
      openCreate();
      clearQuickAction?.();
    }
    if (quickAction?.type === 'create_note_from_task' && quickAction?.task) {
      openCreateFromTask(quickAction.task);
      clearQuickAction?.();
    }
  }, [quickAction, clearQuickAction]);

  const fetchNotes = useCallback(async () => {
    try {
      const params = new URLSearchParams({ keyword, page_size: 100 });
      const res = await request(async () => apiGet(`/api/notes?${params}`));
      if (res.status === 'error') throw new Error(res.message);
      setNotes(res.notes || []);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast, keyword]);

  useEffect(() => { fetchNotes(); }, [fetchNotes]);

  const resetForm = () => {
    setForm({ title: '', content: '', tags: '', task_id: '' });
    setEditing(null);
    setShowForm(false);
  };

  const openCreate = () => {
    resetForm();
    setShowForm(true);
  };

  const openCreateFromTask = (task) => {
    resetForm();
    const taskName = task.task_name || '任务记录';
    const title = `${taskName} 记录`;
    const content = [
      `# ${taskName}`,
      '',
      task.description ? `## 任务说明\n${task.description}\n` : '',
      task.start_time || task.due_time ? `## 时间\n- 开始：${task.start_time || '未设置'}\n- 截止：${task.due_time || '未设置'}\n` : '',
      '## 执行记录',
      '- 背景：',
      '- 进展：',
      '- 问题：',
      '- 下一步：',
      '',
    ].filter(Boolean).join('\n');
    setForm({
      title,
      content,
      tags: task.tags?.join(', ') || '',
      task_id: task.task_id || '',
    });
    setEditing(null);
    setShowForm(true);
  };

  const openEdit = (note) => {
    setForm({
      title: note.title || '',
      content: note.content || '',
      tags: (note.tags || []).join(', '),
      task_id: note.task_id || '',
    });
    setEditing(note);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) { toast('请输入标题', 'error'); return; }
    try {
      const tags = form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
      if (editing) {
        const res = await request(async () =>
          apiPost(`/api/notes/${editing.note_id}`, {
            method_override: 'PUT',
            title: form.title.trim(),
            content: form.content,
            tags,
          })
        );
        // Try actual PUT if backend requires it
        if (res.status === 'error') {
          const putRes = await fetch(`/api/notes/${editing.note_id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: form.title.trim(), content: form.content, tags }),
          }).then(r => r.json());
          if (putRes.status === 'error') throw new Error(putRes.message);
        }
        toast('笔记已更新', 'success');
      } else {
        const res = await request(async () =>
          apiPost('/api/notes', {
            title: form.title.trim(),
            content: form.content,
            tags,
            task_id: form.task_id || undefined,
          })
        );
        if (res.status === 'error') throw new Error(res.message);
        toast('笔记已创建', 'success');
      }
      resetForm();
      fetchNotes();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleDelete = async (noteId) => {
    if (!confirm('确认删除此笔记?')) return;
    try {
      const res = await fetch(`/api/notes/${noteId}`, { method: 'DELETE' }).then(r => r.json());
      if (res.status === 'error') throw new Error(res.message);
      toast('笔记已删除', 'success');
      fetchNotes();
    } catch (e) { toast(e.message, 'error'); }
  };

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <input
          type="text"
          placeholder="搜索笔记..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <div style={{ flex: 1 }} />
        <button className="btn btn-primary" onClick={openCreate}>+ 新笔记</button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 'var(--space-md)' }}>
          <h3 style={{ marginBottom: 'var(--space-md)', fontSize: '0.95rem' }}>
            {editing ? '编辑笔记' : '新建笔记'}
          </h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
              <div className="form-group">
                <label>标题 *</label>
                <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="笔记标题" />
              </div>
              {!!form.task_id && (
                <div className="form-group">
                  <label>关联任务</label>
                  <input value={form.task_id} disabled />
                </div>
              )}
              <div className="form-group">
                <label>内容</label>
                <textarea
                  value={form.content}
                  onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                  placeholder="支持 Markdown 格式"
                  rows={6}
                />
              </div>
              <div className="form-group">
                <label>标签（逗号分隔）</label>
                <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="如 学习, 灵感" />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? '保存中...' : editing ? '更新' : '创建'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Notes Grid */}
      {loading && notes.length === 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-md)' }}>
          {[1, 2, 3, 4].map(i => (
            <div className="card" key={i}>
              <div className="skeleton skeleton-text" style={{ width: '60%' }} />
              <div className="skeleton skeleton-text" style={{ width: '100%', height: 80 }} />
            </div>
          ))}
        </div>
      ) : notes.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📝</div>
            <div className="empty-state-text">暂无笔记</div>
            <div className="empty-state-hint">点击「+ 新笔记」创建你的第一条笔记</div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-md)' }}>
          {notes.map(note => (
            <div className="card" key={note.note_id} style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, lineHeight: 1.3, flex: 1, marginRight: 'var(--space-sm)' }}>
                  {note.title}
                </h3>
                <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => openEdit(note)} title="编辑">✏️</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => handleDelete(note.note_id)} title="删除">🗑️</button>
                </div>
              </div>
              <div style={{
                flex: 1, fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6,
                overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 5, WebkitBoxOrient: 'vertical',
                marginBottom: 'var(--space-sm)',
              }}>
                {note.content || '(空)'}
              </div>
              {!!note.task_id && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
                  <span style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)' }}>关联任务：{note.task_id}</span>
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => onOpenTask?.({ task_id: note.task_id, task_name: note.title.replace(/ 记录$/, '') })}
                  >
                    看任务
                  </button>
                </div>
              )}
              {(note.tags && note.tags.length > 0) && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 'var(--space-sm)' }}>
                  {note.tags.map((tag, i) => (
                    <span key={i} className="badge badge-pending">{tag}</span>
                  ))}
                </div>
              )}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 'auto' }}>
                {formatTimeShort(note.updated_at || note.created_at)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
