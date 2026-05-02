import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort, RECURRENCE_MAP, badgeClass, statusLabel } from '../utils/format';

const PRIORITY_MAP = { 0: '紧急', 1: '高', 2: '中', 3: '低' };
const PRIORITY_COLORS = { 0: 'error', 1: 'warning', 2: 'pending', 3: 'completed' };
const TABS = [
  { key: 'week', label: '周视图' },
  { key: 'all', label: '全部任务' },
];

export default function Tasks() {
  const [tab, setTab] = useState('week');
  return (
    <div>
      <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            className={`btn ${tab === t.key ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'week' ? <WeekView /> : <AllTasksView />}
    </div>
  );
}

/* ── Week View ────────────────────────────────────────── */

function getWeekRange(offset) {
  const now = new Date();
  const day = now.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + mondayOffset + offset * 7);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { monday: fmt(monday), sunday: fmt(sunday), mondayDate: monday, sundayDate: sunday };
}

function WeekView() {
  const { loading, request } = useApi();
  const toast = useToast();
  const [offset, setOffset] = useState(0);
  const [tasks, setTasks] = useState([]);

  const { monday, sunday, mondayDate, sundayDate } = getWeekRange(offset);

  const fetchWeek = useCallback(async () => {
    try {
      const res = await request(async () =>
        apiPost('/api/task', {
          action: 'get_weekly_plan',
          due_time: monday + 'T00:00:00',
          task_name: sunday + 'T23:59:59',
        })
      );
      if (res.status === 'error') throw new Error(res.message);
      setTasks(res.tasks || []);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast, monday, sunday]);

  useEffect(() => { fetchWeek(); }, [fetchWeek]);

  const goPrev = () => { setOffset(o => o - 1); };
  const goNext = () => { setOffset(o => o + 1); };
  const goToday = () => { setOffset(0); };

  const weekLabel = `${mondayDate.getMonth() + 1}/${mondayDate.getDate()} - ${sundayDate.getMonth() + 1}/${sundayDate.getDate()}`;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <button className="btn btn-sm" onClick={goPrev}>&larr; 上一周</button>
        <button className="btn btn-sm btn-primary" onClick={goToday}>本周</button>
        <button className="btn btn-sm" onClick={goNext}>下一周 &rarr;</button>
        <span style={{ fontSize: '0.9rem', fontWeight: 500, marginLeft: 'var(--space-sm)' }}>{weekLabel}</span>
      </div>

      {loading ? (
        <div className="card">
          {[1, 2, 3].map(i => (
            <div className="skeleton skeleton-text" key={i} style={{ height: 60, marginBottom: 'var(--space-sm)' }} />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📅</div>
            <div className="empty-state-text">本周暂无任务</div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>任务</th>
                <th>截止时间</th>
                <th>优先级</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => (
                <tr key={t.task_id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{t.task_name}</div>
                    {t.description && (
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                        {t.description.length > 60 ? t.description.slice(0, 60) + '...' : t.description}
                      </div>
                    )}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>{formatTimeShort(t.due_time)}</td>
                  <td>
                    <span className={`badge badge-${PRIORITY_COLORS[t.priority] || 'pending'}`}>
                      {PRIORITY_MAP[t.priority] || '中'}
                    </span>
                  </td>
                  <td>
                    <span className={`badge badge-${badgeClass(t.status)}`}>{statusLabel(t.status)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── All Tasks View ───────────────────────────────────── */

function AllTasksView() {
  const { loading, request } = useApi();
  const toast = useToast();
  const [tasks, setTasks] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [showForm, setShowForm] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());

  const fetchTasks = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page, keyword, status: statusFilter, page_size: 20 });
      const res = await request(async () => apiGet(`/api/tasks/all?${params}`));
      if (res.status === 'error') throw new Error(res.message);
      setTasks(res.tasks || []);
      setTotal(res.total || 0);
      setTotalPages(res.total_pages || 0);
      setSelectedIds(new Set());
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast, page, keyword, statusFilter]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const handleComplete = async (taskId) => {
    try {
      const res = await apiPost('/api/task', { action: 'complete_task', task_id: taskId });
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已完成', 'success');
      fetchTasks();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleDelete = async (taskId) => {
    if (!confirm('确认删除此任务?')) return;
    try {
      const res = await apiPost('/api/task', { action: 'delete_task', task_id: taskId });
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已删除', 'success');
      fetchTasks();
    } catch (e) { toast(e.message, 'error'); }
  };

  // Batch operations
  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === tasks.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(tasks.map(t => t.task_id)));
    }
  };

  const clearSelection = () => setSelectedIds(new Set());

  const handleBatchComplete = async () => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    try {
      const res = await apiPost('/api/task', { action: 'batch_complete', task_ids: ids });
      if (res.status === 'error') throw new Error(res.message);
      toast(res.message || `已完成 ${ids.length} 项任务`, 'success');
      fetchTasks();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleBatchDelete = async () => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    if (!confirm(`确认删除 ${ids.length} 项任务？`)) return;
    try {
      const res = await apiPost('/api/task', { action: 'batch_delete', task_ids: ids });
      if (res.status === 'error') throw new Error(res.message);
      toast(res.message || `已删除 ${ids.length} 项任务`, 'success');
      fetchTasks();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleSearch = (e) => { setKeyword(e.target.value); setPage(1); };
  const handleStatusFilter = (e) => { setStatusFilter(e.target.value); setPage(1); };

  const allSelected = tasks.length > 0 && selectedIds.size === tasks.length;

  return (
    <div style={{ position: 'relative', paddingBottom: selectedIds.size > 0 ? 60 : 0 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="搜索任务..."
          value={keyword}
          onChange={handleSearch}
          style={{ maxWidth: 240 }}
        />
        <select value={statusFilter} onChange={handleStatusFilter} style={{ maxWidth: 140 }}>
          <option value="active">进行中</option>
          <option value="pending">待办</option>
          <option value="completed">已完成</option>
          <option value="deleted">已删除</option>
        </select>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>共 {total} 项</span>
        <button className="btn btn-primary" onClick={() => setShowForm(f => !f)}>
          {showForm ? '取消' : '+ 新任务'}
        </button>
      </div>

      {/* New Task Form */}
      {showForm && (
        <TaskForm onCreated={() => { setShowForm(false); fetchTasks(); }} toast={toast} />
      )}

      {/* Table */}
      {loading && tasks.length === 0 ? (
        <div className="card">
          {[1, 2, 3, 4, 5].map(i => (
            <div className="skeleton skeleton-text" key={i} style={{ height: 44, marginBottom: 'var(--space-xs)' }} />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-text">暂无任务</div>
            <div className="empty-state-hint">点击「+ 新任务」添加第一个任务</div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                </th>
                <th>任务</th>
                <th>截止时间</th>
                <th>优先级</th>
                <th>重复</th>
                <th>状态</th>
                <th style={{ width: 120 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => (
                <tr key={t.task_id} style={{ background: selectedIds.has(t.task_id) ? 'rgba(10,132,255,0.06)' : undefined }}>
                  <td>
                    <input type="checkbox" checked={selectedIds.has(t.task_id)} onChange={() => toggleSelect(t.task_id)} />
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{t.task_name}</div>
                    {t.description && (
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                        {t.description.length > 60 ? t.description.slice(0, 60) + '...' : t.description}
                      </div>
                    )}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>{formatTimeShort(t.due_time)}</td>
                  <td>
                    <span className={`badge badge-${PRIORITY_COLORS[t.priority] || 'pending'}`}>
                      {PRIORITY_MAP[t.priority] || '中'}
                    </span>
                  </td>
                  <td>{RECURRENCE_MAP[t.recurrence] || t.recurrence}</td>
                  <td>
                    <span className={`badge badge-${badgeClass(t.status)}`}>{statusLabel(t.status)}</span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
                      {t.status === 'pending' && (
                        <button className="btn btn-sm btn-success" onClick={() => handleComplete(t.task_id)}>完成</button>
                      )}
                      {t.status !== 'deleted' && (
                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(t.task_id)}>删除</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>&laquo;</button>
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter(p => Math.abs(p - page) < 4 || p === 1 || p === totalPages)
            .map((p, i, arr) => (
              <span key={p} style={{ display: 'inline-flex', alignItems: 'center' }}>
                {i > 0 && arr[i - 1] !== p - 1 && <span style={{ padding: '0 4px', color: 'var(--text-tertiary)' }}>...</span>}
                <button className={p === page ? 'active' : ''} onClick={() => setPage(p)}>{p}</button>
              </span>
            ))
          }
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>&raquo;</button>
        </div>
      )}

      {/* Floating batch action bar */}
      {selectedIds.size > 0 && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 100,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--space-sm)',
          padding: 'var(--space-sm) var(--space-lg)',
          background: 'var(--bg-card)', borderTop: '1px solid var(--border)',
          boxShadow: '0 -2px 12px rgba(0,0,0,0.12)',
        }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>已选 {selectedIds.size} 项</span>
          <button className="btn btn-sm btn-success" onClick={handleBatchComplete}>批量完成</button>
          <button className="btn btn-sm btn-danger" onClick={handleBatchDelete}>批量删除</button>
          <button className="btn btn-sm btn-ghost" onClick={clearSelection}>取消选择</button>
        </div>
      )}
    </div>
  );
}

/* ── Task Form ────────────────────────────────────────── */

function TaskForm({ onCreated, toast }) {
  const { loading, request } = useApi();
  const [form, setForm] = useState({
    task_name: '', due_time: '', recurrence: 'once', priority: 2, description: '',
    estimated_minutes: '', tags: '',
  });

  const update = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.task_name.trim()) { toast('请输入任务名称', 'error'); return; }
    if (!form.due_time) { toast('请选择截止时间', 'error'); return; }
    try {
      const res = await request(async () => apiPost('/api/task', {
        action: 'add_task',
        task_name: form.task_name.trim(),
        due_time: new Date(form.due_time).toISOString(),
        recurrence: form.recurrence,
        priority: Number(form.priority),
        description: form.description || undefined,
        estimated_minutes: form.estimated_minutes ? Number(form.estimated_minutes) : undefined,
        tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined,
      }));
      if (res.status === 'error') throw new Error(res.message);
      toast('任务创建成功', 'success');
      onCreated();
    } catch (e) { toast(e.message, 'error'); }
  };

  return (
    <div className="card" style={{ marginBottom: 'var(--space-md)' }}>
      <h3 style={{ marginBottom: 'var(--space-md)', fontSize: '0.95rem' }}>新建任务</h3>
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
          <div className="form-group">
            <label>任务名称 *</label>
            <input value={form.task_name} onChange={e => update('task_name', e.target.value)} placeholder="输入任务名称" />
          </div>
          <div className="form-group">
            <label>截止时间 *</label>
            <input type="datetime-local" value={form.due_time} onChange={e => update('due_time', e.target.value)} />
          </div>
          <div className="form-group">
            <label>重复</label>
            <select value={form.recurrence} onChange={e => update('recurrence', e.target.value)}>
              {Object.entries(RECURRENCE_MAP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>优先级</label>
            <select value={form.priority} onChange={e => update('priority', e.target.value)}>
              {Object.entries(PRIORITY_MAP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ gridColumn: '1 / -1' }}>
            <label>描述</label>
            <textarea value={form.description} onChange={e => update('description', e.target.value)} placeholder="任务描述（可选）" rows={2} />
          </div>
          <div className="form-group">
            <label>预估时间（分钟）</label>
            <input type="number" min="1" value={form.estimated_minutes} onChange={e => update('estimated_minutes', e.target.value)} placeholder="如 30" />
          </div>
          <div className="form-group">
            <label>标签（逗号分隔）</label>
            <input value={form.tags} onChange={e => update('tags', e.target.value)} placeholder="如 学习, 工作" />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
          <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? '创建中...' : '创建任务'}</button>
        </div>
      </form>
    </div>
  );
}
