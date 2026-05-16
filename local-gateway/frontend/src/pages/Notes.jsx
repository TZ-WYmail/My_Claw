import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort } from '../utils/format';
import { normalizeList } from '../utils/normalize';

export default function Notes({ quickAction, clearQuickAction, onOpenTask }) {
  const { loading, request } = useApi();
  const toast = useToast();
  const [notes, setNotes] = useState([]);
  const [keyword, setKeyword] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
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
      setNotes(normalizeList(res, ['notes', 'items']));
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

  const linkedCount = notes.filter(note => note.task_id).length;
  const taggedCount = notes.filter(note => note.tags && note.tags.length > 0).length;

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 04 / Archive Clippings</div>
          <h1 className="atlas-chapter-title">笔记页应该像档案剪报册，先看线索和出处，再决定进入哪条任务。</h1>
          <div className="atlas-chapter-copy">
            这里的重点不是“能写字”，而是让记录具备出处、标签和任务关联。你应该先看到哪条记录有价值，再决定展开、编辑或者回跳到原任务。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">档案规则</div>
          <div className="atlas-chapter-note-copy">标题写结论，标签写索引，正文写过程，任务关联写归属。</div>
        </div>
      </section>

      <section className="mission-masthead atlas-leaf">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">INTEL WALL</span>
            <h1 className="mission-title">把笔记做成情报墙，不做无差别便签堆。</h1>
            <div className="mission-copy">
              这里保留真实记录内容、关联任务和标签，但展示上改成档案墙：每条记录像一张贴在作战板上的纸页，先看到主题和线索，再决定进入哪条任务。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{notes.length} 条记录</span>
              <span className="badge badge-completed">{linkedCount} 条已关联任务</span>
              <span className="badge badge-warning">{taggedCount} 条带标签</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">记录准则</div>
            <div className="mission-sidecard-copy">
              标题写结论，正文写推演，标签写检索线索。这样笔记页才像情报站，不像散乱输入框。
            </div>
          </div>
        </div>
      </section>

      <div className="atlas-toolbar">
        <input
          type="text"
          placeholder="搜索笔记..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          style={{ maxWidth: 320 }}
        />
        <div className="board-toolbar-spacer" />
        <button className="btn btn-primary" onClick={openCreate}>+ 新笔记</button>
      </div>

      {showForm && (
        <section className="board-lane atlas-ledger-lane">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">WRITE</div>
              <h3 className="board-lane-title">{editing ? '编辑笔记' : '新建笔记'}</h3>
              <div className="board-lane-copy">
                直接编辑内容本体，保留 Markdown 和关联任务，不额外制造空洞的字段解释。
              </div>
            </div>
          </div>
          <form onSubmit={handleSubmit} className="command-form">
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
                  rows={8}
                />
              </div>
              <div className="form-group">
                <label>标签（逗号分隔）</label>
                <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="如 学习, 灵感" />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? '保存中...' : editing ? '更新' : '创建'}
              </button>
            </div>
          </form>
        </section>
      )}

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">档案总数</div>
          <div className="board-summary-value">{notes.length}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">任务联动</div>
          <div className="board-summary-value">{linkedCount}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">标签密度</div>
          <div className="board-summary-value">{taggedCount}</div>
        </div>
      </div>

      {loading && notes.length === 0 ? (
        <div className="board-card-grid">
          {[1, 2, 3, 4].map(i => (
            <div className="dossier-card" key={i}>
              <div className="skeleton skeleton-text" style={{ width: '60%' }} />
              <div className="skeleton skeleton-text" style={{ width: '100%', height: 80 }} />
            </div>
          ))}
        </div>
      ) : notes.length === 0 ? (
        <section className="board-lane">
          <div className="empty-state">
            <div className="empty-state-icon">📝</div>
            <div className="empty-state-text">暂无笔记</div>
            <div className="empty-state-hint">点击「+ 新笔记」创建你的第一条笔记</div>
          </div>
        </section>
      ) : (
        <section className="board-lane atlas-paper-stack">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">DOSSIERS</div>
              <h3 className="board-lane-title">记录档案墙</h3>
              <div className="board-lane-copy">每一条笔记都是一张可追溯的记录纸，先读摘要，再进入编辑或任务。</div>
            </div>
          </div>

          <div className="board-card-grid">
            {notes.map(note => (
              <div className="dossier-card" key={note.note_id} style={{ transform: `rotate(${note.task_id ? '-0.8deg' : '0.9deg'})` }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-sm)' }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="section-kicker">NOTE #{String(note.note_id).slice(0, 6)}</div>
                    <h3 className="dossier-title">{note.title}</h3>
                  </div>
                  <div className="dossier-actions" style={{ marginTop: 0 }}>
                    <button className="btn btn-sm btn-ghost" onClick={() => openEdit(note)}>编辑</button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(note.note_id)}>删除</button>
                  </div>
                </div>

                <div className="dossier-copy" style={{
                  overflow: 'hidden',
                  display: '-webkit-box',
                  WebkitLineClamp: 6,
                  WebkitBoxOrient: 'vertical',
                }}>
                  {note.content || '(空)'}
                </div>

                <div className="dossier-meta-grid">
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">更新时间</div>
                    <div>{formatTimeShort(note.updated_at || note.created_at)}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">关联任务</div>
                    <div>{note.task_id || '未关联'}</div>
                  </div>
                </div>

                {(note.tags && note.tags.length > 0) && (
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {note.tags.map((tag, i) => (
                      <span key={i} className="badge badge-pending">{tag}</span>
                    ))}
                  </div>
                )}

                <div className="dossier-actions">
                  {!!note.task_id && (
                    <button
                      className="btn btn-sm btn-ghost"
                      onClick={() => onOpenTask?.({ task_id: note.task_id, task_name: note.title.replace(/ 记录$/, '') })}
                    >
                      看任务
                    </button>
                  )}
                  <button className="btn btn-sm btn-primary" onClick={() => openEdit(note)}>打开编辑</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
