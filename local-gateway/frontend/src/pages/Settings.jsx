import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { useTheme } from '../contexts/ThemeContext';
import { useApp } from '../contexts/AppContext';

const KEYBOARD_SHORTCUTS = [
  { keys: 'Cmd/Ctrl + B', desc: '切换侧边栏' },
  { keys: 'Cmd/Ctrl + K', desc: '全局搜索' },
  { keys: 'Cmd/Ctrl + J', desc: 'AI 聊天' },
  { keys: 'Cmd/Ctrl + N', desc: '新建任务' },
  { keys: 'Cmd/Ctrl + Shift + N', desc: '新建笔记' },
  { keys: 'Cmd/Ctrl + 1-5', desc: '快速导航' },
];

export default function Settings() {
  const toast = useToast();
  const { loading, request } = useApi();
  const { theme, toggleTheme } = useTheme();
  const { connected, version } = useApp();

  const [config, setConfig] = useState({
    model: '',
    temperature: 0.7,
    max_tokens: 2048,
    api_base: '',
    api_key: '',
  });
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [configLoaded, setConfigLoaded] = useState(false);

  // Notification config state
  const [notifConfig, setNotifConfig] = useState({
    smtp_host: '',
    smtp_port: 465,
    smtp_user: '',
    smtp_password: '',
    notify_email: '',
    reminder_minutes_before: 15,
    reminder_due_minutes: 30,
  });
  const [notifLoaded, setNotifLoaded] = useState(false);
  const [notifTesting, setNotifTesting] = useState(false);
  const [notifTestResult, setNotifTestResult] = useState(null);
  const [notifExpanded, setNotifExpanded] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await apiGet('/api/chat/config');
      const cfg = res.config || res;
      setConfig({
        model: cfg.model || '',
        temperature: cfg.temperature ?? 0.7,
        max_tokens: cfg.max_tokens ?? 2048,
        api_base: cfg.api_base || '',
        api_key: cfg.api_key_masked || cfg.api_key || '',
      });
      setConfigLoaded(true);
    } catch {
      toast('获取配置失败', 'error');
    }
  }, [toast]);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const fetchNotifConfig = useCallback(async () => {
    try {
      const res = await apiGet('/api/notification/config');
      const cfg = res.config || {};
      setNotifConfig({
        smtp_host: cfg.smtp_host || '',
        smtp_port: cfg.smtp_port ?? 465,
        smtp_user: cfg.smtp_user || '',
        smtp_password: '',
        notify_email: cfg.notify_email || '',
        reminder_minutes_before: cfg.reminder_minutes_before ?? 15,
        reminder_due_minutes: cfg.reminder_due_minutes ?? 30,
      });
      setNotifLoaded(true);
    } catch {
      toast('获取通知配置失败', 'error');
    }
  }, [toast]);

  useEffect(() => { fetchNotifConfig(); }, [fetchNotifConfig]);

  const handleNotifSave = async () => {
    try {
      await request(() => apiPost('/api/notification/config', {
        smtp_host: notifConfig.smtp_host,
        smtp_port: parseInt(notifConfig.smtp_port, 10),
        smtp_user: notifConfig.smtp_user,
        smtp_password: notifConfig.smtp_password || undefined,
        notify_email: notifConfig.notify_email,
        reminder_minutes_before: parseInt(notifConfig.reminder_minutes_before, 10),
        reminder_due_minutes: parseInt(notifConfig.reminder_due_minutes, 10),
      }));
      toast('通知配置已保存', 'success');
      fetchNotifConfig();
    } catch {
      toast('保存通知配置失败', 'error');
    }
  };

  const handleNotifTest = async () => {
    setNotifTesting(true);
    setNotifTestResult(null);
    try {
      const data = await apiPost('/api/notification/test', {});
      setNotifTestResult(data);
      if (data.status === 'success') {
        toast('测试邮件发送成功', 'success');
      } else {
        toast('测试邮件发送失败', 'error');
      }
    } catch {
      setNotifTestResult({ status: 'error', message: '请求失败' });
      toast('测试邮件发送失败', 'error');
    } finally {
      setNotifTesting(false);
    }
  };

  const updateNotifField = (field, value) => setNotifConfig(prev => ({ ...prev, [field]: value }));

  const handleSave = async () => {
    try {
      await request(() => apiPost('/api/chat/config', {
        model: config.model,
        temperature: parseFloat(config.temperature),
        max_tokens: parseInt(config.max_tokens, 10),
        api_base: config.api_base,
        ...(config.api_key ? { api_key: config.api_key } : {}),
      }));
      toast('配置已保存', 'success');
    } catch {
      toast('保存配置失败', 'error');
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const data = await apiPost('/api/chat/test', {});
      setTestResult(data);
      if (data.success || data.status === 'ok') {
        toast('连接测试成功', 'success');
      } else {
        toast('连接测试失败', 'error');
      }
    } catch {
      setTestResult({ success: false, error: '请求失败' });
      toast('连接测试失败', 'error');
    } finally {
      setTesting(false);
    }
  };

  const updateField = (field, value) => setConfig(prev => ({ ...prev, [field]: value }));

  return (
    <div style={{ padding: 'var(--space-lg)', maxWidth: 720, margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: 'var(--space-lg)' }}>设置</h2>

      {/* AI Config */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="card-header">
          <h3>AI 配置</h3>
          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <button className="btn btn-sm btn-ghost" onClick={handleTest} disabled={testing}>
              {testing ? '测试中...' : '测试连接'}
            </button>
            <button className="btn btn-sm btn-primary" onClick={handleSave} disabled={loading}>
              保存
            </button>
          </div>
        </div>

        {testResult && (
          <div style={{
            padding: 'var(--space-sm) var(--space-md)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: 'var(--space-md)',
            fontSize: '0.85rem',
            background: (testResult.success || testResult.status === 'ok') ? 'rgba(48,209,88,0.08)' : 'rgba(255,69,58,0.08)',
            color: (testResult.success || testResult.status === 'ok') ? 'var(--success)' : 'var(--error)',
            border: `1px solid ${(testResult.success || testResult.status === 'ok') ? 'var(--success)' : 'var(--error)'}`,
          }}>
            {(testResult.success || testResult.status === 'ok')
              ? `连接成功 — 模型: ${testResult.model || config.model || '-'}`
              : `连接失败 — ${testResult.error || testResult.message || '未知错误'}`}
          </div>
        )}

        {configLoaded ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            <div className="form-group">
              <label>模型名称</label>
              <input
                value={config.model}
                onChange={e => updateField('model', e.target.value)}
                placeholder="如: glm-4-flash"
              />
            </div>
            <div className="form-group">
              <label>API 地址</label>
              <input
                value={config.api_base}
                onChange={e => updateField('api_base', e.target.value)}
                placeholder="https://open.bigmodel.cn/api/paas/v4"
              />
            </div>
            <div className="form-group">
              <label>API Key</label>
              <input
                type="password"
                value={config.api_key}
                onChange={e => updateField('api_key', e.target.value)}
                placeholder="sk-..."
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
              <div className="form-group">
                <label>Temperature ({config.temperature})</label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={config.temperature}
                  onChange={e => updateField('temperature', parseFloat(e.target.value))}
                  style={{ padding: 0 }}
                />
              </div>
              <div className="form-group">
                <label>最大 Tokens</label>
                <input
                  type="number"
                  min={256}
                  max={32768}
                  value={config.max_tokens}
                  onChange={e => updateField('max_tokens', e.target.value)}
                />
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="skeleton skeleton-text" style={{ width: '60%' }} />
            <div className="skeleton skeleton-text" style={{ width: '80%' }} />
            <div className="skeleton skeleton-text" style={{ width: '50%' }} />
          </>
        )}
      </div>

      {/* Notification Config */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div
          className="card-header"
          style={{ cursor: 'pointer', userSelect: 'none' }}
          onClick={() => setNotifExpanded(prev => !prev)}
        >
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <span style={{ fontSize: '1.1rem' }}>&#9881;</span>
            通知配置
            <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 400 }}>
              {notifExpanded ? '▲' : '▼'}
            </span>
          </h3>
          {notifExpanded && (
            <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
              <button
                className="btn btn-sm btn-ghost"
                onClick={e => { e.stopPropagation(); handleNotifTest(); }}
                disabled={notifTesting}
              >
                {notifTesting ? '发送中...' : '测试邮件'}
              </button>
              <button
                className="btn btn-sm btn-primary"
                onClick={e => { e.stopPropagation(); handleNotifSave(); }}
                disabled={loading}
              >
                保存配置
              </button>
            </div>
          )}
        </div>

        {notifExpanded && (
          <>
            {notifTestResult && (
              <div style={{
                padding: 'var(--space-sm) var(--space-md)',
                borderRadius: 'var(--radius-sm)',
                marginBottom: 'var(--space-md)',
                fontSize: '0.85rem',
                background: notifTestResult.status === 'success' ? 'rgba(48,209,88,0.08)' : 'rgba(255,69,58,0.08)',
                color: notifTestResult.status === 'success' ? 'var(--success)' : 'var(--error)',
                border: `1px solid ${notifTestResult.status === 'success' ? 'var(--success)' : 'var(--error)'}`,
              }}>
                {notifTestResult.status === 'success'
                  ? '测试邮件发送成功，请检查收件箱'
                  : `发送失败 — ${notifTestResult.message || '未知错误'}`}
              </div>
            )}
            {notifLoaded ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                <div className="form-group">
                  <label>SMTP 服务器</label>
                  <input
                    value={notifConfig.smtp_host}
                    onChange={e => updateNotifField('smtp_host', e.target.value)}
                    placeholder="如: smtp.qq.com"
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
                  <div className="form-group">
                    <label>端口</label>
                    <input
                      type="number"
                      min={1}
                      max={65535}
                      value={notifConfig.smtp_port}
                      onChange={e => updateNotifField('smtp_port', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>发件邮箱</label>
                    <input
                      value={notifConfig.smtp_user}
                      onChange={e => updateNotifField('smtp_user', e.target.value)}
                      placeholder="sender@example.com"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>授权码</label>
                  <input
                    type="password"
                    value={notifConfig.smtp_password}
                    onChange={e => updateNotifField('smtp_password', e.target.value)}
                    placeholder="SMTP 授权码（已配置则留空）"
                  />
                </div>
                <div className="form-group">
                  <label>收件邮箱</label>
                  <input
                    value={notifConfig.notify_email}
                    onChange={e => updateNotifField('notify_email', e.target.value)}
                    placeholder="receiver@example.com"
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
                  <div className="form-group">
                    <label>开始前提醒（分钟）</label>
                    <input
                      type="number"
                      min={1}
                      value={notifConfig.reminder_minutes_before}
                      onChange={e => updateNotifField('reminder_minutes_before', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>截止前提醒（分钟）</label>
                    <input
                      type="number"
                      min={1}
                      value={notifConfig.reminder_due_minutes}
                      onChange={e => updateNotifField('reminder_due_minutes', e.target.value)}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="skeleton skeleton-text" style={{ width: '60%' }} />
                <div className="skeleton skeleton-text" style={{ width: '80%' }} />
                <div className="skeleton skeleton-text" style={{ width: '50%' }} />
              </>
            )}
          </>
        )}
      </div>

      {/* Appearance */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="card-header">
          <h3>外观</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 500 }}>主题</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>当前: {theme === 'dark' ? '深色' : '浅色'}</div>
          </div>
          <button className="btn" onClick={toggleTheme}>
            {theme === 'dark' ? '☀️ 浅色' : '🌙 深色'}
          </button>
        </div>
      </div>

      {/* Keyboard Shortcuts */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="card-header">
          <h3>键盘快捷键</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr><th>快捷键</th><th>功能</th></tr>
          </thead>
          <tbody>
            {KEYBOARD_SHORTCUTS.map(s => (
              <tr key={s.keys}>
                <td>
                  <code style={{
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-tertiary)',
                    fontSize: '0.8rem',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {s.keys}
                  </code>
                </td>
                <td style={{ color: 'var(--text-secondary)' }}>{s.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* About */}
      <div className="card">
        <div className="card-header">
          <h3>关于</h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', fontSize: '0.9rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-tertiary)' }}>应用</span>
            <span style={{ fontWeight: 500 }}>LocalCommandCenter</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-tertiary)' }}>版本</span>
            <span style={{ fontWeight: 500 }}>{version || '-'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-tertiary)' }}>后端状态</span>
            <span className={`badge ${connected ? 'badge-completed' : 'badge-error'}`}>
              {connected ? '已连接' : '未连接'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-tertiary)' }}>前端</span>
            <span style={{ fontWeight: 500 }}>React + Vite</span>
          </div>
        </div>
      </div>
    </div>
  );
}
