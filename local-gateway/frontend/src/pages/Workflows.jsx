import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort, escapeHtml } from '../utils/format';

const TRIGGER_TYPES = ['schedule', 'task_completed', 'task_created', 'habit_checkin', 'download_completed', 'webhook', 'startup'];
const ACTION_SAMPLE = JSON.stringify([
  { type: 'create_note', config: { title: '回顾今日输出', content: '记录工作流执行结果' } },
], null, 2);

const emptyForm = {
  name: '',
  description: '',
  trigger_type: 'schedule',
  trigger_config: '',
  actions: ACTION_SAMPLE,
};

function normalizeList(payload, preferredKeys = []) {
  for (const key of preferredKeys) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === 'object') {
    const firstArray = Object.values(payload).find(Array.isArray);
    if (Array.isArray(firstArray)) return firstArray;
  }
  return [];
}

const prettyTriggerLabel = (trigger) => {
  const map = {
    schedule: '定时',
    task_completed: '任务完成',
    task_created: '任务创建',
    habit_checkin: '习惯打卡',
    download_completed: '下载完成',
    webhook: 'Webhook',
    startup: '启动时',
  };
  return map[trigger] || trigger || '未配置';
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
      const data = await request(() => apiGet('/api/workflows/'));
      setWorkflows(normalizeList(data, ['workflows', 'items']));
    } catch {
      toast('获取工作流失败', 'error');
    }
  }, [request, toast]);

  useEffect(() => { fetchWorkflows(); }, [fetchWorkflows]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast('请输入工作流名称', 'warning'); return; }
    try {
      const triggerConfig = form.trigger_config.trim();
      const parsedActions = JSON.parse(form.actions);
      if (!Array.isArray(parsedActions) || parsedActions.length === 0) {
        throw new Error('动作必须是非空 JSON 数组');
      }
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        trigger: {
          type: form.trigger_type,
          config: triggerConfig ? { value: triggerConfig } : {},
          ...(form.trigger_type === 'schedule' && triggerConfig ? { cron: triggerConfig } : {}),
        },
        actions: parsedActions,
        enabled: true,
      };
      await request(() => apiPost('/api/workflows/', payload));
      toast('工作流已创建', 'success');
      setForm(emptyForm);
      setShowForm(false);
      fetchWorkflows();
    } catch (e) {
      toast(e.message || '创建工作流失败', 'error');
    }
  };

  const handleToggle = async (wf) => {
    try {
      const enabled = !wf.enabled;
      const resp = await request(() => fetch(`/api/workflows/${wf.id}/toggle?enabled=${enabled}`, {
        method: 'POST',
      }).then(async r => {
        const data = await r.json();
        if (!r.ok || data?.status === 'error') {
          throw new Error(data?.message || '切换状态失败');
        }
        return data;
      }));
      if (resp.status !== 'success') throw new Error(resp.message || '切换状态失败');
      toast(wf.enabled ? '已禁用' : '已启用', 'success');
      fetchWorkflows();
    } catch (e) {
      toast(e.message || '切换状态失败', 'error');
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
      await request(() => fetch(`/api/workflows/${id}`, {
        method: 'DELETE',
      }).then(async r => {
        const data = await r.json();
        if (!r.ok || data?.status === 'error') {
          throw new Error(data?.message || '删除失败');
        }
        return data;
      }));
      toast('已删除', 'success');
      fetchWorkflows();
    } catch (e) {
      toast(e.message || '删除失败', 'error');
    }
  };

  const loadHistory = async (id) => {
    setHistoryLoading(prev => ({ ...prev, [id]: true }));
    try {
      const data = await apiGet(`/api/workflows/${id}/executions`);
      setHistoryMap(prev => ({ ...prev, [id]: normalizeList(data, ['executions', 'items']) }));
    } catch (e) {
      toast(e.message || '获取历史记录失败', 'error');
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
  const enabledCount = workflows.filter(wf => wf.enabled).length;

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 05 / Assembly Manual</div>
          <h1 className="atlas-chapter-title">工作流页应该像装配步骤册，先看触发和动作链，再决定是否启用或试运行。</h1>
          <div className="atlas-chapter-copy">
            每条工作流本质上都是一张自动化装配卡。你需要一眼看到它由什么触发、会执行什么动作、最近运行得怎样，而不是先钻进配置细节。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">装配顺序</div>
          <div className="atlas-chapter-note-copy">先设触发，再配动作，再试运行，最后看历史记录是否稳定。</div>
        </div>
      </section>

      <section className="mission-masthead atlas-leaf">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">AUTOMATION BOARD</span>
            <h1 className="mission-title">工作流页该像自动化作战板，不该像一串配置清单。</h1>
            <div className="mission-copy">
              这里的核心是触发条件、动作链和执行历史。每个工作流应该像一张自动化战术卡，状态、触发方式和执行入口都在同一视野里。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{workflows.length} 条工作流</span>
              <span className="badge badge-completed">{enabledCount} 条已启用</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">设计准则</div>
            <div className="mission-sidecard-copy">
              优先让“触发什么、会做什么、最近跑得怎样”一眼可见，避免把关键信息藏在表格列和折叠块后面。
            </div>
          </div>
        </div>
      </section>

      <div className="atlas-toolbar">
        <span className="atlas-toolbar-label">已启用 {enabledCount} / {workflows.length}</span>
        <div className="board-toolbar-spacer" />
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '+ 新建工作流'}
        </button>
      </div>

      {showForm && (
        <section className="board-lane atlas-ledger-lane">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">ASSEMBLE</div>
              <h3 className="board-lane-title">组装新工作流</h3>
              <div className="board-lane-copy">保持当前后端契约不变，只把输入区整理成更清晰的配置台。</div>
            </div>
          </div>
          <form onSubmit={handleSubmit} className="command-form">
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
              <textarea value={form.actions} onChange={e => updateField('actions', e.target.value)} rows={5} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
              <button type="button" className="btn btn-ghost" onClick={() => { setShowForm(false); setForm(emptyForm); }}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>创建</button>
            </div>
          </form>
        </section>
      )}

      {loading && workflows.length === 0 ? (
        <div className="board-card-grid">
          {[1, 2, 3].map(i => (
            <div className="dossier-card" key={i}>
              <div className="skeleton skeleton-text" style={{ width: '60%' }} />
              <div className="skeleton skeleton-text" style={{ width: '80%', height: 70 }} />
            </div>
          ))}
        </div>
      ) : workflows.length === 0 ? (
        <section className="board-lane">
          <div className="empty-state">
            <div className="empty-state-icon">🔄</div>
            <div className="empty-state-text">暂无工作流</div>
            <div className="empty-state-hint">点击上方按钮创建你的第一个工作流</div>
          </div>
        </section>
      ) : (
        <section className="board-lane atlas-paper-stack">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">TACTICS</div>
              <h3 className="board-lane-title">自动化战术卡</h3>
              <div className="board-lane-copy">每张卡都直接给出启停、执行、删除和历史查看入口。</div>
            </div>
          </div>

          <div className="board-card-grid">
            {workflows.map(wf => (
              <div className="dossier-card" key={wf.id} style={{ transform: `rotate(${wf.enabled ? '-0.7deg' : '0.75deg'})` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="section-kicker">WORKFLOW</div>
                    <h3 className="dossier-title">{escapeHtml(wf.name)}</h3>
                  </div>
                  <span className={`badge ${wf.enabled ? 'badge-completed' : 'badge-pending'}`}>
                    {wf.enabled ? '启用' : '禁用'}
                  </span>
                </div>

                {wf.description && (
                  <div className="dossier-copy">{escapeHtml(wf.description)}</div>
                )}

                <div className="dossier-meta-grid">
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">触发</div>
                    <div>{prettyTriggerLabel(wf.trigger?.type)}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">配置</div>
                    <div>{wf.trigger?.cron ? escapeHtml(wf.trigger.cron) : '无'}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">动作数</div>
                    <div>{Array.isArray(wf.actions) ? wf.actions.length : '-'}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">上次运行</div>
                    <div>{wf.last_execution ? formatTimeShort(wf.last_execution) : '未运行'}</div>
                  </div>
                </div>

                <div className="dossier-actions">
                  <button className="btn btn-sm btn-ghost" onClick={() => handleToggle(wf)}>
                    {wf.enabled ? '禁用' : '启用'}
                  </button>
                  <button className="btn btn-sm btn-primary" onClick={() => handleExecute(wf)} disabled={!wf.enabled || loading}>
                    执行
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => toggleHistory(wf.id)}>
                    {expandedId === wf.id ? '收起历史' : '看历史'}
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(wf.id)}>删除</button>
                </div>

                {expandedId === wf.id && (
                  <div className="signal-list">
                    {historyLoading[wf.id] ? (
                      <>
                        <div className="skeleton skeleton-text" style={{ width: '80%' }} />
                        <div className="skeleton skeleton-text" style={{ width: '60%' }} />
                      </>
                    ) : (historyMap[wf.id] || []).length === 0 ? (
                      <div className="signal-row">
                        <div className="signal-row-copy">暂无执行记录</div>
                      </div>
                    ) : (
                      historyMap[wf.id].map((h, i) => (
                        <div className="signal-row" key={i}>
                          <div>
                            <div className="signal-row-title">
                              <span className={`badge badge-${h.status === 'success' ? 'completed' : h.status === 'failed' ? 'error' : 'pending'}`}>
                                {h.status === 'success' ? '成功' : h.status === 'failed' ? '失败' : '运行中'}
                              </span>
                            </div>
                            <div className="signal-row-copy">{escapeHtml(h.message || '-')}</div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div className="signal-row-meta">{formatTimeShort(h.started_at || h.created_at)}</div>
                            <div className="signal-row-meta">{h.duration ? `${h.duration}s` : '-'}</div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
