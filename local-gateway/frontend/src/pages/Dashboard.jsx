import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort, operationIcon } from '../utils/format';

const POLL_INTERVAL = 15000; // 15s

function _overdueDays(dueTime) {
  const due = new Date(dueTime);
  const now = new Date();
  return Math.max(0, Math.floor((now - due) / (1000 * 60 * 60 * 24)));
}

export default function Dashboard() {
  const { loading, error, request } = useApi();
  const toast = useToast();
  const [data, setData] = useState(null);
  const pollRef = useRef(null);
  const [streak, setStreak] = useState({ current_streak: 0, longest_streak: 0, weekly_rate: 0, today_total: 0, today_completed: 0 });
  const [overdueTasks, setOverdueTasks] = useState([]);

  const fetchDashboard = useCallback(() => {
    request(async () => {
      const res = await apiGet('/api/dashboard');
      if (res.status === 'error') throw new Error(res.message || '加载失败');
      setData(res);
      return res;
    }).catch(e => toast(e.message, 'error'));
  }, [request, toast]);

  const fetchStreak = useCallback(async () => {
    try {
      const res = await apiGet('/api/streak');
      if (res.status === 'success') {
        setStreak(res);
      }
    } catch { /* silent */ }
  }, []);

  const fetchOverdueTasks = useCallback(async () => {
    try {
      const res = await apiPost('/api/task', { action: 'get_pending_tasks' });
      if (res.status === 'success' && res.tasks) {
        setOverdueTasks(res.tasks.filter(t => t.overdue));
      }
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchDashboard();
    fetchStreak();
    fetchOverdueTasks();
    pollRef.current = setInterval(fetchDashboard, POLL_INTERVAL);
    return () => clearInterval(pollRef.current);
  }, [fetchDashboard, fetchStreak, fetchOverdueTasks]);

  if (loading && !data) return <DashboardSkeleton />;
  if (error && !data) return <DashboardError error={error} onRetry={fetchDashboard} />;
  if (!data) return null;

  const { tasks = {}, downloads = {}, storage = {}, recent_logs = [], recent_downloads = [] } = data;

  const stats = [
    { icon: '📋', value: tasks.active ?? tasks.pending ?? 0, label: '进行中' },
    { icon: '✅', value: tasks.completed ?? 0, label: '已完成' },
    { icon: '📥', value: downloads.total ?? 0, label: '下载总数' },
    { icon: '💾', value: storage.total_size ?? '-', label: '已用空间' },
  ];

  return (
    <div>
      <div className="stats-grid">
        {stats.map((s, i) => (
          <div className="stat-card" key={i}>
            <span className="stat-icon">{s.icon}</span>
            <div>
              <div className="stat-value">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 'var(--space-md)' }}>
        <div className="card" style={{ marginBottom: 'var(--space-md)' }}>
          <h3 style={{ fontSize: '0.9rem', marginBottom: 'var(--space-sm)' }}>📋 今日进度</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
            <div style={{ flex: 1 }}>
              <div style={{
                height: 8, borderRadius: 4, background: 'var(--bg-tertiary)', overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%', borderRadius: 4,
                  background: streak.today_total > 0 && streak.today_completed === streak.today_total
                    ? 'var(--success)' : 'var(--accent)',
                  width: `${streak.today_total > 0 ? (streak.today_completed / streak.today_total * 100) : 0}%`,
                  transition: 'width 0.5s ease',
                }} />
              </div>
            </div>
            <span style={{ fontSize: '0.85rem', fontWeight: 500, whiteSpace: 'nowrap' }}>
              {streak.today_total > 0 && streak.today_completed === streak.today_total
                ? '今日任务全部完成！'
                : `已完成 ${streak.today_completed}/${streak.today_total} 项`}
            </span>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 'var(--space-md)', textAlign: 'center', padding: 'var(--space-lg)' }}>
          <div style={{ fontSize: '3rem', fontWeight: 700, color: 'var(--accent)' }}>
            🔥 {streak.current_streak}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
            {streak.current_streak > 0
              ? `已连续 ${streak.current_streak} 天完成所有任务`
              : '开始你的连续完成之旅'}
          </div>
          {streak.longest_streak > 0 && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
              最长纪录: {streak.longest_streak} 天
            </div>
          )}
        </div>

        {overdueTasks.length > 0 && (
          <div className="card" style={{
            marginBottom: 'var(--space-md)',
            borderLeft: '3px solid var(--error)',
            background: 'rgba(255,59,48,0.04)',
          }}>
            <h3 style={{ fontSize: '0.9rem', marginBottom: 'var(--space-sm)', color: 'var(--error)' }}>
              ⚠️ 逾期任务（{overdueTasks.length}项）
            </h3>
            {overdueTasks.slice(0, 5).map(t => (
              <div key={t.task_id} style={{
                fontSize: '0.85rem', padding: '4px 0',
                borderBottom: '1px solid var(--border)'
              }}>
                {t.task_name}
                <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginLeft: 8 }}>
                  逾期 {_overdueDays(t.due_time)} 天
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
        <div className="card">
          <div className="card-header">
            <h3>📥 最近下载</h3>
          </div>
          {recent_downloads.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📥</div>
              <div className="empty-state-text">暂无下载记录</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {recent_downloads.map((d, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-tertiary)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', overflow: 'hidden' }}>
                    <span>{d.category === 'paper' ? '📄' : d.category === 'video' ? '🎬' : d.category === 'code' ? '💻' : '📎'}</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={d.filename}>
                      {d.filename || d.url}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexShrink: 0 }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>{d.file_size || ''}</span>
                    <span className={`badge badge-${d.security_scan === 'passed' ? 'completed' : d.security_scan === 'failed' ? 'error' : 'pending'}`}>
                      {d.security_scan || '-'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h3>📋 最近操作</h3>
          </div>
          {recent_logs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <div className="empty-state-text">暂无操作日志</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {recent_logs.map((log, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-tertiary)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', overflow: 'hidden' }}>
                    <span>{operationIcon(log.operation)}</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {log.detail || log.operation}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', flexShrink: 0 }}>
                    {formatTimeShort(log.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div>
      <div className="stats-grid">
        {[1, 2, 3, 4].map(i => (
          <div className="stat-card" key={i}>
            <span className="skeleton" style={{ width: 36, height: 36, borderRadius: '50%', display: 'inline-block' }} />
            <div>
              <div className="skeleton skeleton-text" style={{ width: 60 }} />
              <div className="skeleton skeleton-text" style={{ width: 80 }} />
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
        {[1, 2].map(i => (
          <div className="card" key={i}>
            <div className="skeleton skeleton-text" style={{ width: 100, marginBottom: 'var(--space-md)' }} />
            {[1, 2, 3].map(j => (
              <div className="skeleton skeleton-text" key={j} style={{ width: '100%', height: 40, marginBottom: 'var(--space-sm)' }} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardError({ error, onRetry }) {
  return (
    <div className="empty-state" style={{ minHeight: 300 }}>
      <div className="empty-state-icon">⚠️</div>
      <div className="empty-state-text">加载仪表盘失败</div>
      <div className="empty-state-hint">{error}</div>
      <button className="btn btn-primary" onClick={onRetry}>重试</button>
    </div>
  );
}
