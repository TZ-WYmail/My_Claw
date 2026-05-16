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
      toast(data.status === 'success' ? '测试邮件发送成功' : '测试邮件发送失败', data.status === 'success' ? 'success' : 'error');
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
      toast(data.success || data.status === 'ok' ? '连接测试成功' : '连接测试失败', data.success || data.status === 'ok' ? 'success' : 'error');
    } catch {
      setTestResult({ success: false, error: '请求失败' });
      toast('连接测试失败', 'error');
    } finally {
      setTesting(false);
    }
  };

  const updateField = (field, value) => setConfig(prev => ({ ...prev, [field]: value }));

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 10 / Wiring Check</div>
          <h1 className="atlas-chapter-title">设置页应该像接线检定页，先确认链路和状态，再调参数，不应该是一堵普通表单墙。</h1>
          <div className="atlas-chapter-copy">
            AI、通知、外观和快捷键本质上都是系统层配置。你需要先知道哪条链路已经接通、哪块还没校准，再做修改和测试，而不是盲填字段。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">检定顺序</div>
          <div className="atlas-chapter-note-copy">先测 AI，再看通知，再调外观和快捷键，最后复核系统状态。</div>
        </div>
      </section>

      <section className="mission-masthead atlas-leaf">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">CONTROL CHAMBER</span>
            <h1 className="mission-title">设置页该像控制室，不该像一块普通表单墙。</h1>
            <div className="mission-copy">
              AI、通知、外观和快捷键都是系统层配置。这里的重点不是堆字段，而是让你知道什么已经接通、什么还没校准。
            </div>
            <div className="mission-chip-row">
              <span className={`badge ${connected ? 'badge-completed' : 'badge-error'}`}>{connected ? '后端已连接' : '后端未连接'}</span>
              <span className="badge badge-pending">版本 {version || '-'}</span>
              <span className="badge badge-warning">主题 {theme === 'dark' ? '深色' : '浅色'}</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">控制原则</div>
            <div className="mission-sidecard-copy">
              优先确认连接是否可靠，再调模型和通知。外观和快捷键属于节奏优化，不是第一优先级。
            </div>
          </div>
        </div>
      </section>

      <div className="war-room-grid">
        <div className="war-room-stack">
          <section className="board-lane atlas-ledger-lane">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">AI CORE</div>
                <h3 className="board-lane-title">AI 配置台</h3>
                <div className="board-lane-copy">模型、地址、Key 和参数统一放在这里，测试和保存动作保持真实后端接线。</div>
              </div>
              <div className="inline-actions">
                <button className="btn btn-sm btn-ghost" onClick={handleTest} disabled={testing}>{testing ? '测试中...' : '测试连接'}</button>
                <button className="btn btn-sm btn-primary" onClick={handleSave} disabled={loading}>保存</button>
              </div>
            </div>

            {testResult && (
              <div className="radar-item" style={{
                background: (testResult.success || testResult.status === 'ok') ? 'rgba(52,93,76,0.1)' : 'rgba(206,58,44,0.08)',
                borderLeftColor: (testResult.success || testResult.status === 'ok') ? 'var(--success)' : 'var(--error)',
              }}>
                <div className="radar-title">{(testResult.success || testResult.status === 'ok') ? '连接成功' : '连接失败'}</div>
                <div className="radar-copy">
                  {(testResult.success || testResult.status === 'ok')
                    ? `模型: ${testResult.model || config.model || '-'}`
                    : (testResult.error || testResult.message || '未知错误')}
                </div>
              </div>
            )}

            {configLoaded ? (
              <div className="command-form">
                <div className="form-group">
                  <label>模型名称</label>
                  <input value={config.model} onChange={e => updateField('model', e.target.value)} placeholder="如: glm-4-flash" />
                </div>
                <div className="form-group">
                  <label>API 地址</label>
                  <input value={config.api_base} onChange={e => updateField('api_base', e.target.value)} placeholder="https://open.bigmodel.cn/api/paas/v4" />
                </div>
                <div className="form-group">
                  <label>API Key</label>
                  <input type="password" value={config.api_key} onChange={e => updateField('api_key', e.target.value)} placeholder="sk-..." />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
                  <div className="form-group">
                    <label>Temperature ({config.temperature})</label>
                    <input type="range" min="0" max="2" step="0.1" value={config.temperature} onChange={e => updateField('temperature', parseFloat(e.target.value))} style={{ padding: 0 }} />
                  </div>
                  <div className="form-group">
                    <label>最大 Tokens</label>
                    <input type="number" min={256} max={32768} value={config.max_tokens} onChange={e => updateField('max_tokens', e.target.value)} />
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
          </section>

          <section className="board-lane atlas-paper-stack">
            <div
              className="board-lane-header"
              style={{ cursor: 'pointer' }}
              onClick={() => setNotifExpanded(prev => !prev)}
            >
              <div>
                <div className="section-kicker">NOTIFY NETWORK</div>
                <h3 className="board-lane-title">通知配置台</h3>
                <div className="board-lane-copy">{notifExpanded ? '当前展开中，可直接测试和保存通知配置。' : '点击展开 SMTP、提醒时间和测试邮件配置。'}</div>
              </div>
              <div className="inline-actions">
                <span className="badge badge-pending">{notifExpanded ? '已展开' : '已折叠'}</span>
                <button className="btn btn-sm btn-ghost" onClick={e => { e.stopPropagation(); setNotifExpanded(prev => !prev); }}>{notifExpanded ? '收起' : '展开'}</button>
              </div>
            </div>

            {notifExpanded && (
              <>
                <div className="inline-actions" style={{ marginBottom: 'var(--space-md)' }}>
                  <button className="btn btn-sm btn-ghost" onClick={handleNotifTest} disabled={notifTesting}>{notifTesting ? '发送中...' : '测试邮件'}</button>
                  <button className="btn btn-sm btn-primary" onClick={handleNotifSave} disabled={loading}>保存配置</button>
                </div>

                {notifTestResult && (
                  <div className="radar-item" style={{
                    background: notifTestResult.status === 'success' ? 'rgba(52,93,76,0.1)' : 'rgba(206,58,44,0.08)',
                    borderLeftColor: notifTestResult.status === 'success' ? 'var(--success)' : 'var(--error)',
                  }}>
                    <div className="radar-title">{notifTestResult.status === 'success' ? '测试邮件发送成功' : '测试邮件发送失败'}</div>
                    <div className="radar-copy">{notifTestResult.status === 'success' ? '请检查收件箱。' : (notifTestResult.message || '未知错误')}</div>
                  </div>
                )}

                {notifLoaded ? (
                  <div className="command-form">
                    <div className="form-group">
                      <label>SMTP 服务器</label>
                      <input value={notifConfig.smtp_host} onChange={e => updateNotifField('smtp_host', e.target.value)} placeholder="如: smtp.qq.com" />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
                      <div className="form-group">
                        <label>端口</label>
                        <input type="number" min={1} max={65535} value={notifConfig.smtp_port} onChange={e => updateNotifField('smtp_port', e.target.value)} />
                      </div>
                      <div className="form-group">
                        <label>发件邮箱</label>
                        <input value={notifConfig.smtp_user} onChange={e => updateNotifField('smtp_user', e.target.value)} placeholder="sender@example.com" />
                      </div>
                    </div>
                    <div className="form-group">
                      <label>授权码</label>
                      <input type="password" value={notifConfig.smtp_password} onChange={e => updateNotifField('smtp_password', e.target.value)} placeholder="SMTP 授权码（已配置则留空）" />
                    </div>
                    <div className="form-group">
                      <label>收件邮箱</label>
                      <input value={notifConfig.notify_email} onChange={e => updateNotifField('notify_email', e.target.value)} placeholder="receiver@example.com" />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
                      <div className="form-group">
                        <label>开始前提醒（分钟）</label>
                        <input type="number" min={1} value={notifConfig.reminder_minutes_before} onChange={e => updateNotifField('reminder_minutes_before', e.target.value)} />
                      </div>
                      <div className="form-group">
                        <label>截止前提醒（分钟）</label>
                        <input type="number" min={1} value={notifConfig.reminder_due_minutes} onChange={e => updateNotifField('reminder_due_minutes', e.target.value)} />
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
          </section>
        </div>

        <div className="war-room-stack">
          <section className="board-lane atlas-paper-stack">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">APPEARANCE</div>
                <h3 className="board-lane-title">外观切换</h3>
                <div className="board-lane-copy">主题切换属于节奏控制，不是附属小按钮。</div>
              </div>
            </div>
            <div className="signal-row">
              <div>
                <div className="signal-row-title">当前主题</div>
                <div className="signal-row-copy">{theme === 'dark' ? '深色作战室' : '浅色作战室'}</div>
              </div>
              <button className="btn" onClick={toggleTheme}>{theme === 'dark' ? '切换浅色' : '切换深色'}</button>
            </div>
          </section>

          <section className="board-lane atlas-paper-stack">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">SHORTCUTS</div>
                <h3 className="board-lane-title">快捷键指挥条</h3>
                <div className="board-lane-copy">不再用表格列，而是每条快捷键一张指令条。</div>
              </div>
            </div>
            <div className="signal-list">
              {KEYBOARD_SHORTCUTS.map(item => (
                <div className="signal-row" key={item.keys}>
                  <div>
                    <div className="signal-row-title"><code style={{ fontFamily: 'var(--font-mono)' }}>{item.keys}</code></div>
                    <div className="signal-row-copy">{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="board-lane atlas-paper-stack">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">SYSTEM STATUS</div>
                <h3 className="board-lane-title">系统状态</h3>
                <div className="board-lane-copy">把关于信息也纳入控制室视角，而不是尾部说明文。</div>
              </div>
            </div>
            <div className="signal-list">
              <div className="signal-row"><div><div className="signal-row-title">应用</div><div className="signal-row-copy">LocalCommandCenter</div></div></div>
              <div className="signal-row"><div><div className="signal-row-title">版本</div><div className="signal-row-copy">{version || '-'}</div></div></div>
              <div className="signal-row"><div><div className="signal-row-title">后端</div><div className="signal-row-copy">{connected ? '已连接' : '未连接'}</div></div><span className={`badge ${connected ? 'badge-completed' : 'badge-error'}`}>{connected ? '在线' : '离线'}</span></div>
              <div className="signal-row"><div><div className="signal-row-title">前端</div><div className="signal-row-copy">React + Vite</div></div></div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
