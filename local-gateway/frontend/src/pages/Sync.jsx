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
    } catch {}
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const data = await apiGet('/api/sync/devices');
      setDevices(data.devices || data || []);
    } catch {}
  }, []);

  const fetchOfflineQueue = useCallback(async () => {
    try {
      const data = await apiGet('/api/sync/offline/queue');
      setOfflineQueue(data.queue || data.items || data || []);
    } catch {}
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
    <div className="page-shell">
      <section className="mission-masthead">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">SIGNAL HUB</span>
            <h1 className="mission-title">同步页该像信号台，不该像一张设备登记表。</h1>
            <div className="mission-copy">
              先看最后一次同步、在线设备和离线积压，再决定推送、拉取还是完整同步。动作区应该像控制台，设备和队列则像回报面板。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{connectedCount} 台在线</span>
              <span className="badge badge-warning">{queueCount} 条待同步</span>
              <span className="badge badge-completed">{lastSync ? formatTimeShort(lastSync) : '尚未同步'}</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">同步策略</div>
            <div className="mission-sidecard-copy">
              小改动用推送或拉取，冲突感强的时候用完整同步，离线积压只在队列非空时处理。
            </div>
          </div>
        </div>
      </section>

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">上次同步</div>
          <div className="board-summary-value" style={{ fontSize: '1rem' }}>{lastSync ? formatTimeShort(lastSync) : '-'}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">在线设备</div>
          <div className="board-summary-value">{connectedCount}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">离线队列</div>
          <div className="board-summary-value">{queueCount}</div>
        </div>
      </div>

      <section className="board-lane">
        <div className="board-lane-header">
          <div>
            <div className="section-kicker">COMMANDS</div>
            <h3 className="board-lane-title">同步控制台</h3>
            <div className="board-lane-copy">所有动作都还是原来的后端接口，只是把入口改成清晰的战术按钮。</div>
          </div>
        </div>

        <div className="board-card-grid">
          {[
            { key: 'push', label: '推送', copy: '把本地最新改动送到外部设备。', style: 'btn-primary' },
            { key: 'pull', label: '拉取', copy: '取回远端最新变更到当前设备。', style: 'btn-primary' },
            { key: 'full', label: '完整同步', copy: '重新对齐两端状态，适合长时间未同步后使用。', style: 'btn-success' },
            { key: 'offline', label: '离线同步', copy: '处理积压的离线记录，仅在队列非空时启用。', style: 'btn-ghost', disabled: queueCount === 0 },
          ].map(item => (
            <div className="dossier-card" key={item.key}>
              <div className="section-kicker">ACTION</div>
              <h3 className="dossier-title">{item.label}</h3>
              <div className="dossier-copy">{item.copy}</div>
              <div className="dossier-actions">
                <button
                  className={`btn ${item.style}`}
                  onClick={() => handleSync(item.key)}
                  disabled={!!syncing || item.disabled}
                >
                  {syncing === item.key ? '执行中...' : item.label}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="board-lane">
        <div className="board-lane-header">
          <div>
            <div className="section-kicker">DEVICES</div>
            <h3 className="board-lane-title">设备信号板</h3>
            <div className="board-lane-copy">每台设备单独显示状态和最近活跃时间，不再挤进表格行里。</div>
          </div>
        </div>
        {devices.length === 0 ? (
          <div className="empty-state" style={{ padding: 'var(--space-lg)' }}>
            <div className="empty-state-icon">📱</div>
            <div className="empty-state-text">暂无连接设备</div>
          </div>
        ) : (
          <div className="signal-list">
            {devices.map((d, i) => (
              <div className="signal-row" key={d.id || i}>
                <div>
                  <div className="signal-row-title">{d.name || d.device_name || `设备 ${i + 1}`}</div>
                  <div className="signal-row-copy">{d.platform || d.os || '-'}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ marginBottom: 6 }}>
                    <span className={`badge ${d.connected || d.online ? 'badge-completed' : 'badge-pending'}`}>
                      {d.connected || d.online ? '在线' : '离线'}
                    </span>
                  </div>
                  <div className="signal-row-meta">{formatTimeShort(d.last_active || d.lastActive || d.last_seen)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="board-lane">
        <div className="board-lane-header">
          <div>
            <div className="section-kicker">QUEUE</div>
            <h3 className="board-lane-title">离线回传队列</h3>
            <div className="board-lane-copy">队列项像待发回报，不再压成三列表格。</div>
          </div>
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
          <div className="signal-list">
            {offlineQueue.map((item, i) => (
              <div className="signal-row" key={item.id || i}>
                <div>
                  <div className="signal-row-title">
                    <span className="badge badge-pending">{item.action || item.type || 'pending'}</span>
                  </div>
                  <div className="signal-row-copy">{item.target || item.key || '-'}</div>
                </div>
                <div className="signal-row-meta">{formatTimeShort(item.created_at || item.timestamp)}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
