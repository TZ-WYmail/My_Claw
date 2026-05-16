import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort } from '../utils/format';

const CATEGORIES = [
  { value: 'misc', label: '通用' },
  { value: 'paper', label: '文档' },
  { value: 'video', label: '媒体' },
  { value: 'code', label: '代码' },
];

export default function Download() {
  const toast = useToast();
  const { loading, request } = useApi();
  const pollRef = useRef(null);

  const [queue, setQueue] = useState([]);
  const [bandwidth, setBandwidth] = useState(null);
  const [bwEnabled, setBwEnabled] = useState(false);
  const [form, setForm] = useState({ url: '', filename: '', category: 'misc' });
  const [showForm, setShowForm] = useState(false);

  const fetchQueue = useCallback(async () => {
    try {
      const data = await apiGet('/api/download/queue');
      setQueue(data.queue || data.items || data || []);
    } catch {}
  }, []);

  const fetchBandwidth = useCallback(async () => {
    try {
      const data = await apiGet('/api/download/bandwidth');
      setBandwidth(data);
      setBwEnabled(Number(data.limit_kb_s || 0) > 0);
    } catch {}
  }, []);

  useEffect(() => {
    fetchQueue();
    fetchBandwidth();
    pollRef.current = setInterval(fetchQueue, 3000);
    return () => clearInterval(pollRef.current);
  }, [fetchQueue, fetchBandwidth]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.url.trim()) { toast('请输入下载链接', 'warning'); return; }
    try {
      await request(() => apiPost('/api/download', {
        url: form.url.trim(),
        filename: form.filename.trim() || undefined,
        category: form.category,
      }));
      toast('已添加到下载队列', 'success');
      setForm({ url: '', filename: '', category: 'misc' });
      setShowForm(false);
      fetchQueue();
    } catch (e) {
      toast(e.message || '添加下载失败', 'error');
    }
  };

  const handleBandwidthToggle = async () => {
    try {
      const nextLimit = bwEnabled ? 0 : 512;
      const resp = await request(() => fetch(`/api/download/bandwidth?kb_per_second=${nextLimit}`, {
        method: 'POST',
      }).then(async r => {
        const data = await r.json();
        if (!r.ok || data?.status === 'error') {
          throw new Error(data?.message || '切换带宽限制失败');
        }
        return data;
      }));
      setBandwidth(resp);
      setBwEnabled(nextLimit > 0);
      toast(bwEnabled ? '带宽限制已关闭' : '带宽限制已开启', 'success');
    } catch (e) {
      toast(e.message || '切换带宽限制失败', 'error');
    }
  };

  const handleAction = async (id, action) => {
    const labels = { pause: '暂停', resume: '恢复', cancel: '取消' };
    if (action === 'cancel' && !window.confirm('确认取消此下载？')) return;
    try {
      await request(() => apiPost(`/api/download/${action}/${id}`, {}));
      toast(`已${labels[action]}`, 'success');
      fetchQueue();
    } catch (e) {
      toast(e.message || `${labels[action]}失败`, 'error');
    }
  };

  const statusLabel = (s) => {
    const map = { downloading: '下载中', paused: '已暂停', completed: '已完成', failed: '失败', queued: '排队中', cancelled: '已取消' };
    return map[s] || s;
  };

  const statusBadge = (s) => {
    if (s === 'completed') return 'badge-completed';
    if (s === 'failed' || s === 'cancelled') return 'badge-error';
    return 'badge-pending';
  };

  const activeCount = queue.filter(d => d.status === 'downloading').length;
  const completedCount = queue.filter(d => d.status === 'completed').length;

  return (
    <div className="page-shell">
      <section className="mission-masthead">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">SUPPLY ROUTE</span>
            <h1 className="mission-title">下载页该像补给航线，不该像一串普通任务列表。</h1>
            <div className="mission-copy">
              新链接是新的补给单，限速是线路策略，下载中的条目则像正在运输的货箱。核心不是列字段，而是快速看清运输状态并马上处理。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{activeCount} 条运输中</span>
              <span className="badge badge-completed">{completedCount} 条已到站</span>
              <span className="badge badge-warning">{queue.length} 条总任务</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">带宽策略</div>
            <div className="mission-sidecard-copy">
              长时间后台下载时开限速，短时间抢资源时关限速。按钮逻辑不变，只把信息组织得更直观。
            </div>
          </div>
        </div>
      </section>

      <div className="board-toolbar">
        <button className="btn btn-ghost" onClick={handleBandwidthToggle}>
          {bwEnabled ? '限速中' : '不限速'}
        </button>
        <div className="board-toolbar-spacer" />
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '+ 新下载'}
        </button>
      </div>

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">运输中</div>
          <div className="board-summary-value">{activeCount}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">已到站</div>
          <div className="board-summary-value">{completedCount}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">限速状态</div>
          <div className="board-summary-value" style={{ fontSize: '1rem' }}>
            {bwEnabled ? `${bandwidth?.limit_kb_s || 0} KB/s` : '关闭'}
          </div>
        </div>
      </div>

      {showForm && (
        <section className="board-lane">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">NEW ROUTE</div>
              <h3 className="board-lane-title">添加补给单</h3>
              <div className="board-lane-copy">链接、文件名和分类保留原有后端字段，但版面改成更像调度面板。</div>
            </div>
          </div>
          <form onSubmit={handleSubmit} className="command-form">
            <div className="form-group">
              <label>下载链接</label>
              <input value={form.url} onChange={e => setForm(p => ({ ...p, url: e.target.value }))} placeholder="https://..." />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
              <div className="form-group">
                <label>文件名 (可选)</label>
                <input value={form.filename} onChange={e => setForm(p => ({ ...p, filename: e.target.value }))} placeholder="自动检测" />
              </div>
              <div className="form-group">
                <label>分类</label>
                <select value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))}>
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>开始下载</button>
            </div>
          </form>
        </section>
      )}

      {loading && queue.length === 0 ? (
        <div className="board-card-grid">
          {[1, 2, 3].map(i => (
            <div className="dossier-card" key={i}>
              <div className="skeleton skeleton-text" style={{ width: '70%' }} />
              <div className="skeleton skeleton-text" style={{ width: '50%' }} />
            </div>
          ))}
        </div>
      ) : queue.length === 0 ? (
        <section className="board-lane">
          <div className="empty-state">
            <div className="empty-state-icon">📥</div>
            <div className="empty-state-text">下载队列为空</div>
            <div className="empty-state-hint">点击“新下载”添加下载任务</div>
          </div>
        </section>
      ) : (
        <section className="board-lane">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">CARGO</div>
              <h3 className="board-lane-title">运输货箱</h3>
              <div className="board-lane-copy">每个下载任务都用一张货箱卡展示状态、进度和操作，而不是挤在列表行里。</div>
            </div>
          </div>

          <div className="board-card-grid">
            {queue.map(item => (
              <div className="dossier-card" key={item.job_id} style={{ transform: `rotate(${item.status === 'downloading' ? '-0.7deg' : '0.7deg'})` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="section-kicker">DOWNLOAD</div>
                    <h3 className="dossier-title">{item.filename || item.url || `下载 #${item.job_id}`}</h3>
                  </div>
                  <span className={`badge ${statusBadge(item.status)}`}>{statusLabel(item.status)}</span>
                </div>

                <div className="dossier-meta-grid">
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">分类</div>
                    <div>{item.category || '未分类'}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">创建时间</div>
                    <div>{formatTimeShort(item.created_at || item.started_at)}</div>
                  </div>
                </div>

                {(item.status === 'downloading' || item.status === 'paused') && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: 6 }}>
                      <span>{item.progress != null ? `${Math.round(item.progress)}%` : ''}</span>
                      <span>{item.speed_kb_s ? `${item.speed_kb_s} KB/s` : ''}</span>
                    </div>
                    <div style={{ height: 8, background: 'rgba(67, 42, 28, 0.08)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${item.progress != null ? Math.min(item.progress, 100) : 0}%`,
                        background: item.status === 'paused' ? 'var(--warning)' : 'var(--accent)',
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 0.3s var(--ease-apple)',
                      }} />
                    </div>
                  </div>
                )}

                {item.status === 'failed' && item.error && (
                  <div className="dossier-copy" style={{ color: 'var(--error)' }}>{item.error}</div>
                )}

                <div className="dossier-actions">
                  {item.status === 'downloading' && (
                    <button className="btn btn-sm btn-ghost" onClick={() => handleAction(item.job_id, 'pause')}>暂停</button>
                  )}
                  {item.status === 'paused' && (
                    <button className="btn btn-sm btn-ghost" onClick={() => handleAction(item.job_id, 'resume')}>恢复</button>
                  )}
                  {(item.status === 'downloading' || item.status === 'paused' || item.status === 'queued') && (
                    <button className="btn btn-sm btn-danger" onClick={() => handleAction(item.job_id, 'cancel')}>取消</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
