import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort } from '../utils/format';

export default function Sync() {
  const toast = useToast();
  const { request } = useApi();

  const [status, setStatus] = useState(null);
  const [devices, setDevices] = useState([]);
  const [offlineQueue, setOfflineQueue] = useState([]);
  const [syncing, setSyncing] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiGet('/api/sync/status');
      setStatus(data);
    } catch { /* silent */ }
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const data = await apiGet('/api/sync/devices');
      setDevices(data.devices || data || []);
    } catch { /* silent */ }
  }, []);

  const fetchOfflineQueue = useCallback(async () => {
    try {
      const data = await apiGet('/api/sync/offline/queue');
      setOfflineQueue(data.queue || data.items || data || []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchDevices();
    fetchOfflineQueue();
  }, [fetchStatus, fetchDevices, fetchOfflineQueue]);

  const handleSync = async (type) => {
    const endpoints = {
      push: '/api/sync/push',
      pull: '/api/sync/pull',
      full: '/api/sync/full',
      offline: '/api/sync/offline/sync',
    };
    setSyncing(type);
    try {
      await request(() => apiPost(endpoints[type], {}));
      toast(`${type === 'full' ? '完整' : type === 'offline' ? '离线' : type === 'push' ? '推送' : '拉取'}同步成功`, 'success');
      fetchStatus();
      if (type === 'offline') fetchOfflineQueue();
    } catch {
      toast('同步失败', 'error');
    } finally {
      setSyncing(null);
    }
  };

  const lastSync = status?.last_sync || status?.lastSync;
  const connectedCount = devices.filter(d => d.connected || d.online).length;
  const queueCount = offlineQueue.length;

  return (
    <div style={{ padding: 'var(--space-lg)', maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: 'var(--space-lg)' }}>同步</h2>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">🕐</div>
          <div>
            <div className="stat-value">{lastSync ? formatTimeShort(lastSync) : '-'}</div>
            <div className="stat-label">上次同步</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📱</div>
          <div>
            <div className="stat-value">{connectedCount}</div>
            <div className="stat-label">已连接设备</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📩</div>
          <div>
            <div className="stat-value">{queueCount}</div>
            <div className="stat-label">离线队列</div>
          </div>
        </div>
      </div>

      {/* Sync Actions */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="card-header">
          <h3>同步操作</h3>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => handleSync('push')} disabled={!!syncing}>
            {syncing === 'push' ? '同步中...' : '↑ 推送'}
          </button>
          <button className="btn btn-primary" onClick={() => handleSync('pull')} disabled={!!syncing}>
            {syncing === 'pull' ? '同步中...' : '↓ 拉取'}
          </button>
          <button className="btn btn-success" onClick={() => handleSync('full')} disabled={!!syncing}>
            {syncing === 'full' ? '同步中...' : '⟳ 完整同步'}
          </button>
          <button className="btn btn-ghost" onClick={() => handleSync('offline')} disabled={!!syncing || queueCount === 0}>
            {syncing === 'offline' ? '同步中...' : '📶 离线同步'}
          </button>
        </div>
      </div>

      {/* Device List */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="card-header">
          <h3>设备列表</h3>
        </div>
        {devices.length === 0 ? (
          <div className="empty-state" style={{ padding: 'var(--space-lg)' }}>
            <div className="empty-state-icon">📱</div>
            <div className="empty-state-text">暂无连接设备</div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>设备</th><th>平台</th><th>状态</th><th>最后活跃</th></tr>
            </thead>
            <tbody>
              {devices.map((d, i) => (
                <tr key={d.id || i}>
                  <td style={{ fontWeight: 500 }}>{d.name || d.device_name || `设备 ${i + 1}`}</td>
                  <td style={{ color: 'var(--text-tertiary)' }}>{d.platform || d.os || '-'}</td>
                  <td>
                    <span className={`badge ${d.connected || d.online ? 'badge-completed' : 'badge-pending'}`}>
                      {d.connected || d.online ? '在线' : '离线'}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                    {formatTimeShort(d.last_active || d.lastActive || d.last_seen)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Offline Queue */}
      <div className="card">
        <div className="card-header">
          <h3>离线队列</h3>
          {queueCount > 0 && (
            <button className="btn btn-sm btn-ghost" onClick={fetchOfflineQueue}>刷新</button>
          )}
        </div>
        {offlineQueue.length === 0 ? (
          <div className="empty-state" style={{ padding: 'var(--space-lg)' }}>
            <div className="empty-state-icon">✅</div>
            <div className="empty-state-text">队列为空</div>
            <div className="empty-state-hint">所有更改已同步</div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>操作</th><th>目标</th><th>时间</th></tr>
            </thead>
            <tbody>
              {offlineQueue.map((item, i) => (
                <tr key={item.id || i}>
                  <td>
                    <span className="badge badge-pending">{item.action || item.type || 'pending'}</span>
                  </td>
                  <td style={{ color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>{item.target || item.key || '-'}</td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                    {formatTimeShort(item.created_at || item.timestamp)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
