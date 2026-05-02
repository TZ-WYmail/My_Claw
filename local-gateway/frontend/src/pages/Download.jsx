import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort } from '../utils/format';

const CATEGORIES = ['通用', '文档', '媒体', '软件', '代码', '其他'];

export default function Download() {
  const toast = useToast();
  const { loading, request } = useApi();
  const pollRef = useRef(null);

  const [queue, setQueue] = useState([]);
  const [bandwidth, setBandwidth] = useState(null);
  const [bwEnabled, setBwEnabled] = useState(false);
  const [form, setForm] = useState({ url: '', filename: '', category: '通用' });
  const [showForm, setShowForm] = useState(false);

  const fetchQueue = useCallback(async () => {
    try {
      const data = await apiGet('/api/download/queue');
      setQueue(data.queue || data.items || data || []);
    } catch { /* silent poll */ }
  }, []);

  const fetchBandwidth = useCallback(async () => {
    try {
      const data = await apiGet('/api/download/bandwidth');
      setBandwidth(data);
      setBwEnabled(!!data.enabled);
    } catch { /* silent */ }
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
      setForm({ url: '', filename: '', category: '通用' });
      setShowForm(false);
      fetchQueue();
    } catch {
      toast('添加下载失败', 'error');
    }
  };

  const handleBandwidthToggle = async () => {
    try {
      await request(() => apiPost('/api/download/bandwidth', { enabled: !bwEnabled }));
      setBwEnabled(prev => !prev);
      toast(bwEnabled ? '带宽限制已关闭' : '带宽限制已开启', 'success');
    } catch {
      toast('切换带宽限制失败', 'error');
    }
  };

  const handleAction = async (id, action) => {
    const labels = { pause: '暂停', resume: '恢复', cancel: '取消' };
    if (action === 'cancel' && !window.confirm('确认取消此下载？')) return;
    try {
      await request(() => apiPost(`/api/download/${action}/${id}`, {}));
      toast(`已${labels[action]}`, 'success');
      fetchQueue();
    } catch {
      toast(`${labels[action]}失败`, 'error');
    }
  };

  const statusLabel = (s) => {
    const map = { downloading: '下载中', paused: '已暂停', completed: '已完成', failed: '失败', queued: '排队中', cancelled: '已取消' };
    return map[s] || s;
  };

  const statusBadge = (s) => {
    if (s === 'completed') return 'badge-completed';
    if (s === 'failed' || s === 'cancelled') return 'badge-error';
    if (s === 'downloading') return 'badge-pending';
    return 'badge-pending';
  };

  const activeCount = queue.filter(d => d.status === 'downloading').length;
  const completedCount = queue.filter(d => d.status === 'completed').length;

  return (
    <div style={{ padding: 'var(--space-lg)', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-lg)' }}>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>下载管理</h2>
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <button className="btn btn-ghost" onClick={handleBandwidthToggle}>
            {bwEnabled ? '🚫 限速中' : '🚀 不限速'}
          </button>
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? '取消' : '+ 新下载'}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">⬇️</div>
          <div>
            <div className="stat-value">{activeCount}</div>
            <div className="stat-label">下载中</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">✅</div>
          <div>
            <div className="stat-value">{completedCount}</div>
            <div className="stat-label">已完成</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📦</div>
          <div>
            <div className="stat-value">{queue.length}</div>
            <div className="stat-label">总任务</div>
          </div>
        </div>
      </div>

      {/* Bandwidth Info */}
      {bwEnabled && bandwidth && (
        <div className="card" style={{ marginBottom: 'var(--space-md)', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          带宽限制: {bandwidth.limit || bandwidth.max_speed || '-'} KB/s
        </div>
      )}

      {/* New Download Form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
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
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>开始下载</button>
            </div>
          </form>
        </div>
      )}

      {/* Queue */}
      {loading && queue.length === 0 ? (
        <div className="card">
          <div className="skeleton skeleton-text" style={{ width: '70%' }} />
          <div className="skeleton skeleton-text" style={{ width: '50%' }} />
          <div className="skeleton skeleton-text" style={{ width: '60%' }} />
        </div>
      ) : queue.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📥</div>
          <div className="empty-state-text">下载队列为空</div>
          <div className="empty-state-hint">点击"新下载"添加下载任务</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          {queue.map(item => (
            <div key={item.id || item.job_id} className="card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.filename || item.url || `下载 #${item.id}`}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {item.category && <span>{item.category} · </span>}
                    {item.size && <span>{item.size} · </span>}
                    {formatTimeShort(item.created_at || item.started_at)}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', flexShrink: 0 }}>
                  <span className={`badge ${statusBadge(item.status)}`}>{statusLabel(item.status)}</span>
                  {item.status === 'downloading' && (
                    <button className="btn btn-sm btn-ghost" onClick={() => handleAction(item.id, 'pause')}>⏸</button>
                  )}
                  {item.status === 'paused' && (
                    <button className="btn btn-sm btn-ghost" onClick={() => handleAction(item.id, 'resume')}>▶</button>
                  )}
                  {(item.status === 'downloading' || item.status === 'paused' || item.status === 'queued') && (
                    <button className="btn btn-sm btn-danger" onClick={() => handleAction(item.id, 'cancel')}>✕</button>
                  )}
                </div>
              </div>

              {/* Progress bar */}
              {(item.status === 'downloading' || item.status === 'paused') && (
                <div style={{ marginTop: 'var(--space-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: 4 }}>
                    <span>{item.downloaded || '0 B'} / {item.total || '?'}</span>
                    <span>{item.progress != null ? `${Math.round(item.progress)}%` : ''} {item.speed ? `· ${item.speed}` : ''}</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
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

              {/* Error message */}
              {item.status === 'failed' && item.error && (
                <div style={{ marginTop: 'var(--space-sm)', fontSize: '0.8rem', color: 'var(--error)' }}>
                  {item.error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
