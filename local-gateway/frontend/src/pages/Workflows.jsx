import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort, escapeHtml } from '../utils/format';

const TRIGGER_TYPES = ['manual', 'schedule', 'event'];

const emptyForm = {
  name: '',
  description: '',
  trigger_type: 'manual',
  trigger_config: '',
  actions: '',
};

export default function Workflows() {
  const toast = useToast();
  const { loading, request } = useApi();

  const [workflows, setWorkflows] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [historyMap, setHistoryMap] = useState({});
  const [historyLoading, setHistoryLoading] = useState({});

  const fetchWorkflows = useCallback(async () => {
    try {
      const data = await request(() => apiGet('/api/workflows'));
      setWorkflows(data.workflows || data || []);
    } catch {
      toast('获取工作流失败', 'error');
    }
  }, [request, toast]);

  useEffect(() => { fetchWorkflows(); }, [fetchWorkflows]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast('请输入工作流名称', 'warning'); return; }
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        trigger_type: form.trigger_type,
        trigger_config: form.trigger_config.trim(),
        actions: form.actions.trim(),
      };
      await request(() => apiPost('/api/workflows', payload));
      toast('工作流已创建', 'success');
      setForm(emptyForm);
      setShowForm(false);
      fetchWorkflows();
    } catch {
      toast('创建工作流失败', 'error');
    }
  };

  const handleToggle = async (wf) => {
    try {
      await request(() => apiPost(`/api/workflows/${wf.id}/toggle`, { enabled: !wf.enabled }));
      toast(wf.enabled ? '已禁用' : '已启用', 'success');
      fetchWorkflows();
    } catch {
      toast('切换状态失败', 'error');
    }
  };

  const handleExecute = async (wf) => {
    try {
      await request(() => apiPost(`/api/workflows/${wf.id}/execute`, {}));
      toast(`正在执行: ${wf.name}`, 'success');
      loadHistory(wf.id);
    } catch {
      toast('执行失败', 'error');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('确认删除此工作流？')) return;
    try {
      await request(() => apiPost(`/api/workflows/${id}`, { _method: 'DELETE' }));
      toast('已删除', 'success');
      fetchWorkflows();
    } catch {
      toast('删除失败', 'error');
    }
  };

  const loadHistory = async (id) => {
    setHistoryLoading(prev => ({ ...prev, [id]: true }));
    try {
      const data = await apiGet(`/api/workflows/${id}/history`);
      setHistoryMap(prev => ({ ...prev, [id]: data.history || data || [] }));
    } catch {
      toast('获取历史记录失败', 'error');
    } finally {
      setHistoryLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const toggleHistory = (id) => {
    if (expandedId === id) {
      setExpandedId(null);
    } else {
      setExpandedId(id);
      if (!historyMap[id]) loadHistory(id);
    }
  };

  const updateField = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  return (
    <div style={{ padding: 'var(--space-lg)', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-lg)' }}>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>工作流</h2>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '+ 新建工作流'}
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            <div className="form-group">
              <label>名称</label>
              <input value={form.name} onChange={e => updateField('name', e.target.value)} placeholder="工作流名称" />
            </div>
            <div className="form-group">
              <label>描述</label>
              <input value={form.description} onChange={e => updateField('description', e.target.value)} placeholder="简短描述" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
              <div className="form-group">
                <label>触发类型</label>
                <select value={form.trigger_type} onChange={e => updateField('trigger_type', e.target.value)}>
                  {TRIGGER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>触发配置</label>
                <input value={form.trigger_config} onChange={e => updateField('trigger_config', e.target.value)} placeholder='如: "0 9 * * *"' />
              </div>
            </div>
            <div className="form-group">
              <label>动作 (JSON)</label>
              <textarea value={form.actions} onChange={e => updateField('actions', e.target.value)}
                placeholder='[{"type": "task", "title": "..."}]' rows={4} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
              <button type="button" className="btn btn-ghost" onClick={() => { setShowForm(false); setForm(emptyForm); }}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>创建</button>
            </div>
          </form>
        </div>
      )}

      {loading && workflows.length === 0 ? (
        <div className="card">
          <div className="skeleton skeleton-text" style={{ width: '60%' }} />
          <div className="skeleton skeleton-text" style={{ width: '40%' }} />
          <div className="skeleton skeleton-text" style={{ width: '80%' }} />
        </div>
      ) : workflows.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔄</div>
          <div className="empty-state-text">暂无工作流</div>
          <div className="empty-state-hint">点击上方按钮创建你的第一个工作流</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          {workflows.map(wf => (
            <div key={wf.id} className="card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', flex: 1, minWidth: 0 }}>
                  <span style={{ fontSize: '1.2rem' }}>🔄</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {escapeHtml(wf.name)}
                    </div>
                    {wf.description && (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                        {escapeHtml(wf.description)}
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexShrink: 0 }}>
                  <span className={`badge ${wf.enabled ? 'badge-completed' : 'badge-pending'}`}>
                    {wf.enabled ? '启用' : '禁用'}
                  </span>
                  <button className="btn btn-sm btn-ghost" onClick={() => handleToggle(wf)} title={wf.enabled ? '禁用' : '启用'}>
                    {wf.enabled ? '⏸' : '▶'}
                  </button>
                  <button className="btn btn-sm btn-primary" onClick={() => handleExecute(wf)} disabled={!wf.enabled || loading}>
                    执行
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => toggleHistory(wf.id)}>
                    {expandedId === wf.id ? '收起' : '历史'}
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(wf.id)}>删除</button>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 'var(--space-lg)', marginTop: 'var(--space-sm)', fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                <span>触发: {wf.trigger_type}</span>
                {wf.trigger_config && <span>配置: {escapeHtml(wf.trigger_config)}</span>}
                {wf.last_run && <span>上次运行: {formatTimeShort(wf.last_run)}</span>}
              </div>

              {expandedId === wf.id && (
                <div style={{ marginTop: 'var(--space-md)', borderTop: '1px solid var(--border)', paddingTop: 'var(--space-md)' }}>
                  <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>执行历史</h4>
                  {historyLoading[wf.id] ? (
                    <>
                      <div className="skeleton skeleton-text" style={{ width: '80%' }} />
                      <div className="skeleton skeleton-text" style={{ width: '60%' }} />
                    </>
                  ) : (historyMap[wf.id] || []).length === 0 ? (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>暂无执行记录</div>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr><th>时间</th><th>状态</th><th>耗时</th><th>备注</th></tr>
                      </thead>
                      <tbody>
                        {historyMap[wf.id].map((h, i) => (
                          <tr key={i}>
                            <td>{formatTimeShort(h.started_at || h.created_at)}</td>
                            <td>
                              <span className={`badge badge-${h.status === 'success' ? 'completed' : h.status === 'failed' ? 'error' : 'pending'}`}>
                                {h.status === 'success' ? '成功' : h.status === 'failed' ? '失败' : '运行中'}
                              </span>
                            </td>
                            <td>{h.duration ? `${h.duration}s` : '-'}</td>
                            <td style={{ color: 'var(--text-tertiary)' }}>{escapeHtml(h.message || '-')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
